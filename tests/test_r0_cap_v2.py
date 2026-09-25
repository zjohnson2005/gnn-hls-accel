"""R0 cap v2 resamples entries. The H1 runner does not open the cap file."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.r0_cap_v2 import bootstrap_cap  # noqa: E402


def _entry(eid: str, turns: list[dict]) -> dict:
    return {"entry_id": eid, "turns": turns}


def test_bootstrap_uses_full_sample_mean_when_a_depth_is_missing() -> None:
    ledgers = {
        "slo_escalate": [
            _entry(
                "a",
                [
                    {"turn": 0, "placement": "local"},
                    {"turn": 1, "placement": "cloud", "cloud_usd": 2.0},
                ],
            ),
            _entry(
                "b",
                [
                    {"turn": 0, "placement": "cloud", "cloud_usd": 10.0},
                    {"turn": 1, "placement": "local"},
                ],
            ),
        ],
        "emission_escalate": [],
        "full_signal_bounceback": [],
    }
    doc = bootstrap_cap(ledgers, n_draws=200, seed=1)
    assert doc["n_escalated_entries"] == 2
    assert doc["cap_usd"] >= min(doc["expected_usd_draw_mean"], 12.0)
    assert doc["n_depth_fallbacks_to_full_sample_mean"] >= 0
    text = (ROOT / "tools" / "run_h1_hybrid.py").read_text(encoding="utf-8")
    assert "R0_CAP_V2.json" not in text
    assert "R0_CAP.json" not in text
