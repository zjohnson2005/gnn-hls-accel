"""Experiment 0R: CPU-time breakdown of a REAL LangGraph ReAct agent.

**Publishable results** require `--backend openai` (live OpenAI API decisions).
The **scripted** backend is DEBUG ONLY: real LangGraph framework, synthetic
LLM sleeps and TaskSpec tool decisions — use to verify instrumentation only.

The agent under test is a genuine langgraph.prebuilt.create_react_agent
executing the same four real tools (search, code_exec, retrieve,
calculator). Two backends:

  scripted  (default) real LangGraph engine, local chat model that sleeps
            for a seeded latency and emits the task's scripted tool calls.
            Real framework overhead, controlled decisions, no API key.
  openai    fully real: ChatOpenAI decides tool calls itself. Requires
            OPENAI_API_KEY. Use small session counts (validation scale).

Measurement model difference vs Experiment 0 (documented in the report):
tool-side work is tagged by the same category timers (TOOL_COMPUTE,
SERIALIZATION, TOKENIZATION), but the framework's internal per-step CPU
cannot be wrapped region by region. Instead, thread CPU between agent
stream events minus tagged tool CPU is attributed to ORCH_SETUP (first
step) / ORCH_DISPATCH (later steps). This is exactly the Phase 0
definition of orchestration cost (langgraph_react_step residuals), so the
ORCH buckets here are directly comparable to the Phase 0 table.

Run:
  python -m apu_characterization.experiments.real_agent_breakdown \
      --backend scripted --profile mixed --seed 0 --sessions 10

Artifacts: out/real_agent_breakdown.json, out/real_agent_breakdown.md
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..amenability import TIER, compute_category_averages, compute_per_task, compute_per_task_wall_cpu
from ..harness.instr_callback import InstrLLMCallback
from ..harness.runner import _os_times_snapshot, _os_times_delta, _warm_shared_state
from ..harness.synth_text import make_text
from ..instr import (
    CategoryTotals,
    RunAccumulator,
    add_tagged_thread_cpu,
    get_run_accumulator,
    install_gc_hooks,
    measure_timer_overhead_ns,
    reset_gc_session,
    reset_thread_state,
    set_gc_session,
    set_run_accumulator,
    timed,
)
from ..profiles import LOCALITY_ABLATION_PROFILE, PROFILES, ProfileSpec, sample_payload_kb
from ..tools import LOCALITY_LOCAL, LOCALITY_REMOTE, reset_tool_locality, set_tool_locality
from ..tasks import TaskSpec, assign_task, task_by_id
from ..audit import apply_audit_to_artifact
from ..attribution import split_session_orch_after_reconcile
from ..stats import batch_attribution_summary
from ..behavior import summarize_behavior_buckets
from ..setup_validate import load_and_validate
from ..validity import (
    AUDIT_FAILED,
    DEBUG_ONLY,
    PUBLISHABLE,
    WINDOWS_FOOTNOTE_ONLY,
    real_agent_breakdown_stem,
    validity_banner,
    validity_for_real_agent_backend,
)
from ..taxonomy import Category
from .single_agent_breakdown import (
    RESIDUAL_LIMIT,
    _env_info,
    _git_state,
    _load_setup_digest,
    write_report,
)

from ..session_context import rng_ctx as _rng_ctx
from ..session_context import session_id_ctx as _session_ctx
from ..session_context import spec_ctx as _spec_ctx
# Turn-transition machinery lives in session_context so the LLM callback can
# stamp response timestamps without a circular import (see session_context).
from ..session_context import record_turn_transition as _record_turn_transition
from ..session_context import stamp_llm_response_ns
from ..session_context import turn_transition_ctx as _ttl_ctx


def _require_langgraph():
    try:
        from langgraph.prebuilt import create_react_agent  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "langgraph/langchain not installed in this environment. Install with:\n"
            "  py -3 -m pip install -r "
            "orchestration_engine/characterization/requirements-langgraph.txt"
        ) from exc


# ------------------------------------------------------------------ tools
def build_langchain_tools():
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    from ..tools import run_tool

    class QueryInput(BaseModel):
        query: str = Field(description="Tool input (format depends on tool; see description)")

    def make_fn(tool_name: str):
        def fn(query: str) -> str:
            _record_turn_transition()
            session_id = _session_ctx.get()
            rng = _rng_ctx.get()
            spec: ProfileSpec = _spec_ctx.get()
            acc = get_run_accumulator()
            outer = (
                Category.FRAMEWORK
                if acc is not None and acc.instr_version >= 2
                else Category.ORCH_DISPATCH
            )
            with timed(outer, session_id):
                try:
                    result = run_tool(tool_name, query, session_id, rng)
                except Exception as exc:
                    result = {"error": str(exc), "tool": tool_name, "query": query}

                result_bytes = sample_payload_kb(
                    rng, spec.tool_result_kb_min, spec.tool_result_kb_max
                )
                base_json = json.dumps(result)
                padded = dict(result)
                padded["padding"] = make_text(rng, max(0, result_bytes - len(base_json)))

                with timed(Category.SERIALIZATION, session_id, bytes_out=result_bytes):
                    tool_json = json.dumps(padded)

                from ..harness.mock_llm import _count_tokens

                with timed(Category.TOKENIZATION, session_id, bytes_in=len(tool_json)):
                    _count_tokens(tool_json)

            if acc is not None and acc.instr_version >= 3:
                from ..thread_identity import sample_session_threads

                sample_session_threads(acc, burst=True)

            return tool_json

        return fn

    descriptions = {
        "search": "Search a large text corpus. Input: keywords or short phrase.",
        "code_exec": (
            "Run Python that assigns a numeric or string value to variable `result`. "
            "Input must be valid Python code, not English."
        ),
        "retrieve": "Retrieve document chunks for a question. Input: the question text.",
        "calculator": (
            "Evaluate a numeric arithmetic expression only. "
            "Examples: '80 / (100 - 80)', '1000 * 1.05 ** 30'. "
            "Do not send English sentences."
        ),
    }
    return [
        StructuredTool.from_function(
            func=make_fn(name),
            name=name,
            description=desc,
            args_schema=QueryInput,
        )
        for name, desc in descriptions.items()
    ]


# --------------------------------------------------------- scripted model
def build_scripted_model(task: TaskSpec, spec: ProfileSpec, seed: int, llm_scale: float):
    """Local chat model driving the REAL LangGraph engine with the task's
    scripted tool calls. Sleeps a seeded lognormal per call (wall only)."""
    import math
    import random as _random
    import uuid

    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.runnables import Runnable

    # Flatten the task script into per-LLM-call tool decisions. Fan-out
    # turns become one AIMessage with several tool_calls (real LangGraph
    # executes them in its tool node). Reasoning-only, sub-agent,
    # structured, and api turns cannot exist mid-loop in a real ReAct
    # agent (a response without tool calls ends the loop), so they fold
    # into the neighboring responses; documented limitation of real mode.
    script: list[list[tuple[str, str]]] = []
    for turn in task.turns:
        calls = [(c.tool, c.query) for c in turn.calls if c.tool != "api"]
        if calls:
            script.append(calls)

    class ScriptedChatModel(BaseChatModel):
        step: int = 0

        @property
        def _llm_type(self) -> str:
            return "apu_scripted_react"

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            rng = _random.Random(seed + self.step)
            mu = math.log(max(spec.llm_median_s * llm_scale, 1e-6))
            time.sleep(rng.lognormvariate(mu, spec.llm_sigma))

            session_id = _session_ctx.get()
            body = make_text(rng, sample_payload_kb(
                rng, spec.llm_response_kb_min, spec.llm_response_kb_max
            ))
            from ..harness.mock_llm import _count_tokens

            with timed(Category.TOKENIZATION, session_id, bytes_in=len(body)):
                _count_tokens(body)

            idx = self.step
            self.step += 1
            if idx >= len(script):
                msg = AIMessage(content="Task complete. " + body[:200])
            else:
                msg = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": tool,
                            "args": {"query": query},
                            "id": f"call_{uuid.uuid4().hex[:8]}",
                            "type": "tool_call",
                        }
                        for tool, query in script[idx]
                    ],
                )
            stamp_llm_response_ns()
            return ChatResult(generations=[ChatGeneration(message=msg)])

        @property
        def _identifying_params(self) -> dict[str, Any]:
            return {"model": "apu_scripted_react", "task": task.task_id}

        def bind_tools(self, tools: Any, **kwargs: Any) -> Runnable[Any, AIMessage]:
            return self

    return ScriptedChatModel()


def build_replay_model(
    tool_steps: list[list[tuple[str, str]]],
    spec: ProfileSpec,
    seed: int,
    llm_scale: float,
):
    """Replay a recorded tool-call trace through the real LangGraph engine.

    ``tool_steps[i]`` is the list of (tool, query) pairs for LLM step *i*.
    Uses the same wall-only lognormal sleep as the scripted model so replay
    runs are comparable across search localities without live API variance.
    """
    import math
    import random as _random
    import uuid

    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.runnables import Runnable

    class ReplayChatModel(BaseChatModel):
        step: int = 0

        @property
        def _llm_type(self) -> str:
            return "apu_trace_replay"

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            rng = _random.Random(seed + self.step)
            mu = math.log(max(spec.llm_median_s * llm_scale, 1e-6))
            time.sleep(rng.lognormvariate(mu, spec.llm_sigma))

            session_id = _session_ctx.get()
            body = make_text(rng, sample_payload_kb(
                rng, spec.llm_response_kb_min, spec.llm_response_kb_max
            ))
            from ..harness.mock_llm import _count_tokens

            with timed(Category.TOKENIZATION, session_id, bytes_in=len(body)):
                _count_tokens(body)

            idx = self.step
            self.step += 1
            if idx >= len(tool_steps):
                msg = AIMessage(content="Trace replay complete. " + body[:200])
            else:
                calls = tool_steps[idx]
                msg = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": tool,
                            "args": {"query": query},
                            "id": f"call_{uuid.uuid4().hex[:8]}",
                            "type": "tool_call",
                        }
                        for tool, query in calls
                    ],
                )
            return ChatResult(generations=[ChatGeneration(message=msg)])

        @property
        def _identifying_params(self) -> dict[str, Any]:
            return {"model": "apu_trace_replay", "steps": len(tool_steps)}

        def bind_tools(self, tools: Any, **kwargs: Any) -> Runnable[Any, AIMessage]:
            return self

    return ReplayChatModel()


def _session_orch_cpu_ns(acc: RunAccumulator, session_id: str) -> int:
    """Sum ORCH_SETUP + ORCH_DISPATCH tagged to *session_id*."""
    with acc._lock:
        total = 0
        for cat in (Category.ORCH_SETUP.value, Category.ORCH_DISPATCH.value):
            key = (cat, session_id, acc.profile)
            total += acc.by_key.get(key, CategoryTotals()).cpu_ns
    return total


def _align_session_cpu_to_process(
    acc: RunAccumulator, session_id: str, session_process_ns: int
) -> int:
    """Scale session category CPU when parallel tool threads over-sum vs process clock.

    Category timers sum per-thread CPU; process_time counts parallel overlap once.
    Returns ns trimmed from categories (0 if no scaling applied).
    """
    if session_process_ns <= 0:
        return 0

    with acc._lock:
        keys = [k for k in acc.by_key if k[1] == session_id]
        instr = sum(acc.by_key[k].cpu_ns for k in keys)

    if instr <= session_process_ns:
        return 0

    scale = session_process_ns / instr
    trimmed = 0
    with acc._lock:
        for key in keys:
            t = acc.by_key[key]
            old = t.cpu_ns
            t.cpu_ns = int(old * scale)
            trimmed += old - t.cpu_ns
        prov_keys = [k for k in acc.by_provenance if k[1] == session_id]
        for pkey in prov_keys:
            pt = acc.by_provenance[pkey]
            pt.cpu_ns = int(pt.cpu_ns * scale)
    return trimmed


def _align_batch_cpu_to_process(acc: RunAccumulator, batch_process_cpu_ns: int) -> int:
    """Scale all category CPU when parallel sessions over-sum vs batch process clock."""
    if batch_process_cpu_ns <= 0:
        return 0
    batch_instr = acc.instrumented_cpu_ns()
    if batch_instr <= batch_process_cpu_ns:
        return 0
    scale = batch_process_cpu_ns / batch_instr
    trimmed = 0
    with acc._lock:
        for t in acc.by_key.values():
            old = t.cpu_ns
            t.cpu_ns = int(old * scale)
            trimmed += old - t.cpu_ns
        for pt in acc.by_provenance.values():
            pt.cpu_ns = int(pt.cpu_ns * scale)
    return trimmed


def _reconcile_batch_cpu(
    acc: RunAccumulator, batch_process_cpu_ns: int, *, instr_version: int
) -> int:
    """Book one batch-level RESIDUAL gap for concurrent runs (c>1).

    Per-session process_time deltas overlap under parallelism; session-end
    reconcile inflates RESIDUAL. This runs once after all sessions finish.
    Returns residual ns booked (0 if none).
    """
    if batch_process_cpu_ns <= 0 or instr_version < 2:
        return 0
    _align_batch_cpu_to_process(acc, batch_process_cpu_ns)
    batch_instr = acc.instrumented_cpu_ns()
    batch_gap = max(0, batch_process_cpu_ns - batch_instr)
    if batch_gap <= 0:
        return 0
    from ..provenance import RESIDUAL

    acc.book_cpu(
        Category.RESIDUAL_UNATTRIBUTED,
        "_batch_",
        batch_gap,
        batch_gap,
        provenance=RESIDUAL,
    )
    return batch_gap


def tool_sequence_to_steps(sequence: list[dict[str, str]]) -> list[list[tuple[str, str]]]:
    """Group a flat tool_call_sequence into per-LLM-step batches."""
    if not sequence:
        return []
    steps: dict[int, list[tuple[str, str]]] = {}
    for i, entry in enumerate(sequence):
        step = entry.get("llm_step")
        if step is None:
            step = i
        steps.setdefault(int(step), []).append(
            (entry["tool"], entry.get("query", ""))
        )
    return [steps[k] for k in sorted(steps)]


def load_trace_steps_from_artifact(
    artifact: dict[str, Any], task_id: str
) -> list[list[tuple[str, str]]]:
    """Extract replay steps for *task_id* from a real_agent_breakdown artifact."""
    for sess in artifact.get("run", {}).get("per_session", []):
        if sess.get("task_id") == task_id:
            seq = sess.get("tool_call_sequence") or []
            if seq:
                return tool_sequence_to_steps(seq)
    raise KeyError(f"no tool_call_sequence for task {task_id} in trace artifact")


def build_openai_model():
    import os

    from langchain_openai import ChatOpenAI

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set; required for --backend openai")
    max_retries = int(os.getenv("OE_OPENAI_MAX_RETRIES", "15"))
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        timeout=float(os.getenv("OE_OPENAI_TIMEOUT_S", "120")),
        max_retries=max_retries,
    )


# ---------------------------------------------------------------- session
def run_real_session(
    acc: RunAccumulator,
    session_id: str,
    task: TaskSpec,
    spec: ProfileSpec,
    seed: int,
    backend: str,
    llm_scale: float,
    tools: list[Any],
    *,
    replay_steps: list[list[tuple[str, str]]] | None = None,
    instr_version: int = 1,
    defer_session_reconcile: bool = False,
) -> dict[str, Any]:
    import random as _random

    from langchain_core.messages import HumanMessage
    from langgraph.prebuilt import create_react_agent

    set_run_accumulator(acc)
    reset_thread_state()
    set_gc_session(session_id)
    if acc.instr_version >= 3:
        from ..thread_identity import get_thread_registry

        get_thread_registry().begin_session(
            session_id, concurrent=defer_session_reconcile
        )
    rng = _random.Random(seed)
    tok_session = _session_ctx.set(session_id)
    tok_rng = _rng_ctx.set(rng)
    tok_spec = _spec_ctx.set(spec)
    # Turn-transition latency samples (LLM response received -> next tool body
    # entry). The scripted model and InstrLLMCallback both stamp t_llm_ns.
    ttl_holder: dict[str, Any] = {"t_llm_ns": None, "latencies_ms": []}
    tok_ttl = _ttl_ctx.set(ttl_holder)

    def tagged_cpu() -> int:
        total = 0
        with acc._lock:
            for (_cat, sid, _prof), t in acc.by_key.items():
                if sid == session_id:
                    total += t.cpu_ns
        return total

    def tagged_wall() -> int:
        total = 0
        with acc._lock:
            for (_cat, sid, _prof), t in acc.by_key.items():
                if sid == session_id:
                    total += t.wall_ns
        return total

    tool_call_counts: dict[str, int] = {}
    tool_call_sequence: list[dict[str, str]] = []
    try:
        if replay_steps is not None:
            model = build_replay_model(replay_steps, spec, seed, llm_scale)
            max_steps = len(replay_steps) + 4
            callbacks: list[Any] = []
        elif backend == "scripted":
            model = build_scripted_model(task, spec, seed, llm_scale)
            max_steps = len(task.turns) + 4
            callbacks: list[Any] = []
        else:
            model = build_openai_model()
            max_steps = 24
            callbacks = [InstrLLMCallback(session_id)]

        wall_start = time.perf_counter()
        with timed(Category.ORCH_SETUP, session_id):
            agent = create_react_agent(model, tools)
        inputs = {"messages": [HumanMessage(content=task.goal)]}
        config = {"recursion_limit": max_steps * 2, "callbacks": callbacks}

        cpu_start = time.thread_time_ns()
        proc_start = time.process_time()
        last_cpu = cpu_start
        last_wall = time.perf_counter_ns()
        last_proc = proc_start
        last_tagged_cpu = tagged_cpu()
        last_tagged_wall = tagged_wall()
        step_index = 0
        # Wall-clock turn boundaries (seconds since session wall_start), one per
        # LangGraph stream chunk. Consecutive diffs give turn-to-turn latency.
        turn_boundaries_s: list[float] = []

        for chunk in agent.stream(inputs, stream_mode="updates", config=config):
            node = next(iter(chunk.keys()))
            turn_boundaries_s.append(round(time.perf_counter() - wall_start, 6))
            now_cpu = time.thread_time_ns()
            now_wall = time.perf_counter_ns()
            now_tagged_cpu = tagged_cpu()
            now_tagged_wall = tagged_wall()
            proc_now = time.process_time()
            step_cpu = now_cpu - last_cpu
            step_wall = now_wall - last_wall
            step_tagged_cpu = now_tagged_cpu - last_tagged_cpu
            step_tagged_wall = now_tagged_wall - last_tagged_wall
            orch_cpu = max(0, step_cpu - step_tagged_cpu)
            orch_wall = max(0, step_wall - step_tagged_wall)

            category = Category.ORCH_SETUP if step_index == 0 else Category.ORCH_DISPATCH
            acc.book_cpu(category, session_id, orch_cpu, orch_wall)
            # Mark this main-thread CPU as tagged so v3 psutil sampling
            # doesn't book it a second time under FRAMEWORK.
            add_tagged_thread_cpu(orch_cpu)

            if instr_version >= 3:
                from ..thread_identity import sample_session_threads

                # Extra pass after tools/agent stream nodes: fan-out tool pools
                # can finish between LangGraph steps; burst=True catches stragglers.
                sample_session_threads(
                    acc, burst=node in ("tools", "agent")
                )
            elif instr_version >= 2:
                # Step-inferred booking (sequential-only; not valid under concurrency).
                step_proc_ns = int((proc_now - last_proc) * 1e9)
                step_untagged_proc_ns = max(0, step_proc_ns - step_tagged_cpu)
                if step_untagged_proc_ns > 0:
                    from ..provenance import STEP_INFER_NODE_CATEGORIES, STEP_INFERRED

                    cat_name = STEP_INFER_NODE_CATEGORIES.get(node, "CLIENT_HTTP")
                    off_thread = Category(cat_name)
                    acc.book_cpu(
                        off_thread,
                        session_id,
                        step_untagged_proc_ns,
                        step_untagged_proc_ns,
                        provenance=STEP_INFERRED,
                    )

            if node == "tools":
                update = chunk.get("tools") or {}
                for msg in update.get("messages", []):
                    name = getattr(msg, "name", None)
                    if name:
                        tool_call_counts[name] = tool_call_counts.get(name, 0) + 1
                        content = getattr(msg, "content", "") or ""
                        tool_call_sequence.append(
                            {
                                "tool": name,
                                "query": str(content)[:256],
                                "llm_step": max(0, step_index - 1),
                            }
                        )
                # Fan-out tool pools may still be finalizing when the stream
                # chunk arrives; sample after tool messages are recorded.
                if instr_version >= 3:
                    from ..thread_identity import sample_session_threads

                    sample_session_threads(acc, burst=True)

            last_cpu = now_cpu
            last_wall = now_wall
            last_proc = proc_now
            last_tagged_cpu = now_tagged_cpu
            last_tagged_wall = now_tagged_wall
            step_index += 1

        if instr_version >= 3:
            from ..thread_identity import finalize_session_threads, sample_session_threads

            finalize_session_threads(acc, session_id)
            # Last-chance sample before session-end gap (fan-out pool threads).
            sample_session_threads(acc, burst=True)

        # Reconcile: session process CPU (all threads: worker, LangGraph tool
        # pool, httpx) minus everything already tagged to this session.
        session_process_ns = int((time.process_time() - proc_start) * 1e9)
        session_instr_before = tagged_cpu()
        orch_measured_before_ns = _session_orch_cpu_ns(acc, session_id)
        if defer_session_reconcile:
            parallel_trim_ns = 0
            reconcile_added_ns = 0
            session_instr = session_instr_before
            session_gap = 0
            orch_measured_ns = _session_orch_cpu_ns(acc, session_id)
            orch_reconcile_ns = 0
            residual_unattributed_ns = 0
        else:
            reconcile_added_ns = max(0, session_process_ns - session_instr_before)
            parallel_trim_ns = _align_session_cpu_to_process(
                acc, session_id, session_process_ns
            )
            session_instr = tagged_cpu()
            session_gap = max(0, session_process_ns - session_instr)
            orch_measured_ns = 0
            orch_reconcile_ns = 0
            residual_unattributed_ns = 0

        if not defer_session_reconcile and instr_version >= 3:
            from ..provenance import RESIDUAL

            session_instr = tagged_cpu()
            session_gap = max(0, session_process_ns - session_instr)
            if session_gap > 0:
                acc.book_cpu(
                    Category.RESIDUAL_UNATTRIBUTED,
                    session_id,
                    session_gap,
                    session_gap,
                    provenance=RESIDUAL,
                )
            residual_unattributed_ns = session_gap
            orch_total_final_ns = _session_orch_cpu_ns(acc, session_id)
            orch_measured_ns = orch_total_final_ns
            session_instr = tagged_cpu()
        elif not defer_session_reconcile and instr_version >= 2:
            if session_gap > 0:
                from ..provenance import RESIDUAL

                acc.book_cpu(
                    Category.RESIDUAL_UNATTRIBUTED,
                    session_id,
                    session_gap,
                    session_gap,
                    provenance=RESIDUAL,
                )
            residual_unattributed_ns = session_gap
            orch_total_final_ns = _session_orch_cpu_ns(acc, session_id)
            orch_measured_ns = orch_total_final_ns
            session_instr = tagged_cpu()
        elif not defer_session_reconcile:
            session_gap_book = reconcile_added_ns
            if session_gap_book > 0:
                totals = acc.totals_for(Category.ORCH_DISPATCH, session_id)
                with acc._lock:
                    totals.add(session_gap_book, session_gap_book, count=1)
            if parallel_trim_ns > 0:
                session_gap = max(0, session_process_ns - session_instr)
            orch_total_final_ns = _session_orch_cpu_ns(acc, session_id)
            orch_measured_ns, orch_reconcile_ns = split_session_orch_after_reconcile(
                orch_measured_before_ns, reconcile_added_ns, orch_total_final_ns
            )
            residual_unattributed_ns = 0
            session_instr = tagged_cpu()
        elif defer_session_reconcile:
            session_instr = tagged_cpu()

        wall_s = time.perf_counter() - wall_start
        session_cpu = session_process_ns
    finally:
        if acc.instr_version >= 3:
            from ..thread_identity import end_session

            end_session(session_id)
        reset_gc_session()
        _session_ctx.reset(tok_session)
        _rng_ctx.reset(tok_rng)
        _spec_ctx.reset(tok_spec)
        _ttl_ctx.reset(tok_ttl)

    return {
        "session_id": session_id,
        "task_id": task.task_id,
        "turns": step_index,
        "plan_len": len(task.turns),
        "wall_s": wall_s,
        "thread_cpu_ns": session_cpu,
        "process_cpu_ns": session_process_ns,
        "instrumented_cpu_ns": session_instr,
        "reconcile_cpu_ns": session_gap,
        "orch_measured_cpu_ns": orch_measured_ns,
        "orch_reconcile_cpu_ns": orch_reconcile_ns,
        "residual_unattributed_cpu_ns": residual_unattributed_ns,
        "parallel_cpu_trim_ns": parallel_trim_ns,
        "tool_call_counts": tool_call_counts,
        "tool_call_sequence": tool_call_sequence,
        "turn_boundaries_s": turn_boundaries_s,
        "turn_transition_ms": list(ttl_holder["latencies_ms"]),
        "backend": backend,
        "replay": replay_steps is not None,
        "provenance": acc.provenance_summary(session_id),
    }


# ------------------------------------------------------------------ batch
def run_real_batch(
    concurrency: int,
    profile: str,
    seed: int,
    backend: str,
    llm_scale: float,
    workers: int | None = None,
    *,
    search_locality: str = LOCALITY_LOCAL,
    payload_profile: str | None = None,
    instr_version: int = 1,
    task_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Run *concurrency* sessions. Task assignment defaults to the deterministic
    rotation ``assign_task(profile, seed, i)``; pass ``task_ids`` (one id per
    session) to override, e.g. for sampling with replacement in the c-ladder
    concurrency sweep. Existing callers are unaffected.
    """
    if task_ids is not None and len(task_ids) != concurrency:
        raise ValueError(
            f"task_ids has {len(task_ids)} entries but concurrency={concurrency}"
        )
    if payload_profile is None and search_locality == LOCALITY_REMOTE:
        payload_name = LOCALITY_ABLATION_PROFILE.name
    else:
        payload_name = payload_profile or profile
    spec = PROFILES[payload_name]
    install_gc_hooks()
    if instr_version >= 3:
        from ..thread_identity import get_thread_registry, install_thread_identity_hooks

        install_thread_identity_hooks()
        get_thread_registry().snapshot()
    elif instr_version >= 2:
        from ..harness.thread_hooks import install_thread_hooks

        install_thread_hooks()
    _warm_shared_state()
    if instr_version >= 3:
        from ..thread_identity import get_thread_registry

        # Re-baseline after one-time imports/corpus load so pre-first-session
        # MAIN-thread CPU is not attributed to agent_0.
        get_thread_registry().snapshot()
    tools = build_langchain_tools()

    acc = RunAccumulator(profile=spec.name, instr_version=instr_version)
    os_start = _os_times_snapshot()
    wall_start = time.perf_counter_ns()
    proc_start = time.process_time()

    worker_cpu_ns: list[int] = []
    lock = threading.Lock()
    per_session: list[dict[str, Any]] = []
    if backend == "openai":
        # Sequential by default: process-wide CPU attribution stays clean and
        # we avoid OpenAI rate-limit storms during measurement.
        max_workers = workers if workers is not None else 1
    else:
        max_workers = workers or min(16, concurrency)
    defer_session_reconcile = max_workers > 1

    def worker(i: int) -> dict[str, Any]:
        t0 = time.thread_time_ns()
        tok_loc = set_tool_locality(search=search_locality)
        if backend == "openai" and max_workers > 1:
            import os

            stagger_s = float(os.getenv("OE_OPENAI_SESSION_STAGGER_S", "0.75"))
            if stagger_s > 0:
                time.sleep(i * stagger_s)
        try:
            if task_ids is not None:
                task = task_by_id(task_ids[i])
            else:
                task = assign_task(profile, seed, i)
            result = run_real_session(
                acc,
                f"agent_{i}",
                task,
                spec,
                seed + i,
                backend,
                llm_scale,
                tools,
                instr_version=instr_version,
                defer_session_reconcile=defer_session_reconcile,
            )
            result["search_locality"] = search_locality
            return result
        finally:
            reset_tool_locality(tok_loc)
            with lock:
                worker_cpu_ns.append(time.thread_time_ns() - t0)

    # Bypass the patched submit: session workers must not be wrapped in
    # timed(THREADPOOL), which would book each whole session's thread CPU
    # to THREADPOOL|global on top of per-session categories (double count).
    from ..harness.thread_hooks import submit_unwrapped

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = [submit_unwrapped(pool, worker, i) for i in range(concurrency)]
        for fut in as_completed(futs):
            per_session.append(fut.result())

    wall_end = time.perf_counter_ns()
    os_end = _os_times_snapshot()
    proc_end = time.process_time()
    batch_process_cpu_ns = int((proc_end - proc_start) * 1e9)
    session_process_cpu_sum_ns = sum(s.get("process_cpu_ns", 0) for s in per_session)
    if max_workers > 1:
        # Concurrent sessions share one process clock; sum(session process_time)
        # over-counts overlapping CPU. Use the single batch process delta as host
        # CPU basis for attribution shares and the batch-level audit gate.
        total_process_cpu_ns = batch_process_cpu_ns
    elif session_process_cpu_sum_ns > 0:
        total_process_cpu_ns = session_process_cpu_sum_ns
    else:
        total_process_cpu_ns = batch_process_cpu_ns

    if defer_session_reconcile:
        batch_reconcile_ns = _reconcile_batch_cpu(
            acc, batch_process_cpu_ns, instr_version=instr_version
        )
    else:
        batch_reconcile_ns = 0

    result = acc.to_run_dict(
        env={},
        config={
            "concurrency": concurrency,
            "profile": profile,
            "payload_profile": payload_name,
            "search_locality": search_locality,
            "seed": seed,
            "mode": "threads",
            "backend": backend,
            "llm_median_scale": llm_scale,
            "workers": max_workers,
            "total_cpu_basis": (
                "process_time_batch_delta"
                if max_workers > 1
                else "process_time_all_threads"
            ),
            "batch_process_cpu_ns": batch_process_cpu_ns,
            "session_process_cpu_sum_ns": session_process_cpu_sum_ns,
            "batch_reconcile_ns": batch_reconcile_ns,
            "session_reconcile": not defer_session_reconcile,
            "worker_thread_cpu_ns": sum(worker_cpu_ns),
            "instr_version": instr_version,
            "task_sampling": "explicit_task_ids" if task_ids is not None else "rotation",
            "task_ids": task_ids,
        },
        total_thread_cpu_ns=total_process_cpu_ns,
        total_wall_ns=wall_end - wall_start,
        os_times=_os_times_delta(os_start, os_end),
        per_session=sorted(per_session, key=lambda s: s["session_id"]),
    )
    result["provenance_totals"] = acc.provenance_summary()
    result["provenance_detail"] = {
        "|".join(k): v.cpu_ns for k, v in acc.by_provenance.items()
    }
    return result


CATEGORY_OVERRIDE = {
    "ORCH_SETUP": "REAL AGENT MODE: LangGraph first-step CPU residual (framework "
    "graph/session construction), the Phase 0 setup definition",
    "ORCH_DISPATCH": "REAL AGENT MODE: LangGraph per-step CPU residual between stream "
    "events minus tagged tool CPU (completion handling, channel updates, handoff), "
    "the Phase 0 steady definition",
    "PROMPT_ASSEMBLY": "REAL AGENT MODE: inside the framework, not separable; included "
    "in the ORCH buckets",
    "CONTEXT_MGMT": "REAL AGENT MODE: inside the framework (LangGraph state channels), "
    "not separable; included in the ORCH buckets",
    "HTTP_CLIENT": "OpenAI backend: LangChain callback wraps each LLM call "
    "(request build, response parse; network wait costs ~zero thread CPU). "
    "Scripted backend: not used.",
    "LOGGING": "REAL AGENT MODE: not separately instrumented; inside ORCH buckets",
}

CATEGORY_OVERRIDE_REMOTE_SEARCH = {
    **CATEGORY_OVERRIDE,
    "HTTP_CLIENT": "OpenAI backend: LangChain callback wraps each LLM call "
    "(request build, response parse; network wait costs ~zero thread CPU). "
    "Remote search: mock search round-trip wall (I/O wait) also in HTTP_CLIENT.",
    "TOOL_COMPUTE": "Local tool bodies only (code_exec, retrieve, calculator). "
    "Search is remote: HTTP envelope + I/O wait, not TOOL_COMPUTE.",
}


def main() -> None:
    import warnings

    warnings.filterwarnings("ignore", message=".*create_react_agent.*", category=DeprecationWarning)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("scripted", "openai"), default="scripted")
    parser.add_argument("--profile", default="mixed")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--llm-scale", type=float, default=0.05, dest="llm_scale")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument(
        "--search-locality",
        choices=(LOCALITY_LOCAL, LOCALITY_REMOTE),
        default=LOCALITY_LOCAL,
        dest="search_locality",
        help="local = in-process regex search (baseline); remote = mock hosted search API",
    )
    parser.add_argument(
        "--payload-profile",
        default=None,
        dest="payload_profile",
        help="Profile for synthetic tool-result padding (default: task profile, or "
        "locality_ablation when --search-locality remote)",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow experiments when git tree is dirty (not for publishable runs)",
    )
    parser.add_argument("--instr-version", type=int, default=1, dest="instr_version")
    parser.add_argument("--out", type=Path, default=Path("apu_characterization/out"))
    args = parser.parse_args()

    payload_profile = args.payload_profile
    if payload_profile is None and args.search_locality == LOCALITY_REMOTE:
        payload_profile = LOCALITY_ABLATION_PROFILE.name

    _require_langgraph()
    strict_setup = args.backend == "openai" and not args.allow_dirty
    load_and_validate(strict=strict_setup)
    setup_ref = _load_setup_digest()
    if args.backend == "openai" and args.sessions > 20:
        raise SystemExit("openai backend is validation scale: use --sessions 20 or fewer")

    t0 = time.perf_counter()
    run = run_real_batch(
        args.sessions,
        args.profile,
        args.seed,
        args.backend,
        args.llm_scale,
        args.workers,
        search_locality=args.search_locality,
        payload_profile=payload_profile,
        instr_version=args.instr_version,
    )
    batch_wall_s = time.perf_counter() - t0

    task_assignments = [
        assign_task(args.profile, args.seed, i).describe() for i in range(args.sessions)
    ]
    category_override = (
        CATEGORY_OVERRIDE_REMOTE_SEARCH
        if args.search_locality == LOCALITY_REMOTE
        else CATEGORY_OVERRIDE
    )
    artifact: dict[str, Any] = {
        "experiment": "real_agent_breakdown",
        "result_validity": validity_for_real_agent_backend(args.backend),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "setup_ref": setup_ref,
        "task_assignments": task_assignments,
        "git": _git_state(),
        "env": _env_info(),
        "config": {
            "profile": args.profile,
            "payload_profile": payload_profile or args.profile,
            "search_locality": args.search_locality,
            "seed": args.seed,
            "sessions": args.sessions,
            "mode": f"threads/{args.backend}",
            "llm_median_scale": args.llm_scale,
            "note_llm_scale": (
                "scripted backend sleeps (wall only); openai backend ignores this"
            ),
            "total_cpu_basis": "sum(session process_time)",
            "comparison_type": "single_run_distribution_sample",
            "workers": run["config"].get("workers"),
            "execution": (
                "sequential (workers=1, one session at a time)"
                if run["config"].get("workers") == 1
                else f"parallel (workers={run['config'].get('workers')})"
            ),
            "instr_version": args.instr_version,
        },
        "timer_overhead_ns_per_pair": measure_timer_overhead_ns(100_000),
        "batch_wall_s": batch_wall_s,
        "run": run,
        "category_regions_override": category_override,
        "reproduce_cmd": (
            "python -m apu_characterization.experiments.real_agent_breakdown"
            f" --backend {args.backend} --profile {args.profile}"
            f" --seed {args.seed} --sessions {args.sessions} --llm-scale {args.llm_scale}"
            f" --search-locality {args.search_locality}"
            + (
                f" --payload-profile {payload_profile}"
                if payload_profile and payload_profile != args.profile
                else ""
            )
        ),
    }

    artifact["per_task"] = compute_per_task(run)
    artifact["category_averages"] = compute_category_averages(
        artifact["per_task"], run["per_session"]
    )
    artifact["per_task_wall_cpu"] = compute_per_task_wall_cpu(
        artifact["per_task"], run["per_session"]
    )
    artifact["behavior_buckets"] = summarize_behavior_buckets(
        run["per_session"], artifact["per_task"]
    )
    artifact["amenability_tiers"] = TIER

    total = run["totals"]["thread_cpu_ns"]
    artifact["invariant"] = {
        "total_thread_cpu_ns": total,
        "instrumented_cpu_ns": run["totals"]["instrumented_cpu_ns"],
        "residual_cpu_ns": run["residual_cpu_ns"],
        "residual_fraction": run["residual_fraction"],
        "limit": RESIDUAL_LIMIT,
        "pass": run["residual_fraction"] < RESIDUAL_LIMIT,
    }
    artifact["batch_attribution"] = batch_attribution_summary(run, total)

    apply_audit_to_artifact(artifact)
    validity = artifact["result_validity"]
    stem = real_agent_breakdown_stem(args.backend, args.search_locality)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{stem}.json").write_text(
        json.dumps(artifact, indent=2), encoding="utf-8"
    )
    loc_label = (
        "remote search deployment"
        if args.search_locality == LOCALITY_REMOTE
        else "local search (baseline)"
    )
    title = (
        f"Experiment 0R: real LangGraph agent CPU-time breakdown "
        f"({args.backend}, {loc_label})"
    )
    md = write_report(
        artifact,
        args.out,
        stem=stem,
        title=title,
    )

    inv = artifact["invariant"]
    audit = artifact.get("audit", {})
    print(f"validity: {validity}")
    print(f"json: {args.out / (stem + '.json')}")
    print(f"md:   {md}")
    if audit.get("violations"):
        print("AUDIT VIOLATIONS:")
        for v in audit["violations"]:
            print(f"  - {v}")
    if audit.get("warnings"):
        for w in audit["warnings"][:5]:
            print(f"  warn: {w}")
        if len(audit.get("warnings", [])) > 5:
            print(f"  ... and {len(audit['warnings']) - 5} more warnings")
    if validity == DEBUG_ONLY:
        print(
            "NOTE: debug artifact only — re-run with --backend openai for publishable data"
        )
    print(
        f"invariant: residual {inv['residual_fraction'] * 100:.1f}% "
        f"(limit {RESIDUAL_LIMIT * 100:.0f}%) -> {'PASS' if inv['pass'] else 'FAIL'}"
    )
    if not inv["pass"]:
        sys.exit(1)
    if validity == AUDIT_FAILED:
        sys.exit(1)


if __name__ == "__main__":
    main()
