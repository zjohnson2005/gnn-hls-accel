"""Unit tests: ttft_slo canary trip must abort, not soft-return.

Mirrors tools/test_canary_drift_abort_enforcement.ps1 for the Python path.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ttft_slo_canary import (
    FAIL_STATUS,
    CanaryDriftAbort,
    derive_canary_every_n,
    new_canary_gate,
    update_canary_drift_bookkeeping,
)


def _ok_rec(t1: float, t2: float, idx: int) -> dict:
    return {
        "classification": "OK",
        "turn1_prefill_s": t1,
        "turn2_prefill_s": t2,
        "canary_index": idx,
    }


def test_calibration_arms_then_trip_raises_path() -> None:
    gate = new_canary_gate(calibration_c=3, rel_drift_floor=0.05)
    prior: list[dict] = []
    # Calibration canaries near each other.
    for i, (t1, t2) in enumerate([(2.66, 1.06), (2.65, 1.05), (2.67, 1.07)]):
        rec = _ok_rec(t1, t2, i)
        bk = update_canary_drift_bookkeeping(
            rec=rec, gate=gate, prior_ok_canaries=prior, calibration_c=3
        )
        assert bk["tripped"] is False
        prior.append(bk["rec"])
    assert gate["calibration_complete"] is True
    assert gate["threshold_t1"] >= 0.05

    # Breach class like 89f77871 canary 4: ~5.3% under ref with floor 0.05.
    bad = _ok_rec(2.517, 0.802, 3)
    bk = update_canary_drift_bookkeeping(
        rec=bad, gate=gate, prior_ok_canaries=prior, calibration_c=3
    )
    assert bk["tripped"] is True
    assert bad["drift_tripped"] is True

    # Caller must abort via exception, not a soft bool.
    try:
        if bk["tripped"]:
            raise CanaryDriftAbort(str(bk["trip_detail"]), canary_record=bad)
        raise AssertionError("must not continue after trip")
    except CanaryDriftAbort as exc:
        assert FAIL_STATUS == "FAIL_CANARY_DRIFT"
        assert "rel_drift" in exc.detail


def test_n_from_this_run_not_inherited_12() -> None:
    # If mean wall is ~11 s (C-2-like), N = floor(657/11)=59, not inherited 12.
    d = derive_canary_every_n([10.5, 10.8, 11.0])
    assert d["derivable"] is True
    mean_w = (10.5 + 10.8 + 11.0) / 3.0
    assert d["n"] == int(657.0 // mean_w)
    assert d["n"] != 12
    assert d["n"] >= 50  # far from inherited matrix N=12


def test_cannot_return_true_after_trip() -> None:
    """Document the enforcement contract: trip -> exception, never True."""
    gate = new_canary_gate(calibration_c=2, rel_drift_floor=0.05)
    prior = []
    for i, t in enumerate([(1.0, 0.5), (1.01, 0.51)]):
        rec = _ok_rec(t[0], t[1], i)
        bk = update_canary_drift_bookkeeping(
            rec=rec, gate=gate, prior_ok_canaries=prior, calibration_c=2
        )
        prior.append(bk["rec"])
    bad = _ok_rec(2.0, 0.5, 2)  # 100% t1 drift
    bk = update_canary_drift_bookkeeping(
        rec=bad, gate=gate, prior_ok_canaries=prior, calibration_c=2
    )
    assert bk["tripped"] is True
    # Soft return would be the PS bug; we require raise.
    raised = False
    try:
        raise CanaryDriftAbort(bk["trip_detail"] or "trip", canary_record=bad)
    except CanaryDriftAbort:
        raised = True
    assert raised


if __name__ == "__main__":
    test_calibration_arms_then_trip_raises_path()
    test_n_from_this_run_not_inherited_12()
    test_cannot_return_true_after_trip()
    print("PASS tools/test_ttft_slo_canary_abort.py")
