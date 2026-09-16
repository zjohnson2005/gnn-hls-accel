"""Task 4 overfitting guards under edge taxonomy v2."""

from __future__ import annotations

from pathlib import Path

import pytest

from apu_characterization.tlp01.dependence import (
    assert_tier0_subseteq_tier_s,
    tier_0_edges,
    tier_s_edges,
)
from apu_characterization.tlp01.schedule import simulate_model
from apu_characterization.tlp01.schema import load_frozen_trace

REPO = Path(__file__).resolve().parents[3]
S2 = REPO / "apu_characterization/out/tlp01/traces/S2"


def _pairs(edges) -> set[tuple[int, int, str]]:
    return {(e.src_seq, e.dst_seq, e.kind) for e in edges}


@pytest.mark.skipif(not S2.is_dir(), reason="frozen S2 traces not present")
def test_tier0_subseteq_tier_s_all_ser_sessions() -> None:
    for tid in ("MT-SER-01", "MT-SER-02"):
        for seed in range(5):
            path = S2 / f"S2-{tid}-s{seed}.jsonl"
            if not path.is_file():
                continue
            events = load_frozen_trace(path)
            assert_tier0_subseteq_tier_s(events)
            assert _pairs(tier_0_edges(events)) <= _pairs(tier_s_edges(events))


@pytest.mark.skipif(not S2.is_dir(), reason="frozen S2 traces not present")
def test_ser01_m1a_near_one_m1b_matches_hide_turn() -> None:
    for seed in range(5):
        path = S2 / f"S2-MT-SER-01-s{seed}.jsonl"
        if not path.is_file():
            continue
        events = load_frozen_trace(path)
        assert simulate_model(events, "M1a", "Tier_S").speedup == pytest.approx(
            1.0, abs=0.05
        )
        assert simulate_model(events, "M1a", "Tier_C").speedup == pytest.approx(
            1.0, abs=0.05
        )


@pytest.mark.skipif(not S2.is_dir(), reason="frozen S2 traces not present")
def test_ser02_m1a_serial_m1b_is_speculation_headroom() -> None:
    path = S2 / "S2-MT-SER-02-s3.jsonl"
    if not path.is_file():
        pytest.skip("SER-02 s3 missing")
    events = load_frozen_trace(path)
    m1a = simulate_model(events, "M1a", "Tier_S")
    m1b = simulate_model(events, "M1b", "Tier_S")
    assert m1a.speedup == pytest.approx(1.0, abs=0.05)
    assert m1b.speedup > 1.2  # turn-hide headroom, not a bug


# Data-oracle pairs only (DS). Structural SC-EMIT/HO live in the assembled graph.
_REFERENCE_TS_DATA_PAIRS: dict[str, set[tuple[int, int]]] = {
    "S2-MT-FILE-01-s0": {(1, 3), (1, 4), (2, 4), (3, 4)},
    "S2-MT-RS-01-s0": set(),  # envelope exclusion removed turn→tool DS
    "S2-MT-FAN-01-s0": set(),
    "S2-MT-MIX-01-s0": {(1, 2), (1, 3)},
    "S2-MT-SER-01-s0": {(1, 2), (1, 3), (2, 3)},
    "S2-MT-SER-02-s0": {(1, 2), (2, 3)},
}


@pytest.mark.skipif(not S2.is_dir(), reason="frozen S2 traces not present")
@pytest.mark.parametrize("session_id,expected", sorted(_REFERENCE_TS_DATA_PAIRS.items()))
def test_reference_session_tier_s_data_edges(
    session_id: str, expected: set[tuple[int, int]]
) -> None:
    path = S2 / f"{session_id}.jsonl"
    if not path.is_file():
        pytest.skip(f"{session_id} missing")
    events = load_frozen_trace(path)
    got = {
        (e.src_seq, e.dst_seq)
        for e in tier_s_edges(events)
        if e.kind == "data"
    }
    assert got == expected, (
        f"{session_id}: Tier-S data edges changed {got ^ expected}; "
        "enumerate and justify before updating"
    )
