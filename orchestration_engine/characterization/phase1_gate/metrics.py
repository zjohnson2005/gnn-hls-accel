"""Metrics derived from workload profiles for Phase 1 gate checks."""

from __future__ import annotations

from orchestration_engine.characterization.taxonomy import COORDINATION_BUCKET, WorkloadProfile


def wall_batch_us(profile: WorkloadProfile) -> int:
    """Wall-clock span of a concurrent batch (parallel completion time proxy)."""
    if not profile.spans:
        return 0
    # batch_wall_s is real elapsed time — only meaningful for wall-clock traces.
    # For simulated-clock (mock) traces it is trace-generation time; ignore it.
    batch_s = profile.meta.get("batch_wall_s")
    if batch_s and profile.meta.get("wall_clock") == "True":
        return max(1, int(float(batch_s) * 1_000_000))
    if profile.concurrency <= 1:
        return profile.total_us()
    # Staggered simulated traces: per-agent sequential time approximates parallel batch.
    return max(1, profile.total_us() // profile.concurrency)


def orchestration_us(profile: WorkloadProfile) -> int:
    return profile.bucket_totals_us()[COORDINATION_BUCKET]


def orchestration_decisions(profile: WorkloadProfile) -> int:
    return sum(1 for s in profile.spans if s.bucket == COORDINATION_BUCKET)


def cores_equivalent(profile: WorkloadProfile) -> float:
    """Orchestration CPU-seconds / batch wall-seconds = cores worth of coord work."""
    wall = wall_batch_us(profile)
    return orchestration_us(profile) / wall if wall else 0.0


def per_agent_orchestration_us(profile: WorkloadProfile) -> float:
    c = max(1, profile.concurrency)
    return orchestration_us(profile) / c


def orchestration_setup_steady_us(profile: WorkloadProfile) -> tuple[int, int]:
    """Split orchestration into (per-agent first-step setup, steady-state dispatch).

    The first orchestration span of each agent includes LangGraph session/graph
    initialization (~1.6-3 ms measured) vs ~310 us steady-state dispatch steps.
    Works on old traces too (ordering-based, no metadata required).
    """
    per_agent: dict[str, list] = {}
    for s in profile.spans:
        if s.bucket == COORDINATION_BUCKET:
            per_agent.setdefault(s.agent_id, []).append(s)
    setup = 0
    steady = 0
    for spans in per_agent.values():
        spans.sort(key=lambda x: x.start_us)
        setup += spans[0].duration_us
        steady += sum(x.duration_us for x in spans[1:])
    return setup, steady


def steady_orchestration_pct_of_accelerable(profile: WorkloadProfile) -> float:
    """Steady-state dispatch as % of accelerable CPU with setup removed from both."""
    from orchestration_engine.characterization.taxonomy import (
        ACCELERABLE_CPU_BUCKETS,
    )

    setup, steady = orchestration_setup_steady_us(profile)
    totals = profile.bucket_totals_us()
    accelerable = sum(totals[b] for b in ACCELERABLE_CPU_BUCKETS)
    denom = accelerable - setup
    return 100.0 * steady / denom if denom > 0 else 0.0


def steady_orchestration_us_per_decision(profile: WorkloadProfile) -> float:
    setup, steady = orchestration_setup_steady_us(profile)
    per_agent: dict[str, int] = {}
    for s in profile.spans:
        if s.bucket == COORDINATION_BUCKET:
            per_agent[s.agent_id] = per_agent.get(s.agent_id, 0) + 1
    steady_decisions = sum(max(0, n - 1) for n in per_agent.values())
    return steady / steady_decisions if steady_decisions else 0.0


def per_decision_orchestration_us(profile: WorkloadProfile) -> float:
    d = orchestration_decisions(profile)
    return orchestration_us(profile) / d if d else 0.0
