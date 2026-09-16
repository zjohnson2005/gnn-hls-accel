from __future__ import annotations

import json

import pytest

from apu_characterization.tlp01.analyze import analyze_experiment
from apu_characterization.tlp01.extract import make_synthetic_parallel_session
from apu_characterization.tlp01.labels import (
    DATA_SOURCE_REAL,
    DATA_SOURCE_SYNTHETIC,
    audit_g_smoke_label,
    finalize_claim_label,
)


def _synthetic_sessions():
    return [
        make_synthetic_parallel_session(
            session_id=f"syn-FO-s{seed}", seed=seed, width=4
        )
        for seed in range(5)
    ]


def test_synthetic_analyze_emits_smoke_diagnostics_not_rungs() -> None:
    aggregate = analyze_experiment(
        _synthetic_sessions(), data_source=DATA_SOURCE_SYNTHETIC
    )
    assert aggregate["data_source"] == DATA_SOURCE_SYNTHETIC
    assert aggregate["ceiling_claim"]["rung"] is None
    assert aggregate["frontier_claim"]["rung"] is None
    assert str(aggregate["ceiling_claim"]["smoke_diagnostic"]).startswith(
        "smoke_diagnostic:"
    )
    assert str(aggregate["frontier_claim"]["smoke_diagnostic"]).startswith(
        "smoke_diagnostic:"
    )
    gate = audit_g_smoke_label(aggregate)
    assert gate["pass"], gate["errors"]


def test_real_source_keeps_rung_labels() -> None:
    claim = finalize_claim_label(
        {
            "rung": "rung_2a",
            "name": "taxonomy",
            "language": "TLP taxonomy",
            "criterion": "x",
        },
        data_source=DATA_SOURCE_REAL,
    )
    assert claim["rung"] == "rung_2a"
    assert claim["smoke_diagnostic"] is None


def test_g_smoke_label_fails_when_rung_attached_to_smoke() -> None:
    """Negative test: G-SMOKE-LABEL must catch rung_* on non-real data."""
    bad = {
        "data_source": DATA_SOURCE_SYNTHETIC,
        "ceiling_claim": {
            "rung": "rung_2a",
            "smoke_diagnostic": None,
            "name": "taxonomy",
        },
        "frontier_claim": {
            "rung": "rung_1b",
            "smoke_diagnostic": "smoke_diagnostic: boundary_detected_in_synthetic_surface",
            "name": "boundary",
        },
    }
    gate = audit_g_smoke_label(bad)
    assert gate["pass"] is False
    assert gate["errors"]
    assert "rung_2a" in json.dumps(gate) or any(
        "rung" in err for err in gate["errors"]
    )


def test_g_smoke_label_negative_raises_in_runner_contract() -> None:
    """Constructed failure must be detectable before publication."""
    aggregate = analyze_experiment(
        _synthetic_sessions(), data_source=DATA_SOURCE_SYNTHETIC
    )
    # Poison a published field the way a regression would.
    aggregate["ceiling_claim"]["rung"] = "rung_2a"
    gate = audit_g_smoke_label(aggregate)
    assert not gate["pass"]
    with pytest.raises(RuntimeError, match="G-SMOKE-LABEL"):
        if not gate["pass"]:
            raise RuntimeError(
                "G-SMOKE-LABEL FAILED: " + "; ".join(gate["errors"])
            )
