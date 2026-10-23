"""Task BL: CC amendment predictions (DERIVED) match their generator and leave BJ's untouched."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import cc_bl_predict as bl  # noqa: E402
from tools import cc_predict as cc  # noqa: E402

CC_DIR = ROOT / "derived" / "cc"


def test_committed_bl_predictions_match_generator() -> None:
    doc = json.loads((CC_DIR / "CC_BL_PREDICTIONS.json").read_text(encoding="utf-8"))
    assert doc == json.loads(json.dumps(bl.build()))
    assert doc["runner_must_not_read_this_file"] is True


def test_bj_predictions_unchanged() -> None:
    doc = json.loads((CC_DIR / "CC_PREDICTIONS.json").read_text(encoding="utf-8"))
    assert doc == json.loads(json.dumps(cc.build()))
    assert doc["xps_resident_limits"]["u4:c256"]["point"] == 63319


def test_hypotheses_fit_both_sealed_limits() -> None:
    c, budget = bl.h_quad()
    for p in ("f16", "u4"):
        n = cc.SEALED_XPS[p][0]
        assert abs(n * cc.K_KV[p] + c * n * n - budget) < 1.0
    assert round(bl.act_limit("f16", 256)) == 24676
    assert round(bl.act_limit("u4", 256)) == 87736


def test_t2s_concurrency_steps() -> None:
    conc = bl.build()["t2s"]["conc"]
    assert conc["ii_dynamic_cap256_fails_at_N"] == 10
    assert conc["i_unbounded_simultaneous_fails_at_N"] == 6
    assert conc["iii_fixed_40GiB_cap256_preemption_from_N"] == 9


def test_runners_never_read_bl_files() -> None:
    for name in ("run_resident_limit.py", "boot4_session.py", "run_h1_hybrid.py"):
        text = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert "CC_BL_PREDICTIONS" not in text
