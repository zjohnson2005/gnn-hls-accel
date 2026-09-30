"""Healthy-session canary floors replace the 0.05 drift floor."""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ttft_slo_canary import (  # noqa: E402
    HEALTHY_FLOOR_P95_T1,
    HEALTHY_FLOOR_P95_T2,
    HEALTHY_FLOOR_SESSIONS,
    HEALTHY_FLOOR_T1,
    HEALTHY_FLOOR_T2,
    TtftSloCanaryGuard,
    new_canary_gate,
    update_canary_drift_bookkeeping,
)

POOL = ROOT / "derived" / "c2_ttft" / "analysis" / "canary_threshold_pool.json"
REFUSED_T1 = 2.658880859
REFUSED_REL_T1 = 0.06364551681998237


def test_floors_match_the_pooled_series() -> None:
    doc = json.loads(POOL.read_text(encoding="utf-8"))
    rows = [
        row
        for session in doc["sessions"]
        for row in session["series"]
        if row["in_current_rule_pool"]
    ]
    rel_t1 = [row["rel_t1"] for row in rows]
    rel_t2 = [row["rel_t2"] for row in rows]
    assert max(rel_t1) == HEALTHY_FLOOR_T1
    assert max(rel_t2) == HEALTHY_FLOOR_T2
    assert doc["pooled_max_rel_t1"] == HEALTHY_FLOOR_T1
    assert doc["pooled_max_rel_t2"] == HEALTHY_FLOOR_T2
    assert doc["previous_healthy_floor_t1"] == 0.07709453214145699
    assert doc["previous_healthy_floor_t2"] == 0.5655217613849336
    assert doc["n_canaries"] == 31
    excluded_t2 = [
        row["rel_t2"]
        for session in doc["sessions"]
        for row in session["series"]
        if not row["in_current_rule_pool"]
    ]
    assert doc["previous_healthy_floor_t2"] in excluded_t2
    assert doc["previous_healthy_floor_t2"] not in rel_t2
    p95_t1 = statistics.quantiles(rel_t1, n=100, method="inclusive")[94]
    p95_t2 = statistics.quantiles(rel_t2, n=100, method="inclusive")[94]
    assert p95_t1 == HEALTHY_FLOOR_P95_T1
    assert p95_t2 == HEALTHY_FLOOR_P95_T2
    assert [session["run_id"] for session in doc["sessions"]] == list(HEALTHY_FLOOR_SESSIONS)
    assert REFUSED_REL_T1 < HEALTHY_FLOOR_T1


def test_refused_turn1_stays_under_the_new_floor() -> None:
    gate = new_canary_gate()
    prior: list[dict[str, object]] = []
    samples = (
        (2.52504248, 1.018973144, True),
        (2.499781005, 0.840779479, False),
        (2.529414306, 0.671709289, False),
        (2.489255859, 0.688477294, False),
    )
    for turn1, turn2, warmup in samples:
        book = update_canary_drift_bookkeeping(
            rec={
                "classification": "OK",
                "turn1_prefill_s": turn1,
                "turn2_prefill_s": turn2,
                "warmup": warmup,
            },
            gate=gate,
            prior_ok_canaries=prior,
        )
        assert book["tripped"] is False
        prior.append(book["rec"])
    check = update_canary_drift_bookkeeping(
        rec={
            "classification": "OK",
            "turn1_prefill_s": REFUSED_T1,
            "turn2_prefill_s": 0.721247436,
            "warmup": False,
        },
        gate=gate,
        prior_ok_canaries=prior,
    )
    rel = abs(REFUSED_T1 - float(gate["ref_turn1_prefill_s"])) / float(gate["ref_turn1_prefill_s"])
    assert rel == pytest.approx(REFUSED_REL_T1)
    assert rel > 0.05
    assert rel < HEALTHY_FLOOR_T1
    assert gate["threshold_t1"] == pytest.approx(HEALTHY_FLOOR_T1)
    assert check["tripped"] is False


def test_a_drift_above_the_floor_still_trips() -> None:
    gate = new_canary_gate()
    prior: list[dict[str, object]] = []
    for turn1 in (2.50, 2.50, 2.50):
        book = update_canary_drift_bookkeeping(
            rec={"classification": "OK", "turn1_prefill_s": turn1, "turn2_prefill_s": 0.70},
            gate=gate,
            prior_ok_canaries=prior,
        )
        prior.append(book["rec"])
    breach = 2.50 * (1.0 + HEALTHY_FLOOR_T1 + 0.01)
    book = update_canary_drift_bookkeeping(
        rec={"classification": "OK", "turn1_prefill_s": breach, "turn2_prefill_s": 0.70},
        gate=gate,
        prior_ok_canaries=prior,
    )
    assert book["tripped"] is True


def test_every_plan_records_the_derivation(tmp_path: Path) -> None:
    guard = TtftSloCanaryGuard(
        root=ROOT,
        model_spec=ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml",
        work_dir=tmp_path,
        planned_probe_count=4,
    )
    recorded = guard.plan_fragment()["threshold_derivation"]
    assert recorded["formula"] == "threshold = max(2 * early_max_rel, healthy_floor)"
    assert recorded["sessions"] == list(HEALTHY_FLOOR_SESSIONS)
    assert recorded["healthy_floor_t1"] == HEALTHY_FLOOR_T1
    assert recorded["healthy_floor_t2"] == HEALTHY_FLOOR_T2
    assert recorded["previous_healthy_floor_t2"] == 0.5655217613849336
    assert "first" in recorded["pool_rule"]
    assert recorded["replaced_floor"] == 0.05
    assert "Kill WorkloadsSessionHost" in guard.plan_fragment()["workloads_session_host_policy"]
