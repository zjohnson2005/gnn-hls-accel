"""DEMO-2 draft prereg generator: deterministic, within the $150 ceiling."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo2_predict  # noqa: E402


def test_draft_is_deterministic_and_within_ceiling() -> None:
    a, b = demo2_predict.draft(), demo2_predict.draft()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert set(a["cells"]) == {"D-X", "T-X", "D-T", "T-T"}
    assert a["spend"]["caps_sum_usd"] <= 150.0
    assert "DEFERRED" in a["ablations"]
    assert a["profiles"]["control"]["kv"].startswith("READBACK_PENDING")
    assert a["profiles"]["control"]["context_window"] == 4096
    assert a["status"].startswith("DRAFT")
    for cell in a["predictions"]["per_cell"].values():
        assert (
            cell["lo"]["usd_per_task"]
            <= cell["point"]["usd_per_task"]
            <= cell["hi"]["usd_per_task"]
        )


def test_runner_never_reads_the_prereg() -> None:
    for name in ("run_h1_hybrid.py", "launch_h1.ps1", "context_window.py"):
        assert "DEMO2_PREREG" not in (ROOT / "tools" / name).read_text(encoding="utf-8")
