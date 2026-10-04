"""Rehearsal entry points under Set-StrictMode. Smokes are stubbed."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRICT_MARKERS = (
    "VariableIsUndefined",
    "PropertyNotFound",
    "has not been set",
    "cannot be found on this object",
)


def _run(script: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["SEAM_BOOT_SMOKE_STUB"] = "1"
    command = (
        "Set-StrictMode -Version Latest; "
        f"& '{ROOT / 'tools' / script}' -Rehearsal; "
        "exit $LASTEXITCODE"
    )
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _assert_no_strict_fault(proc: subprocess.CompletedProcess[str], script: str) -> None:
    combined = proc.stdout + proc.stderr
    for marker in STRICT_MARKERS:
        assert marker not in combined, f"{script} strict-mode fault:\n{combined}"


def test_boot4_rehearsal_strict_mode_stubs_smokes() -> None:
    proc = _run("launch_boot4.ps1")
    _assert_no_strict_fault(proc, "launch_boot4.ps1")
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "smoke_stub" in combined
    assert "REHEARSAL_COMPLETE" in combined
    assert "BOOT_COMPLETE" in combined


def test_resident_limit_rehearsal_strict_mode_stubs_smokes() -> None:
    proc = _run("launch_resident_limit.ps1")
    _assert_no_strict_fault(proc, "launch_resident_limit.ps1")
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "smoke_stub" in combined
    assert "REHEARSAL_COMPLETE" in combined
    assert "BOOT_COMPLETE" in combined
    assert "resident_limit_estimate_sum_s=3396" in combined
    assert "fits_one_window=true" in combined


def test_resident_limit_2_rehearsal_strict_mode_stubs_smokes() -> None:
    proc = _run("launch_resident_limit_2.ps1")
    _assert_no_strict_fault(proc, "launch_resident_limit_2.ps1")
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "hang_probe_stub" in combined
    assert "smoke_stub" in combined
    assert "REHEARSAL_COMPLETE" in combined
    assert "BOOT_COMPLETE" in combined
    assert "resident_limit_estimate_sum_s=4282" in combined
    assert "fits_one_window=true" in combined
    assert "RESIDENT-LIMIT u4" in combined
    assert "P0 EXCHANGE-RATE" in combined


def test_p0_v2_rehearsal_strict_mode_stubs_smokes() -> None:
    proc = _run("launch_p0_v2.ps1")
    _assert_no_strict_fault(proc, "launch_p0_v2.ps1")
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "smoke_stub" in combined
    assert "REHEARSAL_COMPLETE" in combined
    assert "BOOT_COMPLETE" in combined
    assert "p0_v2_estimate_sum_s=3159" in combined
    assert "fits_one_window=true" in combined
    assert "P0-V2 EXCHANGE-RATE" in combined
    assert "RESIDENT-LIMIT u4" not in combined


def test_p1_a0_rehearsal_strict_mode_stubs_smokes() -> None:
    proc = _run("launch_p1_a0.ps1")
    _assert_no_strict_fault(proc, "launch_p1_a0.ps1")
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "smoke_stub" in combined
    assert "REHEARSAL_COMPLETE" in combined
    assert "BOOT_COMPLETE" in combined
    assert "p1_a0_estimate_sum_s=4814" in combined
    assert "fits_one_window=true" in combined
    assert "P1 A0" in combined
    assert "--canary-calibrate" in combined
    assert "--smoke" not in combined


def test_result_kinds_rehearse_through_the_cell_invoker() -> None:
    """Ceiling and det share the $ran.Exit read. Rehearsal must call it."""
    env = os.environ.copy()
    env["SEAM_BOOT_CELL_STUB"] = "1"
    env["SEAM_BOOT_SMOKE_STUB"] = "1"
    command = (
        "Set-StrictMode -Version Latest; "
        f"& '{ROOT / 'tools' / 'launch_boot1.ps1'}' -Profile boot1 -Rehearsal; "
        "exit $LASTEXITCODE"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    combined = proc.stdout + proc.stderr
    _assert_no_strict_fault(proc, "boot1 rehearsal invoker")
    assert proc.returncode == 0, combined
    assert "cell_invoke kind=det" in combined
    assert "cell_invoke kind=ceiling" in combined
    assert "SMOKE_OK det" in combined
    assert "REHEARSAL_COMPLETE" in combined
    assert "no rehearsal smoke" not in combined


def test_t2s_rehearsal_strict_mode_stubs_smokes() -> None:
    proc = _run("launch_t2s_boot1.ps1")
    _assert_no_strict_fault(proc, "launch_t2s_boot1.ps1")
    combined = proc.stdout + proc.stderr
    assert "rehearsal_context=strict_harness" in combined
    assert "json_ok" in combined
    if proc.returncode == 0:
        assert "smoke_stub" in combined
        assert "REHEARSAL_COMPLETE" in combined
        assert "BOOT_COMPLETE" in combined
    else:
        assert "REFUSED --" in combined
