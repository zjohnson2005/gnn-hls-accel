from __future__ import annotations

from apu_characterization.tlp01.extract import make_synthetic_parallel_session
from apu_characterization.tlp01.labels import DATA_SOURCE_REAL, DATA_SOURCE_SYNTHETIC
from apu_characterization.tlp01.phase_diagram import (
    render_phase_diagram_markdown,
    select_frontier_rung,
    sweep_phase_diagram,
    write_phase_diagram_artifact,
)


def test_phase_diagram_sweep_produces_regions(tmp_path) -> None:
    sessions = [
        make_synthetic_parallel_session(
            session_id=f"syn-FO-s{seed}", seed=seed, width=4
        )
        for seed in range(5)
    ]
    phase = sweep_phase_diagram(sessions)
    assert phase["policies"]
    assert phase["optimal_by_penalty_accuracy"]
    assert "10ms_software" in phase["penalties_ns"]
    assert "20us_praetor_tier_d" in phase["penalties_ns"]
    assert phase["praetor_label"]
    path = write_phase_diagram_artifact(phase, tmp_path / "m4_predictor")
    assert path.is_file()
    md = "\n".join(render_phase_diagram_markdown(phase))
    assert "phase diagram" in md.lower()
    assert "Tier D" in md
    assert "rung_" not in md


def test_frontier_smoke_uses_diagnostic_not_rung() -> None:
    sessions = [
        make_synthetic_parallel_session(
            session_id=f"syn-FO-s{seed}", seed=seed, width=4
        )
        for seed in range(5)
    ]
    phase = sweep_phase_diagram(sessions)
    claim = select_frontier_rung(phase, data_source=DATA_SOURCE_SYNTHETIC)
    assert claim["rung"] is None
    assert claim["smoke_diagnostic"].startswith("smoke_diagnostic:")


def test_frontier_real_source_keeps_rung() -> None:
    sessions = [
        make_synthetic_parallel_session(
            session_id=f"syn-FO-s{seed}", seed=seed, width=4
        )
        for seed in range(5)
    ]
    phase = sweep_phase_diagram(sessions)
    claim = select_frontier_rung(phase, data_source=DATA_SOURCE_REAL)
    assert claim["rung"] in {"rung_1b", "rung_2b", "rung_3b"}
