"""Task BJ: CC predictions (DERIVED) match their generator; runners never read them."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import cc_predict as cc  # noqa: E402


def test_committed_predictions_match_generator() -> None:
    path = ROOT / "derived" / "cc" / "CC_PREDICTIONS.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc == json.loads(json.dumps(cc.build()))
    assert doc["runner_must_not_read_this_file"] is True


def test_pair_fit_reproduces_the_sealed_limits() -> None:
    for (a, b), (c, budget) in zip(
        (("f16", "u4"), ("f16", "u8"), ("u8", "u4")),
        (cc.pair_fit("f16", "u4"), cc.pair_fit("f16", "u8"), cc.pair_fit("u8", "u4")),
        strict=True,
    ):
        for p in (a, b):
            assert abs(cc.SEALED_XPS[p][0] * (cc.K_KV[p] + c) - budget) < 1.0


def test_cap_lifts_u4_more_than_f16_and_t2s_window_binds() -> None:
    doc = cc.build()
    lim = doc["xps_resident_limits"]
    assert lim["u4:c256"]["point"] > lim["u4:unl_explicit"]["point"] * 2
    assert doc["xps_ratios"]["c256_u4_over_f16"]["band"][1] <= 3.6
    assert doc["t2s"]["holds_at_40960_every_arm"] is True


def test_runners_never_read_cc_files() -> None:
    for name in ("run_resident_limit.py", "boot4_session.py", "run_h1_hybrid.py"):
        text = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert "CC_PREDICTIONS" not in text
        assert "derived/cc" not in text
