"""tools/score_p1_sweep_a0.py on the sealed sweep A0 B=10 boot."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import score_p1_sweep_a0 as s

ROOT = Path(__file__).resolve().parents[1]
RUN = "bdc32a87-8f91-4cd5-9cb0-2daafe659fc8"


def test_scorer_opens_no_amendment() -> None:
    text = (ROOT / "tools" / "score_p1_sweep_a0.py").read_text(encoding="ascii")
    assert "LOCAL_QUALITY_AMENDMENT" not in text and "open(" not in text


@pytest.mark.skipif(
    not (ROOT / "derived" / "p1_quality" / f"sealed_{RUN}" / "points").is_dir(),
    reason="sealed sweep points not present",
)
def test_sweep_a0_b10_first_half() -> None:
    result = s.score(RUN)
    assert result["entries"] == "lexicographic [0:100]"
    assert result["budget_s"] == 10.0
    assert result["in_budget_passes"] == result["in_budget_passes_summary"] == 14
    assert result["reference"]["in_budget_passes_same_entries"] == 14
    assert result["determinism"]["in_budget_pass_agree"] == 100
    assert result["a4_b10_floor"]["value"] == 14
