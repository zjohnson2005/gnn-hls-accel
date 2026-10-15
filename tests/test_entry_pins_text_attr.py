"""Every runtime-pinned entry file must be checked out byte for byte (-text).

ENTRY_PINS paths are hashed at launch (assert_entry_set_pinned). Without
-text, a core.autocrlf=true Windows checkout rewrites LF to CRLF and the sha256
no longer matches (DEMO-2 rehearsal be91e69d, 2026-10-14).
The W-3 default entries file is pinned to its CRLF checkout form and has no
ENTRY_PINS path; it is not covered here.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_h1_hybrid import ENTRY_PINS  # noqa: E402


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_every_entry_pin_path_is_minus_text() -> None:
    paths = [p["path"] for p in ENTRY_PINS.values() if p.get("path")]
    assert "derived/h1_hybrid/demo2/DEMO2_HELDOUT_60.json" in paths
    for path in paths:
        out = subprocess.run(
            ["git", "check-attr", "text", path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert out.endswith("text: unset"), out
