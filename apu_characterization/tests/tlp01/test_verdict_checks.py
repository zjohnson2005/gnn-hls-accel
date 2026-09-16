"""Check A v2 (analytical) + Check B (phase-diagram zero point)."""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from apu_characterization.tlp01.check_a_v2 import (
    compute_control_expectations,
    evaluate_check_a_v2,
    freeze_expectations,
    load_expectations,
)
from apu_characterization.tlp01.extract import make_synthetic_chain_session
from apu_characterization.tlp01.phase_diagram import replay_speculation_policy
from apu_characterization.tlp01.schedule import (
    simulate_in_order,
    simulate_in_order_work,
    simulate_model,
)
from apu_characterization.tlp01.schema import load_frozen_trace

REPO = Path(__file__).resolve().parents[3]
S2 = REPO / "apu_characterization/out/tlp01/traces/S2"
EXPECTATIONS = (
    REPO / "apu_characterization/tlp01/check_a_v2_expectations.json"
)


def _ser_sessions() -> dict[str, list]:
    by: dict[str, list] = defaultdict(list)
    for tid in ("MT-SER-01", "MT-SER-02"):
        for seed in range(5):
            path = S2 / f"S2-{tid}-s{seed}.jsonl"
            if path.is_file():
                by[tid].append(load_frozen_trace(path))
    return by


@pytest.mark.skipif(not S2.is_dir(), reason="frozen S2 traces not present")
def test_check_a_v2_expectations_frozen_and_match() -> None:
    sessions = _ser_sessions()
    assert sessions.get("MT-SER-01") and sessions.get("MT-SER-02")
    if not EXPECTATIONS.is_file():
        freeze_expectations(compute_control_expectations(sessions))
    exp = load_expectations()
    assert exp.get("frozen") is True
    result = evaluate_check_a_v2(sessions, expectations=exp, tier="Tier_S")
    assert result["status"] == "PASS", result["rows"]


def test_m1a_baseline_is_work_not_recorded_wall() -> None:
    events = make_synthetic_chain_session(steps=3, unit_ns=10_000_000, orch_ns=0)
    work = simulate_in_order_work(events, charge_orch=False)
    m1a = simulate_model(events, "M1a", "Tier_C")
    assert m1a.baseline_makespan_ns == work.makespan_ns
    _ = simulate_in_order(events)


def test_check_b_phase_diagram_zero_point_is_no_speculation() -> None:
    events = make_synthetic_chain_session(steps=4, orch_ns=0)
    model: dict[str, Counter[str]] = {}
    rng = random.Random(0)
    none = replay_speculation_policy(
        events,
        model,
        policy="no_speculation",
        penalty_ns=10_000_000,
        accuracy_target=0.8,
        confidence_threshold=0.5,
        rng=rng,
    )
    assert none.wall_ns == none.useful_work_ns
    assert none.wasted_ns == 0
