from __future__ import annotations

from apu_characterization.turntrace_v2.labeling import (
    RawTurnEvent,
    label_trajectory,
    validate_taxonomy,
)


def test_label_trajectory_mechanism_and_semantic() -> None:
    events = [
        RawTurnEvent(0, ("read_file",), None, None, expected_horizon=4),
        RawTurnEvent(1, ("edit_file",), None, None, expected_horizon=4),
        RawTurnEvent(2, ("run_tests",), None, None, expected_horizon=4),
        RawTurnEvent(3, ("edit_file",), None, None, expected_horizon=4),
    ]
    labeled = label_trajectory(events)
    assert labeled[0][0] == "read_file"
    assert labeled[0][1].tool_class == "read_only"
    assert labeled[1][1].tool_class == "state_mutating"
    assert labeled[0][1].is_tool_call is True
    assert labeled[3][1].repeat_count == 2


def test_fanout_siblings_not_separate_steps() -> None:
    events = [
        RawTurnEvent(0, ("read_file", "grep"), None, None, expected_horizon=1),
    ]
    labeled = label_trajectory(events)
    assert len(labeled) == 1
    assert labeled[0][1].fanout_siblings == 1
    assert labeled[0][0] == "read_file+grep"


def test_taxonomy_validation_runs() -> None:
    events = [
        RawTurnEvent(0, ("read_file",), None, None, expected_horizon=3),
        RawTurnEvent(1, ("edit_file",), None, None, expected_horizon=3),
        RawTurnEvent(2, ("run_tests",), None, None, expected_horizon=3),
    ]
    labeled = label_trajectory(events)
    traj = [(sem, feat, "ok") for sem, feat in labeled]
    report = validate_taxonomy([traj, traj], min_support=2)
    assert 0.0 <= report.agreement_rate <= 1.0
    assert report.assigned_types
