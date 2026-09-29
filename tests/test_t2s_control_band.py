"""T2S n=18687 f16 control band and the UNCOLD_UPTIME seal field."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import pytest

from seam.measurement_gates import UNCOLD_UPTIME_REASON
from tools.seal_c2_ttft import deviation_for_seal
from tools.t2s_control_band import (
    CONTROL_N,
    CONTROL_REPEATS,
    MATCHING_ARM,
    REFERENCE_RUN_ID,
    RESOLUTION,
    check_work,
    evaluate_control,
    load_exponents,
    load_prefills,
    noreboot_deviation,
    reference_band,
    reference_work,
    select_b_t2s,
    within_session_window,
)
from tools.ttft_slo_canary import CanaryBudgetRefuse, assert_canary_budget_fits

ROOT = Path(__file__).resolve().parents[1]


def test_reference_band_uses_f16_exponent_and_keeps_the_old_window() -> None:
    work = reference_work(ROOT)
    prefills = load_prefills(work)
    assert len(prefills) == CONTROL_REPEATS
    window = within_session_window(prefills)
    median = float(statistics.median(prefills))
    spread = max(abs(v - median) / median for v in prefills)
    assert window["within_session_low"] == pytest.approx(min(prefills) * (1.0 - spread))
    assert window["within_session_high"] == pytest.approx(max(prefills) * (1.0 + spread))
    exponents = load_exponents(ROOT)
    assert MATCHING_ARM in exponents
    published = reference_band(ROOT)
    tol = exponents[MATCHING_ARM] * (RESOLUTION / CONTROL_N)
    assert published["reference_run_id"] == REFERENCE_RUN_ID
    assert published["b_t2s"] == exponents[MATCHING_ARM]
    assert published["b_t2s_source"] == "matching_kv"
    assert published["b_t2s_arm"] == MATCHING_ARM
    assert published["tol"] == pytest.approx(tol)
    assert published["low"] == pytest.approx(median * (1.0 - tol))
    assert published["high"] == pytest.approx(median * (1.0 + tol))
    assert published["within_session_low"] == window["within_session_low"]
    assert published["estimate_s"] == 782
    assert published["noreboot_reason"] == UNCOLD_UPTIME_REASON


def test_tol_gate_passes_when_the_old_window_would_fail(tmp_path: Path) -> None:
    band = reference_band(ROOT)
    inside = evaluate_control([9.83, 9.83, 9.83], band)
    assert inside["pass"] is True
    assert inside["reason"] == "inside_tol"
    assert inside["old_within_session_pass"] is True
    # Just above the within-session high, still inside median*(1+tol).
    drifted = float(band["within_session_high"]) + 0.01
    assert drifted < float(band["high"])
    report_only = evaluate_control([drifted, drifted, drifted], band)
    assert report_only["pass"] is True
    assert report_only["old_within_session_pass"] is False
    outside = evaluate_control([12.0, 12.0, 12.0], band)
    assert outside["pass"] is False
    assert outside["reason"] == "median_outside_tol"
    assert outside["old_within_session_pass"] is False
    short = evaluate_control([9.83], band)
    assert short["pass"] is False
    assert short["old_within_session_pass"] is None
    work = tmp_path / "work"
    work.mkdir()
    for repeat, value in enumerate((9.83, 9.83, 9.83)):
        name = f"gpu_only_f16.n{CONTROL_N}.r{repeat}.a0.result.json"
        (work / name).write_text(
            json.dumps({"generation": {"prefill_s": value}}),
            encoding="utf-8",
        )
    assert check_work(ROOT, work)["pass"] is True


def test_noreboot_deviation_and_seal_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEAM_NOREBOOT_DEVIATION", raising=False)
    assert noreboot_deviation() is None
    monkeypatch.setenv("SEAM_NOREBOOT_DEVIATION", "1")
    monkeypatch.setenv("SEAM_NOREBOOT_UPTIME_S", "12345.5")
    dev = noreboot_deviation()
    assert dev is not None
    assert dev["kind"] == "UNCOLD_UPTIME"
    assert dev["uptime_s"] == 12345.5
    assert dev["reason"] == UNCOLD_UPTIME_REASON
    assert deviation_for_seal({}, {"deviation": dev}) == dev
    assert deviation_for_seal({"deviation": dev}, {}) == dev
    assert deviation_for_seal({}, {}) is None


def test_missing_matching_kv_uses_the_mean_of_the_fits() -> None:
    exponents = {"gpu_only_u8": 1.5, "gpu_only_u4": 2.5, "gpu_only_f16": 3.5}
    matched = select_b_t2s(exponents, "gpu_only_f16")
    assert matched["b_t2s"] == 3.5
    assert matched["b_t2s_source"] == "matching_kv"
    fallback = select_b_t2s(
        {"gpu_only_u8": 1.5, "gpu_only_u4": 2.5},
        "gpu_only_f16",
    )
    assert fallback["b_t2s"] == pytest.approx(2.0)
    assert fallback["b_t2s_source"] == "mean_of_arms"
    assert fallback["b_t2s_arm"] is None


def test_fixed_n_canary_budget_fits_repeats_plus_one() -> None:
    assert_canary_budget_fits(CONTROL_REPEATS + 1)
    with pytest.raises(CanaryBudgetRefuse):
        assert_canary_budget_fits(CONTROL_REPEATS)
