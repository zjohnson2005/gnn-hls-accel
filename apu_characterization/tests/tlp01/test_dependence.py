from __future__ import annotations

from apu_characterization.tlp01.dependence import (
    assert_bracket_invariant,
    disagreement_pairs,
    tier_c_edges,
    tier_s_edges,
)
from apu_characterization.tlp01.extract import (
    make_synthetic_chain_session,
    make_synthetic_parallel_session,
)


def test_bracket_invariant_on_parallel_and_chain() -> None:
    for factory in (make_synthetic_parallel_session, make_synthetic_chain_session):
        events = factory()
        assert_bracket_invariant(events)
        s = {(e.src_seq, e.dst_seq, e.kind) for e in tier_s_edges(events)}
        c = {(e.src_seq, e.dst_seq, e.kind) for e in tier_c_edges(events)}
        assert s.issubset(c)


def test_chain_has_syntactic_data_edges() -> None:
    events = make_synthetic_chain_session(steps=4)
    data_s = [e for e in tier_s_edges(events) if e.kind == "data"]
    assert data_s, "producer-consumer chain must create Tier-S data edges"


def test_parallel_tools_disagree_or_stay_sparse() -> None:
    events = make_synthetic_parallel_session(width=4)
    # Independent tool bodies should not all be Tier-S linked to each other.
    s_data = {
        (e.src_seq, e.dst_seq)
        for e in tier_s_edges(events)
        if e.kind == "data" and e.src_seq >= 1 and e.dst_seq >= 1
    }
    assert len(s_data) == 0
    # Tier-C may overcount via adjacency; disagreement is allowed data.
    assert isinstance(disagreement_pairs(events), list)
