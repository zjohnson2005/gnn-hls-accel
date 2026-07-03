"""ReAct-style agent workload simulator with realistic timing knobs.

Models plan → act (tool) → observe loops with configurable action-heavy vs
reasoning-heavy mixes. Orchestration cost uses an explicit microsecond model
that scales with graph size and concurrency (global-scan penalty).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .profiler import Profiler, merge_profiles
from .taxonomy import Bucket, WorkloadProfile


@dataclass
class TimingModel:
    """Per-operation latencies in microseconds."""

    gpu_prefill_us: int = 80_000
    gpu_decode_per_token_us: int = 35_000
    decode_tokens_mean: int = 64

    tool_io_mean_us: int = 800_000
    tool_io_spread_us: int = 2_000_000

    parse_request_us: int = 800
    parse_response_us: int = 2_500
    tokenize_us: int = 400
    detokenize_us: int = 350

    state_update_us: int = 1_200
    kv_touch_us: int = 3_000

    dispatch_us: int = 25
    dep_check_us: int = 8
    completion_match_us: int = 12
    route_result_us: int = 15
    replan_us: int = 120

    subagents_per_step_mean: int = 2
    deps_per_dispatch: int = 3


@dataclass
class WorkloadPreset:
    name: str
    steps: int
    timing: TimingModel
    action_heavy: float
    seed: int = 42


PRESETS: dict[str, WorkloadPreset] = {
    "action_heavy": WorkloadPreset(
        name="action_heavy_react",
        steps=12,
        timing=TimingModel(
            gpu_prefill_us=60_000,
            decode_tokens_mean=32,
            tool_io_mean_us=1_200_000,
            tool_io_spread_us=3_000_000,
            subagents_per_step_mean=4,
            deps_per_dispatch=5,
        ),
        action_heavy=0.85,
    ),
    "reasoning_heavy": WorkloadPreset(
        name="reasoning_heavy_react",
        steps=8,
        timing=TimingModel(
            gpu_prefill_us=200_000,
            decode_tokens_mean=256,
            tool_io_mean_us=150_000,
            tool_io_spread_us=400_000,
            subagents_per_step_mean=1,
            deps_per_dispatch=2,
        ),
        action_heavy=0.25,
    ),
    "balanced": WorkloadPreset(
        name="balanced_react",
        steps=10,
        timing=TimingModel(),
        action_heavy=0.55,
    ),
}


def _orch_cost_us(timing: TimingModel, rng: random.Random, num_live_tasks: int) -> int:
    """Coordinator work per loop iteration — scales with live task count (scan penalty)."""
    base = (
        timing.dispatch_us
        + timing.dep_check_us * timing.deps_per_dispatch
        + timing.completion_match_us
        + timing.route_result_us
        + timing.replan_us
    )
    scan_penalty = timing.dep_check_us * max(0, num_live_tasks - 1)
    jitter = rng.randint(0, timing.dispatch_us)
    return base + scan_penalty + jitter


def _tool_io_us(timing: TimingModel, rng: random.Random, action_heavy: float) -> int:
    mean = timing.tool_io_mean_us
    if action_heavy > 0.7:
        mean = int(mean * 1.3)
    spread = timing.tool_io_spread_us
    return mean + rng.randint(0, spread)


def simulate_react_agent(
    preset: WorkloadPreset,
    agent_id: str = "agent_0",
    live_tasks: int = 1,
) -> WorkloadProfile:
    rng = random.Random(preset.seed + hash(agent_id) % 10_000)
    t = preset.timing
    prof = Profiler(name=f"{preset.name}:{agent_id}", concurrency=1)
    prof.use_simulated_clock(0)
    prof.set_agent(agent_id)

    num_live = live_tasks

    for step in range(preset.steps):
        prefill = t.gpu_prefill_us + rng.randint(-10_000, 20_000)
        prof.record(f"step{step}_gpu_prefill", Bucket.GPU_INFERENCE, max(10_000, prefill))

        decode_tokens = max(8, t.decode_tokens_mean + rng.randint(-8, 32))
        if preset.action_heavy < 0.4:
            decode_tokens = int(decode_tokens * 1.5)
        decode_us = decode_tokens * t.gpu_decode_per_token_us
        prof.record(
            f"step{step}_gpu_decode",
            Bucket.GPU_INFERENCE,
            decode_us,
            tokens=str(decode_tokens),
        )

        prof.record(f"step{step}_tokenize_prompt", Bucket.CPU_TOKENIZE, t.tokenize_us)
        prof.record(f"step{step}_parse_tool_schema", Bucket.CPU_PARSE, t.parse_request_us)

        orch = _orch_cost_us(t, rng, num_live)
        prof.record(
            f"step{step}_orchestration",
            Bucket.CPU_ORCHESTRATION,
            orch,
            live_tasks=str(num_live),
        )

        if rng.random() < preset.action_heavy:
            io_us = _tool_io_us(t, rng, preset.action_heavy)
            prof.record(
                f"step{step}_tool_io",
                Bucket.CPU_IO_WAIT,
                io_us,
                tool=rng.choice(["web_search", "code_exec", "api_call", "retrieval"]),
            )
            prof.record(f"step{step}_parse_tool_result", Bucket.CPU_PARSE, t.parse_response_us)
            prof.record(f"step{step}_detokenize", Bucket.CPU_TOKENIZE, t.detokenize_us)
            prof.record(
                f"step{step}_state_append",
                Bucket.CPU_STATE,
                t.state_update_us + t.kv_touch_us,
            )
            num_live = min(num_live + rng.randint(0, t.subagents_per_step_mean), 512)
        else:
            prof.record(f"step{step}_state_touch", Bucket.CPU_STATE, t.kv_touch_us)

    return prof.finish()


def simulate_concurrent_agents(
    preset: WorkloadPreset,
    concurrency: int,
) -> WorkloadProfile:
    """Run N agents with staggered start; orchestration sees cumulative live tasks."""
    profiles: list[WorkloadProfile] = []
    for i in range(concurrency):
        agent_id = f"agent_{i}"
        live = 1 + (i * preset.timing.subagents_per_step_mean // 2)
        p = simulate_react_agent(preset, agent_id=agent_id, live_tasks=live)
        offset = i * 50_000
        shifted: list = []
        for s in p.spans:
            from .taxonomy import SpanRecord

            shifted.append(
                SpanRecord(
                    name=s.name,
                    bucket=s.bucket,
                    start_us=s.start_us + offset,
                    end_us=s.end_us + offset,
                    agent_id=s.agent_id,
                    meta=s.meta,
                )
            )
        profiles.append(WorkloadProfile(name=p.name, spans=shifted, concurrency=1))

    merged = merge_profiles(profiles, name=f"{preset.name}_c{concurrency}")
    merged.concurrency = concurrency
    merged.meta = {"preset": preset.name, "concurrency": str(concurrency)}
    return merged


def scaling_study(
    preset: WorkloadPreset,
    concurrency_levels: list[int],
) -> list[WorkloadProfile]:
    return [simulate_concurrent_agents(preset, c) for c in concurrency_levels]
