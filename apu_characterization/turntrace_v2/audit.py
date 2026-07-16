"""Audit gates for TurnTrace v2 CallRecords."""

from __future__ import annotations

from typing import Callable, Sequence

from apu_characterization.turntrace_v2.contracts import load_protocol
from apu_characterization.turntrace_v2.schema import CallRecord

PrefillFn = Callable[[int], float]


def conservation_residual_ms(record: CallRecord) -> float:
    accounted = (
        record.t_orch_pre_ms
        + record.t_prefill_ms
        + record.t_decode_ms
        + record.t_network_ms
        + record.t_orch_post_ms
    )
    wall = max(0.0, (record.wall_clock_end - record.wall_clock_start) * 1000.0)
    return abs(wall - accounted)


def conservation_budget_ms(record: CallRecord) -> float:
    protocol = load_protocol()
    gates = protocol["audit_gates"]
    wall_ms = max(0.0, (record.wall_clock_end - record.wall_clock_start) * 1000.0)
    return max(float(gates["conservation_abs_ms"]), float(gates["conservation_rel"]) * wall_ms)


def check_conservation(record: CallRecord) -> str | None:
    if conservation_residual_ms(record) > conservation_budget_ms(record):
        return "residual_exceeds_budget"
    return None


def check_domain_coverage(
    record: CallRecord,
    *,
    grid_min: int | None,
    grid_max: int | None,
) -> str | None:
    """F1: never silently attribute outside the fitted profile domain."""
    if grid_min is None or grid_max is None:
        return None
    n = record.engine_tokens_in
    if n < grid_min or n > grid_max:
        return "attribution_out_of_domain"
    return None


def check_profile_consistency(
    record: CallRecord,
    f_prefill: PrefillFn,
    *,
    cache_disabled_only: bool = True,
    grid_min: int | None = None,
    grid_max: int | None = None,
) -> str | None:
    if cache_disabled_only and record.cache_state != "disabled":
        return None
    # Out-of-domain calls are flagged separately; do not also pile on profile_drift.
    if grid_min is not None and grid_max is not None:
        if record.engine_tokens_in < grid_min or record.engine_tokens_in > grid_max:
            return None
    protocol = load_protocol()
    tol = float(protocol["audit_gates"]["profile_consistency_rel"])
    expected = float(f_prefill(record.engine_tokens_in))
    if expected <= 0:
        return "profile_drift" if record.t_prefill_ms > 0 else None
    rel = abs(record.t_prefill_ms - expected) / expected
    if rel > tol:
        return "profile_drift"
    return None


def check_cache_state(
    record: CallRecord,
    f_prefill: PrefillFn,
    *,
    tol_rel: float | None = None,
) -> str | None:
    """Claimed prefix hits must be consistent with observed prefill within profile bars."""
    protocol = load_protocol()
    tol = float(tol_rel if tol_rel is not None else protocol["audit_gates"]["profile_consistency_rel"])
    if record.prefix_hit_tokens > record.engine_tokens_in:
        return "token_accounting_anomaly"
    if record.cache_state in ("cold", "disabled"):
        if record.prefix_hit_tokens != 0:
            return "cache_state_unverified"
        return None
    effective = max(0, record.engine_tokens_in - record.prefix_hit_tokens)
    expected = float(f_prefill(effective))
    if expected <= 0:
        return None
    if abs(record.t_prefill_ms - expected) / expected > tol:
        return "cache_state_unverified"
    return None


def check_token_reconciliation(
    record: CallRecord,
    *,
    delta_lo: float | None = None,
    delta_hi: float | None = None,
) -> str | None:
    """F3: reconciliation delta must lie in the calibrated template-overhead envelope."""
    if delta_lo is None or delta_hi is None:
        return None
    delta = float(record.token_reconciliation_delta)
    if delta < delta_lo or delta > delta_hi:
        return "token_accounting_anomaly"
    return None


def audit_call_record(
    record: CallRecord,
    *,
    f_prefill: PrefillFn | None = None,
    token_count_local: int | None = None,
    token_count_api: int | None = None,
    power_mode_changed: bool = False,
    grid_min: int | None = None,
    grid_max: int | None = None,
    token_delta_lo: float | None = None,
    token_delta_hi: float | None = None,
) -> list[str]:
    flags = list(record.audit_flags)
    for flag in (
        check_conservation(record),
        check_domain_coverage(record, grid_min=grid_min, grid_max=grid_max),
        check_token_reconciliation(record, delta_lo=token_delta_lo, delta_hi=token_delta_hi),
    ):
        if flag and flag not in flags:
            flags.append(flag)
    if f_prefill is not None:
        for flag in (
            check_profile_consistency(
                record, f_prefill, grid_min=grid_min, grid_max=grid_max
            ),
            check_cache_state(record, f_prefill),
        ):
            if flag and flag not in flags:
                flags.append(flag)
    if (
        token_count_local is not None
        and token_count_api is not None
        and token_count_local != token_count_api
    ):
        if "token_count_mismatch" not in flags:
            flags.append("token_count_mismatch")
    if power_mode_changed and "power_mode_changed" not in flags:
        flags.append("power_mode_changed")
    # Mirror attribution's within-band clamp: only flag when under-prediction
    # exceeds the profile-consistency tolerance.
    if (
        record.t_prefill_redundant_ms == 0.0
        and record.t_prefill_ms < record.t_prefill_necessary_ms
    ):
        nec = float(record.t_prefill_necessary_ms)
        under_rel = (nec - float(record.t_prefill_ms)) / nec if nec > 0 else 0.0
        tol = float(load_protocol()["audit_gates"]["profile_consistency_rel"])
        if under_rel > tol and "negative_prefill_residual" not in flags:
            flags.append("negative_prefill_residual")
    record.audit_flags = flags
    return flags


def headline_eligible(records: Sequence[CallRecord]) -> list[CallRecord]:
    blocked = {
        "residual_exceeds_budget",
        "profile_drift",
        "cache_state_unverified",
        "power_mode_changed",
        "missing_replay_bundle",
        "attribution_out_of_domain",
        "token_accounting_anomaly",
        "implausible_cold_sample",
    }
    return [r for r in records if not (blocked & set(r.audit_flags))]


def in_domain(record: CallRecord, *, grid_min: int, grid_max: int) -> bool:
    return grid_min <= record.engine_tokens_in <= grid_max
