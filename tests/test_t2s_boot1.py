"""T2S boot-1 dry-run stays report-only and does not open the prereg."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LAUNCHER = ROOT / "tools" / "launch_t2s_boot1.ps1"
SEQUENCER = ROOT / "tools" / "launch_boot1.ps1"


def test_t2s_launcher_does_not_name_the_prereg() -> None:
    for path in (LAUNCHER, SEQUENCER):
        text = path.read_text(encoding="utf-8")
        assert "PARITY_REMEASURE_PREREG.json" not in text


def test_t2s_boot1_dry_run() -> None:
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-File",
            str(LAUNCHER),
            "-DryRun",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    for name in (
        "platform_id=evo-t2",
        "battery_present=false",
        "free_memory_floor_mb=24000",
        "onset_s=null",
        "canary_onset_s=657",
        "provenance=borrowed",
        "DRY_RUN_OK T2S 4B-int4 GPU u8",
        "DRY_RUN_OK T2S 8B-int4 GPU u8",
        "gpu_only_u8",
        "--low 14000",
        "--high 26000",
        "Qwen3-4B-int4-ov.yaml",
        "Qwen3-8B-int4-ov.yaml",
    ):
        assert name in out, name
    assert "--allow-unguarded" not in out
