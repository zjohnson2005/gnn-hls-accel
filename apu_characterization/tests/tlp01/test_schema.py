from __future__ import annotations

import pytest

from apu_characterization.tlp01.extract import make_synthetic_parallel_session
from apu_characterization.tlp01.schema import (
    recorded_makespan_ns,
    trace_sha256,
    validate_trace_events,
    write_frozen_trace,
)


def test_validate_and_hash_stable() -> None:
    events = make_synthetic_parallel_session()
    assert len(events) >= 3
    digest = trace_sha256(events)
    assert len(digest) == 64
    assert digest == trace_sha256(events)


def test_frozen_trace_is_immutable(tmp_path) -> None:
    events = make_synthetic_parallel_session()
    path = tmp_path / "session.jsonl"
    payload = [
        {
            "session_id": e.session_id,
            "seq": e.seq,
            "event_type": e.event_type,
            "t_issue_ns": e.t_issue_ns,
            "t_complete_ns": e.t_complete_ns,
            "inputs_hash": e.inputs_hash,
            "output_hash": e.output_hash,
            "output_text_ref": e.output_text_ref,
            "tool_name": e.tool_name,
            "args_ref": e.args_ref,
            "result_ref": e.result_ref,
            "stage_timings": dict(e.stage_timings),
            "harness_order_index": e.harness_order_index,
            "task_class": e.task_class,
            "seed": e.seed,
            "control_parent_seq": e.control_parent_seq,
            "produced_paths": list(e.produced_paths),
            "result_ids": list(e.result_ids),
            "input_text": e.input_text,
            "output_text": e.output_text,
            "dep_refs": None if e.dep_refs is None else list(e.dep_refs),
        }
        for e in events
    ]
    meta = write_frozen_trace(payload, path)
    assert meta["event_count"] == len(events)
    assert recorded_makespan_ns(events) == meta["recorded_makespan_ns"]
    with pytest.raises(FileExistsError):
        write_frozen_trace(payload, path)


def test_rejects_duplicate_seq() -> None:
    events = make_synthetic_parallel_session()
    payload = [
        {
            "session_id": e.session_id,
            "seq": 0,
            "event_type": e.event_type,
            "t_issue_ns": e.t_issue_ns,
            "t_complete_ns": e.t_complete_ns,
            "inputs_hash": e.inputs_hash,
            "output_hash": e.output_hash,
            "output_text_ref": e.output_text_ref,
            "tool_name": e.tool_name,
            "args_ref": e.args_ref,
            "result_ref": e.result_ref,
            "stage_timings": dict(e.stage_timings),
            "harness_order_index": e.harness_order_index,
            "dep_refs": [],
        }
        for e in events[:2]
    ]
    with pytest.raises(ValueError, match="unique"):
        validate_trace_events(payload)
