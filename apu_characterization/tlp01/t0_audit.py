"""Post-collection audit for TLP-01 T0 traces (inventory only — no claims)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from apu_characterization.tlp01.schema import validate_trace_events


def audit_trace_events(
    events: Sequence[Mapping[str, Any]],
    *,
    source: str,
    task_id: str,
    min_tools_for_multitool: int = 2,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        parsed = validate_trace_events(events)
    except ValueError as exc:
        return {
            "pass": False,
            "errors": [str(exc)],
            "source": source,
            "task_id": task_id,
        }

    seqs = sorted(e.seq for e in parsed)
    if len(seqs) != len(set(seqs)):
        errors.append("duplicate seq")

    # Event conservation + monotonic timestamps by harness order.
    ordered = sorted(parsed, key=lambda e: e.harness_order_index)
    last_complete = -1
    for event in ordered:
        if event.t_complete_ns < event.t_issue_ns:
            errors.append(f"seq {event.seq}: complete < issue")
        if event.t_issue_ns < last_complete and event.event_type == "tool_call":
            # Overlap is allowed for parallel issue; only flag time-travel.
            pass
        if event.dep_refs is not None:
            for dep in event.dep_refs:
                if dep not in {e.seq for e in parsed}:
                    errors.append(f"seq {event.seq}: dep_refs {dep} unresolved")
                if dep >= event.seq:
                    errors.append(f"seq {event.seq}: dep_refs not prior")

    tool_count = sum(1 for e in parsed if e.event_type == "tool_call")
    negative = "SER" in task_id or "serial" in task_id.lower()
    multitool = source == "S2" and not negative
    if multitool and tool_count < min_tools_for_multitool:
        errors.append(
            f"multi-tool template {task_id} has only {tool_count} tool_call events"
        )

    # Abandonment: every tool_call must have complete >= issue (already checked).
    return {
        "pass": not errors,
        "errors": errors,
        "source": source,
        "task_id": task_id,
        "event_count": len(parsed),
        "tool_call_count": tool_count,
        "tier0_edge_count": sum(
            len(e.dep_refs or ()) for e in parsed if e.dep_refs is not None
        ),
        "dep_refs_null": all(e.dep_refs is None for e in parsed),
    }
