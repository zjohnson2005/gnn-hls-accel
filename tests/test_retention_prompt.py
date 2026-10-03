"""SEM-IMPL builder. Fixture labels only. The runner does not open a prereg."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.retention_prompt import RetentionError, build_cell, semantic_prompt  # noqa: E402
from tools.retention_smoke import main  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "retention_labels.json"
SOURCE = "alpha beta GAMMA delta epsilon"


def test_semantic_prompt_uses_document_order_and_inserts_nothing() -> None:
    prompt = semantic_prompt(SOURCE, [(17, 30), (0, 11)])
    assert prompt == SOURCE[0:11] + SOURCE[17:30]
    assert prompt == "alpha beta delta epsilon"
    assert "GAMMA" not in prompt
    assert "..." not in prompt
    assert "[omitted]" not in prompt


def test_resident_count_must_equal_the_positional_budget() -> None:
    with pytest.raises(RetentionError, match="positional budget"):
        build_cell(
            source=SOURCE,
            spans=[(0, 11), (17, 30)],
            positional_budget_tokens=9,
            observations=["one two three"],
            obs_mask_k=1,
        )


def test_obs_mask_records_k_and_adds_no_marker() -> None:
    built = build_cell(
        source=SOURCE,
        spans=[(0, 11), (17, 30)],
        positional_budget_tokens=4,
        observations=["one two three four", "solo"],
        obs_mask_k=2,
    )
    assert built["semantic_tokens"] == 4
    assert built["positional_budget_tokens"] == 4
    assert built["obs_mask_k"] == 2
    assert built["obs_mask"] == ["one two", "solo"]
    assert all("..." not in str(item) for item in built["obs_mask"])


def test_overlapping_span_is_refused() -> None:
    with pytest.raises(RetentionError):
        semantic_prompt(SOURCE, [(0, 11), (10, 16)])


def test_runner_source_does_not_name_a_prereg_and_refuses_one(tmp_path: Path) -> None:
    text = (ROOT / "tools" / "retention_smoke.py").read_text(encoding="utf-8")
    assert "PREREG.json" not in text
    assert "derived/" not in text
    banned = tmp_path / "CELL_PREREG.json"
    banned.write_text("{}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="does not read prereg"):
        main(["--fixture", str(banned)])


def test_cpu_smoke_on_the_fixture() -> None:
    assert main(["--fixture", str(FIXTURE)]) == 0
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    built = build_cell(
        source=doc["source"],
        spans=[(int(a), int(b)) for a, b in doc["required_spans"]],
        positional_budget_tokens=int(doc["positional_budget_tokens"]),
        observations=doc["observations"],
        obs_mask_k=int(doc["obs_mask_k"]),
    )
    assert built["semantic_prompt"] == "alpha beta delta epsilon"
    assert built["semantic_tokens"] == int(doc["positional_budget_tokens"])
