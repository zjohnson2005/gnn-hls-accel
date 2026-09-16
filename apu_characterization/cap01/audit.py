"""Frozen CAP-01 G1 through G8 publication gates."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from .contracts import CandidateEvent, load_protocol
from .floor import qualify_floor

Record = Mapping[str, Any]
Verifier = Callable[[Record], Any]


def audit_accounting(
    cell: Record,
    *,
    residual_limit: float = 0.15,
    conservation_tolerance_fraction: float = 0.01,
    conservation_tolerance_ns: int = 1_000,
) -> dict[str, Any]:
    """G1: cap residual CPU and conserve process CPU accounting."""
    source = _nested(cell, "accounting")
    process = _number(source, "process_cpu_ns", "total_cpu_ns", "cpu_ns")
    residual = _number(source, "residual_cpu_ns", "residual_ns")
    accounted = _number(
        source, "accounted_cpu_ns", "instrumented_cpu_ns", "attributed_cpu_ns"
    )
    if not accounted:
        categories = source.get("category_cpu_ns", source.get("categories", {}))
        if isinstance(categories, Mapping):
            accounted = sum(
                _metric(value, "cpu_ns") for name, value in categories.items()
                if str(name).upper() not in {"RESIDUAL", "RESIDUAL_UNATTRIBUTED"}
            )
    errors: list[str] = []
    if process <= 0:
        errors.append("process CPU must be positive")
    if residual < 0 or accounted < 0:
        errors.append("accounted and residual CPU must be non-negative")
    residual_fraction = residual / process if process > 0 else math.inf
    if residual_fraction >= residual_limit:
        errors.append(
            f"residual CPU fraction {residual_fraction:.6f} is not below "
            f"{residual_limit:.6f}"
        )
    conservation_error = abs(process - accounted - residual)
    tolerance = max(
        float(conservation_tolerance_ns),
        conservation_tolerance_fraction * max(process, 0.0),
    )
    if conservation_error > tolerance:
        errors.append(
            f"CPU conservation error {conservation_error:.0f} ns exceeds "
            f"{tolerance:.0f} ns"
        )
    return _gate(
        "G1",
        errors,
        process_cpu_ns=process,
        accounted_cpu_ns=accounted,
        residual_cpu_ns=residual,
        residual_fraction=residual_fraction,
        conservation_error_ns=conservation_error,
        conservation_tolerance_ns=tolerance,
    )


def audit_budget_integrity(
    cells: Sequence[Record],
    *,
    max_overshoot_fraction: float = 0.02,
    max_violating_task_cell_fraction: float = 0.01,
) -> dict[str, Any]:
    """G2: enforce deadline overshoot and started-event conservation."""
    errors: list[str] = []
    violations: list[dict[str, Any]] = []
    overshoot_cells = 0
    for position, cell in enumerate(cells):
        label = _cell_label(cell, position)
        events = _events(cell)
        started = _integer(
            cell,
            "started",
            "candidates_started",
            default=len(events),
        )
        counted = _integer(
            cell,
            "counted",
            "candidates_counted",
            default=sum(bool(event.get("counted")) for event in events),
        )
        abandoned = _integer(
            cell,
            "abandoned",
            "candidates_abandoned",
            default=sum(bool(event.get("abandoned")) for event in events),
        )
        if started != counted + abandoned:
            message = (
                f"{label}: started {started} != counted {counted} + "
                f"abandoned {abandoned}"
            )
            errors.append(message)
            violations.append({"cell": label, "kind": "conservation", "message": message})
        for event_index, event in enumerate(events):
            if bool(event.get("counted")) == bool(event.get("abandoned")):
                message = (
                    f"{label}: event {event_index} must be exactly one of "
                    "counted or abandoned"
                )
                errors.append(message)
                violations.append(
                    {"cell": label, "kind": "event_conservation", "message": message}
                )

        budget = _number(cell, "budget_ns", "wall_budget_ns")
        if not budget:
            budget_ms = _number(cell, "wall_budget_ms", "budget_ms")
            budget = budget_ms * 1_000_000
        elapsed = _number(cell, "elapsed_ns", "wall_ns", "task_wall_ns")
        limit = budget * (1.0 + max_overshoot_fraction)
        if budget <= 0 or elapsed < 0:
            message = f"{label}: wall budget and elapsed time must be valid"
            errors.append(message)
            violations.append({"cell": label, "kind": "budget", "message": message})
        elif elapsed > limit:
            overshoot_cells += 1
            message = (
                f"{label}: elapsed {elapsed:.0f} ns exceeds +2% deadline "
                f"{limit:.0f} ns"
            )
            violations.append({"cell": label, "kind": "overshoot", "message": message})

    fraction = overshoot_cells / len(cells) if cells else 1.0
    if not cells:
        errors.append("no task-cells retained")
    if fraction > max_violating_task_cell_fraction:
        errors.append(
            f"overshoot task-cell fraction {fraction:.6f} exceeds "
            f"{max_violating_task_cell_fraction:.6f}"
        )
    return _gate(
        "G2",
        errors,
        violations=violations,
        task_cells=len(cells),
        overshoot_task_cells=overshoot_cells,
        overshoot_fraction=fraction,
    )


def audit_candidate_matching(
    cells: Sequence[Record],
    seed_orderings: Mapping[Any, Sequence[Any]],
) -> dict[str, Any]:
    """G3: each consumed stream is a seeded prefix shared across harnesses."""
    errors: list[str] = []
    violations: list[dict[str, Any]] = []
    streams: dict[tuple[str, int], list[tuple[str, tuple[str, ...]]]] = defaultdict(list)
    for position, cell in enumerate(cells):
        task_id = str(cell.get("task_id", ""))
        seed = int(cell.get("seed", _nested(cell, "coordinates").get("seed", -1)))
        label = _cell_label(cell, position)
        expected = _seed_order(seed_orderings, task_id, seed)
        events = sorted(_events(cell), key=lambda event: int(event.get("sequence_index", 0)))
        sequence_indices = [int(event.get("sequence_index", index)) for index, event in enumerate(events)]
        consumed = tuple(str(event.get("candidate_id", "")) for event in events)
        if sequence_indices != list(range(len(events))):
            message = f"{label}: consumed sequence indices are not contiguous from zero"
            errors.append(message)
            violations.append({"cell": label, "kind": "indices", "message": message})
        if expected is None:
            message = f"{label}: missing frozen candidate ordering for task/seed"
            errors.append(message)
            violations.append({"cell": label, "kind": "ordering", "message": message})
        elif consumed != expected[: len(consumed)]:
            message = f"{label}: consumed candidates are not a prefix of seed ordering"
            errors.append(message)
            violations.append({"cell": label, "kind": "prefix", "message": message})
        exhausted = bool(
            cell.get("pool_exhausted")
            or cell.get("candidate_pool_exhausted")
            or (expected is not None and len(consumed) > len(expected))
        )
        if exhausted:
            message = f"{label}: candidate pool exhausted"
            errors.append(message)
            violations.append({"cell": label, "kind": "pool_exhaustion", "message": message})
        streams[(task_id, seed)].append((label, consumed))

    for (task_id, seed), labeled in streams.items():
        for left_index, (left_label, left) in enumerate(labeled):
            for right_label, right in labeled[left_index + 1 :]:
                common = min(len(left), len(right))
                if left[:common] != right[:common]:
                    message = (
                        f"task {task_id} seed {seed}: {left_label} and {right_label} "
                        "are not prefixes of the same cross-harness sequence"
                    )
                    errors.append(message)
                    violations.append(
                        {
                            "task_id": task_id,
                            "seed": seed,
                            "kind": "cross_harness",
                            "message": message,
                        }
                    )
    return _gate("G3", errors, violations=violations, stream_count=sum(map(len, streams.values())))


def audit_verifier_determinism(
    cells: Sequence[Record],
    reexecute: Verifier | None = None,
    *,
    offline_verdicts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """G4: re-execute each original verdict exactly once and ledger every flip."""
    if reexecute is None and offline_verdicts is None:
        return _gate(
            "G4",
            ["offline verifier re-execution is required"],
            ledger=[],
            removed_task_ids=[],
            reexecutions=0,
        )
    errors: list[str] = []
    ledger: list[dict[str, Any]] = []
    removed: set[str] = set()
    reexecutions = 0
    code_runtimes: set[str] = set()
    for cell_index, cell in enumerate(cells):
        task_id = str(cell.get("task_id", ""))
        domain = str(cell.get("domain", "")).upper()
        for event_index, event in enumerate(_events(cell)):
            if not bool(event.get("counted")):
                continue
            if domain == "CODE":
                runtime = event.get("verifier_runtime")
                if isinstance(runtime, str) and runtime:
                    code_runtimes.add(runtime)
                else:
                    errors.append(
                        f"{_cell_label(cell, cell_index)}: CODE verifier runtime missing"
                    )
                if event.get("verifier_network_isolated") is not True:
                    errors.append(
                        f"{_cell_label(cell, cell_index)}: CODE verifier lacks "
                        "confirmed network isolation"
                    )
            candidate_id = str(event.get("candidate_id", ""))
            record = {
                **cell,
                **event,
                "task_id": task_id,
                "cell": _cell_label(cell, cell_index),
            }
            original = _verdict(event)
            if offline_verdicts is not None:
                key = candidate_id or f"{task_id}:{event_index}"
                if key not in offline_verdicts:
                    errors.append(f"{record['cell']}: no offline verdict for {key}")
                    continue
                rerun_raw = offline_verdicts[key]
            else:
                assert reexecute is not None
                rerun_raw = reexecute(record)
            reexecutions += 1
            rerun = _verdict(rerun_raw)
            flipped = not _same_verdict(original, rerun)
            entry = {
                "task_id": task_id,
                "candidate_id": candidate_id,
                "cell": record["cell"],
                "original": {"solved": original[0], "digest": original[1]},
                "offline": {"solved": rerun[0], "digest": rerun[1]},
                "flipped": flipped,
            }
            ledger.append(entry)
            if flipped:
                removed.add(task_id)
                errors.append(
                    f"{record['cell']}: verifier verdict flipped for {candidate_id}"
                )
    if len(code_runtimes) > 1:
        errors.append(
            "CODE verifier used multiple interpreter versions: "
            + ", ".join(sorted(code_runtimes))
        )
    return _gate(
        "G4",
        errors,
        ledger=ledger,
        removed_task_ids=sorted(removed),
        reexecutions=reexecutions,
        code_verifier_runtimes=sorted(code_runtimes),
    )


def audit_replication(
    cells: Sequence[Record],
    *,
    required_cells: Sequence[Record | str] | None = None,
    expected_seeds: Iterable[int] = range(5),
) -> dict[str, Any]:
    """G5: require exactly the frozen five distinct seeds in every required cell."""
    expected = tuple(sorted(int(seed) for seed in expected_seeds))
    expected_set = set(expected)
    observed: dict[str, list[int]] = defaultdict(list)
    for cell in cells:
        seeds = cell.get("seeds")
        if isinstance(seeds, Sequence) and not isinstance(seeds, (str, bytes)):
            observed[_replication_key(cell)].extend(int(seed) for seed in seeds)
        else:
            observed[_replication_key(cell)].append(
                int(cell.get("seed", _nested(cell, "coordinates").get("seed", -1)))
            )
    required = (
        {_replication_key(cell) if not isinstance(cell, str) else cell for cell in required_cells}
        if required_cells is not None
        else set(observed)
    )
    errors: list[str] = []
    details: dict[str, Any] = {}
    if not required:
        errors.append("no required replication cells")
    for key in sorted(required | set(observed)):
        seeds = observed.get(key, [])
        details[key] = {"seeds": sorted(seeds), "required": key in required}
        if key in required and (set(seeds) != expected_set or len(seeds) != len(expected)):
            errors.append(
                f"{key}: present seeds {sorted(seeds)}, expected exactly {list(expected)}"
            )
        elif key not in required:
            errors.append(f"{key}: observed cell is not in the required matrix")
    return _gate("G5", errors, cells=details, required_seeds=list(expected))


def audit_throughput_consistency(
    cell: Record,
    *,
    relative_tolerance: float = 0.25,
) -> dict[str, Any]:
    """G7: compare candidates/s with Rmax using all frozen denominator terms."""
    events = [event for event in _events(cell) if bool(event.get("counted"))]
    errors: list[str] = []
    floor_ns = _number(
        cell,
        "host_measured_floor_ns",
        "measured_floor_ns",
        "harness_floor_ns",
    )
    elapsed_ns = _number(cell, "elapsed_ns", "wall_ns", "task_wall_ns")
    latency_ns = sum(_number(event, "latency_ns", "latency_draw_ns") for event in events)
    verifier_ns = sum(_number(event, "verifier_wall_ns") for event in events)
    floor_total_ns = floor_ns * len(events)
    denominator_ns = latency_ns + floor_total_ns + verifier_ns
    count = len(events)
    observed_value = _optional_number(cell, "candidates_per_second", "candidate_rate")
    observed = observed_value if observed_value is not None else 0.0
    if observed_value is None and elapsed_ns > 0:
        observed = count * 1_000_000_000.0 / elapsed_ns
    rmax = count * 1_000_000_000.0 / denominator_ns if denominator_ns > 0 else math.inf
    relative_error = (
        abs(observed - rmax) / rmax
        if rmax > 0 and math.isfinite(rmax) and observed >= 0
        else math.inf
    )
    if count == 0:
        errors.append("no counted candidates for throughput consistency")
    if floor_ns <= 0:
        errors.append("host-measured harness floor is missing or non-positive")
    if elapsed_ns <= 0 and observed <= 0:
        errors.append("observed candidate rate is unavailable")
    if any(_number(event, "latency_ns", "latency_draw_ns") < 0 for event in events):
        errors.append("actual latency draws must be non-negative")
    if any(_number(event, "verifier_wall_ns") < 0 for event in events):
        errors.append("measured verifier wall times must be non-negative")
    if relative_error > relative_tolerance:
        errors.append(
            f"candidate rate {observed:.6f}/s differs from Rmax {rmax:.6f}/s "
            f"by {relative_error:.6f}, beyond +/-{relative_tolerance:.2f}"
        )
    return _gate(
        "G7",
        errors,
        observed_candidates_per_second=observed,
        rmax_candidates_per_second=rmax,
        relative_error=relative_error,
        denominator_ns=denominator_ns,
        denominator={
            "actual_latency_draw_ns": latency_ns,
            "host_measured_harness_floor_ns": floor_total_ns,
            "measured_verifier_wall_ns": verifier_ns,
        },
        counted_candidates=count,
    )


def audit_experiment(
    cells: Sequence[Record],
    *,
    seed_orderings: Mapping[Any, Sequence[Any]],
    reexecute_verifier: Verifier | None = None,
    offline_verdicts: Mapping[str, Any] | None = None,
    required_cells: Sequence[Record | str] | None = None,
    floor_measurements_ns: Mapping[str, int] | None = None,
    protocol: Mapping[str, Any] | None = None,
    g8_measurement: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all frozen gates and retain gate, cell, and verifier violations."""
    cfg = dict(protocol or load_protocol())
    gate_cfg = cfg["gates"]
    g1_cells = [
        {"cell": _cell_label(cell, index), **audit_accounting(
            cell,
            residual_limit=float(gate_cfg["G1"]["residual_limit_fraction"]),
        )}
        for index, cell in enumerate(cells)
    ]
    g1_errors = [
        f"{result['cell']}: {error}"
        for result in g1_cells
        for error in result["errors"]
    ]
    g1 = _gate("G1", g1_errors, task_cells=g1_cells)
    g2 = audit_budget_integrity(
        cells,
        max_overshoot_fraction=float(gate_cfg["G2"]["max_overshoot_fraction"]),
        max_violating_task_cell_fraction=float(
            gate_cfg["G2"]["max_violating_task_cell_fraction"]
        ),
    )
    g3 = audit_candidate_matching(cells, seed_orderings)
    g4 = audit_verifier_determinism(
        cells, reexecute_verifier, offline_verdicts=offline_verdicts
    )
    g5 = audit_replication(cells, required_cells=required_cells)

    harnesses = sorted(
        {
            str(cell.get("harness", _nested(cell, "coordinates").get("harness", "")))
            for cell in cells
            if cell.get("harness", _nested(cell, "coordinates").get("harness"))
        }
    )
    floor_measurements_ns = floor_measurements_ns or {}
    floor_results: dict[str, Any] = {}
    g6_errors: list[str] = []
    for harness in harnesses:
        if harness not in floor_measurements_ns:
            g6_errors.append(f"{harness}: missing host-measured 20 ms floor")
            continue
        result = qualify_floor(harness, floor_measurements_ns[harness], protocol=cfg)
        floor_results[harness] = result.as_dict()
        g6_errors.extend(f"{harness}: {error}" for error in result.violations)
    if not harnesses:
        g6_errors.append("no harnesses present for floor verification")
    g6 = _gate("G6", g6_errors, harnesses=floor_results)

    g7_cells = [
        {"cell": _cell_label(cell, index), **audit_throughput_consistency(
            _with_floor(cell, floor_measurements_ns),
            relative_tolerance=float(gate_cfg["G7"]["relative_tolerance"]),
        )}
        for index, cell in enumerate(cells)
    ]
    g7_errors = [
        f"{result['cell']}: {error}"
        for result in g7_cells
        for error in result["errors"]
    ]
    g7 = _gate("G7", g7_errors, task_cells=g7_cells)
    from .verification_audit import audit_g8_verifier_cost_parity

    g8_relative = float(gate_cfg["G8"]["relative_tolerance"])
    if g8_measurement is None:
        g8 = _gate(
            "G8",
            [
                "G8 verifier-cost-parity measurement is required before P3; "
                "run apu_characterization/tools/run_cap01_verification_audit.py"
            ],
            relative_tolerance=g8_relative,
        )
    else:
        g8_result = audit_g8_verifier_cost_parity(
            g8_measurement, relative_tolerance=g8_relative
        )
        # FAIL only on cross-harness cost divergence among measured arms.
        # Toolchain gaps remain FLAGGED in the verification audit, not G8 FAIL.
        g8 = _gate(
            "G8",
            list(g8_measurement.get("failures") or []),
            relative_tolerance=g8_relative,
            domains=g8_result.get("domains"),
            flagged=g8_result.get("flagged"),
            primary_eligible=g8_result.get("primary_eligible"),
        )
    gates = {gate["gate"]: gate for gate in (g1, g2, g3, g4, g5, g6, g7, g8)}
    violations = [
        {"gate": gate_name, "message": error}
        for gate_name, gate in gates.items()
        for error in gate["errors"]
    ]
    return {
        "pass": not violations,
        "primary_eligible": not violations,
        "gates": gates,
        "violations": violations,
        "removed_task_ids": g4["removed_task_ids"],
        "verifier_ledger": g4["ledger"],
        "retained_task_cells": len(cells),
    }


def audit_cell(
    cell: Record,
    *,
    expected_candidate_ids: Sequence[Any],
) -> dict[str, Any]:
    """Convenience audit for fixture tests of G1, G2, G3, and G7."""
    task_id = str(cell.get("task_id", ""))
    seed = int(cell.get("seed", _nested(cell, "coordinates").get("seed", -1)))
    gates = {
        "G1": audit_accounting(cell),
        "G2": audit_budget_integrity([cell]),
        "G3": audit_candidate_matching([cell], {(task_id, seed): expected_candidate_ids}),
        "G7": audit_throughput_consistency(cell),
    }
    violations = [
        {"gate": name, "message": error}
        for name, gate in gates.items()
        for error in gate["errors"]
    ]
    return {"pass": not violations, "gates": gates, "violations": violations}


def _events(cell: Record) -> list[dict[str, Any]]:
    values = cell.get("candidate_events", cell.get("events", ()))
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    result: list[dict[str, Any]] = []
    for value in values:
        if isinstance(value, CandidateEvent):
            result.append(asdict(value))
        elif is_dataclass(value):
            result.append(asdict(value))
        elif isinstance(value, Mapping):
            result.append(dict(value))
    return result


def _seed_order(
    orderings: Mapping[Any, Sequence[Any]], task_id: str, seed: int
) -> tuple[str, ...] | None:
    keys: tuple[Any, ...] = ((task_id, seed), f"{task_id}:{seed}", seed)
    value: Sequence[Any] | None = None
    for key in keys:
        if key in orderings:
            value = orderings[key]
            break
    if value is None:
        nested = orderings.get(task_id)
        if isinstance(nested, Mapping):
            value = nested.get(seed, nested.get(str(seed)))  # type: ignore[assignment]
    if value is None:
        return None
    return tuple(
        str(item.get("candidate_id")) if isinstance(item, Mapping) else str(item)
        for item in value
    )


def _verdict(value: Any) -> tuple[bool, str | None]:
    if isinstance(value, Mapping):
        solved = bool(value.get("solved", value.get("passed", value.get("verdict", False))))
        digest = value.get("verdict_digest", value.get("digest"))
        return solved, str(digest) if digest is not None else None
    if isinstance(value, (tuple, list)) and value:
        return bool(value[0]), str(value[1]) if len(value) > 1 and value[1] is not None else None
    return bool(value), None


def _same_verdict(
    original: tuple[bool, str | None], offline: tuple[bool, str | None]
) -> bool:
    if original[0] != offline[0]:
        return False
    return (
        original[1] == offline[1]
        if original[1] is not None and offline[1] is not None
        else True
    )


def _with_floor(cell: Record, floors: Mapping[str, int]) -> dict[str, Any]:
    result = dict(cell)
    harness = str(cell.get("harness", _nested(cell, "coordinates").get("harness", "")))
    if harness in floors:
        result["host_measured_floor_ns"] = floors[harness]
    return result


def _replication_key(cell: Record) -> str:
    coordinates = dict(_nested(cell, "coordinates"))
    merged = {
        "task_id": cell.get("task_id", coordinates.get("task_id")),
        "harness": cell.get("harness", coordinates.get("harness")),
        "latency_scale_ms": cell.get(
            "latency_scale_ms", coordinates.get("latency_scale_ms")
        ),
        "wall_budget_ms": cell.get(
            "wall_budget_ms", coordinates.get("wall_budget_ms")
        ),
        "instr_mode": cell.get("instr_mode", coordinates.get("instr_mode", "throttle")),
        "budget_kind": cell.get("budget_kind", coordinates.get("budget_kind", "wall")),
    }
    return "|".join(f"{key}={merged[key]}" for key in sorted(merged))


def _cell_label(cell: Record, position: int) -> str:
    return str(
        cell.get("task_cell_id")
        or cell.get("cell_id")
        or _nested(cell, "coordinates").get("cell_id")
        or f"task-cell-{position}"
    )


def _nested(value: Record, key: str) -> Record:
    nested = value.get(key)
    return nested if isinstance(nested, Mapping) else value


def _number(value: Record, *keys: str) -> float:
    for source in (value, _nested(value, "coordinates")):
        for key in keys:
            item = source.get(key)
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                return float(item)
    return 0.0


def _optional_number(value: Record, *keys: str) -> float | None:
    for source in (value, _nested(value, "coordinates")):
        for key in keys:
            item = source.get(key)
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                return float(item)
    return None


def _integer(value: Record, *keys: str, default: int) -> int:
    for key in keys:
        item = value.get(key)
        if isinstance(item, int) and not isinstance(item, bool):
            return item
    return default


def _metric(value: Any, key: str) -> float:
    if isinstance(value, Mapping):
        return _number(value, key, key.removesuffix("_ns"))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _gate(name: str, errors: list[str], **details: Any) -> dict[str, Any]:
    return {"gate": name, "pass": not errors, "errors": errors, **details}
