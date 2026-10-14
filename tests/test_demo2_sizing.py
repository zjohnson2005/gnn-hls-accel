"""DEMO-2 sizing is reproducible from committed data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo2_sizing  # noqa: E402

OUT = ROOT / "analysis" / "demo2" / "DEMO2_SIZING_20261014.json"


def test_sizing_matches_committed_file() -> None:
    doc = demo2_sizing.sizing()
    assert json.loads(json.dumps(doc)) == json.loads(OUT.read_text(encoding="utf-8"))
    base = doc["mechanical"]["multi_turn_base_FULL"]
    assert base["control_4096"]["entry_share"] == 0.685
    assert base["tuned_XPS"]["escalated_entries"] == 0
    long_obs = doc["mechanical"]["multi_turn_long_context_OBS_MASK_K1024"]
    assert long_obs["tuned_T2S"]["entry_share"] == 0.015
    assert doc["quality_triggers"]["emission_escalate"]["entries_with_cloud_turn"] == 59


def test_design_doc_is_ascii_and_not_read_by_runner() -> None:
    doc = ROOT / "docs" / "amendments" / "DEMO2_DESIGN_2026-10-14.md"
    doc.read_text(encoding="ascii")
    runner = (ROOT / "tools" / "run_h1_hybrid.py").read_text(encoding="utf-8")
    assert "DEMO2_DESIGN" not in runner
