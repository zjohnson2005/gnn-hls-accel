"""OA-01 integrity audits; flags never remove trajectories."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from apu_characterization.oa01.bundle import load_bundle
from apu_characterization.oa01.schema import ApiBoundaryRecord, ToolExecSpan, TurnRecord


def audit_trajectory(
    *,
    turns: Sequence[TurnRecord],
    api_records: Sequence[ApiBoundaryRecord],
    exec_spans: Sequence[ToolExecSpan],
    run_meta: dict[str, Any],
    bundle_path: Path,
    conservation_rel: float = 0.02,
    conservation_abs_ms: float = 1.0,
) -> dict[str, Any]:
    flags: list[str] = []
    checks: dict[str, Any] = {}

    observed_successes = int(run_meta.get("turns_observed", -1))
    retained_attempts = sum(turn.api_attempt_count for turn in turns)
    successful_turns = sum(turn.status == "ok" for turn in turns)
    call_count_ok = (
        retained_attempts == len(api_records)
        and successful_turns == observed_successes
    )
    checks["call_count_reconciliation"] = {
        "pass": call_count_ok,
        "turns": len(turns),
        "api_records": len(api_records),
        "retained_api_attempts": retained_attempts,
        "successful_turns": successful_turns,
        "run_observed": run_meta.get("turns_observed"),
    }
    if not call_count_ok:
        flags.append("call_count_reconciliation")

    residuals = []
    conservation_ok = True
    for turn in turns:
        accounted = turn.t_model_observed_ms + turn.t_tool_ms + turn.t_orch_gap_ms
        residual = abs(turn.t_turn_wall_ms - accounted)
        budget = max(conservation_abs_ms, conservation_rel * turn.t_turn_wall_ms)
        residuals.append(
            {
                "turn_index": turn.turn_index,
                "residual_ms": residual,
                "budget_ms": budget,
                "pass": residual <= budget,
            }
        )
        conservation_ok &= residual <= budget
    checks["gap_conservation"] = {"pass": conservation_ok, "turns": residuals}
    if not conservation_ok:
        flags.append("gap_conservation")

    raw_complete = all(
        bool(record.request_body_b64)
        and bool(record.response_body_b64)
        and record.response_first_body_byte_unix_ns
        <= record.response_last_body_byte_unix_ns
        for record in api_records
    )
    checks["proxy_raw_completeness"] = {"pass": raw_complete}
    if not raw_complete:
        flags.append("proxy_raw_completeness")

    success_records = [record for record in api_records if record.response_status < 400]
    usage_ok = all(
        "usage_missing" not in record.flags
        and "cached_tokens_field_missing" not in record.flags
        for record in success_records
    )
    checks["usage_and_cache_fields"] = {
        "pass": usage_ok,
        "success_records": len(success_records),
        "error_records": len(api_records) - len(success_records),
        "flagged_call_ids": [
            record.call_id
            for record in success_records
            if {"usage_missing", "cached_tokens_field_missing"} & set(record.flags)
        ],
    }
    if not usage_ok:
        flags.append("usage_and_cache_fields")

    cache_violations = [
        turn.turn_index
        for turn in turns
        if "provider_cache_reconciliation" in turn.audit_flags
    ]
    checks["provider_cache_reconciliation"] = {
        "pass": not cache_violations,
        "violating_turns": cache_violations,
        "rule": "provider_recovered <= structural + template_overhead_envelope",
    }
    if cache_violations:
        flags.append("provider_cache_reconciliation")

    tool_calls = sum(1 for turn in turns if turn.is_tool_call)
    completed_exec = [
        span
        for span in exec_spans
        if span.docker_operation == "exec" and "missing_exec_end" not in span.flags
    ]
    tool_observation_ok = tool_calls == 0 or bool(completed_exec)
    checks["tool_boundary_observation"] = {
        "pass": tool_observation_ok,
        "tool_call_turns": tool_calls,
        "completed_exec_spans": len(completed_exec),
    }
    if not tool_observation_ok:
        flags.append("tool_boundary_observation")

    try:
        bundle = load_bundle(bundle_path)
        bundle_ok = (
            bundle.get("trajectory_id") == run_meta.get("trajectory_id")
            and len(bundle.get("api_boundary_records") or []) == len(api_records)
        )
    except Exception as exc:
        bundle_ok = False
        checks["replay_bundle_error"] = f"{type(exc).__name__}: {exc}"
    checks["replay_bundle_integrity"] = {"pass": bundle_ok}
    if not bundle_ok:
        flags.append("replay_bundle_integrity")

    return {
        "schema_version": "oa01_audit_v1",
        "trajectory_id": run_meta.get("trajectory_id"),
        "pass": not flags,
        "checks": checks,
        "flags": flags,
        "retention": "trajectory retained regardless of audit result",
    }

