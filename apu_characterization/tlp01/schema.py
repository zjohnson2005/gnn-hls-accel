"""Trace schema validation and hashing for TLP-01 Phase T0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from apu_characterization.tlp01.contracts import (
    TRACE_SCHEMA_VERSION,
    TraceEvent,
    canonical_json_bytes,
    load_protocol,
    sha256_bytes,
    sha256_json,
)


def validate_event_dict(value: Mapping[str, Any]) -> TraceEvent:
    return TraceEvent.from_dict(value)


def validate_trace_events(events: Sequence[Mapping[str, Any]]) -> list[TraceEvent]:
    if not events:
        raise ValueError("trace must contain at least one event")
    parsed = [validate_event_dict(event) for event in events]
    session_ids = {event.session_id for event in parsed}
    if len(session_ids) != 1:
        raise ValueError(f"trace must be single-session, got {sorted(session_ids)}")
    seqs = [event.seq for event in parsed]
    if len(seqs) != len(set(seqs)):
        raise ValueError("trace seq values must be unique")
    orders = [event.harness_order_index for event in parsed]
    if len(orders) != len(set(orders)):
        raise ValueError("harness_order_index values must be unique")
    return sorted(parsed, key=lambda event: event.harness_order_index)


def recorded_makespan_ns(events: Sequence[TraceEvent]) -> int:
    if not events:
        return 0
    return max(event.t_complete_ns for event in events) - min(
        event.t_issue_ns for event in events
    )


def trace_sha256(events: Sequence[TraceEvent] | Sequence[Mapping[str, Any]]) -> str:
    if events and isinstance(events[0], TraceEvent):
        payload = [
            {
                "session_id": event.session_id,
                "seq": event.seq,
                "event_type": event.event_type,
                "t_issue_ns": event.t_issue_ns,
                "t_complete_ns": event.t_complete_ns,
                "inputs_hash": event.inputs_hash,
                "output_hash": event.output_hash,
                "output_text_ref": event.output_text_ref,
                "tool_name": event.tool_name,
                "args_ref": event.args_ref,
                "result_ref": event.result_ref,
                "stage_timings": dict(event.stage_timings),
                "harness_order_index": event.harness_order_index,
                "dep_refs": (
                    None if event.dep_refs is None else list(event.dep_refs)
                ),
            }
            for event in events  # type: ignore[union-attr]
        ]
    else:
        payload = list(events)  # type: ignore[arg-type]
    return sha256_json(payload)


def write_frozen_trace(
    events: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    content_store: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    parsed = validate_trace_events(events)
    if path.exists():
        raise FileExistsError(f"trace already frozen at {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "session_id": event.session_id,
                "seq": event.seq,
                "event_type": event.event_type,
                "t_issue_ns": event.t_issue_ns,
                "t_complete_ns": event.t_complete_ns,
                "inputs_hash": event.inputs_hash,
                "output_hash": event.output_hash,
                "output_text_ref": event.output_text_ref,
                "tool_name": event.tool_name,
                "args_ref": event.args_ref,
                "result_ref": event.result_ref,
                "stage_timings": dict(event.stage_timings),
                "harness_order_index": event.harness_order_index,
                "task_class": event.task_class,
                "seed": event.seed,
                "control_parent_seq": event.control_parent_seq,
                "produced_paths": list(event.produced_paths),
                "result_ids": list(event.result_ids),
                "input_text": event.input_text,
                "output_text": event.output_text,
                "dep_refs": (
                    None if event.dep_refs is None else list(event.dep_refs)
                ),
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        for event in parsed
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    digest = sha256_bytes(path.read_bytes())
    meta = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "session_id": parsed[0].session_id,
        "event_count": len(parsed),
        "trace_sha256": digest,
        "recorded_makespan_ns": recorded_makespan_ns(parsed),
        "protocol_trace_schema_sha256": sha256_json(
            load_protocol()["trace_schema"]
        ),
    }
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta_path.write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if content_store is not None:
        store_path = path.with_suffix(path.suffix + ".content.json")
        store_path.write_bytes(canonical_json_bytes(dict(content_store)))
    return meta


def load_frozen_trace(path: Path) -> list[TraceEvent]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return validate_trace_events(events)


def assert_schema_matches_protocol(
    events: Iterable[TraceEvent] | Sequence[Mapping[str, Any]],
) -> None:
    protocol = load_protocol()
    schema = protocol["trace_schema"]
    if schema["version"] != TRACE_SCHEMA_VERSION:
        raise ValueError("protocol/schema version drift")
    validate_trace_events(
        [
            event
            if isinstance(event, Mapping)
            else {
                "session_id": event.session_id,
                "seq": event.seq,
                "event_type": event.event_type,
                "t_issue_ns": event.t_issue_ns,
                "t_complete_ns": event.t_complete_ns,
                "inputs_hash": event.inputs_hash,
                "output_hash": event.output_hash,
                "output_text_ref": event.output_text_ref,
                "tool_name": event.tool_name,
                "args_ref": event.args_ref,
                "result_ref": event.result_ref,
                "stage_timings": dict(event.stage_timings),
                "harness_order_index": event.harness_order_index,
                "dep_refs": (
                    None if event.dep_refs is None else list(event.dep_refs)
                ),
            }
            for event in events
        ]
    )
