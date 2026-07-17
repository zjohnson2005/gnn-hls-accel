"""Audit gates for TurnTrace v2 CallRecords."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Sequence

from apu_characterization.turntrace_v2.contracts import (
    canonical_json_bytes,
    load_protocol,
    sha256_bytes,
)
from apu_characterization.turntrace_v2.schema import CallRecord, TrajectoryRecord
from apu_characterization.turntrace_v2.replay import ReplayBundle

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
    # Cloud ttft_derived prefills are not comparable to a local f(n) grid.
    if record.prefill_method == "ttft_derived":
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
    # Non-positive f(effective) cannot verify a warm claim; fail closed.
    if expected <= 0:
        return "cache_state_unverified"
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


def check_provider_cache_reconciliation(record: CallRecord) -> str | None:
    """OA-01 three-way cache split with provider block-quantization envelope."""
    if record.structurally_redundant_tokens > record.engine_tokens_in:
        return "provider_cache_reconciliation"
    observed_template_delta = max(0, record.token_reconciliation_delta)
    envelope = max(256, observed_template_delta + 32)
    if (
        record.provider_cached_tokens
        > record.structurally_redundant_tokens + envelope
    ):
        return "provider_cache_reconciliation"
    expected = max(
        0, record.structurally_redundant_tokens - record.provider_cached_tokens
    )
    if record.actually_recomputed_tokens != expected:
        return "provider_cache_reconciliation"
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
        check_provider_cache_reconciliation(record),
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
        "pair_context_divergence",
        "append_discipline_violated",
        "quality_parity_failed",
        "provider_cache_reconciliation",
        "pair_missing",
        "cache_truth_unverified",
    }
    return [r for r in records if not (blocked & set(r.audit_flags))]


def in_domain(record: CallRecord, *, grid_min: int, grid_max: int) -> bool:
    return grid_min <= record.engine_tokens_in <= grid_max


@dataclass
class PairAuditResult:
    pair_id: str
    causal_class: str
    passed: bool
    flags: list[str] = field(default_factory=list)
    n_turns_a: int = 0
    n_turns_b: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _flag_records(records: Sequence[CallRecord], flag: str) -> None:
    for record in records:
        if flag not in record.audit_flags:
            record.audit_flags.append(flag)


def audit_pair(
    calls_a: Sequence[CallRecord],
    calls_b: Sequence[CallRecord],
    *,
    trajectory_a: TrajectoryRecord,
    trajectory_b: TrajectoryRecord,
    causal_class: str,
    bundle_a: ReplayBundle | None = None,
    bundle_b: ReplayBundle | None = None,
) -> PairAuditResult:
    """G-PAIR + G-PARITY for one baseline/optimized trajectory pair."""
    flags: list[str] = []
    pair_id = trajectory_a.pair_id or trajectory_b.pair_id
    if (
        not pair_id
        or trajectory_a.pair_id != trajectory_b.pair_id
        or any(record.pair_id != pair_id for record in [*calls_a, *calls_b])
    ):
        flags.append("pair_missing")
    if trajectory_a.arm != "baseline_naive" or trajectory_b.arm != "orchestration_optimized":
        flags.append("pair_missing")
    if (
        trajectory_a.workload_id != trajectory_b.workload_id
        or trajectory_a.harness_id != trajectory_b.harness_id
        or trajectory_a.deployment_id != trajectory_b.deployment_id
    ):
        flags.append("pair_context_divergence")

    seq_a = [(record.turn_index, record.step_type_semantic) for record in calls_a]
    seq_b = [(record.turn_index, record.step_type_semantic) for record in calls_b]
    if seq_a != seq_b:
        flags.append("pair_context_divergence")
    else:
        for record_a, record_b in zip(calls_a, calls_b):
            record_b.t_orch_overhead_b_ms = (
                record_b.t_orch_pre_ms
                + record_b.t_orch_post_ms
                - record_a.t_orch_pre_ms
                - record_a.t_orch_post_ms
            )

    if (
        trajectory_a.task_success != trajectory_b.task_success
        or not bool(trajectory_a.task_success)
        or not bool(trajectory_b.task_success)
    ):
        flags.append("quality_parity_failed")

    if causal_class == "Class_I":
        if bundle_a is None or bundle_b is None or len(bundle_a.turns) != len(bundle_b.turns):
            flags.append("pair_context_divergence")
        else:
            for turn_a, turn_b in zip(bundle_a.turns, bundle_b.turns):
                hash_a = sha256_bytes(canonical_json_bytes(turn_a.assembled_context))
                hash_b = sha256_bytes(canonical_json_bytes(turn_b.assembled_context))
                if (
                    turn_a.context_byte_sha256 not in (None, hash_a)
                    or turn_b.context_byte_sha256 not in (None, hash_b)
                ):
                    flags.append("pair_context_divergence")
                    break
                if hash_a != hash_b:
                    flags.append("pair_context_divergence")
                    break
    elif causal_class == "Class_II":
        if any(
            record.turn_index > 0
            and (
                record.retemplated_tokens != 0
                or "append_discipline_violated" in record.audit_flags
            )
            for record in calls_b
        ):
            flags.append("append_discipline_violated")
    else:
        raise ValueError(f"unknown causal class: {causal_class}")

    flags = sorted(set(flags))
    for flag in flags:
        _flag_records(calls_a, flag)
        _flag_records(calls_b, flag)
    return PairAuditResult(
        pair_id=pair_id,
        causal_class=causal_class,
        passed=not flags,
        flags=flags,
        n_turns_a=len(calls_a),
        n_turns_b=len(calls_b),
    )


def audit_cache_truth(
    records: Sequence[CallRecord],
    *,
    f_prefill: PrefillFn,
) -> list[str]:
    """G-CACHE-TRUTH for a local optimized batch with B-CACHE active."""
    flags: list[str] = []
    candidates = [
        record
        for record in records
        if record.arm == "orchestration_optimized"
        and "B-CACHE" in record.interventions_active
        and record.turn_index > 0
    ]
    if not candidates:
        return ["cache_truth_unverified"]
    for record in candidates:
        if record.cache_state not in ("warm-hit", "warm-partial"):
            if "cache_truth_unverified" not in record.audit_flags:
                record.audit_flags.append("cache_truth_unverified")
            flags.append("cache_truth_unverified")
            continue
        if check_cache_state(record, f_prefill) is not None:
            if "cache_truth_unverified" not in record.audit_flags:
                record.audit_flags.append("cache_truth_unverified")
            flags.append("cache_truth_unverified")
    return sorted(set(flags))
