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
    assert "resident_limit_estimate_sum_s=1132" in combined
    assert "fits_one_window=true" in combined
    assert "RESIDENT-LIMIT u4" in combined


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
