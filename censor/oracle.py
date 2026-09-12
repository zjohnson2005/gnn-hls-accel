"""Cost oracle under trajectory-invariance (static) assumption.

CRITICAL: multi-turn agents are NOT independent — routing turn t changes
turns t+1+. The single-turn matrix-max oracle does not transfer.

Phase 2 assumes trajectory structure is invariant to routing (STATIC).
This makes the bound LOOSE (an upper bound on an upper bound).
Invariance bias: UNMEASURED (Phase 4 online slice).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from censor.frictions_cost import (
    F1_decision_cost,
    F2_switching_cost,
    F3_cloud_capacity,
    F4_local_capacity,
    f4_output_label,
    inference_cost,
)
from censor.phase2_constants import CostModelParams
from censor.schema import Tier, Trajectory


STATIC_ASSUMPTION_NOTE = (
    "STATIC TRAJECTORY INVARIANCE ASSUMED: the logged turn sequence, context "
    "lengths, and tool structure are treated as fixed under counterfactual "
    "tier assignments. Because routing turn t can change turns t+1+, this "
    "static number is an upper bound on an upper bound (loose). "
    "Invariance bias: UNMEASURED."
)


@dataclass
class OracleResult:
    seconds: float
    usd: float
    joules: float
    tier_assignment: list[Tier]
    cloud_only_seconds: float
    cloud_only_usd: float
    local_only_seconds: float
    local_only_usd: float
    static_assumption_flag: bool = True
    static_assumption_note: str = STATIC_ASSUMPTION_NOTE
    invariance_bias: str = "UNMEASURED"
    f4_label: str = "F4 UNMEASURED"
    f1_flags: list[str] = field(default_factory=list)
    friction_mask: dict[str, bool] = field(default_factory=dict)
    quality_held_at: str = (
        "Manski upper bound (local succeeds on every unobserved turn) — "
        "most generous assumption for hybrid execution"
    )


def _path_cost(
    trajectory: Trajectory,
    assignment: Sequence[Tier],
    params: CostModelParams,
) -> tuple[float, float, float, list[str]]:
    """Evaluate a fixed tier assignment under enabled frictions."""
    f3 = F3_cloud_capacity(trajectory, params.f3)
    # F4 stub: constant factor; label UNMEASURED.
    f4 = F4_local_capacity(trajectory, elapsed_load=0.0, params=params.f4)
    f4_factor = f4.throughput_factor if params.f4.enabled else 1.0

    total_s = 0.0
    total_usd = 0.0
    total_j = 0.0
    local_s = 0.0
    cloud_s = 0.0
    flags: list[str] = []
    prev: Tier | None = None

    for turn, tier in zip(trajectory.turns, assignment):
        if params.f1.enabled:
            f1 = F1_decision_cost(turn, params.f1)
            total_s += f1.seconds
            total_j += f1.joules
            if f1.flag:
                flags.append(f1.flag)

        f2 = F2_switching_cost(turn, prev, tier, params.f2)
        # When F2 enabled: pay switch prefill (or warm). When disabled: warm only
        # is still part of inference; F2 delta is the friction.
        if params.f2.enabled:
            if f2.switched:
                total_s += f2.delta_seconds
                total_usd += f2.delta_usd
            # Warm prefill seconds are subsumed in inference_cost for local
            # (full ctx) / cloud logged latency; do not double-count warm.

        inf = inference_cost(
            turn,
            tier,
            params.inference,
            f4_throughput_factor=f4_factor if tier == "local" else 1.0,
        )
        if tier == "local":
            local_s += inf.seconds
        else:
            cloud_s += inf.seconds
        total_s += inf.seconds
        total_usd += inf.usd
        total_j += inf.joules
        prev = tier

    # Apply F3 as a wall-clock compression on the cloud portion only.
    # When F3 off: divide cloud time by assumed_concurrency (naive fantasy).
    # When F3 on: divide by effective_speedup (= min(assumed, max_speedup)).
    if cloud_s > 0:
        speedup = f3.effective_speedup
        # Reconstruct: total_s = local_s + cloud_s + other; replace cloud_s.
        other = total_s - local_s - cloud_s
        compressed_cloud = cloud_s / max(1e-12, speedup)
        total_s = other + local_s + compressed_cloud

    if params.f4.enabled:
        flags.append(f4_output_label(params.f4))
    return total_s, total_usd, total_j, flags


def _uniform_assignment(trajectory: Trajectory, tier: Tier) -> list[Tier]:
    return [tier for _ in trajectory.turns]


def cost_oracle(trajectory: Trajectory, cost_model: CostModelParams) -> OracleResult:
    """Perfect-hindsight tier assignment minimizing COST ONLY.

    Quality held at the Manski upper bound (local succeeds everywhere
    unobserved) — the most generous assumption for hybrid execution.

    Exact DP over tiers with trajectory structure held fixed (static).
    """
    n = len(trajectory.turns)
    if n == 0:
        return OracleResult(
            seconds=0.0,
            usd=0.0,
            joules=0.0,
            tier_assignment=[],
            cloud_only_seconds=0.0,
            cloud_only_usd=0.0,
            local_only_seconds=0.0,
            local_only_usd=0.0,
            f4_label=f4_output_label(cost_model.f4),
            friction_mask={
                "F1": cost_model.f1.enabled,
                "F2": cost_model.f2.enabled,
                "F3": cost_model.f3.enabled,
                "F4": cost_model.f4.enabled,
            },
        )

    # Exact DP over tier sequences. F3 compresses cloud mass linearly, so the
    # objective add - cloud*(1-1/speedup) is additive across turns.
    tiers: list[Tier] = ["local", "cloud"]
    INF = 1e300
    add_best = [{t: INF for t in tiers} for _ in range(n)]
    cloud_mass = [{t: 0.0 for t in tiers} for _ in range(n)]
    local_mass = [{t: 0.0 for t in tiers} for _ in range(n)]
    usd_best = [{t: INF for t in tiers} for _ in range(n)]
    joules_best = [{t: 0.0 for t in tiers} for _ in range(n)]
    parent: list[dict[Tier, Tier | None]] = [{t: None for t in tiers} for _ in range(n)]

    f4 = F4_local_capacity(trajectory, 0.0, cost_model.f4)
    f4_factor = f4.throughput_factor if cost_model.f4.enabled else 1.0
    f1_flags: list[str] = []
    f3 = F3_cloud_capacity(trajectory, cost_model.f3)
    speedup = f3.effective_speedup
    # final = add - cloud*(1 - 1/speedup); DP on that linear objective.
    cloud_penalty = 1.0 - 1.0 / max(1e-12, speedup)
    score_best = [{t: INF for t in tiers} for _ in range(n)]

    for i, turn in enumerate(trajectory.turns):
        prev_tiers: list[Tier | None]
        if i == 0:
            prev_tiers = [None]
        else:
            prev_tiers = list(tiers)
        for new_tier in tiers:
            for prev in prev_tiers:
                add_s = 0.0
                add_usd = 0.0
                add_j = 0.0
                c_mass = 0.0
                l_mass = 0.0
                if cost_model.f1.enabled:
                    f1 = F1_decision_cost(turn, cost_model.f1)
                    add_s += f1.seconds
                    add_j += f1.joules
                    if f1.flag and f1.flag not in f1_flags:
                        f1_flags.append(f1.flag)
                f2 = F2_switching_cost(turn, prev, new_tier, cost_model.f2)
                if cost_model.f2.enabled and f2.switched:
                    add_s += f2.delta_seconds
                    add_usd += f2.delta_usd
                inf = inference_cost(
                    turn,
                    new_tier,
                    cost_model.inference,
                    f4_throughput_factor=f4_factor if new_tier == "local" else 1.0,
                )
                add_s += inf.seconds
                add_usd += inf.usd
                add_j += inf.joules
                if new_tier == "cloud":
                    c_mass += inf.seconds
                else:
                    l_mass += inf.seconds

                if prev is None:
                    cand_add = add_s
                    cand_usd = add_usd
                    cand_j = add_j
                    cand_c = c_mass
                    cand_l = l_mass
                    par = None
                else:
                    cand_add = add_best[i - 1][prev] + add_s
                    cand_usd = usd_best[i - 1][prev] + add_usd
                    cand_j = joules_best[i - 1][prev] + add_j
                    cand_c = cloud_mass[i - 1][prev] + c_mass
                    cand_l = local_mass[i - 1][prev] + l_mass
                    par = prev

                cand_score = cand_add - cloud_penalty * cand_c
                if cand_score < score_best[i][new_tier]:
                    score_best[i][new_tier] = cand_score
                    add_best[i][new_tier] = cand_add
                    usd_best[i][new_tier] = cand_usd
                    joules_best[i][new_tier] = cand_j
                    cloud_mass[i][new_tier] = cand_c
                    local_mass[i][new_tier] = cand_l
                    parent[i][new_tier] = par

    def final_seconds(tier: Tier) -> float:
        add = add_best[n - 1][tier]
        c = cloud_mass[n - 1][tier]
        l = local_mass[n - 1][tier]
        other = add - c - l
        return other + l + c / max(1e-12, speedup)

    end_tier = min(tiers, key=final_seconds)
    # Reconstruct assignment
    assignment: list[Tier] = [end_tier]
    cur = end_tier
    for i in range(n - 1, 0, -1):
        p = parent[i][cur]
        assert p is not None
        assignment.append(p)
        cur = p
    assignment.reverse()

    seconds = final_seconds(end_tier)
    usd = usd_best[n - 1][end_tier]
    joules = joules_best[n - 1][end_tier]

    cloud_s, cloud_usd, _, _ = _path_cost(
        trajectory, _uniform_assignment(trajectory, "cloud"), cost_model
    )
    local_s, local_usd, _, _ = _path_cost(
        trajectory, _uniform_assignment(trajectory, "local"), cost_model
    )

    return OracleResult(
        seconds=seconds,
        usd=usd,
        joules=joules,
        tier_assignment=assignment,
        cloud_only_seconds=cloud_s,
        cloud_only_usd=cloud_usd,
        local_only_seconds=local_s,
        local_only_usd=local_usd,
        static_assumption_flag=True,
        static_assumption_note=STATIC_ASSUMPTION_NOTE,
        invariance_bias="UNMEASURED",
        f4_label=f4_output_label(cost_model.f4),
        f1_flags=f1_flags,
        friction_mask={
            "F1": cost_model.f1.enabled,
            "F2": cost_model.f2.enabled,
            "F3": cost_model.f3.enabled,
            "F4": cost_model.f4.enabled,
        },
    )


def cloud_only_baseline(
    trajectory: Trajectory, cost_model: CostModelParams
) -> OracleResult:
    """Serial all-cloud baseline (denominator for unreachable fraction).

    No hybrid routing, no F1/F2/F4, and **no** concurrency fantasy: cloud
    wall-clock is uncompressed (effective_speedup = 1). F3's rate-limit cap
    is a hybrid-parallelism friction; the non-hybrid baseline is serial cloud.
    """
    from dataclasses import replace

    from censor.phase2_constants import F3Params, SourcedFloat

    mask = {
        "F1": False,
        "F2": False,
        "F3": True,  # force speedup path, but with assumed=max=1 → serial
        "F4": False,
    }
    serial_f3 = F3Params(
        enabled=True,
        max_speedup=SourcedFloat(
            1.0,
            "serial cloud-only baseline: no parallelism credit "
            "(denominator for unreachable fraction)",
        ),
        assumed_concurrency=SourcedFloat(
            1.0,
            "serial cloud-only baseline: assumed_concurrency=1",
        ),
    )
    base = replace(
        cost_model.with_friction_mask(mask),
        f3=serial_f3,
    )
    assignment = _uniform_assignment(trajectory, "cloud")
    s, u, j, flags = _path_cost(trajectory, assignment, base)
    return OracleResult(
        seconds=s,
        usd=u,
        joules=j,
        tier_assignment=assignment,
        cloud_only_seconds=s,
        cloud_only_usd=u,
        local_only_seconds=0.0,
        local_only_usd=0.0,
        f4_label="F4 not applied (baseline)",
        f1_flags=flags,
        friction_mask=mask,
        quality_held_at="n/a (serial cloud-only baseline)",
    )
