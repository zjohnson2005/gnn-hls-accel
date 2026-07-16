from __future__ import annotations

from apu_characterization.turntrace_v2.calibration import synthesize_prefill_sweep
from apu_characterization.turntrace_v2.coverage import check_profile_covers_workload


def test_coverage_detects_missing_low_end() -> None:
    profile = synthesize_prefill_sweep(seed=1, n_grid=(256, 512, 1024), reps=5)
    bad = check_profile_covers_workload(profile, expected_context_lo=32, expected_context_hi=200)
    assert bad.ok is False
    assert "MISSING" in bad.message


def test_coverage_passes_when_inside() -> None:
    profile = synthesize_prefill_sweep(
        seed=1, n_grid=(32, 64, 128, 256, 512), reps=5
    )
    ok = check_profile_covers_workload(profile, expected_context_lo=40, expected_context_hi=400)
    assert ok.ok is True
