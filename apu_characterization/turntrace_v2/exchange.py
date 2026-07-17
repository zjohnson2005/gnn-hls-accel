"""Offline, idempotent rev C orchestration exchange-rate derivation."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from apu_characterization.turntrace_v2.audit import headline_eligible
from apu_characterization.turntrace_v2.schema import CallRecord, TrajectoryRecord


@dataclass(frozen=True)
class PairExchange:
    pair_id: str
    workload_id: str
    deployment_id: str
    harness_id: str
    interventions_active: tuple[str, ...]
    n_turns: int
    redundant_a_ms: float
    redundant_b_ms: float
    recovered_model_ms: float
    recovered_fraction: float | None
    redundant_ideal_ms: float | None
    ideal_bound_capture: float | None
    orch_a_ms: float
    orch_b_ms: float
    added_orch_ms: float
    added_orch_ms_per_turn: float
    exchange_rate_ms_per_ms: float | None
    usd_a: float
    usd_b: float
    recovered_usd_per_task: float
    recovered_usd_per_task_per_ms_per_turn: float | None
    joules_a: float | None
    joules_b: float | None
    exchange_rate_j_per_j: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _orch_ms(record: CallRecord) -> float:
    return float(record.t_orch_pre_ms) + float(record.t_orch_post_ms)


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0 or not math.isfinite(denominator):
        return None
    return numerator / denominator


def derive_pair_exchange(
    calls_a: Sequence[CallRecord],
    calls_b: Sequence[CallRecord],
    *,
    trajectory_a: TrajectoryRecord,
    trajectory_b: TrajectoryRecord,
    redundant_ideal_ms: float | None = None,
) -> PairExchange:
    if not calls_a or not calls_b:
        raise ValueError("paired exchange requires non-empty arms")
    if trajectory_a.pair_id != trajectory_b.pair_id or not trajectory_a.pair_id:
        raise ValueError("paired exchange requires matching non-empty pair_id")
    if trajectory_a.arm != "baseline_naive":
        raise ValueError("trajectory_a must be baseline_naive")
    if trajectory_b.arm != "orchestration_optimized":
        raise ValueError("trajectory_b must be orchestration_optimized")
    if (
        trajectory_a.workload_id != trajectory_b.workload_id
        or trajectory_a.harness_id != trajectory_b.harness_id
        or trajectory_a.deployment_id != trajectory_b.deployment_id
    ):
        raise ValueError("paired exchange trajectory metadata mismatch")
    if (
        trajectory_a.task_success != trajectory_b.task_success
        or not bool(trajectory_a.task_success)
    ):
        raise ValueError("paired exchange requires successful quality parity")
    for records, trajectory, expected_arm in (
        (calls_a, trajectory_a, "baseline_naive"),
        (calls_b, trajectory_b, "orchestration_optimized"),
    ):
        expected_interventions = tuple(trajectory.interventions_active)
        if any(
            record.pair_id != trajectory.pair_id
            or record.arm != expected_arm
            or record.harness_id != trajectory.harness_id
            or record.deployment_id != trajectory.deployment_id
            or tuple(record.interventions_active) != expected_interventions
            for record in records
        ):
            raise ValueError("paired exchange call metadata mismatch")
    seq_a = [(record.turn_index, record.step_type_semantic) for record in calls_a]
    seq_b = [(record.turn_index, record.step_type_semantic) for record in calls_b]
    if seq_a != seq_b:
        raise ValueError("paired exchange requires identical turn/step sequence")

    redundant_a = sum(float(record.t_prefill_redundant_ms) for record in calls_a)
    redundant_b = sum(float(record.t_prefill_redundant_ms) for record in calls_b)
    recovered_ms = redundant_a - redundant_b
    recovered_fraction = _safe_ratio(recovered_ms, redundant_a)
    ideal_capture = None
    if redundant_ideal_ms is not None:
        ideal_capture = _safe_ratio(
            recovered_ms, redundant_a - float(redundant_ideal_ms)
        )

    orch_a = sum(_orch_ms(record) for record in calls_a)
    orch_b = sum(_orch_ms(record) for record in calls_b)
    added_orch = orch_b - orch_a
    n_turns = len(calls_a)
    added_per_turn = added_orch / n_turns
    for call_a, call_b in zip(calls_a, calls_b):
        call_b.t_orch_overhead_b_ms = _orch_ms(call_b) - _orch_ms(call_a)

    usd_a = float(trajectory_a.usd_model_cost)
    usd_b = float(trajectory_b.usd_model_cost)
    recovered_usd = usd_a - usd_b
    usd_per_orch_ms_turn = _safe_ratio(recovered_usd, added_per_turn)

    # J/J remains null until the box sidecar supplies a separable Arm-B
    # orchestration-energy increment. Total trajectory joules alone cannot
    # identify that denominator without fabricating an energy attribution.
    return PairExchange(
        pair_id=trajectory_a.pair_id,
        workload_id=trajectory_a.workload_id,
        deployment_id=trajectory_a.deployment_id,
        harness_id=trajectory_a.harness_id,
        interventions_active=tuple(trajectory_b.interventions_active),
        n_turns=n_turns,
        redundant_a_ms=redundant_a,
        redundant_b_ms=redundant_b,
        recovered_model_ms=recovered_ms,
        recovered_fraction=recovered_fraction,
        redundant_ideal_ms=redundant_ideal_ms,
        ideal_bound_capture=ideal_capture,
        orch_a_ms=orch_a,
        orch_b_ms=orch_b,
        added_orch_ms=added_orch,
        added_orch_ms_per_turn=added_per_turn,
        exchange_rate_ms_per_ms=_safe_ratio(recovered_ms, added_orch),
        usd_a=usd_a,
        usd_b=usd_b,
        recovered_usd_per_task=recovered_usd,
        recovered_usd_per_task_per_ms_per_turn=usd_per_orch_ms_turn,
        joules_a=trajectory_a.joules_total,
        joules_b=trajectory_b.joules_total,
        exchange_rate_j_per_j=None,
    )


def _band(values: Iterable[float | None]) -> dict[str, float | None]:
    clean = sorted(float(value) for value in values if value is not None)
    if not clean:
        return {"min": None, "median": None, "max": None}
    return {
        "min": clean[0],
        "median": statistics.median(clean),
        "max": clean[-1],
    }


def aggregate_exchange(
    pairs: Sequence[PairExchange],
    *,
    include_sparse: bool = False,
) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str, tuple[str, ...]], list[PairExchange]] = (
        defaultdict(list)
    )
    for pair in pairs:
        groups[
            (
                pair.workload_id,
                pair.deployment_id,
                pair.harness_id,
                pair.interventions_active,
            )
        ].append(pair)
    rows: list[dict[str, object]] = []
    for key, values in sorted(groups.items()):
        if len(values) < 5 and not include_sparse:
            continue
        workload_id, deployment_id, harness_id, interventions = key
        rows.append(
            {
                "workload_id": workload_id,
                "deployment_id": deployment_id,
                "harness_id": harness_id,
                "interventions_active": list(interventions),
                "n_pairs": len(values),
                "sparse_n_lt_5": len(values) < 5,
                "recovered_fraction": _band(v.recovered_fraction for v in values),
                "ideal_bound_capture": _band(
                    v.ideal_bound_capture for v in values
                ),
                "exchange_rate_ms_per_ms": _band(
                    v.exchange_rate_ms_per_ms for v in values
                ),
                "recovered_usd_per_task": _band(
                    v.recovered_usd_per_task for v in values
                ),
                "arm_b_orch_overhead_ms_per_turn": _band(
                    v.added_orch_ms_per_turn for v in values
                ),
                "exchange_rate_j_per_j": _band(
                    v.exchange_rate_j_per_j for v in values
                ),
            }
        )
    return rows


def load_call_records(path: Path) -> list[CallRecord]:
    return [
        CallRecord.from_dict(json.loads(line))
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_trajectory_records(path: Path) -> list[TrajectoryRecord]:
    return [
        TrajectoryRecord.from_dict(json.loads(line))
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def derive_corpus_exchange(
    calls: Sequence[CallRecord],
    trajectories: Sequence[TrajectoryRecord],
    *,
    ideal_by_pair: Mapping[str, float] | None = None,
) -> tuple[list[PairExchange], list[dict[str, object]]]:
    calls_by_pair_arm: dict[tuple[str, str], list[CallRecord]] = defaultdict(list)
    traj_by_pair_arm: dict[tuple[str, str], TrajectoryRecord] = {}
    for record in calls:
        calls_by_pair_arm[(record.pair_id, record.arm)].append(record)
    for trajectory in trajectories:
        traj_by_pair_arm[(trajectory.pair_id, trajectory.arm)] = trajectory
    pair_ids = sorted(
        pair_id
        for pair_id in {trajectory.pair_id for trajectory in trajectories}
        if pair_id
    )
    pairs: list[PairExchange] = []
    for pair_id in pair_ids:
        key_a = (pair_id, "baseline_naive")
        key_b = (pair_id, "orchestration_optimized")
        if key_a not in traj_by_pair_arm or key_b not in traj_by_pair_arm:
            continue
        calls_a = sorted(calls_by_pair_arm[key_a], key=lambda r: r.turn_index)
        calls_b = sorted(calls_by_pair_arm[key_b], key=lambda r: r.turn_index)
        combined = [*calls_a, *calls_b]
        if len(headline_eligible(combined)) != len(combined):
            continue
        trajectory_a = traj_by_pair_arm[key_a]
        trajectory_b = traj_by_pair_arm[key_b]
        if (
            trajectory_a.task_success != trajectory_b.task_success
            or not bool(trajectory_a.task_success)
        ):
            continue
        pairs.append(
            derive_pair_exchange(
                calls_a,
                calls_b,
                trajectory_a=trajectory_a,
                trajectory_b=trajectory_b,
                redundant_ideal_ms=(ideal_by_pair or {}).get(pair_id),
            )
        )
    return pairs, aggregate_exchange(pairs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls", type=Path, required=True)
    parser.add_argument("--trajectories", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    pairs, aggregate = derive_corpus_exchange(
        load_call_records(args.calls),
        load_trajectory_records(args.trajectories),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    payload = {
        "pair_rows": [pair.to_dict() for pair in pairs],
        "aggregate_rows": aggregate,
        "note": "J/J remains null until box energy sidecar isolates Arm-B orchestration energy.",
    }
    (args.out / "C-D3_exchange_rate.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"n_pairs": len(pairs), "n_groups": len(aggregate)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
