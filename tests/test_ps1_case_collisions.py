"""PowerShell variable names are case-insensitive.

4fbf323 added -ProbeDir to Invoke-SeamMeasurementGates while the function
already assigned a local $probeDir, which is the same variable, so the
argument was overwritten and a live launch_h1 still wrote its gate JSON to
derived/_gate_probes/. These tests keep that class out of the launchers:
a static scan (always), and pwsh runs when pwsh is installed.

Task AV (2026-10-16): the scan also covers top-level script code. launch_h1.ps1
assigned $kv in the -PolicyCapUsd parser, which is the [ValidateSet] -Kv
parameter, so every -PolicyCapUsd launch threw (broken since 3d9d6c4).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
GATES_PS1 = TOOLS / "_run_measurement_gates.ps1"
SCANNED = (GATES_PS1, TOOLS / "launch_h1.ps1", TOOLS / "launch_boot1.ps1")
PWSH = shutil.which("pwsh")

_ASSIGN = re.compile(
    r"(?:^|[;{(\s])\$([A-Za-z_][A-Za-z0-9_]*)\s*(?:=(?!=)|\+=|-=)"
    r"|foreach\s*\(\s*\$([A-Za-z_][A-Za-z0-9_]*)\s+in",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_comments(text: str) -> str:
    return re.sub(r"(?m)(^|\s)#.*$", r"\1", text)


def _close(text: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    for index in range(start, len(text)):
        if text[index] == opening:
            depth += 1
        elif text[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    return len(text) - 1


def _param_block(body: str) -> tuple[list[str], str]:
    match = re.match(r"\s*(?:\[CmdletBinding\(\)\]\s*)?param\s*\(", body, re.IGNORECASE)
    if match is None:
        return [], body
    end = _close(body, match.end() - 1, "(", ")")
    block = body[match.end() - 1 : end + 1]
    names = re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|,|\)|$)", block, re.MULTILINE)
    return names, body[end + 1 :]


def _functions(text: str) -> list[tuple[str, list[str], str]]:
    found = []
    for match in re.finditer(r"(?im)^\s*function\s+([A-Za-z0-9_-]+)\s*\{", text):
        start = match.end() - 1
        body = text[start + 1 : _close(text, start, "{", "}")]
        params, rest = _param_block(body)
        found.append((match.group(1), params, rest))
    return found


def _script_params(text: str) -> list[str]:
    match = re.search(r"(?m)^\s*param\s*\(", text)
    if match is None or re.search(r"(?im)^\s*function\s", text[: match.start()]):
        return []
    params, _ = _param_block(text[match.start() :])
    return params


def _top_level(text: str) -> str:
    """Script text with function bodies and the script param block removed."""
    out = text
    for match in reversed(list(re.finditer(r"(?im)^\s*function\s+[A-Za-z0-9_-]+\s*\{", out))):
        start = match.end() - 1
        out = out[: match.start()] + out[_close(out, start, "{", "}") + 1 :]
    match = re.search(r"(?m)^\s*param\s*\(", out)
    if match is not None:
        out = out[: match.start()] + out[_close(out, match.end() - 1, "(", ")") + 1 :]
    return out


def collisions(text: str) -> list[str]:
    """Locals that are a param of the same function, or a script param in another case."""
    text = _strip_comments(text)
    script_params = _script_params(text)
    problems: list[str] = []
    top_assigned = {a or b for a, b in _ASSIGN.findall(_top_level(text))}
    for local in sorted(top_assigned):
        for param in script_params:
            if local.lower() == param.lower() and local != param:
                problems.append(f"script: ${local} shadows script parameter ${param}")
    for name, params, rest in _functions(text):
        assigned = {a or b for a, b in _ASSIGN.findall(rest)}
        for local in sorted(assigned):
            for param in params:
                if local.lower() == param.lower():
                    problems.append(f"{name}: ${local} overwrites its parameter ${param}")
            for param in script_params:
                if local.lower() == param.lower() and local != param:
                    problems.append(f"{name}: ${local} shadows script parameter ${param}")
    return problems


def test_scanner_catches_the_4fbf323_bug() -> None:
    buggy = """
function Invoke-SeamMeasurementGates {
    param(
        [string]$RepoRoot,
        [switch]$DryRun,
        [string]$ProbeDir = ""
    )
    $probeDir = Join-Path $RepoRoot "derived\\_gate_probes"
    if (-not [string]::IsNullOrWhiteSpace($ProbeDir)) { $probeDir = $ProbeDir }
}
"""
    assert collisions(buggy) == [
        "Invoke-SeamMeasurementGates: $probeDir overwrites its parameter $ProbeDir"
    ]


def test_scanner_catches_a_script_param_shadow() -> None:
    text = """
param([switch]$LoadOnly)
function Get-X {
    param($Cell)
    $loadOnly = $Cell.LoadOnly
}
"""
    assert collisions(text) == ["Get-X: $loadOnly shadows script parameter $LoadOnly"]


def test_scanner_catches_the_policycapusd_kv_bug() -> None:
    text = """
param(
    [ValidateSet("", "default", "u8", "u4", "f16")]
    [string]$Kv = "",
    [string]$PolicyCapUsd = ""
)
foreach ($item in @($PolicyCapUsd -split ",")) {
    $kv = $item -split "=", 2
}
"""
    assert collisions(text) == ["script: $kv shadows script parameter $Kv"]


@pytest.mark.parametrize("path", SCANNED, ids=lambda p: p.name)
def test_no_case_insensitive_collisions(path: Path) -> None:
    assert collisions(path.read_text(encoding="utf-8")) == []


def test_gate_dir_precedence_text() -> None:
    text = GATES_PS1.read_text(encoding="utf-8")
    body = text[text.index("function Invoke-SeamMeasurementGates") :]
    body = body[: body.index("function Get-SeamGateRefusals")]
    assert "$probeDir" not in body.replace("$ProbeDir", "")
    first = body.index("if (-not [string]::IsNullOrWhiteSpace($ProbeDir)) {")
    dry = body.index("} elseif ($DryRun) {")
    live = body.index('$outDir = Join-Path $RepoRoot "derived\\_gate_probes"\n')
    assert first < dry < live


# ---------------------------------------------------------------- pwsh


def _fake_python(tmp_path: Path) -> Path:
    exe = tmp_path / "fake_python"
    payload = json.dumps({"all_passed": True, "refusal_reasons": []})
    exe.write_text(f"#!/bin/sh\necho '{payload}'\n", encoding="ascii")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


def _gate_dir(tmp_path: Path, extra: str) -> Path:
    repo = tmp_path / "R"
    repo.mkdir(exist_ok=True)
    script = (
        f". '{GATES_PS1}'; "
        f"$j = Invoke-SeamMeasurementGates -RepoRoot '{repo}' "
        f"-PythonExe '{_fake_python(tmp_path)}' {extra} 6>$null; "
        "Write-Output ('GATE_JSON=' + $j)"
    )
    done = subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "POWERSHELL_TELEMETRY_OPTOUT": "1"},
    )
    line = [x for x in done.stdout.splitlines() if x.startswith("GATE_JSON=")][-1]
    gate_json = Path(line.split("=", 1)[1])
    assert gate_json.is_file()
    return gate_json.parent


@pytest.mark.skipif(PWSH is None, reason="pwsh not installed")
def test_pwsh_probe_dir_precedence(tmp_path) -> None:
    repo = tmp_path / "R"
    launch = tmp_path / "X" / "launch"
    assert _gate_dir(tmp_path, f"-ProbeDir '{launch}'") == launch
    assert _gate_dir(tmp_path, f"-DryRun -ProbeDir '{launch}'") == launch
    assert _gate_dir(tmp_path, "-DryRun") == repo / "derived" / "_gate_probes" / "_dryrun"
    assert _gate_dir(tmp_path, "") == repo / "derived" / "_gate_probes"


@pytest.mark.skipif(PWSH is None, reason="pwsh not installed")
def test_pwsh_policy_cap_parser_with_kv() -> None:
    """-Kv and -PolicyCapUsd together get past the cap parser (dry run, no host)."""
    done = subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(TOOLS / "launch_h1.ps1"),
            "-DryRun",
            "-AllowDirty",
            "-NoCloudPing",
            "-Interleaved",
            "-InterleavedPolicies",
            "local_only",
            "-PolicyCapUsd",
            "local_only=0",
            "-SessionMaxUsd",
            "1",
            "-Placement",
            "gpu_only",
            "-Kv",
            "default",
            "-Residency",
            "RESIDENT",
            "-Entries",
            "derived/h1_hybrid/demo1/DEMO1_BASE_30.json",
            "-EntryCount",
            "2",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "POWERSHELL_TELEMETRY_OPTOUT": "1"},
    )
    out = done.stdout + done.stderr
    assert "not a valid value for the Kv variable" not in out
    assert "Mode           : INTERLEAVED" in out


@pytest.mark.skipif(PWSH is None, reason="pwsh not installed")
def test_pwsh_parses_every_tools_ps1() -> None:
    script = (
        "$bad = @(); foreach ($f in Get-ChildItem tools/*.ps1) { $t = $null; $e = $null; "
        "[void][System.Management.Automation.Language.Parser]::ParseFile("
        "$f.FullName, [ref]$t, [ref]$e); "
        "if ($e.Count -gt 0) { $bad += $f.Name } }; "
        "Write-Output ('PARSE_BAD=' + ($bad -join ','))"
    )
    done = subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    line = [x for x in done.stdout.splitlines() if x.startswith("PARSE_BAD=")][-1]
    assert line == "PARSE_BAD="
