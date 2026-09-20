"""INF-6 unit tests: criterion-aware timeout, power transition, plan prediction pointer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.canary_power_gate import (
    CanaryPowerTransitionAbort,
    assert_no_ac_transition,
)
from tools.criterion_timeout import (
    TTFT_SLO_TIMEOUT_MULTIPLIER,
    derive_probe_timeout_s,
)
from tools.ttft_slo_predictions import (
    match_cap3_arm,
    resolve_ttft_slo_plan_predictions,
)

ROOT = Path(__file__).resolve().parents[1]


def test_ttft_slo_timeout_is_three_times_slo() -> None:
    d = derive_probe_timeout_s(criterion="ttft_slo", slo_s=10.0, config_timeout_s=1800.0)
    assert d["timeout_s"] == 30.0
    assert d["multiplier"] == TTFT_SLO_TIMEOUT_MULTIPLIER == 3.0
    assert d["formula"] == "timeout_s = slo_s * 3"
    assert d["config_timeout_s_not_used"] == 1800.0
    assert "derivation" in d and "30" in d["derivation"]


def test_completion_timeout_keeps_config() -> None:
    d = derive_probe_timeout_s(criterion="completion", slo_s=None, config_timeout_s=1800.0)
    assert d["timeout_s"] == 1800.0
    assert d["config_timeout_s_not_used"] is None


def test_ttft_slo_requires_positive_slo() -> None:
    with pytest.raises(ValueError):
        derive_probe_timeout_s(criterion="ttft_slo", slo_s=None, config_timeout_s=1800.0)
    with pytest.raises(ValueError):
        derive_probe_timeout_s(criterion="ttft_slo", slo_s=0.0, config_timeout_s=1800.0)


def test_no_battery_passes_trivially() -> None:
    snap = {
        "battery_present": False,
        "on_ac": True,
        "battery_status_values": None,
        "estimated_charge_remaining_pct": None,
        "note": "no_battery_mains_only_assume_ac",
        "probe_error": None,
    }
    out = assert_no_ac_transition(previous=None, current=snap)
    assert out["ok"] is True
    assert out["action"] == "pass_no_battery"
    out2 = assert_no_ac_transition(previous=snap, current=snap)
    assert out2["ok"] is True


def test_ac_to_battery_transition_refuses() -> None:
    prev = {
        "battery_present": True,
        "on_ac": True,
        "battery_status_values": [2],
        "estimated_charge_remaining_pct": 100,
        "note": "ac_ok",
        "probe_error": None,
    }
    cur = {
        "battery_present": True,
        "on_ac": False,
        "battery_status_values": [1],
        "estimated_charge_remaining_pct": 99,
        "note": "AC_offline",
        "probe_error": None,
    }
    with pytest.raises(CanaryPowerTransitionAbort) as ei:
        assert_no_ac_transition(previous=prev, current=cur)
    assert "transition" in str(ei.value).lower() or "on_ac" in str(ei.value)


def test_stable_ac_passes() -> None:
    snap = {
        "battery_present": True,
        "on_ac": True,
        "battery_status_values": [2],
        "estimated_charge_remaining_pct": 100,
        "note": "ac_ok",
        "probe_error": None,
    }
    assert assert_no_ac_transition(previous=None, current=snap)["action"] == "baseline"
    assert assert_no_ac_transition(previous=snap, current=snap)["ok"] is True


def test_probe_failure_refuses_not_guess() -> None:
    bad = {
        "battery_present": None,
        "on_ac": None,
        "note": "probe_failed",
        "probe_error": "boom",
    }
    with pytest.raises(CanaryPowerTransitionAbort):
        assert_no_ac_transition(previous=None, current=bad)


def _c2_default(*, slo_s: float, repeats: int) -> dict:
    return {
        "primary_prediction": {
            "status": "ACTIVE",
            "claim": "three turn-1 TTFT limits AGREE within resolution",
        },
        "slo": {"prefill_s_max": slo_s, "repeats": repeats},
    }


def test_plan_prediction_pointer_for_8b_cap3() -> None:
    pred = resolve_ttft_slo_plan_predictions(
        model_spec=ROOT / "configs/models/Qwen3-8B-int4-ov.yaml",
        arm_ids=["gpu_only_f16"],
        slo_s=10.0,
        repeats=3,
        default_c2_predictions=_c2_default,
        repo_root=ROOT,
    )
    assert pred["source"] == "cap3_predictions_file"
    assert pred["predictions_path"] == "derived/cap3/CAP3_PREDICTIONS.json"
    assert pred["arm_key"] == "arm1_8b_int4"
    assert pred["c2_am038_not_applicable"] is True
    assert "P1_limit_band" in (pred.get("predictions") or {})


def test_plan_prediction_default_c2_for_4b_int4() -> None:
    pred = resolve_ttft_slo_plan_predictions(
        model_spec=ROOT / "configs/models/Qwen3-4B-int4-ov.yaml",
        arm_ids=["gpu_only_f16", "gpu_only_u8", "gpu_only_u4"],
        slo_s=10.0,
        repeats=3,
        default_c2_predictions=_c2_default,
        repo_root=ROOT,
    )
    assert pred["source"] == "c2_am038_inline"
    assert pred["predictions_path"] is None
    assert pred["c2_am038_not_applicable"] is False
    assert pred["primary_prediction"]["status"] == "ACTIVE"


def test_match_cap3_arm_int8() -> None:
    m = match_cap3_arm(
        model_spec=ROOT / "configs/models/Qwen3-4B-int8-ov.yaml",
        repo_root=ROOT,
    )
    assert m is not None
    assert m[0] == "arm2_4b_int8"


def test_launch_h1_has_modelspec_param() -> None:
    text = (ROOT / "tools/launch_h1.ps1").read_text(encoding="utf-8")
    assert "[string]$ModelSpec" in text
    assert "--model-spec" in text
    assert "Qwen3-8B-int4-ov" in text or "R2B_8B" in text or "ModelSpec" in text


def test_r2b_8b_predictions_file_exists() -> None:
    p = ROOT / "derived/h1_hybrid/R2B_8B_PREDICTIONS.json"
    assert p.is_file()
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["status"] == "pre_registered_before_measurement"
    assert doc["predictions"]["P1_escalations"]["predicted_n_escalated"] == 13
    assert doc["predictions"]["P2_cloud_usd"]["predicted_cloud_usd"] == 3.5
    assert "cloud_usd > 8.0" in doc["joint_falsifier"]["falsified_if_any"]


def test_contaminated_sessions_recorded() -> None:
    p = ROOT / "derived/cap3/CONTAMINATED_SESSIONS.json"
    assert p.is_file()
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert "9c037801-342b-478e-8e95-5b66d369eab8" in doc["sessions"]
    assert doc["sessions"]["c3efd48e-84c5-46c6-bb1f-42d13f7c0a16"]["contamination"] == (
        "contaminated_power"
    )
