from __future__ import annotations

from apu_characterization.tlp01.analyze import (
    analyze_experiment,
    bracket_line,
    select_claim_rung,
    speedup_bands,
)
from apu_characterization.tlp01.extract import (
    make_synthetic_chain_session,
    make_synthetic_parallel_session,
)
from apu_characterization.tlp01.labels import DATA_SOURCE_REAL, DATA_SOURCE_SYNTHETIC


def test_bracket_line_never_a_point() -> None:
    text = bracket_line(4.0, 2.5)
    assert "2.50x" in text and "4.00x" in text
    assert "Tier-C" in text and "Tier-S" in text


def test_parallel_sessions_smoke_diagnostic_not_rung() -> None:
    sessions = [
        make_synthetic_parallel_session(
            session_id=f"syn-FO-s{seed}", seed=seed, width=4, orch_ns=0
        )
        for seed in range(5)
    ]
    bands = speedup_bands(sessions, model="M1a")
    claim = select_claim_rung(bands, data_source=DATA_SOURCE_SYNTHETIC)
    assert claim["rung"] is None
    assert "taxonomy_shape" in claim["smoke_diagnostic"] or "tlp_exists" in claim[
        "smoke_diagnostic"
    ]


def test_real_source_selects_ceiling_rung() -> None:
    sessions = [
        make_synthetic_parallel_session(
            session_id=f"syn-FO-s{seed}", seed=seed, width=4, orch_ns=0
        )
        for seed in range(5)
    ]
    bands = speedup_bands(sessions, model="M1a")
    claim = select_claim_rung(bands, data_source=DATA_SOURCE_REAL)
    assert claim["rung"] in {"rung_1a", "rung_2a"}


def test_chain_only_smoke_diagnostics_present() -> None:
    sessions = [
        make_synthetic_chain_session(
            session_id=f"syn-CN-s{seed}", seed=seed, steps=4, orch_ns=0
        )
        for seed in range(5)
    ]
    aggregate = analyze_experiment(
        sessions, data_source=DATA_SOURCE_SYNTHETIC
    )
    assert aggregate["headline_form"] == "S_C_bracket_never_point"
    assert aggregate["ceiling_claim"]["rung"] is None
    assert aggregate["frontier_claim"]["rung"] is None
    assert "smoke_diagnostic:" in aggregate["ceiling_claim"]["smoke_diagnostic"]
    assert "smoke_diagnostic:" in aggregate["frontier_claim"]["smoke_diagnostic"]
    assert "phase_diagram" in aggregate
