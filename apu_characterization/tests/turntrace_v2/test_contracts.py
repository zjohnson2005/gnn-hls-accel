from __future__ import annotations

from apu_characterization.turntrace_v2.contracts import (
    FORBIDDEN_CLAIM_FRAGMENTS,
    PROTOCOL_VERSION,
    load_protocol,
    validate_protocol,
)


def test_protocol_loads_and_validates() -> None:
    protocol = load_protocol()
    assert protocol["protocol_version"] == PROTOCOL_VERSION
    assert protocol["revision"] == "B"
    assert not validate_protocol(protocol)


def test_locked_step_unit_and_replay_mandatory() -> None:
    protocol = load_protocol()
    assert protocol["locked_decisions"]["step_unit"] == "one_model_call_equals_one_step"
    assert protocol["replay_bundle"]["mandatory_for_headline"] is True
    assert "retemplated_tokens" in protocol["call_record_required_fields"]
    assert "replay_bundle_path" in protocol["trajectory_record_required_fields"]


def test_no_forbidden_fragments_in_claim() -> None:
    protocol = load_protocol()
    text = str(protocol.get("claim_under_test") or "").lower()
    for fragment in FORBIDDEN_CLAIM_FRAGMENTS:
        assert fragment not in text
