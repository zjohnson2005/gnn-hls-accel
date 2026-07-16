"""Derive CallRecords / TrajectoryRecords from raw event streams."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from apu_characterization.turntrace_v2.attribution import (
    attribute_prefill,
    token_lcp_diff,
)
from apu_characterization.turntrace_v2.audit import audit_call_record
from apu_characterization.turntrace_v2.labeling import RawTurnEvent, label_trajectory
from apu_characterization.turntrace_v2.schema import CallRecord, TrajectoryRecord

PrefillFn = Callable[[int], float]
DecodePredictFn = Callable[[float, int], float]


@dataclass
class RawModelCallEvent:
    """Raw timing stream for one model call (never destroy; derive re-runnable)."""

    trajectory_id: str
    turn_index: int
    harness_id: str
    deployment_id: str
    assembled_context: str
    raw_model_output: str
    tool_names: tuple[str, ...] = ()
    graph_node: str | None = None
    call_site_tag: str | None = None
    status: str = "ok"
    t_orch_pre_ms: float = 0.0
    t_orch_post_ms: float = 0.0
    t_network_ms: float = 0.0
    network_method: str = "measured"
    t_prefill_ms: float = 0.0
    prefill_method: str = "direct"
    t_decode_ms: float = 0.0
    engine_tokens_in: int | None = None
    requested_tokens_in: int | None = None
    engine_token_ids: tuple[int, ...] = ()
    tokens_out: int | None = None
    cache_state: str = "disabled"
    prefix_hit_tokens: int = 0
    model_id: str = "unknown"
    quantization: str = "unknown"
    reasoning_mode: str = "n/a"
    engine: str = "unknown"
    engine_version: str = "unknown"
    wall_clock_start: float = 0.0
    wall_clock_end: float = 0.0
    energy_j: float | None = None
    tokenizer_id: str = "whitespace_v0"
    expected_horizon: int = 15
    pred_decode_tokens: float | None = None
    prior_semantic_token_ids: tuple[int, ...] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    # Back-compat alias used by older call sites.
    @property
    def context_tokens_in(self) -> int | None:
        return self.engine_tokens_in


def derive_call_records(
    events: Sequence[RawModelCallEvent],
    *,
    f_prefill: PrefillFn,
    predict_decode_ms: DecodePredictFn | None = None,
    ideal_cache: bool = False,
    grid_min: int | None = None,
    grid_max: int | None = None,
    token_delta_lo: float | None = None,
    token_delta_hi: float | None = None,
) -> list[CallRecord]:
    if not events:
        return []
    label_events = [
        RawTurnEvent(
            turn_index=ev.turn_index,
            tool_names=ev.tool_names,
            graph_node=ev.graph_node,
            call_site_tag=ev.call_site_tag,
            status=ev.status,
            expected_horizon=ev.expected_horizon,
        )
        for ev in events
    ]
    labels = label_trajectory(label_events)

    records: list[CallRecord] = []
    prior_engine_ids: list[str] = []
    for ev, (semantic, features) in zip(events, labels):
        # F3: LCP over engine-tokenized post-template sequences only.
        if ev.engine_token_ids:
            engine_ids = [str(t) for t in ev.engine_token_ids]
            engine_tokens = (
                int(ev.engine_tokens_in)
                if ev.engine_tokens_in is not None
                else len(ev.engine_token_ids)
            )
        elif ev.engine_tokens_in is not None:
            # Count-only fallback (no ids): treat as opaque blob — LCP sees all-new.
            engine_ids = [f"__n{ev.engine_tokens_in}__"]
            engine_tokens = int(ev.engine_tokens_in)
        else:
            raise ValueError(
                f"turn {ev.turn_index}: engine_tokens_in / engine_token_ids required (F3)"
            )

        requested = (
            int(ev.requested_tokens_in)
            if ev.requested_tokens_in is not None
            else engine_tokens
        )
        delta = engine_tokens - requested
        out_tokens = int(ev.tokens_out) if ev.tokens_out is not None else 1

        prior_semantic = (
            [str(t) for t in ev.prior_semantic_token_ids]
            if ev.prior_semantic_token_ids is not None
            else None
        )
        diff = token_lcp_diff(
            prior_engine_ids,
            engine_ids,
            prior_semantic_tokens=prior_semantic,
        )
        # When we only have count-level ids, estimate new tokens from count growth.
        if engine_ids and engine_ids[0].startswith("__n") and prior_engine_ids:
            try:
                prev_n = int(prior_engine_ids[0][3:-2])
                new_tokens = max(0, engine_tokens - prev_n)
            except ValueError:
                new_tokens = diff.new_tokens_this_turn
        else:
            new_tokens = diff.new_tokens_this_turn

        attr = attribute_prefill(
            t_prefill_ms=ev.t_prefill_ms,
            context_tokens_in=engine_tokens,
            new_tokens_this_turn=new_tokens,
            prefix_hit_tokens=ev.prefix_hit_tokens,
            f_prefill=f_prefill,
            retemplated_tokens=diff.retemplated_tokens,
            ideal_cache=ideal_cache,
        )
        ratio = float(engine_tokens) / float(out_tokens) if out_tokens else float("inf")
        pred_decode = (
            float(ev.pred_decode_tokens)
            if ev.pred_decode_tokens is not None
            else float(out_tokens)
        )
        pred_prefill = float(f_prefill(engine_tokens))
        if ev.cache_state in ("warm-hit", "warm-partial"):
            pred_prefill = float(f_prefill(max(0, engine_tokens - ev.prefix_hit_tokens)))
        pred_decode_ms = (
            float(predict_decode_ms(pred_decode, engine_tokens))
            if predict_decode_ms is not None
            else 0.0
        )
        record = CallRecord(
            trajectory_id=ev.trajectory_id,
            turn_index=ev.turn_index,
            harness_id=ev.harness_id,
            deployment_id=ev.deployment_id,
            step_type_semantic=semantic,
            step_features=features,
            t_orch_pre_ms=ev.t_orch_pre_ms,
            t_orch_post_ms=ev.t_orch_post_ms,
            t_network_ms=ev.t_network_ms,
            network_method=ev.network_method,
            t_prefill_ms=ev.t_prefill_ms,
            prefill_method=ev.prefill_method,
            t_decode_ms=ev.t_decode_ms,
            context_tokens_in=engine_tokens,
            engine_tokens_in=engine_tokens,
            requested_tokens_in=requested,
            token_reconciliation_delta=delta,
            tokens_out=out_tokens,
            call_shape_ratio=ratio,
            cache_state=ev.cache_state,  # type: ignore[arg-type]
            prefix_hit_tokens=ev.prefix_hit_tokens,
            prefill_necessary_tokens=attr.prefill_necessary_tokens,
            prefill_redundant_tokens=attr.prefill_redundant_tokens,
            t_prefill_necessary_ms=attr.t_prefill_necessary_ms,
            t_prefill_redundant_ms=attr.t_prefill_redundant_ms,
            retemplated_tokens=attr.retemplated_tokens,
            pred_context_tokens=engine_tokens,
            pred_cache_state=ev.cache_state,  # type: ignore[arg-type]
            pred_decode_tokens=pred_decode,
            pred_t_prefill_ms=pred_prefill,
            pred_t_decode_ms=pred_decode_ms,
            energy_j=ev.energy_j,
            model_id=ev.model_id,
            quantization=ev.quantization,
            reasoning_mode=ev.reasoning_mode,  # type: ignore[arg-type]
            engine=ev.engine,
            engine_version=ev.engine_version,
            wall_clock_start=ev.wall_clock_start,
            wall_clock_end=ev.wall_clock_end,
            audit_flags=["negative_prefill_residual"] if attr.negative_residual else [],
        )
        audit_call_record(
            record,
            f_prefill=f_prefill,
            grid_min=grid_min,
            grid_max=grid_max,
            token_delta_lo=token_delta_lo,
            token_delta_hi=token_delta_hi,
        )
        records.append(record)
        prior_engine_ids = engine_ids
    return records


def derive_trajectory_record(
    calls: Sequence[CallRecord],
    *,
    workload_id: str,
    cache_mode: str,
    task_success: bool | float,
    success_metric: str,
    replay_bundle_path: str | None,
    total_cost_usd: float = 0.0,
    headline: bool = False,
) -> TrajectoryRecord:
    if not calls:
        raise ValueError("cannot derive trajectory from empty calls")
    first = calls[0]
    energy_vals = [c.energy_j for c in calls if c.energy_j is not None]
    total_energy = sum(energy_vals) if energy_vals else None
    wall_ms = sum(max(0.0, (c.wall_clock_end - c.wall_clock_start) * 1000.0) for c in calls)
    traj = TrajectoryRecord(
        trajectory_id=first.trajectory_id,
        workload_id=workload_id,
        harness_id=first.harness_id,
        deployment_id=first.deployment_id,
        cache_mode=cache_mode,
        task_success=task_success,
        success_metric=success_metric,
        n_turns=len(calls),
        total_wall_clock_ms=wall_ms,
        total_cost_usd=total_cost_usd,
        total_energy_j=total_energy,
        replay_bundle_path=replay_bundle_path,
    )
    traj.validate(headline=headline)
    if headline and not replay_bundle_path:
        for call in calls:
            if "missing_replay_bundle" not in call.audit_flags:
                call.audit_flags.append("missing_replay_bundle")
    return traj


def flatten_call_dicts(records: Sequence[CallRecord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        row = record.to_dict()
        features = row.pop("step_features")
        for key, value in features.items():
            row[f"step_features.{key}"] = value
        rows.append(row)
    return rows
