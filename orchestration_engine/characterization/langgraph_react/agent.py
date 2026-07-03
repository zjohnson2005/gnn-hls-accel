"""Build LangGraph ReAct agent (mock or OpenAI)."""

from __future__ import annotations

import os
import time
from typing import Any, Callable

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from dataclasses import replace

from .callbacks import OpenAILLMCallback
from .context import reset_profiler, set_profiler
from .mock_model import MockReActChatModel
from .rate_limit import is_rate_limit_error
from .timing import AgentTiming, timing_for_preset
from .tools import build_tools
from orchestration_engine.characterization.profiler import Profiler
from orchestration_engine.characterization.taxonomy import Bucket, WorkloadProfile


def build_agent(
    preset: str = "action_heavy",
    backend: str = "mock",
    seed: int = 0,
    calibrated: bool = False,
    timing: AgentTiming | None = None,
    wall_clock_tools: bool = False,
):
    timing = timing or timing_for_preset(preset, calibrated=calibrated)
    tools = build_tools(timing, seed=seed, wall_clock=wall_clock_tools)

    if backend == "mock":
        model = MockReActChatModel(timing=timing, tools=tools)
    elif backend == "openai":
        from langchain_openai import ChatOpenAI

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set")
        timeout_s = float(os.getenv("OE_OPENAI_TIMEOUT_S", "120"))
        model = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            max_retries=int(os.getenv("OE_OPENAI_MAX_RETRIES", "10")),
            timeout=timeout_s,
        )
    else:
        raise ValueError(f"Unknown backend: {backend}")

    return create_react_agent(model, tools), timing


def _count_stream_steps(profile: WorkloadProfile) -> int:
    return sum(1 for s in profile.spans if s.name == "langgraph_react_step")


def run_session(
    preset: str = "action_heavy",
    backend: str = "mock",
    agent_id: str = "agent_0",
    seed: int = 0,
    task: str = "Research the latest benchmarks and summarize findings.",
    live_tasks_seed: int = 1,
    calibrated: bool = False,
    wall_clock: bool | None = None,
    react_steps_override: int | None = None,
) -> WorkloadProfile:
    use_wall = wall_clock if wall_clock is not None else (backend == "openai")
    timing = timing_for_preset(preset, calibrated=calibrated)
    if react_steps_override is not None:
        timing = replace(timing, react_steps=react_steps_override)

    tool_wall = use_wall and backend == "mock"
    agent, timing = build_agent(
        preset=preset,
        backend=backend,
        seed=seed + hash(agent_id) % 1000,
        calibrated=calibrated,
        timing=timing,
        wall_clock_tools=tool_wall,
    )
    prof = Profiler(name=f"langgraph_react_{preset}", concurrency=1)
    if use_wall:
        pass  # default perf_counter wall clock
    else:
        prof.use_simulated_clock(start_us=(seed % 1000) * 1000)
    prof.set_agent(agent_id)

    token = set_profiler(prof)
    callbacks = [OpenAILLMCallback(prof)] if backend == "openai" else []

    try:
        if use_wall:
            with prof.span("session_init", Bucket.CPU_STATE):
                pass
        else:
            prof.record("session_init", Bucket.CPU_STATE, timing.state_update_us)

        config: dict[str, Any] = {
            "recursion_limit": timing.react_steps + 4,
            "callbacks": callbacks,
        }
        live_tasks = live_tasks_seed
        inputs = {"messages": [HumanMessage(content=task)]}

        last_ts = time.perf_counter()
        span_idx = prof.span_count()
        step_index = 0
        # Steps longer than this indicate the host slept/hibernated mid-run;
        # the wall residual would absorb the gap and corrupt orchestration numbers.
        max_step_us = int(float(os.getenv("OE_MAX_STEP_WALL_S", "300")) * 1_000_000)
        anomaly_steps = 0
        for chunk in agent.stream(inputs, stream_mode="updates", config=config):
            node = next(iter(chunk.keys()))
            now = time.perf_counter()
            step_wall_us = max(0, int((now - last_ts) * 1_000_000))
            if step_wall_us > max_step_us:
                anomaly_steps += 1

            if use_wall and backend == "openai":
                # Residual local time after subtracting child I/O recorded this step.
                # Tool steps use simulated I/O durations; cap attribution at wall time.
                attributed_us = prof.sum_span_us_since(
                    span_idx,
                    exclude_buckets=(Bucket.CPU_ORCHESTRATION,),
                )
                orch_us = max(1, step_wall_us - min(attributed_us, step_wall_us))
                prof.record(
                    "langgraph_react_step",
                    Bucket.CPU_ORCHESTRATION,
                    orch_us,
                    node=node,
                    measured="wall_residual",
                    live_tasks=str(live_tasks),
                    step_index=str(step_index),
                    phase="setup" if step_index == 0 else "steady",
                )
            else:
                cost = timing.orchestration_per_step_us + (
                    timing.orchestration_live_task_penalty_us * live_tasks
                )
                if step_index == 0:
                    cost += timing.orchestration_setup_us
                prof.record(
                    "langgraph_react_step",
                    Bucket.CPU_ORCHESTRATION,
                    cost,
                    node=node,
                    live_tasks=str(live_tasks),
                    step_index=str(step_index),
                    phase="setup" if step_index == 0 else "steady",
                )

            if node == "tools":
                live_tasks = min(live_tasks + 1, 512)
            span_idx = prof.span_count()
            last_ts = now
            step_index += 1
    finally:
        reset_profiler(token)

    profile = prof.finish()
    profile.meta["backend"] = backend
    profile.meta["wall_clock"] = str(use_wall)
    profile.meta["calibrated"] = str(calibrated)
    if anomaly_steps:
        profile.meta["wall_anomaly_steps"] = str(anomaly_steps)
    if use_wall and backend == "openai":
        profile.meta["orch_measurement"] = "wall_residual"
    return profile


def run_concurrent(
    preset: str = "action_heavy",
    backend: str = "mock",
    concurrency: int = 1,
    seed: int = 42,
    calibrated: bool = False,
    wall_clock: bool | None = None,
    max_workers: int | None = None,
    react_steps_override: int | None = None,
    task: str | None = None,
    on_agent_done: Callable[[int, int], None] | None = None,
) -> WorkloadProfile:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from orchestration_engine.characterization.profiler import merge_profiles
    from orchestration_engine.characterization.taxonomy import SpanRecord

    use_wall = wall_clock if wall_clock is not None else (backend == "openai")
    profiles: list[WorkloadProfile] = []

    def shift_profile(profile: WorkloadProfile, offset_us: int) -> WorkloadProfile:
        shifted = [
            SpanRecord(
                name=s.name,
                bucket=s.bucket,
                start_us=s.start_us + offset_us,
                end_us=s.end_us + offset_us,
                agent_id=s.agent_id,
                meta=s.meta,
            )
            for s in profile.spans
        ]
        return WorkloadProfile(name=profile.name, spans=shifted, concurrency=1, meta=profile.meta)

    def worker(idx: int) -> WorkloadProfile:
        agent_task = task or "Research the latest benchmarks and summarize findings."
        max_attempts = int(os.getenv("OE_OPENAI_AGENT_RETRIES", "12"))
        for attempt in range(max_attempts):
            try:
                prof = run_session(
                    preset=preset,
                    backend=backend,
                    agent_id=f"agent_{idx}",
                    seed=seed + idx,
                    task=agent_task,
                    live_tasks_seed=1 + idx // 2,
                    calibrated=calibrated,
                    wall_clock=use_wall,
                    react_steps_override=react_steps_override,
                )
                break
            except Exception as exc:
                if not is_rate_limit_error(exc) or attempt + 1 >= max_attempts:
                    raise
                delay_s = min(90.0, 2.0 ** attempt)
                time.sleep(delay_s)
        else:
            raise RuntimeError(f"agent_{idx} failed after {max_attempts} rate-limit retries")
        if use_wall:
            return prof
        return shift_profile(prof, offset_us=idx * 100_000_000)

    if backend == "openai":
        default_workers = int(os.getenv("OE_OPENAI_MAX_WORKERS", "16"))
        cap = max_workers if max_workers is not None else default_workers
        workers = max(1, min(concurrency, cap))
        if concurrency <= 1:
            execution_mode = "single_agent"
        elif workers > 1:
            execution_mode = "parallel"
        else:
            execution_mode = "sequential"
    else:
        workers = min(concurrency, 32)
        execution_mode = "mock_parallel"

    batch_start = time.perf_counter()
    pool = ThreadPoolExecutor(max_workers=workers)
    futures = [pool.submit(worker, i) for i in range(concurrency)]
    done = 0
    try:
        for fut in as_completed(futures):
            profiles.append(fut.result())
            done += 1
            if on_agent_done is not None:
                on_agent_done(done, concurrency)
    except KeyboardInterrupt:
        for fut in futures:
            fut.cancel()
        pool.shutdown(wait=False, cancel_futures=True)
        print(f"\n  Interrupted after {done}/{concurrency} agents.", flush=True)
        raise
    else:
        pool.shutdown(wait=True)
    batch_wall_s = time.perf_counter() - batch_start

    merged = merge_profiles(profiles, name=f"langgraph_react_{preset}_c{concurrency}")
    merged.concurrency = concurrency
    orch_us = sum(
        s.end_us - s.start_us
        for s in merged.spans
        if s.bucket == Bucket.CPU_ORCHESTRATION
    )
    merged.meta = {
        "source": "langgraph_react instrumented run",
        "preset": preset,
        "backend": backend,
        "concurrency": str(concurrency),
        "calibrated": str(calibrated),
        "wall_clock": str(use_wall),
        "parallel_workers": str(workers),
        "execution_mode": execution_mode,
        "batch_wall_s": f"{batch_wall_s:.2f}",
        "orch_ms_per_agent": f"{orch_us / max(1, concurrency) / 1000:.3f}",
        "orch_measurement": "wall_residual",
    }
    anomaly_agents = sum(1 for p in profiles if p.meta.get("wall_anomaly_steps"))
    if anomaly_agents:
        merged.meta["wall_anomaly_agents"] = str(anomaly_agents)
    return merged
