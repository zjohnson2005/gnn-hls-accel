"""Launcher papercuts: the dry-run gate summary, and dry-run gate probes.

Hardware-free; PowerShell is not run. The launchers are checked as text and
the ignore rules with git itself. No gate logic or threshold is touched.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from seam.measurement_gates import GateResult, MeasurementGateReport

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
GATES_PS1 = TOOLS / "_run_measurement_gates.ps1"
ASSIGN = "$gateFails = @(Get-SeamGateRefusals -GateJson $gateJson)"


def _launchers_using_gate_fails() -> list[Path]:
    return sorted(
        p for p in TOOLS.glob("launch_*.ps1") if "$gateFails" in p.read_text(encoding="utf-8")
    )


def test_every_gate_fails_use_is_assigned_first() -> None:
    found = _launchers_using_gate_fails()
    names = {p.name for p in found}
    assert {
        "launch_c1.ps1",
        "launch_c2.ps1",
        "launch_h1.ps1",
        "launch_n1.ps1",
        "launch_w2.ps1",
        "launch_w3.ps1",
        "launch_x2.ps1",
    } <= names
    for path in found:
        text = path.read_text(encoding="utf-8")
        uses = [m.start() for m in re.finditer(r"\$gateFails(?!\s*=)", text)]
        assigned = text.find(ASSIGN)
        assert assigned >= 0, path.name
        assert all(assigned < use for use in uses), path.name
        call = text.find("$gateJson = Invoke-SeamMeasurementGates")
        assert 0 <= call < assigned, path.name
        dot = text.find('. (Join-Path $PSScriptRoot "_run_measurement_gates.ps1")')
        assert 0 <= dot < call, path.name


def test_gate_refusal_reader_reads_refusal_reasons() -> None:
    text = GATES_PS1.read_text(encoding="utf-8")
    assert "function Get-SeamGateRefusals" in text
    assert "refusal_reasons" in text
    # The reader never exits or refuses; it only reports.
    body = text[text.index("function Get-SeamGateRefusals") :]
    assert "exit" not in body


def test_gate_payload_carries_refusal_reasons() -> None:
    report = MeasurementGateReport(
        platform_id="aipc-c1",
        gates=[GateResult(name="ac", passed=False, reason="on_battery")],
        all_passed=False,
        refusal_reasons=["ac:on_battery"],
    )
    assert report.to_dict()["refusal_reasons"] == ["ac:on_battery"]


def test_dry_run_probes_go_to_the_ignored_dir() -> None:
    text = GATES_PS1.read_text(encoding="utf-8")
    assert '$outDir = Join-Path $RepoRoot "derived\\_gate_probes\\_dryrun"' in text
    assert '$outDir = Join-Path $RepoRoot "derived\\_gate_probes"\n' in text
    boot = (TOOLS / "launch_boot1.ps1").read_text(encoding="utf-8")
    block = boot[boot.index("function Invoke-BootGates") :]
    block = block[: block.index("New-Item")]
    assert '$probeDir = Join-Path $LaunchDir "gate_probes"' in block
    assert "} elseif ($DryRun) {" in block
    assert '$probeDir = Join-Path $root "derived\\_gate_probes\\_dryrun"' in block
    assert '$probeDir = Join-Path $root "derived\\_gate_probes"\n' in block


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_ignore_rules_dry_run_ignored_live_kept() -> None:
    def ignored(rel: str) -> bool:
        done = subprocess.run(
            ["git", "check-ignore", "-q", rel], cwd=ROOT, check=False, capture_output=True
        )
        return done.returncode == 0

    assert ignored("derived/_gate_probes/_dryrun/gates_20261013_000000.json")
    assert ignored("derived/_gate_probes/_dryrun/boot1_P1_sweep_A0_B=10_20261013_000000.json")
    assert not ignored("derived/_gate_probes/gates_20261013_000000.json")
    assert not ignored("derived/_gate_probes/boot1_NPU-1_MAX_PROMPT_LEN=1024_20261013_000000.json")
