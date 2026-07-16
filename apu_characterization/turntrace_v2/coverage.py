"""Pre-run profile domain coverage check (F1 permanent gate)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from apu_characterization.turntrace_v2.calibration import PrefillProfile


@dataclass(frozen=True)
class CoverageReport:
    ok: bool
    grid_min: int
    grid_max: int
    expected_lo: int
    expected_hi: int
    message: str


def check_profile_covers_workload(
    profile: PrefillProfile,
    *,
    expected_context_lo: int,
    expected_context_hi: int,
) -> CoverageReport:
    """Fail the gate if the cell's expected context range is not covered by f(n)."""
    if not profile.points:
        return CoverageReport(
            ok=False,
            grid_min=0,
            grid_max=0,
            expected_lo=expected_context_lo,
            expected_hi=expected_context_hi,
            message="prefill profile has no points",
        )
    grid_min = min(n for n, _ in profile.points)
    grid_max = max(n for n, _ in profile.points)
    ok = expected_context_lo >= grid_min and expected_context_hi <= grid_max
    if ok:
        msg = (
            f"coverage OK: workload [{expected_context_lo}, {expected_context_hi}] "
            f"⊆ profile [{grid_min}, {grid_max}]"
        )
    else:
        msg = (
            f"coverage MISSING: workload expected engine-token context "
            f"[{expected_context_lo}, {expected_context_hi}] but profile grid is "
            f"[{grid_min}, {grid_max}]. Extend the prefill sweep before corpus collection."
        )
    return CoverageReport(
        ok=ok,
        grid_min=grid_min,
        grid_max=grid_max,
        expected_lo=expected_context_lo,
        expected_hi=expected_context_hi,
        message=msg,
    )


def assert_coverage_or_raise(
    profile: PrefillProfile,
    *,
    expected_context_lo: int,
    expected_context_hi: int,
) -> CoverageReport:
    report = check_profile_covers_workload(
        profile,
        expected_context_lo=expected_context_lo,
        expected_context_hi=expected_context_hi,
    )
    if not report.ok:
        raise SystemExit(report.message)
    return report


def domain_bounds(profile: PrefillProfile) -> tuple[int, int]:
    return min(n for n, _ in profile.points), max(n for n, _ in profile.points)


def estimate_bounds_from_pilot(engine_token_counts: Sequence[int]) -> tuple[int, int]:
    if not engine_token_counts:
        raise ValueError("pilot produced no engine token counts")
    return min(engine_token_counts), max(engine_token_counts)
