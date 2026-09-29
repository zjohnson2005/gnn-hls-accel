"""Boot-4 dry-run and the rule that measurement runners do not open the prereg files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREREG = (
    ROOT / "derived" / "delta_prefill" / "WARM_KV_PREREG.json",
    ROOT / "derived" / "delta_prefill" / "WARM_KV_AMEND_1.json",
    ROOT / "derived" / "delta_prefill" / "WARM_KV_AMEND_2.json",
    ROOT / "derived" / "c2_ttft" / "DECODE_MATCH_PREREG.json",
    ROOT / "derived" / "c2_ttft" / "DECODE_MATCH_AMEND_1.json",
    ROOT / "derived" / "q8b" / "Q_TIER_CLEAN_PREREG.json",
    ROOT / "derived" / "q8b" / "Q_TIER_CLEAN_AMEND_1.json",
    ROOT / "derived" / "q_kv" / "Q_KV_CLEAN_PREREG.json",
    ROOT / "derived" / "h1_hybrid" / "H1_CPU_PREREG.json",
    ROOT / "derived" / "h1_hybrid" / "H1_CPU_AMEND_1.json",
    ROOT / "derived" / "h1_hybrid" / "R0_CLOUD_ONLY_PREREG.json",
    ROOT / "derived" / "h1_hybrid" / "CACHE_ARM_PREREG.json",
    ROOT / "derived" / "h1_hybrid" / "LOCAL_QUALITY_PREREG.json",
)
RUNNERS = (
    "tools/run_h1_hybrid.py",
    "tools/run_c1_ceiling.py",
    "tools/run_det_probe.py",
    "tools/run_q_8b_quality.py",
    "tools/run_q_kv_quality.py",
    "tools/run_warm_kv.py",
    "tools/run_decode_match.py",
)


def test_prereg_files_exist_and_runners_do_not_name_them() -> None:
    names = [path.name for path in PREREG]
    for path in PREREG:
        assert path.is_file()
        doc_text = path.read_text(encoding="utf-8")
        assert "runner_must_not_read_this_file" in doc_text
    for rel in RUNNERS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for name in names:
            assert name not in text, rel


def test_boot4_dry_run() -> None:
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-File",
            str(ROOT / "tools" / "launch_boot4.ps1"),
            "-DryRun",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    for name in (
        "DRY_RUN_OK WARM-KV f16",
        "DRY_RUN_OK WARM-KV u8",
        "DRY_RUN_OK WARM-KV u4",
        "DRY_RUN_OK DECODE-MATCH",
    ):
        assert name in proc.stdout
    assert "run_warm_kv.py" in proc.stdout
    assert "run_decode_match.py" in proc.stdout
    assert "--n 2000,4000,8000" in proc.stdout
    assert "boot4_estimate_sum_s=4644" in proc.stdout
    assert "fits_one_window=true" in proc.stdout
    assert "smoke_planned WARM-KV f16" in proc.stdout
    assert "smoke_planned DECODE-MATCH" in proc.stdout
    assert "--smoke" in proc.stdout
