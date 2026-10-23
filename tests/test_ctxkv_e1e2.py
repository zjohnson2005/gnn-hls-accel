"""Task BH: CTXKV-E1E2 predictions (DERIVED) match their generator; formula identities."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import ctxkv_e1e2_predict as e1e2  # noqa: E402


def test_committed_predictions_match_generator() -> None:
    path = ROOT / "derived" / "ctxkv" / "CTXKV_E1E2_PREDICTIONS.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc == json.loads(json.dumps(e1e2.build()))
    assert doc["runner_must_not_read_this_file"] is True


def test_e1e2_identities() -> None:
    assert e1e2.f_need(0.58, 0.95, 0.85) == pytest.approx(0.27 / 0.37)
    assert e1e2.f_need(0.887, 0.95, 0.85) == 0.0
    assert e1e2.f_need(0.5, 0.80, 0.85) == float("inf")
    assert e1e2.kv_gib("qwen3:8b", 40_960, "f16") == pytest.approx(5.625)
    r, x1 = e1e2.e2_cost(214.8), e1e2.e2_cost(75.4)
    assert r["usd_per_session_active_hour_basis"] == pytest.approx(1.31, abs=0.01)
    assert x1["usd_per_session_active_hour_basis"] == pytest.approx(0.46, abs=0.01)


def test_runner_never_reads_the_registration() -> None:
    for name in ("run_h1_hybrid.py", "launch_h1.ps1", "context_window.py"):
        text = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert "CTXKV_E1E2" not in text
