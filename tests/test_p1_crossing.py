"""B=10 crossing score (amendments 8 and 9) is reproducible from sealed runs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import score_p1_crossing as spc  # noqa: E402

OUT = ROOT / "derived" / "p1_quality" / "analysis" / "CROSSING_B10_20261014.json"


def test_exact_binomial() -> None:
    assert spc.exact_binomial_two_sided(0, 0) == 1.0
    assert spc.exact_binomial_two_sided(2, 1) == 1.0
    assert abs(spc.exact_binomial_two_sided(0, 6) - 0.03125) < 1e-12
    assert abs(spc.exact_binomial_two_sided(1, 8) - 0.0390625) < 1e-12


def test_b10_score_matches_committed_file() -> None:
    doc = spc.score(10)
    assert doc == json.loads(OUT.read_text(encoding="utf-8"))
    assert doc["a0"]["in_budget_passes"] == 14 and doc["a4"]["in_budget_passes"] == 13
    assert doc["mcnemar"] == {
        "b_a0_pass_a4_fail": 2,
        "c_a0_fail_a4_pass": 1,
        "p_two_sided_exact": 1.0,
    }
    assert doc["crossing_at_b"] is False
    assert doc["sweep_floor"]["holds"] is False
    assert (
        doc["close_fraction"]["closed_and_parsed"] == 92
        and doc["close_fraction"]["a4_steps"] == 789
    )
    assert "eb6cd6ce-ad9f-4b61-898d-bde9585a56cb" in doc["not_used"]
