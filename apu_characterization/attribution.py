"""ORCH measured vs reconcile attribution helpers."""

from __future__ import annotations

from typing import Any

ORCH_CATEGORIES = ("ORCH_SETUP", "ORCH_DISPATCH")


def orch_total_from_session_categories(categories: dict[str, Any]) -> int:
    return sum(categories.get(name, {}).get("cpu_ns", 0) for name in ORCH_CATEGORIES)


def split_session_orch_after_reconcile(
    orch_measured_before_ns: int,
    reconcile_added_ns: int,
    orch_total_final_ns: int,
) -> tuple[int, int]:
    """Attribute final session ORCH between measured step residual and reconcile gap."""
    if reconcile_added_ns <= 0 or orch_total_final_ns <= 0:
        return orch_total_final_ns, 0
    denom = orch_measured_before_ns + reconcile_added_ns
    if denom <= 0:
        return 0, orch_total_final_ns
    reconcile_ns = int(orch_total_final_ns * reconcile_added_ns / denom)
    return orch_total_final_ns - reconcile_ns, reconcile_ns


def backfill_session_orch_fields(
    session: dict[str, Any],
    per_session_category: dict[str, Any],
) -> bool:
    """Fill orch_measured_cpu_ns / orch_reconcile_cpu_ns on legacy session rows."""
    if session.get("orch_measured_cpu_ns") is not None and session.get(
        "orch_reconcile_cpu_ns"
    ) is not None:
        return False

    sid = session.get("session_id", "")
    cats = per_session_category.get(sid, {})
    orch_total_final = orch_total_from_session_categories(cats)
    reconcile_added = max(0, int(session.get("reconcile_cpu_ns", 0)))
    measured_before = max(0, orch_total_final - reconcile_added)
    measured, reconcile = split_session_orch_after_reconcile(
        measured_before, reconcile_added, orch_total_final
    )
    session["orch_measured_cpu_ns"] = measured
    session["orch_reconcile_cpu_ns"] = reconcile
    return True
