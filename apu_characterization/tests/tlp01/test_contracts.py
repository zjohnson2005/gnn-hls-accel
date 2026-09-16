from __future__ import annotations

from apu_characterization.tlp01.contracts import (
    FORBIDDEN_CLAIM_FRAGMENTS,
    GATE_NAMES,
    MACHINE_MODELS,
    load_protocol,
    validate_template,
)


def test_template_validates_v2() -> None:
    protocol = load_protocol()
    assert protocol["protocol_version"] == "tlp01_v2.1"
    assert not validate_template(protocol)


def test_gates_and_models_frozen() -> None:
    protocol = load_protocol()
    assert set(GATE_NAMES) <= set(protocol["gates"])
    assert set(MACHINE_MODELS) <= set(protocol["machine_models"])
    assert protocol["gates"]["G_V"]["relative_tolerance"] == 0.05
    assert protocol["gates"]["G_J"]["kappa_threshold"] == 0.6
    assert protocol["gates"]["G_R"]["required_seeds"] == 5


def test_two_track_ladder_and_no_forbidden_language() -> None:
    protocol = load_protocol()
    assert "ceiling_track" in protocol["claim_ladder"]
    assert "frontier_track" in protocol["claim_ladder"]
    affirmative = (
        str(protocol.get("claim_under_test") or "")
        + str(protocol["claim_ladder"])
    ).lower()
    for fragment in FORBIDDEN_CLAIM_FRAGMENTS:
        assert fragment not in affirmative
    assert protocol["trace_sources"]["S3"]["required_for_v1"] is False
    assert protocol["projection"]["blocked_subject_claim"] == "Praetor achieves"
    assert protocol["timer_resolution"]["sub_ms_absolute_floor_ns"] >= 5000
