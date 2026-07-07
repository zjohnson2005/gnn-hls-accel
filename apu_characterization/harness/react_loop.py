"""Plain-Python ReAct agent loop with category instrumentation.

Each session executes one named TaskSpec. The turn model covers the
structural archetypes the analysis groups by:

- single tool call per turn (SH/CH/RH/RE/LH)
- fan-out: several calls in one turn, completions land back-to-back on
  the join node (FO, AH)
- chaining: pipe_result feeds tool A's output into tool B's arguments,
  paying the parse-and-rebuild handoff explicitly (CN, MX)
- sub-agents: a turn spawns child sessions, each with its own OrchEngine
  graph, so ORCH_SETUP repeats per child (SW)
- structured emission: a turn re-emits and validates the full accumulated
  JSON artifact (SO, MX)
- mock remote API calls: HTTP_CLIENT envelopes around pure I/O wait (AH)

Every CPU-bearing region is wrapped in a category timer; mock LLM and
mock API sleeps are I/O wait (zero thread CPU). Per-session tool-call
counts and bytes are recorded for the per-task analysis.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import random
import time
from typing import Any

from ..instr import get_run_accumulator, timed
from ..profiles import ProfileSpec, sample_payload_kb
from ..tasks import SUBTASKS, TaskSpec, ToolCall, TurnSpec
from ..taxonomy import Category
from ..tools import run_tool
from .mock_api import mock_api_call
from .mock_llm import mock_llm_call
from .orch_engine import NodeKind, OrchEngine
from .synth_text import make_text

logger = logging.getLogger("apu_characterization")

STRUCTURED_ROWS_PER_TURN = 4


def _structured_rows(rng: random.Random, n: int) -> list[dict[str, Any]]:
    items = ["pancake mix", "syrup", "berries", "juice", "butter", "flour",
             "eggs", "milk", "sugar", "napkins", "plates", "fruit"]
    return [
        {
            "item": items[rng.randint(0, len(items) - 1)],
            "qty": rng.randint(1, 6),
            "aisle": rng.randint(1, 14),
        }
        for _ in range(n)
    ]


async def _execute_call(
    call: ToolCall,
    session_id: str,
    rng: random.Random,
    last_result_json: str,
    llm_median_scale: float,
) -> dict[str, Any]:
    """Run one tool or API call, applying the piped-handoff cost if scripted."""
    query = call.query
    if call.pipe_result and last_result_json:
        # Handoff: parse the previous tool's result, then build this tool's
        # arguments from it. This is the pair-wise cost chains measure.
        with timed(Category.SERIALIZATION, session_id, bytes_in=len(last_result_json)):
            prev = json.loads(last_result_json)
        with timed(Category.PROMPT_ASSEMBLY, session_id):
            excerpt = json.dumps(prev)[:200]
            if call.tool == "code_exec":
                query = f"prev = {excerpt!r}\n" + call.query
            else:
                query = call.query  # numeric args stay; the cost was paid above

    if call.tool == "api":
        return await mock_api_call(query, rng, session_id, latency_scale=llm_median_scale)
    return run_tool(call.tool, query, session_id, rng)


async def run_agent_session(
    session_id: str,
    spec: ProfileSpec,
    task: TaskSpec,
    seed: int,
    llm_median_scale: float = 1.0,
) -> dict[str, Any]:
    rng = random.Random(seed)
    orch = OrchEngine()
    orch.setup_session(session_id, task.tool_counts_per_turn())

    messages: list[dict[str, Any]] = [{"role": "user", "content": task.goal}]
    state: dict[str, Any] = {
        "task_id": task.task_id,
        "messages": messages,
        "turn": 0,
        "artifacts": [],
        "structured_list": [],
    }
    tool_call_counts: dict[str, int] = {}
    tool_bytes: dict[str, int] = {}
    children: list[dict[str, Any]] = []
    last_result_json = ""

    session_wall_start = time.perf_counter()
    turns_executed = 0

    for turn_index, turn in enumerate(task.turns):
        is_last = turn_index == len(task.turns) - 1
        response_bytes = sample_payload_kb(
            rng, spec.llm_response_kb_min, spec.llm_response_kb_max
        )

        with timed(Category.CONTEXT_MGMT, session_id, bytes_in=len(str(state))):
            _snapshot = copy.deepcopy(state)

        with timed(Category.PROMPT_ASSEMBLY, session_id):
            prompt_messages = list(messages)

        dispatched = orch.dispatch_ready(session_id)
        llm_node = next((n for n in dispatched if n.kind == NodeKind.COMPUTE), None)

        response = await mock_llm_call(
            prompt_messages,
            rng,
            spec.llm_median_s * llm_median_scale,
            spec.llm_sigma,
            response_bytes,
            session_id,
        )

        with timed(Category.LOGGING, session_id):
            logger.debug(
                "session=%s task=%s turn=%s calls=%d structured=%s subagents=%d",
                session_id,
                task.task_id,
                turn_index,
                len(turn.calls),
                turn.structured_emit,
                len(turn.subagent_goals),
            )

        if llm_node is not None:
            orch.complete_node(session_id, llm_node.id)

        turns_executed += 1

        # ---------------------------------------------------------- sub-agents
        if turn.subagent_goals:
            child_tasks = [
                run_agent_session(
                    f"{session_id}/sub_{goal}",
                    spec,
                    SUBTASKS[goal],
                    seed + 1000 + j,
                    llm_median_scale,
                )
                for j, goal in enumerate(turn.subagent_goals)
            ]
            children = list(await asyncio.gather(*child_tasks))
            with timed(Category.CONTEXT_MGMT, session_id):
                for child in children:
                    state["artifacts"].append(
                        {"subagent": child["session_id"], "turns": child["turns"]}
                    )
                messages.append(
                    {"role": "assistant", "content": f"merged {len(children)} sections"}
                )

        # ----------------------------------------------------------- tool calls
        if turn.calls:
            dispatched = orch.dispatch_ready(session_id)
            tool_nodes = [n for n in dispatched if n.kind == NodeKind.TOOL]

            results: list[dict[str, Any]] = []
            if all(c.tool == "api" for c in turn.calls) and len(turn.calls) > 1:
                # Fan-out API burst: sleeps overlap on the event loop.
                results = list(
                    await asyncio.gather(
                        *[
                            _execute_call(c, session_id, rng, last_result_json, llm_median_scale)
                            for c in turn.calls
                        ]
                    )
                )
            else:
                for call in turn.calls:
                    results.append(
                        await _execute_call(
                            call, session_id, rng, last_result_json, llm_median_scale
                        )
                    )

            for call, result in zip(turn.calls, results):
                result_bytes = sample_payload_kb(
                    rng, spec.tool_result_kb_min, spec.tool_result_kb_max
                )
                base_json = json.dumps(result)
                padded = dict(result)
                padded["padding"] = make_text(rng, max(0, result_bytes - len(base_json)))

                with timed(Category.SERIALIZATION, session_id, bytes_out=result_bytes):
                    tool_json = json.dumps(padded)
                last_result_json = tool_json

                with timed(Category.CONTEXT_MGMT, session_id, bytes_in=len(tool_json)):
                    messages.append({"role": "tool", "content": tool_json})
                    state["artifacts"].append({"tool": call.tool, "bytes": len(tool_json)})

                tool_call_counts[call.tool] = tool_call_counts.get(call.tool, 0) + 1
                tool_bytes[call.tool] = tool_bytes.get(call.tool, 0) + len(tool_json)

            # Completion burst: all fan-out completions land back-to-back,
            # each scattering into the ALL_OF join node.
            for n in tool_nodes:
                orch.complete_node(session_id, n.id)

        # ---------------------------------------------------- structured output
        if turn.structured_emit:
            state["structured_list"].extend(_structured_rows(rng, STRUCTURED_ROWS_PER_TURN))
            # Size is only known after encoding; the validate region below
            # carries the byte count for this emit.
            with timed(Category.SERIALIZATION, session_id):
                emitted = json.dumps({"shopping_list": state["structured_list"]})
            with timed(Category.SERIALIZATION, session_id, bytes_in=len(emitted), bytes_out=len(emitted)):
                validated = json.loads(emitted)
                for row in validated["shopping_list"]:
                    assert set(row) == {"item", "qty", "aisle"}
            with timed(Category.CONTEXT_MGMT, session_id, bytes_in=len(emitted)):
                messages.append({"role": "assistant", "content": emitted})

        with timed(Category.CONTEXT_MGMT, session_id):
            messages.append(
                {"role": "assistant", "content": response.get("content", "")[:512]}
            )
            state["turn"] = turns_executed

        if is_last:
            break

    session_wall_s = time.perf_counter() - session_wall_start

    acc = get_run_accumulator()
    session_cpu = 0
    if acc is not None:
        for (_cat, sid, _prof), totals in acc.by_key.items():
            if sid == session_id:
                session_cpu += totals.cpu_ns

    result: dict[str, Any] = {
        "session_id": session_id,
        "task_id": task.task_id,
        "turns": turns_executed,
        "plan_len": len(task.turns),
        "wall_s": session_wall_s,
        "thread_cpu_ns": session_cpu,
        "tool_call_counts": tool_call_counts,
        "tool_result_bytes": tool_bytes,
        "graph_nodes": len(orch.nodes),
        "graph_setup_ops": orch.stats_setup_ops,
        "dispatch_decisions": orch.stats_dispatch,
    }
    if children:
        result["subagents"] = [c["session_id"] for c in children]
        result["subagent_results"] = children
    return result
