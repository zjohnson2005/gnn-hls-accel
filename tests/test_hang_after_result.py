"""A child that writes its result and spins is killed, and the search continues."""

from __future__ import annotations

from seam.tools.delta_n import configured_hang_after_result_s
from seam.tools.hang_fault_injection import run_fault_injection


def test_hang_grace_is_thirty_seconds() -> None:
    assert configured_hang_after_result_s() == 30


def test_stub_child_is_killed_and_bisection_continues() -> None:
    report = run_fault_injection()
    assert report["ok"] is True, report
    assert report["hang_disposition"] == "HUNG_AFTER_RESULT"
    assert report["outcome"] == "fail"
    assert report["failure_mode"] == "turn1:RuntimeError"
    assert report["continued"] is True
    assert report["probed"][1] == 1000
    assert report["largest_n_cached"] == 500
    duration = float(report["hang_duration_s"])
    assert 30 <= duration < 32
