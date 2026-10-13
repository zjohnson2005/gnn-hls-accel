"""tools/score_p1_a5.py: exact McNemar, sealed-data totals, no amendment reads."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import score_p1_a5 as s

ROOT = Path(__file__).resolve().parents[1]


def test_mcnemar_exact_p() -> None:
    assert s.mcnemar_exact_p(0, 0) == 1.0
    assert s.mcnemar_exact_p(7, 1) == pytest.approx(0.0703125)
    assert s.mcnemar_exact_p(1, 7) == s.mcnemar_exact_p(7, 1)
    assert s.mcnemar_exact_p(13, 2) == pytest.approx(0.00738525390625)


def test_scorer_never_opens_an_amendment() -> None:
    text = (ROOT / "tools" / "score_p1_a5.py").read_text(encoding="ascii")
    assert "LOCAL_QUALITY_AMENDMENT" not in text
    assert "open(" not in text


@pytest.mark.skipif(
    not (ROOT / "derived" / "p1_quality" / f"sealed_{s.HALVES[0][1]}" / "points").is_dir(),
    reason="sealed A5 points not present",
)
def test_sealed_a5_score() -> None:
    result = s.score()
    assert [h["in_budget_passes"] for h in result["halves"]] == [8, 4]
    assert result["total"]["in_budget_passes"] == 12
    assert result["total"]["paired_vs_a0"]["a0_in_budget_passes"] == 23
    assert result["verdict"] == "MISS"
