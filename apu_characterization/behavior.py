"""Behavioral buckets from realized session observables (not task labels)."""

from __future__ import annotations

from typing import Any


def _total_tool_calls(counts: dict[str, int]) -> int:
    return sum(counts.values())


def classify_session_behavior(session: dict[str, Any]) -> str:
    """Assign one behavioral bucket from observables after the run."""
    counts = session.get("tool_call_counts") or {}
    turns = session.get("turns", 0)
    n_tools = _total_tool_calls(counts)
    has_search = counts.get("search", 0) > 0
    has_code = counts.get("code_exec", 0) > 0
    has_retrieve = counts.get("retrieve", 0) > 0

    if n_tools == 0:
        return "B0_io_only"
    if has_code and counts.get("code_exec", 0) >= 5:
        return "B4_code_burst"
    if has_search and not has_code and not has_retrieve:
        return "B1_search_only"
    if has_search and (has_code or has_retrieve):
        return "B2_mixed_tools"
    if has_retrieve and counts.get("retrieve", 0) >= 5:
        return "B3_retrieve_heavy"
    if has_retrieve:
        return "B3_retrieve_light"
    if has_code:
        return "B4_code_light"
    if turns <= 2:
        return "B0_short"
    return "B5_other"


BEHAVIOR_LABELS: dict[str, str] = {
    "B0_io_only": "no tool calls (LLM-only)",
    "B0_short": "short session, few turns",
    "B1_search_only": "search only (no local code/retrieve)",
    "B2_mixed_tools": "search plus code and/or retrieve",
    "B3_retrieve_heavy": "retrieve-heavy (≥5 calls)",
    "B3_retrieve_light": "retrieve-light (<5 calls)",
    "B4_code_burst": "code_exec burst (≥5 calls)",
    "B4_code_light": "code_exec light (<5 calls)",
    "B5_other": "other tool mix",
}


def summarize_behavior_buckets(
    per_session: list[dict[str, Any]],
    per_task: dict[str, Any],
    *,
    cpu_floor_ms: float = 200.0,
) -> dict[str, Any]:
    """Group sessions by behavioral bucket; amenability only above cpu_floor."""
    buckets: dict[str, list[str]] = {}
    session_meta: dict[str, dict[str, Any]] = {}

    for s in per_session:
        tid = s.get("task_id", "unknown")
        bid = classify_session_behavior(s)
        buckets.setdefault(bid, []).append(tid)
        session_meta[tid] = {
            "behavior_bucket": bid,
            "behavior_label": BEHAVIOR_LABELS.get(bid, bid),
            "task_label": tid.split("-")[0] if tid else "?",
            "turns": s.get("turns"),
            "tool_call_counts": s.get("tool_call_counts", {}),
            "host_cpu_ms": s.get("process_cpu_ns", 0) / 1e6,
            "above_cpu_floor": (s.get("process_cpu_ns", 0) / 1e6) >= cpu_floor_ms,
        }

    bucket_stats: dict[str, Any] = {}
    for bid, task_ids in sorted(buckets.items()):
        cpus = [session_meta[t]["host_cpu_ms"] for t in task_ids]
        strict = []
        broad = []
        for t in task_ids:
            if t in per_task:
                strict.append(per_task[t]["amenable_strict_share"])
                broad.append(per_task[t]["amenable_broad_share"])
        bucket_stats[bid] = {
            "label": BEHAVIOR_LABELS.get(bid, bid),
            "tasks": task_ids,
            "task_labels": sorted({session_meta[t]["task_label"] for t in task_ids}),
            "mean_host_cpu_ms": sum(cpus) / len(cpus) if cpus else 0,
            "mean_amenable_strict": sum(strict) / len(strict) if strict else None,
            "mean_amenable_broad": sum(broad) / len(broad) if broad else None,
        }

    return {
        "session_meta": session_meta,
        "buckets": bucket_stats,
        "cpu_floor_ms": cpu_floor_ms,
        "note": (
            "Buckets are assigned from realized tool calls and turn count, "
            "not from task archetype labels. Task-label tables are prompt-intent only."
        ),
    }
