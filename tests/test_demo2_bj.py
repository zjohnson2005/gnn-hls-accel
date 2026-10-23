"""Task BJ part A: XPS P' rows for the BF0 secondary contrasts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo2_bf0_predict as bf0  # noqa: E402
from tools import demo2_bj_pprime_predict as bj  # noqa: E402

DEMO2 = ROOT / "derived" / "h1_hybrid" / "demo2"


def test_committed_pprime_predictions_match_generator() -> None:
    doc = json.loads((DEMO2 / "DEMO2_BJ_PPRIME_PREDICTIONS.json").read_text(encoding="utf-8"))
    assert doc == json.loads(json.dumps(bj.build()))
    assert doc["runner_must_not_read_this_file"] is True
    assert set(doc["contrasts"]) == {"XPS"}
    assert set(doc["contrasts"]["XPS"]) == {"P' vs R-full", "P' vs I-4K", "P' vs C"}


def test_pprime_rows_use_bf0_model_and_bf0_unchanged() -> None:
    bf0_doc = json.loads((DEMO2 / "DEMO2_BF0_PREDICTIONS.json").read_text(encoding="utf-8"))
    assert bf0_doc == json.loads(json.dumps(bf0.build()))
    rows = bj.build()["contrasts"]["XPS"]
    # Same model: P' vs R-full and P' vs C equal BF0's own XPS "P' vs A" (same p_R and f_R).
    assert rows["P' vs R-full"] == bf0_doc["contrasts"]["XPS"]["P' vs A"]
    assert rows["P' vs C"] == bf0_doc["contrasts"]["XPS"]["P' vs A"]


def test_runner_never_reads_bj_files() -> None:
    for name in ("run_h1_hybrid.py", "launch_h1.ps1", "context_window.py"):
        text = (ROOT / "tools" / name).read_text(encoding="utf-8")
        for needle in ("DEMO2_BJ_PPRIME", "DEMO2_AMEND_2026-10-23b", "demo2_bj_pprime"):
            assert needle not in text
