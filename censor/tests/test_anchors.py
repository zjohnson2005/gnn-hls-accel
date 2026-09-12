"""Anchor gate tests.

Each anchor is a test: does our model reproduce the published measurement within
tolerance, with NO parameters fitted to that anchor? A failing anchor BLOCKS
any finding in that regime.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from censor.anchors import (
    eval_A_BATCH_A100,
    eval_A_BATCH_HERALD_8K,
    eval_A_BATCH_HERALD_32K,
    eval_A_CACHE_TIERS,
    eval_A_ENERGY_CLOUD,
    eval_A_ENERGY_LOCAL,
    eval_A_ENERGY_RATIO,
    run_all_anchors,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "characterization" / "v2"


def _assert_gate(result) -> None:
    assert result.fitted_params == "NONE", (
        f"{result.anchor_id}: fitted_params must be NONE, got {result.fitted_params!r}"
    )
    assert result.passed, (
        f"{result.anchor_id} FAILED: predicted={result.predicted} "
        f"published={result.published} disagreement={result.disagreement:.3f}x "
        f"tolerance={result.tolerance} — {result.notes}"
    )


def test_A_BATCH_A100() -> None:
    _assert_gate(eval_A_BATCH_A100())


def test_A_BATCH_HERALD_8K() -> None:
    _assert_gate(eval_A_BATCH_HERALD_8K())


def test_A_BATCH_HERALD_32K() -> None:
    _assert_gate(eval_A_BATCH_HERALD_32K())


def test_A_ENERGY_LOCAL() -> None:
    _assert_gate(eval_A_ENERGY_LOCAL())


def test_A_ENERGY_CLOUD() -> None:
    _assert_gate(eval_A_ENERGY_CLOUD())


def test_A_ENERGY_RATIO() -> None:
    _assert_gate(eval_A_ENERGY_RATIO())


def test_A_CACHE_TIERS() -> None:
    _assert_gate(eval_A_CACHE_TIERS())


def test_write_anchors_csv() -> None:
    """Side-effect test: materialise anchors.csv for the v2 artifact bundle."""
    OUT.mkdir(parents=True, exist_ok=True)
    results = run_all_anchors()
    path = OUT / "anchors.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "anchor_id", "passed", "predicted", "published", "tolerance",
                "disagreement", "unit", "fitted_params", "citation", "notes",
            ],
        )
        w.writeheader()
        for r in results:
            w.writerow({
                "anchor_id": r.anchor_id,
                "passed": r.passed,
                "predicted": r.predicted,
                "published": r.published,
                "tolerance": r.tolerance,
                "disagreement": r.disagreement,
                "unit": r.unit,
                "fitted_params": r.fitted_params,
                "citation": r.citation,
                "notes": r.notes,
            })
    assert path.is_file()
    assert all(r.fitted_params == "NONE" for r in results)
