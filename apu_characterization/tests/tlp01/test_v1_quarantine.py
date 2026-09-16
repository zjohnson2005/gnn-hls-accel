"""Tests for G-V1-QUARANTINE promotion gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
QUARANTINE = REPO / "apu_characterization/tools/check_tlp01_v1_quarantine.py"


def test_v1_quarantine_passes_on_repo() -> None:
    # Closeout artifacts must exist before this test (gate builds them first).
    build = REPO / "apu_characterization/tools/build_tlp01_closeout.py"
    if build.is_file():
        subprocess.run(
            [sys.executable, str(build)],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        )
    proc = subprocess.run(
        [sys.executable, str(QUARANTINE)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_v1_quarantine_detects_forbidden_source_line() -> None:
    from apu_characterization.tools import check_tlp01_v1_quarantine as mod

    bad = REPO / "apu_characterization/out/tlp01/t2/_test_v1_bad.md"
    bad.write_text(
        "Aggregate t1_index a45e88c2 used as frozen input for bands.\n",
        encoding="utf-8",
    )
    try:
        errors = mod.check_file(bad)
        assert errors, "expected v1 hash cited as source to fail"
    finally:
        if bad.is_file():
            bad.unlink()
