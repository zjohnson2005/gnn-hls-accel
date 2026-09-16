"""Phase T0 extraction helpers: synthesize or adapt session records into traces."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from apu_characterization.tlp01.contracts import TraceEvent
from apu_characterization.tlp01.schema import validate_trace_events


def _task_class_from_id(task_id: str) -> str:
    if not task_id:
        return "UNKNOWN"
    prefix = task_id.split("-", 1)[0]
    return prefix or task_id


def extract_from_replication_session(
    session: Mapping[str, Any],
    *,
    session_id: str | None = None,
) -> list[TraceEvent]:
    """Best-effort extraction from a TurnTrace replication session record.

    The standing replication JSON is not yet a frozen TLP trace; this adapter
    projects available fields into the TLP schema for S1 bootstrap. Missing
    content fields remain empty so Tier-S stays conservative.
    """
    sid = session_id or str(
        session.get("session_id")
        or session.get("run_id")
        or f"{session.get('task_id', 'task')}-s{session.get('seed', 0)}"
    )
    task_id = str(session.get("task_id") or "")
    seed = int(session.get("seed") or 0)
    sequence = list(session.get("tool_call_sequence") or [])
    events: list[dict[str, Any]] = []
    cursor_ns = 0
    # One synthetic turn node, then one tool_call node per recorded call.
    turn_dur = int(float(session.get("wall_s") or 0.0) * 1e9) // max(len(sequence), 1)
    turn_dur = max(turn_dur, 1_000_000)
    events.append(
        {
            "session_id": sid,
            "seq": 0,
            "event_type": "turn",
            "t_issue_ns": cursor_ns,
            "t_complete_ns": cursor_ns + turn_dur,
            "inputs_hash": "turn-0",
            "output_hash": "turn-0-out",
            "output_text_ref": None,
            "tool_name": None,
            "args_ref": None,
            "result_ref": None,
            "stage_timings": {
                "orch_ns": int(session.get("orch_measured_cpu_ns") or 0)
                // max(len(sequence), 1)
            },
            "harness_order_index": 0,
            "task_class": _task_class_from_id(task_id),
            "seed": seed,
            "control_parent_seq": None,
            "input_text": str(session.get("goal") or ""),
            "output_text": "",
            # S1: Tier-0 absent (null) — not empty-list independence.
            "dep_refs": None,
        }
    )
    cursor_ns += turn_dur
    for index, call in enumerate(sequence, start=1):
        tool = str(call.get("tool") or call.get("name") or "tool")
        query = str(call.get("query") or call.get("args") or "")
        dur = max(turn_dur // 2, 1_000_000)
        events.append(
            {
                "session_id": sid,
                "seq": index,
                "event_type": "tool_call",
                "t_issue_ns": cursor_ns,
                "t_complete_ns": cursor_ns + dur,
                "inputs_hash": f"tool-{index}-in",
                "output_hash": f"tool-{index}-out",
                "output_text_ref": f"result-{index}",
                "tool_name": tool,
                "args_ref": f"args-{index}",
                "result_ref": f"result-{index}",
                "stage_timings": {"orch_ns": 0},
                "harness_order_index": index,
                "task_class": _task_class_from_id(task_id),
                "seed": seed,
                "control_parent_seq": 0,
                "result_ids": [f"result-{index}"],
                "input_text": query,
                "output_text": query,
                "dep_refs": None,
            }
        )
        cursor_ns += dur
    return validate_trace_events(events)


def make_synthetic_parallel_session(
    *,
    session_id: str = "syn-FO-01-s0",
    task_class: str = "FO",
    seed: int = 0,
    width: int = 4,
    unit_ns: int = 10_000_000,
    orch_ns: int = 5_000_000,
) -> list[TraceEvent]:
    """Construct a session with one turn spawning `width` independent tool calls.

    Used by unit tests and the gate contract to exercise T1/T2 without live data.
    """
    events: list[dict[str, Any]] = [
        {
            "session_id": session_id,
            "seq": 0,
            "event_type": "turn",
            "t_issue_ns": 0,
            "t_complete_ns": unit_ns,
            "inputs_hash": "goal",
            "output_hash": "plan",
            "output_text_ref": "plan",
            "tool_name": None,
            "args_ref": None,
            "result_ref": None,
            "stage_timings": {"orch_ns": orch_ns},
            "harness_order_index": 0,
            "task_class": task_class,
            "seed": seed,
            "input_text": "compare sources",
            "output_text": "call independent tools",
            "dep_refs": [],
        }
    ]
    cursor = unit_ns
    for index in range(1, width + 1):
        events.append(
            {
                "session_id": session_id,
                "seq": index,
                "event_type": "tool_call",
                "t_issue_ns": cursor,
                "t_complete_ns": cursor + unit_ns,
                "inputs_hash": f"in-{index}",
                "output_hash": f"out-{index}",
                "output_text_ref": f"out-{index}",
                "tool_name": f"source{index}.search",
                "args_ref": f"args-{index}",
                "result_ref": f"result-{index}",
                "stage_timings": {"orch_ns": orch_ns},
                "harness_order_index": index,
                "task_class": task_class,
                "seed": seed,
                "control_parent_seq": 0,
                "result_ids": [f"RID-{index}"],
                "input_text": f"query for unique topic {index} alpha",
                "output_text": f"unique topic {index} alpha payload",
                "dep_refs": [],
            }
        )
        cursor += unit_ns
    # Final turn consumes nothing shared — independent of tool outputs under Tier-S
    # when using distinct tokens; Tier-C may still over-connect via adjacency.
    events.append(
        {
            "session_id": session_id,
            "seq": width + 1,
            "event_type": "turn",
            "t_issue_ns": cursor,
            "t_complete_ns": cursor + unit_ns,
            "inputs_hash": "final",
            "output_hash": "answer",
            "output_text_ref": "answer",
            "tool_name": None,
            "args_ref": None,
            "result_ref": None,
            "stage_timings": {"orch_ns": orch_ns},
            "harness_order_index": width + 1,
            "task_class": task_class,
            "seed": seed,
            "control_parent_seq": 0,
            "input_text": "summarize without quoting",
            "output_text": "final answer",
            "dep_refs": [],
        }
    )
    return validate_trace_events(events)


def make_synthetic_chain_session(
    *,
    session_id: str = "syn-CN-01-s0",
    task_class: str = "CN",
    seed: int = 0,
    steps: int = 4,
    unit_ns: int = 10_000_000,
    orch_ns: int = 5_000_000,
) -> list[TraceEvent]:
    """Serial producer→consumer chain (low TLP under both tiers)."""
    events: list[dict[str, Any]] = []
    cursor = 0
    token = "CHAINTOKEN"
    for index in range(steps):
        output_text = f"{token}-{index}"
        prev_rid = f"RID-{index - 1}"
        prev_path = f"/tmp/chain-{index - 1}.txt"
        # Consumer must literally mention prior output / id / path so Tier-S
        # creates data edges (M1 breaks control edges).
        consumer_input = (
            "start"
            if index == 0
            else f"use {token} id={prev_rid} path={prev_path}"
        )
        events.append(
            {
                "session_id": session_id,
                "seq": index,
                "event_type": "tool_call" if index else "turn",
                "t_issue_ns": cursor,
                "t_complete_ns": cursor + unit_ns,
                "inputs_hash": f"in-{index}",
                "output_hash": f"out-{index}",
                "output_text_ref": f"out-{index}",
                "tool_name": f"pipe.step{index}" if index else None,
                "args_ref": f"args-{index}",
                "result_ref": f"result-{index}",
                "stage_timings": {"orch_ns": orch_ns},
                "harness_order_index": index,
                "task_class": task_class,
                "seed": seed,
                "control_parent_seq": index - 1 if index else None,
                "result_ids": [f"RID-{index}"],
                "produced_paths": [f"/tmp/chain-{index}.txt"],
                "input_text": consumer_input,
                "output_text": output_text,
                "dep_refs": [index - 1] if index else [],
            }
        )
        token = output_text
        cursor += unit_ns
    return validate_trace_events(events)
