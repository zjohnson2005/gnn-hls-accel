from __future__ import annotations

import pytest

from apu_characterization.tlp01.extract import (
    make_synthetic_chain_session,
    make_synthetic_parallel_session,
)
from apu_characterization.tlp01.schedule import simulate_model


def test_parallel_session_has_m1a_width_and_m1b_headroom() -> None:
    events = make_synthetic_parallel_session(width=4, orch_ns=0)
    m1a_s = simulate_model(events, "M1a", "Tier_S")
    m1b_s = simulate_model(events, "M1b", "Tier_S")
    # With SC-EMIT respected, tools wait for the planning turn.
    assert m1a_s.speedup >= 1.5
    # Perfect SC break can only improve or match.
    assert m1b_s.speedup >= m1a_s.speedup


def test_chain_near_serial_under_m1a() -> None:
    events = make_synthetic_chain_session(steps=4, orch_ns=0)
    m1a = simulate_model(events, "M1a", "Tier_S")
    assert m1a.speedup < 1.5


def test_m2_not_above_m1b() -> None:
    events = make_synthetic_parallel_session(width=4, orch_ns=5_000_000)
    m1b = simulate_model(events, "M1b", "Tier_S")
    m2 = simulate_model(events, "M2", "Tier_S")
    assert m2.speedup <= m1b.speedup + 1e-9


def test_unqualified_m1_raises() -> None:
    events = make_synthetic_chain_session(steps=3)
    with pytest.raises(ValueError, match="M1a or M1b"):
        simulate_model(events, "M1", "Tier_S")
