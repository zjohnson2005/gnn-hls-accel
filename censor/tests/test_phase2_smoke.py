"""Deterministic smoke tests for the Phase-2 censor engine."""

from __future__ import annotations

from censor.frictions_cost import F1_decision_cost, F2_switching_cost
from censor.oracle import cost_oracle
from censor.phase2_constants import CostModelParams, F1Params
from censor.quality_bounds import bounds_table, manski_bounds
from censor.schema import Trajectory, Turn
from censor.waterfall import unreachable_fraction


def _toy_traj(n: int = 3) -> Trajectory:
    turns = []
    ctx = 100
    for i in range(n):
        turns.append(
            Turn(
                turn_index=i,
                context_len_before=ctx,
                tokens_out=20,
                tool_type="bash",
                step_type_semantic="inspect",
                logged_latency_ms=500.0,
                logged_cost_usd=0.01,
                necessary_prefill_tokens=40,
                cloud_success=False,
                local_success=None,
                local_observed=False,
            )
        )
        ctx += 50
    return Trajectory(
        trajectory_id="toy-1",
        scaffold="toy",
        task_id="toy_task",
        task_class="toy",
        logged_tier="cloud",
        task_outcome=False,
        outcome_source="swebench_exact",
        truncated=False,
        parse_failure=False,
        censored=False,
        turns=turns,
    )


def test_f1_sourced_and_flag():
    turn = _toy_traj().turns[0]
    # embedding router at 5ms sits inside crossover — may or may not flag
    # (flag when router > lo=5.4). embedding=5.0 should NOT exceed 5.4.
    r = F1_decision_cost(turn, F1Params(router_type="embedding"))
    assert r.seconds > 0
    assert not r.router_exceeds_local_crossover
    r2 = F1_decision_cost(turn, F1Params(router_type="llm"))
    assert r2.router_exceeds_local_crossover


def test_f2_grows_with_context():
    traj = _toy_traj(3)
    p = CostModelParams().f2
    a = F2_switching_cost(traj.turns[0], "local", "cloud", p)
    b = F2_switching_cost(traj.turns[2], "local", "cloud", p)
    assert b.delta_tokens > a.delta_tokens
    assert b.delta_seconds > a.delta_seconds


def test_manski_and_a1():
    traj = _toy_traj()
    lo, hi = manski_bounds(traj, [traj])
    assert lo == 0.0 and hi == 1.0
    table = bounds_table([traj])
    a1 = next(r for r in table if "A1" in r.assumption_set and "A2" not in r.assumption_set)
    assert a1.upper == 0.0


def test_oracle_static_flag():
    r = cost_oracle(_toy_traj(), CostModelParams())
    assert r.static_assumption_flag is True
    assert r.invariance_bias == "UNMEASURED"
    assert "UNMEASURED" in r.f4_label


def test_unreachable_algebra():
    # (W0-W4)/(W0-cloud) == (W4-W0)/(cloud-W0)
    w0, w4, cloud = 10.0, 14.0, 20.0
    a = unreachable_fraction(w0, w4, cloud)
    b = (w4 - w0) / (cloud - w0)
    assert abs(a - b) < 1e-12
    # Serial cloud baseline must be >> compressed hybrid W0 for a sane fraction.
    assert 0.0 < a < 1.0


def test_cloud_only_is_serial():
    from censor.oracle import cloud_only_baseline, cost_oracle
    from censor.waterfall import _mask_from_subset

    traj = _toy_traj()
    params = CostModelParams()
    serial = cloud_only_baseline(traj, params).seconds
    # Hybrid W0 with F3 off compresses cloud by assumed_concurrency=8.
    w0 = cost_oracle(traj, params.with_friction_mask(_mask_from_subset([]))).seconds
    assert serial > w0 * 2.0
