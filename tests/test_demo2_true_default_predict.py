"""tools/demo2_true_default_predict.py: sealed-data predictions for the DEMO-2 redesign."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import demo2_true_default_predict as tdp  # noqa: E402

COMMITTED = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_AMEND_TRUE_DEFAULT_PREDICTIONS.json"


def test_rebuild_matches_committed_file() -> None:
    doc = tdp.build()
    text = json.dumps(doc, indent=2) + "\n"
    assert text == COMMITTED.read_text(encoding="ascii")


def test_registered_sha256() -> None:
    digest = hashlib.sha256(COMMITTED.read_bytes()).hexdigest()
    amend = (ROOT / "docs" / "amendments" / "DEMO2_AMEND_2026-10-16_TRUE_DEFAULT.md").read_text(
        encoding="utf-8"
    )
    assert digest in amend


def test_d_carries_registered_band_and_a_has_no_window() -> None:
    doc = json.loads(COMMITTED.read_text(encoding="ascii"))
    prereg = json.loads(tdp.PREREG.read_text(encoding="utf-8"))
    reg = prereg["predictions"]["per_cell"]["D-X"]
    for bound in ("lo", "point", "hi"):
        assert doc["D_X2_prediction_of_record"][bound] == reg[bound]
        assert doc["per_cell_usd"]["A-X"][bound]["triggers"]["window"] is None
        assert doc["per_cell_usd"]["A-T"][bound]["triggers"]["memory_limit"] is None
    assert doc["caps_usd"]["D-X2"] == round(1.5 * reg["hi"]["usd_total"], 2)


def test_proxy_reproduces_sealed_cells() -> None:
    px = tdp.proxy()
    assert px["XPS"]["FULL"]["usd_per_task"] == 0.308
    assert px["XPS"]["OBS_MASK_K1024"]["usd_per_task"] == 0.184
    assert px["T2S"]["FULL"]["usd_per_task"] == 0.096
    assert px["T2S"]["OBS_MASK_K1024"]["usd_per_task"] == 0.013


def test_first_trigger_rules() -> None:
    turns = [
        {"n_ctx": 4000, "max_step_prompt_tokens": 4500},
        {"n_ctx": 12000, "max_step_prompt_tokens": 12500},
        {"n_ctx": 21000, "max_step_prompt_tokens": 21000},
    ]
    a_xps = tdp.triggers("XPS", "A", "point")
    assert tdp.first_trigger(turns, a_xps, every_turn=False) == 2  # memory limit 20,000
    assert tdp.first_trigger(turns, a_xps, every_turn=True) == 1  # warm edge counted
    d_xps = tdp.triggers("XPS", "D", "point")
    assert tdp.first_trigger(turns, d_xps, every_turn=False) == 0  # 4096 window
    a_t2s = tdp.triggers("T2S", "A", "point")
    assert tdp.first_trigger(turns, a_t2s, every_turn=True) == 2  # edge 18,500
