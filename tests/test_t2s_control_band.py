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
    REFERENCE_RUN_ID,
    band_from_prefills,
    check_work,
    evaluate_control,
    load_prefills,
    noreboot_deviation,
    reference_band,
    reference_work,
)
from tools.ttft_slo_canary import CanaryBudgetRefuse, assert_canary_budget_fits

ROOT = Path(__file__).resolve().parents[1]


def test_reference_band_widens_the_sealed_repeats() -> None:
    work = reference_work(ROOT)
    prefills = load_prefills(work)
    assert len(prefills) == CONTROL_REPEATS
    band = band_from_prefills(prefills)
    median = float(statistics.median(prefills))
    spread = max(abs(v - median) / median for v in prefills)
    assert band["reference_run_id"] == REFERENCE_RUN_ID
    assert band["n"] == CONTROL_N
    assert band["min"] == min(prefills)
    assert band["max"] == max(prefills)
    assert band["median"] == median
    assert band["max_relative_spread"] == spread
    assert band["low"] == pytest.approx(min(prefills) * (1.0 - spread))
    assert band["high"] == pytest.approx(max(prefills) * (1.0 + spread))
    published = reference_band(ROOT)
    assert published["estimate_s"] == 782
    assert published["noreboot_reason"] == UNCOLD_UPTIME_REASON


def test_control_median_inside_band_passes_and_outside_fails(tmp_path: Path) -> None:
    band = reference_band(ROOT)
    inside = evaluate_control([9.83, 9.83, 9.83], band)
    assert inside["pass"] is True
    assert inside["reason"] == "inside_band"
    outside = evaluate_control([12.0, 12.0, 12.0], band)
    assert outside["pass"] is False
    assert outside["reason"] == "median_outside_band"
    short = evaluate_control([9.83], band)
    assert short["pass"] is False
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


def test_fixed_n_canary_budget_fits_repeats_plus_one() -> None:
    assert_canary_budget_fits(CONTROL_REPEATS + 1)
    with pytest.raises(CanaryBudgetRefuse):
        assert_canary_budget_fits(CONTROL_REPEATS)
