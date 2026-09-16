"""Tier-0 dep_refs + G-D extension (Tier-0 ⊆ Tier-C)."""

from __future__ import annotations

from apu_characterization.tlp01.dependence import (
    assert_tier0_subseteq_tier_c,
    assert_tier0_subseteq_tier_s,
    tier_0_edges,
    tier_c_edges,
    tier_s_edges,
)
from apu_characterization.tlp01.schema import validate_trace_events
from apu_characterization.tlp01.t0_audit import audit_trace_events


def _events_with_dep_ref() -> list[dict]:
    return [
        {
            "session_id": "t0-test",
            "seq": 0,
            "event_type": "turn",
            "t_issue_ns": 0,
            "t_complete_ns": 10,
            "inputs_hash": "in0",
            "output_hash": "out0",
            "output_text_ref": None,
            "tool_name": None,
            "args_ref": None,
            "result_ref": None,
            "stage_timings": {"orch_ns": 0},
            "harness_order_index": 0,
            "task_class": "MT",
            "seed": 0,
            "input_text": "goal",
            "output_text": "",
            "dep_refs": [],
        },
        {
            "session_id": "t0-test",
            "seq": 1,
            "event_type": "tool_call",
            "t_issue_ns": 10,
            "t_complete_ns": 20,
            "inputs_hash": "in1",
            "output_hash": "out1",
            "output_text_ref": "result-1",
            "tool_name": "calculator",
            "args_ref": "args-1",
            "result_ref": "result-1",
            "stage_timings": {"orch_ns": 0},
            "harness_order_index": 1,
            "task_class": "MT",
            "seed": 0,
            "result_ids": ["1"],
            "input_text": "1+1",
            "output_text": '{"value": 2}',
            "dep_refs": [],
        },
        {
            "session_id": "t0-test",
            "seq": 2,
            "event_type": "tool_call",
            "t_issue_ns": 20,
            "t_complete_ns": 30,
            "inputs_hash": "in2",
            "output_hash": "out2",
            "output_text_ref": "result-2",
            "tool_name": "calculator",
            "args_ref": "args-2",
            "result_ref": "result-2",
            "stage_timings": {"orch_ns": 0},
            "harness_order_index": 2,
            "task_class": "MT",
            "seed": 0,
            "result_ids": ["2"],
            "input_text": "add one\nfrom_result=1",
            "output_text": '{"value": 3}',
            "dep_refs": [1],
        },
    ]


def test_tier0_edges_from_dep_refs() -> None:
    events = validate_trace_events(_events_with_dep_ref())
    edges = tier_0_edges(events)
    pairs = {(e.src_seq, e.dst_seq) for e in edges}
    assert pairs == {(1, 2)}


def test_tier0_subseteq_tier_c() -> None:
    events = validate_trace_events(_events_with_dep_ref())
    assert_tier0_subseteq_tier_c(events)
    t0 = {(e.src_seq, e.dst_seq, e.kind) for e in tier_0_edges(events)}
    tc = {(e.src_seq, e.dst_seq, e.kind) for e in tier_c_edges(events)}
    assert t0.issubset(tc)


def test_tier0_subseteq_tier_s() -> None:
    events = validate_trace_events(_events_with_dep_ref())
    assert_tier0_subseteq_tier_s(events)
    t0 = {(e.src_seq, e.dst_seq, e.kind) for e in tier_0_edges(events)}
    ts = {(e.src_seq, e.dst_seq, e.kind) for e in tier_s_edges(events)}
    assert t0.issubset(ts)


def test_null_dep_refs_skip_tier0_gate() -> None:
    payload = _events_with_dep_ref()
    for row in payload:
        row["dep_refs"] = None
    events = validate_trace_events(payload)
    assert tier_0_edges(events) == set()
    assert_tier0_subseteq_tier_c(events)  # no-op


def test_t0_audit_rejects_unresolved_dep_ref() -> None:
    payload = _events_with_dep_ref()
    payload[2]["dep_refs"] = [99]
    result = audit_trace_events(payload, source="S2", task_id="MT-SER-01")
    assert result["pass"] is False
    assert any("unresolved" in e for e in result["errors"])


def test_t0_audit_multitool_min_tools() -> None:
    payload = _events_with_dep_ref()[:2]  # only one tool
    result = audit_trace_events(payload, source="S2", task_id="MT-RS-01")
    assert result["pass"] is False
    assert any("only 1 tool_call" in e for e in result["errors"])


def test_s2_session_record_maps_from_result() -> None:
    from apu_characterization.tlp01.s2_harness import session_record_to_events

    record = {
        "ok": True,
        "task_id": "MT-SER-01",
        "seed": 0,
        "prompt_sha256": "abc",
        "t_session_start_ns": 1_000_000,
        "final_text": "done",
        "tool_log": [
            {
                "tool": "calculator",
                "query": "1+1",
                "from_result": None,
                "dep_refs": [],
                "result_id": 1,
                "t_issue_ns": 1_000_010,
                "t_complete_ns": 1_000_020,
                "output": '{"v":2}',
            },
            {
                "tool": "calculator",
                "query": "prior+1",
                "from_result": 1,
                "dep_refs": [1],
                "result_id": 2,
                "t_issue_ns": 1_000_030,
                "t_complete_ns": 1_000_040,
                "output": '{"v":3}',
            },
        ],
    }
    events = session_record_to_events(record, "S2-MT-SER-01-s0")
    assert events[2]["dep_refs"] == [1]
    assert "from_result=1" in events[2]["input_text"]
    audit = audit_trace_events(events, source="S2", task_id="MT-SER-01")
    assert audit["pass"], audit["errors"]
