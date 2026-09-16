"""Artifact-only CAP-01 post-processing."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .contracts import PROTOCOL_VERSION, load_protocol
from .statistics import (
    DEFAULT_BOOTSTRAP_RESAMPLES,
    DEFAULT_BOOTSTRAP_SEED,
    analyze_pairs,
)

HARNESSES = ("langgraph", "rust", "raw_python")
CONTRASTS = (("langgraph", "rust"), ("langgraph", "raw_python"))
POPULATIONS = ("SCALING", "ALL")


def load_task_cell_runs(paths: Sequence[Path]) -> list[dict[str, Any]]:
    """Load immutable JSON inputs without altering source files."""
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(item for item in path.rglob("*.json") if item.is_file()))
        else:
            files.append(path)
    if not files:
        raise ValueError("no task-cell JSON files were provided")
    artifacts: list[dict[str, Any]] = []
    for path in files:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"{path}: artifact root must be an object")
        value["_source_path"] = str(path)
        artifacts.append(value)
    return artifacts


def analyze_artifacts(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    protocol: Mapping[str, Any] | None = None,
    bootstrap_resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Build the complete CAP-01 aggregate from immutable task-cell runs."""
    cfg = dict(protocol or load_protocol())
    rows = normalize_task_cells(artifacts)
    removed_task_ids = _removed_task_ids(artifacts)
    rows = [row for row in rows if row["task_id"] not in removed_task_ids]
    if not rows:
        raise ValueError("artifacts contain no task-cell results")
    _validate_unique_rows(rows)

    statistical_cells = _statistical_cells(
        rows,
        bootstrap_resamples=bootstrap_resamples,
        bootstrap_seed=bootstrap_seed,
    )
    gates = _aggregate_gates(artifacts)
    expectations = _expectation_rows(rows)
    throughput_clipping = _throughput_clipping_confirmed(expectations, cfg)
    primary_result = _domain_primary_result(
        rows,
        cfg,
        contrast=("langgraph", "rust"),
        latency_scale_ms=int(cfg["statistics"]["primary_cell"]["latency_scale_ms"]),
        bootstrap_resamples=bootstrap_resamples,
        bootstrap_seed=bootstrap_seed,
    )
    secondary_results = _secondary_results(
        rows,
        cfg,
        bootstrap_resamples=bootstrap_resamples,
        bootstrap_seed=bootstrap_seed,
    )
    positive_control = _positive_control(secondary_results, cfg)
    floor_fit = _capability_floor_fit(rows, cfg)
    claim = _select_claim_rung(
        primary_result,
        secondary_results,
        gates,
        positive_control,
        throughput_clipping,
        cfg,
    )
    classifications = _classification_counts(rows)
    aggregate = {
        "protocol_version": PROTOCOL_VERSION,
        "analysis": "CAP-01 post-processing",
        "source_artifact_count": len(artifacts),
        "source_paths": sorted(
            str(item.get("_source_path"))
            for item in artifacts
            if item.get("_source_path")
        ),
        "task_cell_count": len(rows),
        "removed_task_ids": sorted(removed_task_ids),
        "bootstrap": {
            "method": "BCa",
            "resamples": bootstrap_resamples,
            "unit": "task",
            "random_seed": bootstrap_seed,
        },
        "populations": {
            "primary": cfg["calibration"]["primary_population"],
            "secondary": cfg["calibration"]["secondary_population"],
        },
        "domain_budget_tiers": {
            domain: {
                "primary_tier_ms": details["primary_tier_ms"],
                "rationale": details["report_rationale"],
            }
            for domain, details in cfg["corpus"]["domains"].items()
        },
        "classification_counts": classifications,
        "statistics": statistical_cells,
        "primary_result": primary_result,
        "secondary_results": secondary_results,
        "positive_control": positive_control,
        "capability_floor_fit": floor_fit,
        "gate_matrix": gates,
        "abandonment_tails": _abandonment_tails(rows),
        "expectation_actual_vs_predicted": expectations,
        "throughput_clipping_confirmed": throughput_clipping,
        "claim_rung": claim,
        "headline_blocked": primary_result is None or not positive_control["holds"],
        "promotion_summary": _promotion_summary(claim, positive_control),
        "figure_data": _figure_data(rows, cfg),
    }
    return aggregate


def normalize_task_cells(
    artifacts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize common immutable run layouts into one task-harness row."""
    rows: list[dict[str, Any]] = []
    classifications = _all_classifications(artifacts)
    floors = _floor_measurements_ms(artifacts)
    for artifact in artifacts:
        for run in _runs(artifact):
            coordinates = _mapping(run.get("coordinates"))
            task_values = _task_values(run)
            for task in task_values:
                merged = dict(coordinates)
                merged.update(
                    {
                        key: value
                        for key, value in run.items()
                        if key not in {"coordinates", "tasks", "task_results", "results"}
                    }
                )
                merged.update(task)
                if not _looks_like_task_cell(merged):
                    continue
                if not any(
                    name in merged
                    for name in ("population", "task_class", "classification")
                ):
                    classification = classifications.get(str(merged.get("task_id")))
                    if classification is not None:
                        merged["task_class"] = classification
                row = _normalize_row(merged, artifact)
                if (
                    row["host_measured_floor_ms"] is None
                    and row["harness"] in floors
                ):
                    row["host_measured_floor_ms"] = floors[row["harness"]]
                rows.append(row)
    return rows


def _runs(artifact: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for key in ("runs", "cells", "task_cells"):
        value = artifact.get(key)
        if isinstance(value, list):
            for run in value:
                if not isinstance(run, Mapping):
                    raise ValueError(f"{key} entries must be objects")
                yield run
            return
    yield artifact


def _task_values(run: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("tasks", "task_results", "results"):
        value = run.get(key)
        if isinstance(value, list):
            return [dict(_mapping(item)) for item in value]
        if isinstance(value, Mapping):
            return [
                {"task_id": str(task_id), **dict(_mapping(item))}
                for task_id, item in value.items()
            ]
    if run.get("task_id") is not None:
        return [dict(run)]
    return []


def _normalize_row(
    value: Mapping[str, Any], artifact: Mapping[str, Any]
) -> dict[str, Any]:
    outcome = _mapping(value.get("outcome"))
    measurements = _mapping(value.get("measurements"))
    events = _candidate_events(value)
    raw_task_class = _first(
        value, "population", "task_class", "classification"
    )
    if raw_task_class is None:
        raise ValueError(
            f"{value.get('task_id')}: frozen task classification is required"
        )
    task_class = str(raw_task_class).upper()
    if task_class not in {"SCALING", "SATURATED", "DEAD"}:
        raise ValueError(f"unsupported task classification: {task_class}")
    harness = str(_required(value, "harness"))
    if harness not in HARNESSES:
        raise ValueError(f"unsupported harness: {harness}")
    solved = _first(
        value,
        "solved",
        default=outcome.get(
            "solved",
            any(event.get("counted") and event.get("solved") for event in events),
        ),
    )
    if solved is None:
        raise ValueError(f"{value.get('task_id')}: solved outcome is required")
    row = {
        "task_id": str(_required(value, "task_id")),
        "task_class": task_class,
        "domain": str(value.get("domain", "UNKNOWN")),
        "harness": harness,
        "latency_scale_ms": int(
            _required(value, "latency_scale_ms", "model_latency_scale_ms")
        ),
        "wall_budget_ms": int(_required(value, "wall_budget_ms", "budget_ms")),
        "seed": int(_required(value, "seed")),
        "solved": bool(solved),
        "host_measured_floor_ms": _duration_ms(
            value,
            measurements,
            ms_names=("host_measured_floor_ms", "harness_floor_ms"),
            ns_names=("host_measured_harness_floor_ns", "harness_floor_ns"),
        ),
        "measured_verifier_wall_ms": _duration_ms(
            value,
            measurements,
            ms_names=("measured_verifier_wall_ms", "verifier_wall_ms"),
            ns_names=("measured_verifier_wall_ns", "verifier_wall_ns"),
        )
        or _mean_event_duration_ms(events, "verifier_wall_ns"),
        "latency_draw_wall_ms": _duration_ms(
            value,
            measurements,
            ms_names=("latency_draw_wall_ms", "model_latency_wall_ms"),
            ns_names=("latency_draw_wall_ns", "model_latency_wall_ns"),
        )
        or _mean_event_duration_ms(events, "latency_ns", "latency_draw_ns"),
        "predicted_candidates": _optional_float(
            _first(
                value,
                "predicted_candidates",
                "rmax_predicted_candidates",
                "expected_candidates",
            )
        ),
        "actual_candidates": _actual_candidates(value),
        "abandoned_count": _abandoned_count(value),
        "abandonment_tail_ms": _abandonment_tail(value),
        "source_path": artifact.get("_source_path"),
    }
    return row


def _statistical_cells(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    scales = sorted({int(row["latency_scale_ms"]) for row in rows}, reverse=True)
    budgets = sorted({int(row["wall_budget_ms"]) for row in rows})
    results: list[dict[str, Any]] = []
    for population in POPULATIONS:
        for budget in budgets:
            for scale in scales:
                selected = [
                    row
                    for row in rows
                    if int(row["wall_budget_ms"]) == budget
                    and int(row["latency_scale_ms"]) == scale
                    and (population == "ALL" or row["task_class"] == population)
                ]
                for contrast_index, (first_name, second_name) in enumerate(CONTRASTS):
                    pairs = _make_pairs(selected, first_name, second_name)
                    if not pairs:
                        continue
                    stats = analyze_pairs(
                        pairs,
                        bootstrap_resamples=bootstrap_resamples,
                        bootstrap_seed=bootstrap_seed
                        + budget * 1009
                        + scale * 9176
                        + contrast_index * 37
                        + (0 if population == "SCALING" else 1),
                    )
                    results.append(
                        {
                            "population": population,
                            "wall_budget_ms": budget,
                            "latency_scale_ms": scale,
                            "contrast": [first_name, second_name],
                            **stats,
                        }
                    )
    return results


def _make_pairs(
    rows: Sequence[Mapping[str, Any]], first_name: str, second_name: str
) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, int], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        harness = str(row["harness"])
        if harness not in {first_name, second_name}:
            continue
        key = (str(row["task_id"]), int(row["seed"]))
        if harness in by_key[key]:
            raise ValueError(f"duplicate {harness} row for {key[0]}, seed {key[1]}")
        by_key[key][harness] = row
    return [
        {
            "task_id": task_id,
            "seed": seed,
            "first_solved": pair[first_name]["solved"],
            "second_solved": pair[second_name]["solved"],
        }
        for (task_id, seed), pair in sorted(by_key.items())
        if first_name in pair and second_name in pair
    ]


def _domain_primary_rows(
    rows: Sequence[Mapping[str, Any]],
    protocol: Mapping[str, Any],
    *,
    latency_scale_ms: int,
    domain: str | None = None,
    off_tier: bool = False,
) -> list[Mapping[str, Any]]:
    primary = protocol["statistics"]["primary_cell"]
    tiers = protocol["matrix"]["domain_primary_tiers_ms"]
    budgets = {int(value) for value in protocol["matrix"]["wall_budgets_ms"]}
    selected = []
    for row in rows:
        row_domain = str(row["domain"])
        if row_domain not in tiers or (domain is not None and row_domain != domain):
            continue
        primary_budget = int(tiers[row_domain])
        target_budget = (
            sorted(budgets - {primary_budget})[0] if off_tier else primary_budget
        )
        if (
            row["task_class"] == primary["population"]
            and int(row["latency_scale_ms"]) == latency_scale_ms
            and int(row["wall_budget_ms"]) == target_budget
        ):
            selected.append(row)
    return selected


def _analyze_selected(
    rows: Sequence[Mapping[str, Any]],
    *,
    contrast: tuple[str, str],
    bootstrap_resamples: int,
    bootstrap_seed: int,
    metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    first_keys = {
        (str(row["task_id"]), int(row["seed"]))
        for row in rows
        if row["harness"] == contrast[0]
    }
    second_keys = {
        (str(row["task_id"]), int(row["seed"]))
        for row in rows
        if row["harness"] == contrast[1]
    }
    if first_keys != second_keys:
        return None
    pairs = _make_pairs(rows, *contrast)
    if not pairs:
        return None
    return {
        **metadata,
        "contrast": list(contrast),
        **analyze_pairs(
            pairs,
            bootstrap_resamples=bootstrap_resamples,
            bootstrap_seed=bootstrap_seed,
        ),
    }


def _domain_primary_result(
    rows: Sequence[Mapping[str, Any]],
    protocol: Mapping[str, Any],
    *,
    contrast: tuple[str, str],
    latency_scale_ms: int,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> dict[str, Any] | None:
    selected = _domain_primary_rows(
        rows, protocol, latency_scale_ms=latency_scale_ms
    )
    required_domains = set(protocol["statistics"]["primary_cell"]["domains"])
    if {str(row["domain"]) for row in selected} != required_domains:
        return None
    return _analyze_selected(
        selected,
        contrast=contrast,
        bootstrap_resamples=bootstrap_resamples,
        bootstrap_seed=bootstrap_seed,
        metadata={
            "test_id": "primary_pooled_domain_tiers",
            "population": protocol["calibration"]["primary_population"],
            "latency_scale_ms": latency_scale_ms,
            "budget_selection": "domain_primary_tier",
            "domains": list(protocol["statistics"]["primary_cell"]["domains"]),
            "pooling": "pooled_discordant_counts_across_domains",
        },
    )


def _secondary_results(
    rows: Sequence[Mapping[str, Any]],
    protocol: Mapping[str, Any],
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    domains = list(protocol["statistics"]["primary_cell"]["domains"])
    primary_scale = int(protocol["statistics"]["primary_cell"]["latency_scale_ms"])
    control_scale = int(protocol["statistics"]["positive_control"]["latency_scale_ms"])
    tests: list[dict[str, Any]] = []

    def add(
        selected: Sequence[Mapping[str, Any]],
        contrast: tuple[str, str],
        test_id: str,
        **metadata: Any,
    ) -> None:
        result = _analyze_selected(
            selected,
            contrast=contrast,
            bootstrap_resamples=bootstrap_resamples,
            bootstrap_seed=bootstrap_seed + len(tests) * 7919,
            metadata={"test_id": test_id, **metadata},
        )
        if result is not None:
            tests.append(result)

    for domain in domains:
        add(
            _domain_primary_rows(
                rows, protocol, latency_scale_ms=primary_scale, domain=domain
            ),
            ("langgraph", "rust"),
            f"per_domain_primary:{domain}",
            family="per_domain_primary",
            domain=domain,
            latency_scale_ms=primary_scale,
            budget_selection="domain_primary_tier",
        )
    for domain in domains:
        add(
            _domain_primary_rows(
                rows,
                protocol,
                latency_scale_ms=primary_scale,
                domain=domain,
                off_tier=True,
            ),
            ("langgraph", "rust"),
            f"per_domain_off_tier:{domain}",
            family="per_domain_off_tier",
            domain=domain,
            latency_scale_ms=primary_scale,
            budget_selection="domain_off_tier",
        )
    add(
        _domain_primary_rows(rows, protocol, latency_scale_ms=primary_scale),
        ("langgraph", "raw_python"),
        "pooled_primary:langgraph_vs_raw_python",
        family="langgraph_vs_raw_python",
        domain="POOLED",
        latency_scale_ms=primary_scale,
        budget_selection="domain_primary_tier",
    )
    add(
        _domain_primary_rows(rows, protocol, latency_scale_ms=control_scale),
        ("langgraph", "rust"),
        "positive_control:POOLED",
        family="positive_control",
        domain="POOLED",
        latency_scale_ms=control_scale,
        budget_selection="domain_primary_tier",
    )
    for domain in domains:
        add(
            _domain_primary_rows(
                rows, protocol, latency_scale_ms=control_scale, domain=domain
            ),
            ("langgraph", "rust"),
            f"positive_control:{domain}",
            family="positive_control",
            domain=domain,
            latency_scale_ms=control_scale,
            budget_selection="domain_primary_tier",
        )
    _apply_holm(
        tests,
        alpha=float(protocol["statistics"]["primary_alpha"]),
        family_size=17,
    )
    return tests


def _apply_holm(
    tests: Sequence[dict[str, Any]], *, alpha: float, family_size: int
) -> None:
    if len(tests) > family_size:
        raise ValueError("Holm result count exceeds the pre-registered family")
    ordered = sorted(
        enumerate(tests),
        key=lambda item: float(item[1]["mcnemar"]["p_value"]),
    )
    running_adjusted = 0.0
    total = family_size
    for rank, (_, test) in enumerate(ordered, start=1):
        raw = float(test["mcnemar"]["p_value"])
        adjusted = min(1.0, max(running_adjusted, (total - rank + 1) * raw))
        running_adjusted = adjusted
        test["holm"] = {
            "family_size": total,
            "rank": rank,
            "raw_p_value": raw,
            "adjusted_p_value": adjusted,
            "reject": adjusted < alpha,
        }


def _positive_control(
    secondary_results: Sequence[Mapping[str, Any]],
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    scale = int(protocol["statistics"]["positive_control"]["latency_scale_ms"])
    tests = [
        test
        for test in secondary_results
        if test.get("family") == "positive_control"
    ]
    expected_count = 1 + len(protocol["statistics"]["primary_cell"]["domains"])
    failures = [
        {
            "domain": test["domain"],
            "contrast": test["contrast"],
            "raw_p_value": test["mcnemar"]["p_value"],
            "holm_adjusted_p_value": test["holm"]["adjusted_p_value"],
        }
        for test in tests
        if bool(test["holm"]["reject"])
    ]
    return {
        "latency_scale_ms": scale,
        "expected": protocol["statistics"]["positive_control"]["expected"],
        "tests_evaluated": len(tests),
        "tests_expected": expected_count,
        "failures": failures,
        "per_domain": {
            str(test["domain"]): not bool(test["holm"]["reject"])
            for test in tests
            if test["domain"] != "POOLED"
        },
        "pooled_holds": any(
            test["domain"] == "POOLED" and not bool(test["holm"]["reject"])
            for test in tests
        ),
        "holds": len(tests) == expected_count and not failures,
        "failure_action": protocol["statistics"]["positive_control"]["failure_action"],
    }


def _capability_floor_fit(
    rows: Sequence[Mapping[str, Any]], protocol: Mapping[str, Any]
) -> dict[str, Any]:
    primary = protocol["statistics"]["primary_cell"]
    selected = _domain_primary_rows(
        rows,
        protocol,
        latency_scale_ms=int(primary["latency_scale_ms"]),
    )
    points = []
    for harness in HARNESSES:
        arm = [
            row
            for row in selected
            if row["harness"] == harness
            and row.get("host_measured_floor_ms") is not None
        ]
        if not arm:
            continue
        x = sum(float(row["host_measured_floor_ms"]) for row in arm) / len(arm)
        y = 100.0 * sum(bool(row["solved"]) for row in arm) / len(arm)
        points.append({"harness": harness, "floor_ms": x, "solve_rate_pct": y})
    result: dict[str, Any] = {
        "label": "DESCRIPTIVE ONLY, THREE MEASURED X POINTS, NON-INFERENTIAL",
        "points": points,
        "fit": None,
        "residuals": [],
    }
    if len(points) != 3:
        result["reason"] = "requires one host-measured floor point per harness"
        return result
    mean_x = sum(point["floor_ms"] for point in points) / 3.0
    mean_y = sum(point["solve_rate_pct"] for point in points) / 3.0
    sxx = sum((point["floor_ms"] - mean_x) ** 2 for point in points)
    slope = (
        sum(
            (point["floor_ms"] - mean_x) * (point["solve_rate_pct"] - mean_y)
            for point in points
        )
        / sxx
        if sxx
        else 0.0
    )
    intercept = mean_y - slope * mean_x
    residuals = [
        {
            "harness": point["harness"],
            "residual_pp": point["solve_rate_pct"]
            - (intercept + slope * point["floor_ms"]),
        }
        for point in points
    ]
    result["fit"] = {
        "intercept_pp": intercept,
        "slope_pp_per_ms": slope,
        "n_x_points": 3,
    }
    result["residuals"] = residuals
    return result


def _aggregate_gates(
    artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for gate_name in (f"G{index}" for index in range(1, 9)):
        observations = []
        errors: list[str] = []
        for artifact in artifacts:
            sources = [artifact]
            nested = list(_runs(artifact))
            if not (len(nested) == 1 and nested[0] is artifact):
                sources.extend(nested)
            for source in sources:
                audit = _mapping(source.get("audit"))
                gates = _mapping(
                    _first(
                        audit,
                        "gates",
                        default=(
                            source.get("gates")
                            if source.get("gates") is not None
                            else audit
                        ),
                    )
                )
                gate = gates.get(gate_name)
                if isinstance(gate, Mapping):
                    observations.append(bool(gate.get("pass")))
                    errors.extend(str(item) for item in gate.get("errors") or [])
                elif isinstance(gate, bool):
                    observations.append(gate)
        result[gate_name] = {
            "evaluated": bool(observations),
            "pass": bool(observations) and all(observations),
            "observations": len(observations),
            "errors": errors,
        }
    return result


def _classification_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    classes: dict[str, tuple[str, str]] = {}
    for row in rows:
        task_id = str(row["task_id"])
        task_class = str(row["task_class"])
        domain = str(row["domain"])
        if task_id in classes and classes[task_id] != (domain, task_class):
            raise ValueError(f"inconsistent classification for task {task_id}")
        classes[task_id] = (domain, task_class)
    counts = Counter(task_class for _, task_class in classes.values())
    domains = sorted({domain for domain, _ in classes.values()})
    return {
        "SCALING": counts["SCALING"],
        "SATURATED": counts["SATURATED"],
        "DEAD": counts["DEAD"],
        "ALL": len(classes),
        "by_domain": {
            domain: {
                "SCALING": sum(
                    item_domain == domain and task_class == "SCALING"
                    for item_domain, task_class in classes.values()
                ),
                "SATURATED": sum(
                    item_domain == domain and task_class == "SATURATED"
                    for item_domain, task_class in classes.values()
                ),
                "DEAD": sum(
                    item_domain == domain and task_class == "DEAD"
                    for item_domain, task_class in classes.values()
                ),
                "ALL": sum(
                    item_domain == domain for item_domain, _ in classes.values()
                ),
            }
            for domain in domains
        },
    }


def _abandonment_tails(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, int], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row["harness"]),
                int(row["latency_scale_ms"]),
                int(row["wall_budget_ms"]),
            )
        ].append(row)
    summaries = []
    for (harness, scale, budget), group in sorted(grouped.items()):
        tails = sorted(
            float(value)
            for row in group
            for value in row.get("abandonment_tail_ms") or []
        )
        actual = sum(int(row.get("actual_candidates") or 0) for row in group)
        abandoned = sum(int(row.get("abandoned_count") or 0) for row in group)
        summaries.append(
            {
                "harness": harness,
                "latency_scale_ms": scale,
                "wall_budget_ms": budget,
                "abandoned_candidates": abandoned,
                "started_candidates": actual,
                "abandoned_fraction": abandoned / actual if actual else 0.0,
                "tail_p95_ms": _quantile(tails, 0.95) if tails else None,
                "tail_max_ms": max(tails) if tails else None,
            }
        )
    return summaries


def _expectation_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, int], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row["harness"]),
                int(row["latency_scale_ms"]),
                int(row["wall_budget_ms"]),
            )
        ].append(row)
    output = []
    for (harness, scale, budget), group in sorted(grouped.items()):
        actual_values = [
            float(row["actual_candidates"])
            for row in group
            if row.get("actual_candidates") is not None
        ]
        predicted = []
        for row in group:
            direct_prediction = row.get("predicted_candidates")
            if direct_prediction is not None:
                predicted.append(float(direct_prediction))
                continue
            floor = row.get("host_measured_floor_ms")
            verifier = row.get("measured_verifier_wall_ms")
            if floor is None or verifier is None:
                continue
            latency = row.get("latency_draw_wall_ms")
            denominator = (
                float(latency) if latency is not None else scale
            ) + float(floor) + float(verifier)
            if denominator > 0:
                predicted.append(budget / denominator)
        actual = sum(actual_values) / len(actual_values) if actual_values else None
        expectation = sum(predicted) / len(predicted) if predicted else None
        output.append(
            {
                "harness": harness,
                "latency_scale_ms": scale,
                "wall_budget_ms": budget,
                "actual_candidates_mean": actual,
                "predicted_candidates_mean": expectation,
                "actual_over_predicted": (
                    actual / expectation
                    if actual is not None and expectation not in (None, 0.0)
                    else None
                ),
                "prediction_terms": [
                    "latency_draw_wall",
                    "host_measured_harness_floor",
                    "measured_verifier_wall",
                ],
            }
        )
    return output


def _throughput_clipping_confirmed(
    expectations: Sequence[Mapping[str, Any]],
    protocol: Mapping[str, Any],
) -> bool:
    evaluable = [
        item
        for item in expectations
        if item["actual_candidates_mean"] is not None
        and item["predicted_candidates_mean"] is not None
    ]
    tolerance = float(protocol["gates"]["G7"]["relative_tolerance"])
    return bool(evaluable) and all(
        float(item["actual_candidates_mean"])
        <= (1.0 + tolerance) * float(item["predicted_candidates_mean"])
        for item in evaluable
    )


def _select_claim_rung(
    primary: Mapping[str, Any] | None,
    secondary_results: Sequence[Mapping[str, Any]],
    gates: Mapping[str, Mapping[str, Any]],
    positive_control: Mapping[str, Any],
    throughput_clipping: bool,
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    alpha = float(protocol["statistics"]["primary_alpha"])
    primary_significant = bool(
        primary
        and float(primary["mcnemar"]["p_value"]) < alpha
        and float(primary["difference_pp"]) < 0.0
    )
    seed_sign_ok = bool(
        primary
        and primary["seed_sensitivity"]["leave_one_seed_out_preserves_sign"]
    )
    clean = all(bool(gates[name]["pass"]) for name in ("G3", "G6", "G7"))
    significant = [
        cell
        for cell in secondary_results
        if cell.get("family") != "positive_control"
        and bool((cell.get("holm") or {}).get("reject"))
        and float(cell["difference_pp"]) < 0.0
    ]
    if primary_significant and seed_sign_ok and positive_control["holds"] and clean:
        name = "rung_1"
    else:
        families = {str(cell.get("family")) for cell in significant}
        only_raw = bool(significant) and all(
            cell["contrast"] == ["langgraph", "raw_python"] for cell in significant
        )
        if significant and (len(families) == 1 or only_raw):
            name = "rung_2"
        elif not significant and throughput_clipping:
            name = "rung_3"
        else:
            name = "unearned"
    return {
        "name": name,
        "protocol_language": (
            protocol["claim_ladder"].get(name)
            if name != "unearned"
            else "No CAP-01 claim rung earned."
        ),
        "primary_significant_predicted_direction": primary_significant,
        "leave_one_seed_out_preserves_sign": seed_sign_ok,
        "positive_control_holds": bool(positive_control["holds"]),
        "G3_G6_G7_clean": clean,
        "throughput_clipping_confirmed": throughput_clipping,
    }


def _promotion_summary(
    claim: Mapping[str, Any], positive_control: Mapping[str, Any]
) -> str:
    if not positive_control["holds"]:
        return (
            "Headline blocked. The 4000ms positive-control null failed; stop before "
            "a capability headline and diagnose the harness separation."
        )
    if claim["name"] == "rung_1":
        return (
            "CAP-01 rung 1 earned within the frozen primary scope: "
            "5ms model latency, each domain at its frozen primary resource tier, "
            "SCALING tasks pooled across five domains, LangGraph versus rust."
        )
    if claim["name"] == "rung_2":
        return "CAP-01 rung 2 earned: report only the observed scoped gap."
    if claim["name"] == "rung_3":
        return (
            "CAP-01 rung 3 earned: no significant separation; throughput clipping "
            "is confirmed."
        )
    return "No CAP-01 promotion claim is licensed by this aggregate."


def _figure_data(
    rows: Sequence[Mapping[str, Any]], protocol: Mapping[str, Any]
) -> dict[str, Any]:
    primary = protocol["statistics"]["primary_cell"]
    selected = [
        row
        for scale in protocol["latency_backend"]["median_scales_ms"]
        for row in _domain_primary_rows(
            rows,
            protocol,
            latency_scale_ms=int(scale),
        )
    ]
    curves = []
    for harness in HARNESSES:
        arm = [row for row in selected if row["harness"] == harness]
        for scale in sorted({int(row["latency_scale_ms"]) for row in arm}):
            at_scale = [row for row in arm if int(row["latency_scale_ms"]) == scale]
            curves.append(
                {
                    "harness": harness,
                    "latency_scale_ms": scale,
                    "solve_rate_pct": 100.0
                    * sum(bool(row["solved"]) for row in at_scale)
                    / len(at_scale),
                }
            )
    return {
        "solve_rate_curves": curves,
        "capability_floor_points": _capability_floor_fit(rows, protocol)["points"],
        "projection_label": protocol["projection"]["required_label"],
        "projection_target_floor_us": protocol["projection"]["target_floor_us"],
    }


def _validate_unique_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    seen = set()
    for row in rows:
        key = (
            row["task_id"],
            row["harness"],
            row["latency_scale_ms"],
            row["wall_budget_ms"],
            row["seed"],
        )
        if key in seen:
            raise ValueError(f"duplicate task-cell row: {key}")
        seen.add(key)


def _actual_candidates(value: Mapping[str, Any]) -> int | None:
    direct = _first(
        value,
        "actual_candidates",
        "started",
        "candidates_started",
        "started_candidates",
        "candidate_count",
    )
    if direct is not None:
        return int(direct)
    events = value.get("candidate_events")
    return len(events) if isinstance(events, list) else None


def _abandoned_count(value: Mapping[str, Any]) -> int:
    direct = _first(
        value, "abandoned_count", "abandoned", "candidates_abandoned"
    )
    if direct is not None:
        return int(direct)
    events = value.get("candidate_events")
    if isinstance(events, list):
        return sum(
            bool(event.get("abandoned"))
            for event in events
            if isinstance(event, Mapping)
        )
    return 0


def _abandonment_tail(value: Mapping[str, Any]) -> list[float]:
    direct = value.get("abandonment_tail_ms")
    if isinstance(direct, list):
        return [float(item) for item in direct]
    if direct is not None:
        return [float(direct)]
    events = value.get("candidate_events")
    if not isinstance(events, list):
        return []
    tails = []
    for event in events:
        if not isinstance(event, Mapping) or not event.get("abandoned"):
            continue
        tail = _first(event, "abandonment_tail_ms", "elapsed_after_deadline_ms")
        if tail is None:
            deadline_ns = value.get("deadline_ns")
            started_ns = event.get("started_ns")
            latency_ns = event.get("latency_ns")
            if all(
                isinstance(item, (int, float))
                for item in (deadline_ns, started_ns, latency_ns)
            ):
                tail = max(
                    0.0,
                    (
                        float(started_ns)
                        + float(latency_ns)
                        - float(deadline_ns)
                    )
                    / 1_000_000.0,
                )
        if tail is not None:
            tails.append(float(tail))
    return tails


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(
    value: Mapping[str, Any], *names: str, default: Any = None
) -> Any:
    for name in names:
        if name in value and value[name] is not None:
            return value[name]
    return default


def _required(value: Mapping[str, Any], *names: str) -> Any:
    result = _first(value, *names)
    if result is None:
        raise ValueError(f"required field missing: {' or '.join(names)}")
    return result


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _duration_ms(
    value: Mapping[str, Any],
    measurements: Mapping[str, Any],
    *,
    ms_names: Sequence[str],
    ns_names: Sequence[str],
) -> float | None:
    milliseconds = _first(
        value,
        *ms_names,
        default=_first(measurements, *ms_names),
    )
    if milliseconds is not None:
        return float(milliseconds)
    nanoseconds = _first(
        value,
        *ns_names,
        default=_first(measurements, *ns_names),
    )
    return float(nanoseconds) / 1_000_000.0 if nanoseconds is not None else None


def _candidate_events(value: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    events = value.get("candidate_events", value.get("events"))
    if not isinstance(events, list):
        return []
    return [event for event in events if isinstance(event, Mapping)]


def _mean_event_duration_ms(
    events: Sequence[Mapping[str, Any]], *names: str
) -> float | None:
    values = [
        float(duration)
        for event in events
        if event.get("counted")
        for duration in [_first(event, *names)]
        if duration is not None
    ]
    return sum(values) / len(values) / 1_000_000.0 if values else None


def _looks_like_task_cell(value: Mapping[str, Any]) -> bool:
    coordinates = _mapping(value.get("coordinates"))
    merged = {**coordinates, **value}
    return (
        merged.get("task_id") is not None
        and merged.get("harness") is not None
        and merged.get("latency_scale_ms") is not None
        and merged.get("wall_budget_ms") is not None
        and merged.get("seed") is not None
        and (
            merged.get("solved") is not None
            or isinstance(merged.get("candidate_events"), list)
            or isinstance(merged.get("events"), list)
        )
    )


def _all_classifications(
    artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for artifact in artifacts:
        direct = _mapping(
            _first(artifact, "classifications", "task_classifications")
        )
        for task_id, raw in direct.items():
            classification = (
                _first(raw, "population", "task_class", "classification")
                if isinstance(raw, Mapping)
                else raw
            )
            if classification is not None:
                result[str(task_id)] = str(classification).upper()
        tasks = artifact.get("tasks")
        if isinstance(tasks, list):
            for task in tasks:
                if not isinstance(task, Mapping) or task.get("task_id") is None:
                    continue
                classification = _first(
                    task, "population", "task_class", "classification"
                )
                if classification is not None:
                    result[str(task["task_id"])] = str(classification).upper()
    return result


def _floor_measurements_ms(
    artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for artifact in artifacts:
        direct = _mapping(
            _first(artifact, "floor_measurements_ns", "host_measured_floors_ns")
        )
        for harness, value in direct.items():
            result[str(harness)] = float(value) / 1_000_000.0
        gates = _mapping(_mapping(artifact.get("audit")).get("gates"))
        if not gates:
            gates = _mapping(artifact.get("gates"))
        g6 = _mapping(gates.get("G6"))
        for harness, details in _mapping(g6.get("harnesses")).items():
            if not isinstance(details, Mapping):
                continue
            value = _first(
                details,
                "x_coordinate_ns",
                "measured_floor_ns",
            )
            if value is not None:
                result[str(harness)] = float(value) / 1_000_000.0
    return result


def _removed_task_ids(
    artifacts: Sequence[Mapping[str, Any]],
) -> set[str]:
    removed: set[str] = set()
    for artifact in artifacts:
        audit = _mapping(artifact.get("audit"))
        for value in (
            artifact.get("removed_task_ids"),
            audit.get("removed_task_ids"),
        ):
            if isinstance(value, list):
                removed.update(str(item) for item in value)
    return removed


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot take quantile of no values")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--bootstrap-resamples", type=int, default=DEFAULT_BOOTSTRAP_RESAMPLES
    )
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    args = parser.parse_args()
    aggregate = analyze_artifacts(
        load_task_cell_runs(args.inputs),
        bootstrap_resamples=args.bootstrap_resamples,
        bootstrap_seed=args.bootstrap_seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
