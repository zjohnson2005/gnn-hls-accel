"""Boot clean-tree rule and the ceiling Status read that crashed boot 1."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.boot_tree_check import classify_porcelain  # noqa: E402

ANCHOR_SUMMARY = (
    ROOT / "derived" / "c2_ttft" / "c2246b1f-c588-4998-838a-5507da87e9ee" / "summary.json"
)


def test_modified_tracked_and_untracked_code_block() -> None:
    verdict = classify_porcelain(
        [
            " M tools/launch_boot1.ps1",
            "?? tools/new_helper.py",
            "?? tests/test_boot_tree_and_ceiling_result.py",
            "?? configs/extra.yaml",
            "?? seam/extra.py",
            "?? derived/c2_ttft/c2246b1f-c588-4998-838a-5507da87e9ee/summary.json",
            "?? derived/h1_hybrid/det_probe_cb9773be-71a7-4cc8-b9ff-f7b18e5231f8/plan.json",
        ]
    )
    assert len(verdict["blocked"]) == 5
    assert verdict["untracked_derived"] == [
        "derived/c2_ttft/c2246b1f-c588-4998-838a-5507da87e9ee/summary.json",
        "derived/h1_hybrid/det_probe_cb9773be-71a7-4cc8-b9ff-f7b18e5231f8/plan.json",
    ]


def test_untracked_derived_alone_does_not_block() -> None:
    verdict = classify_porcelain(
        ["?? derived/c2_ttft/sealed_c2246b1f-c588-4998-838a-5507da87e9ee/.sealed"]
    )
    assert verdict["blocked"] == []
    assert verdict["untracked_derived"]


def test_boot2_estimates_add_measured_canary_overhead() -> None:
    text = (ROOT / "tools" / "launch_boot1.ps1").read_text(encoding="utf-8")
    boot2 = text.split("Boot 2: estimate = base_s + canary_overhead_s.", 1)[1]
    boot2 = boot2.split("} else {", 1)[0]
    names = [
        'Name = "XPS 8B-int4 GPU u8"',
        'Name = "XPS 4B-int8 GPU u8"',
        'Name = "DET-PROBE-KV"',
        'Name = "XPS 4B-int4 CPU u8"',
    ]
    positions = [boot2.index(name) for name in names]
    assert positions == sorted(positions)
    overhead = 944.242457 - 192.1065557
    assert overhead == pytest.approx(752.1359013)
    ceilings = {
        "XPS 8B-int4 GPU u8": 315 + overhead,
        "XPS 4B-int8 GPU u8": 338 + overhead,
        "DET-PROBE-KV": 840.522023,
        "XPS 4B-int4 CPU u8": 2010 + overhead,
    }
    for name, raw in ceilings.items():
        assert f'Name = "{name}"' in boot2
        assert f"EstimateS = {int(__import__('math').ceil(raw))}" in boot2


def test_boot3_dry_run_covers_each_cell_type() -> None:
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-File",
            str(ROOT / "tools" / "launch_boot3.ps1"),
            "-DryRun",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    for name in (
        "DRY_RUN_OK XPS 4B-int8 GPU u8",
        "DRY_RUN_OK DET-PROBE-KV",
        "DRY_RUN_OK XPS 4B-int4 CPU u8",
    ):
        assert name in proc.stdout
    assert "--arms gpu_only_u8" in proc.stdout
    assert "--arms A" in proc.stdout
    assert "run_det_probe.py --arm gpu_only_f16" in proc.stdout
    assert "expect_kv=u8" in proc.stdout
    assert "expect_kv=" in proc.stdout


def test_shared_extraction_smoke_path_is_refused() -> None:
    from tools.c2_extraction_smoke import main

    with pytest.raises(SystemExit, match="cell run dir"):
        main(["--out", str(ROOT / "derived" / "c2_ttft" / "_extraction_smoke")])


def test_det_probe_kv_prereg_is_not_named_by_runners() -> None:
    name = "DET_PROBE_KV_PREREG.json"
    assert (ROOT / "derived" / "h1_hybrid" / name).is_file()
    for rel in ("tools/run_det_probe.py", "tools/run_c1_ceiling.py"):
        assert name not in (ROOT / rel).read_text(encoding="utf-8")


def test_ceiling_status_from_c2246b1f_summary() -> None:
    assert ANCHOR_SUMMARY.is_file()
    summary = json.loads(ANCHOR_SUMMARY.read_text(encoding="utf-8"))
    stdout = [
        "session_id c2246b1f-c588-4998-838a-5507da87e9ee",
        f"status {summary['status']}",
        "ttft_limit gpu_only_u8 10000",
    ]
    script = ROOT / "tools" / "boot_cell_result.ps1"
    command = (
        f". '{script}'; "
        f"$ran = Get-BootCeilingResult -SummaryPath '{ANCHOR_SUMMARY}' "
        f"-Stdout @({','.join(repr(line) for line in stdout)}) "
        "-ExitCode 0 -RunId 'c2246b1f-c588-4998-838a-5507da87e9ee'; "
        'if ($ran -isnot [pscustomobject]) { throw "result is $($ran.GetType().FullName)" }; '
        "Write-Output $ran.Status; "
        "Write-Output $ran.RunId"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    assert lines[-2] == "complete"
    assert lines[-1] == "c2246b1f-c588-4998-838a-5507da87e9ee"


def test_boot_summary_appends_cells_and_drops_nameless() -> None:
    script = ROOT / "tools" / "boot_cell_result.ps1"
    command = (
        f". '{script}'; "
        "$prior = @("
        "  [pscustomobject]@{ name = 'int8'; status = 'complete' }, "
        "  [pscustomobject]@{ normalized = 'u8' }, "
        "  [pscustomobject]@{ name = 'det'; status = 'complete' }"
        "); "
        "$added = @([pscustomobject]@{ name = 'cpu'; status = 'complete' }); "
        "$merged = @(Merge-BootCells -Prior $prior -Added $added); "
        "($merged | ForEach-Object { $_.name }) -join ','"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == "int8,det,cpu"
    text = (ROOT / "tools" / "launch_boot1.ps1").read_text(encoding="utf-8")
    assert "$rows" not in text
    assert "Merge-BootCells" in text
