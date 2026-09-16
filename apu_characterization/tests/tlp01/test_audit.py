from __future__ import annotations

from apu_characterization.tlp01.audit import audit_experiment, audit_session
from apu_characterization.tlp01.extract import make_synthetic_parallel_session


def test_synthetic_session_passes_load_bearing_gates() -> None:
    sessions = [
        make_synthetic_parallel_session(session_id=f"syn-FO-s{seed}", seed=seed)
        for seed in range(5)
    ]
    audit = audit_experiment(sessions, kappa=0.7)
    assert audit["pass"]
    assert audit["gates"]["G_V"]["pass"]
    assert audit["gates"]["G_D"]["pass"]
    assert audit["gates"]["G_A"]["pass"]
    assert audit["gates"]["G_R"]["pass"]
    assert audit["tier_j_in_headline"] is True


def test_low_kappa_demotes_tier_j_but_experiment_can_pass() -> None:
    sessions = [
        make_synthetic_parallel_session(session_id=f"syn-FO-s{seed}", seed=seed)
        for seed in range(5)
    ]
    audit = audit_experiment(sessions, kappa=0.2)
    assert audit["pass"]
    assert audit["gates"]["G_J"]["pass"] is False
    assert audit["tier_j_in_headline"] is False


def test_single_session_audit_shape() -> None:
    result = audit_session(make_synthetic_parallel_session())
    assert set(result["gates"]) == {"G_V", "G_D", "G_A"}
