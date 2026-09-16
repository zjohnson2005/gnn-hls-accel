"""Dependency-free paired statistics for CAP-01."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from statistics import NormalDist
from typing import Any, Mapping, Sequence

DEFAULT_BOOTSTRAP_RESAMPLES = 10_000
DEFAULT_BOOTSTRAP_SEED = 0xCA_01


def mcnemar_exact_two_sided(
    first: Sequence[bool], second: Sequence[bool]
) -> dict[str, Any]:
    """Return the exact, two-sided McNemar test for paired binary outcomes."""
    if len(first) != len(second):
        raise ValueError("McNemar inputs must have equal length")
    first_only = sum(bool(a) and not bool(b) for a, b in zip(first, second))
    second_only = sum(not bool(a) and bool(b) for a, b in zip(first, second))
    discordant = first_only + second_only
    if discordant == 0:
        p_value = 1.0
    else:
        lower = min(first_only, second_only)
        tail = sum(math.comb(discordant, k) for k in range(lower + 1))
        p_value = min(1.0, 2.0 * tail / (2**discordant))
    return {
        "first_only": first_only,
        "second_only": second_only,
        "discordant": discordant,
        "p_value": p_value,
        "method": "mcnemar_exact_two_sided",
    }


def paired_solve_rate_difference_pp(
    first: Sequence[bool], second: Sequence[bool]
) -> float:
    """Return first minus second solve rate in percentage points."""
    if len(first) != len(second):
        raise ValueError("paired outcomes must have equal length")
    if not first:
        raise ValueError("paired outcomes cannot be empty")
    return 100.0 * (
        sum(bool(value) for value in first) - sum(bool(value) for value in second)
    ) / len(first)


def clustered_bca_interval(
    pairs: Sequence[Mapping[str, Any]],
    *,
    confidence: float = 0.95,
    resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    random_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Task-clustered BCa interval for the paired solve-rate difference.

    Every selected task contributes all of its seed observations. Repeated
    bootstrap task draws repeat the complete cluster.
    """
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between zero and one")
    clusters = _clusters(pairs)
    task_ids = sorted(clusters)
    if not task_ids:
        raise ValueError("at least one paired task is required")

    observed = _difference_from_rows(
        [row for task_id in task_ids for row in clusters[task_id]]
    )
    rng = random.Random(random_seed)
    bootstrap: list[float] = []
    for _ in range(resamples):
        rows: list[Mapping[str, Any]] = []
        for _draw in task_ids:
            rows.extend(clusters[rng.choice(task_ids)])
        bootstrap.append(_difference_from_rows(rows))

    less = sum(value < observed for value in bootstrap)
    equal = sum(value == observed for value in bootstrap)
    probability = (less + 0.5 * equal) / resamples
    epsilon = 0.5 / resamples
    z0 = NormalDist().inv_cdf(min(1.0 - epsilon, max(epsilon, probability)))

    jackknife = []
    if len(task_ids) > 1:
        for omitted in task_ids:
            jackknife.append(
                _difference_from_rows(
                    [
                        row
                        for task_id in task_ids
                        if task_id != omitted
                        for row in clusters[task_id]
                    ]
                )
            )
    acceleration = _jackknife_acceleration(jackknife)
    alpha = (1.0 - confidence) / 2.0
    low_probability = _bca_probability(alpha, z0, acceleration)
    high_probability = _bca_probability(1.0 - alpha, z0, acceleration)
    ordered = sorted(bootstrap)
    return {
        "low_pp": _quantile(ordered, low_probability),
        "high_pp": _quantile(ordered, high_probability),
        "confidence": confidence,
        "method": "BCa",
        "resamples": resamples,
        "unit": "task",
        "random_seed": random_seed,
        "bias_correction": z0,
        "acceleration": acceleration,
    }


def seed_sensitivity(pairs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize per-seed effects and leave-one-seed-out sign stability."""
    by_seed: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in pairs:
        by_seed[int(row["seed"])].append(row)
    if not by_seed:
        raise ValueError("at least one paired observation is required")
    overall = _difference_from_rows(pairs)
    per_seed = {
        str(seed): _difference_from_rows(rows)
        for seed, rows in sorted(by_seed.items())
    }
    leave_one_out: dict[str, float | None] = {}
    for omitted in sorted(by_seed):
        retained = [
            row
            for seed, rows in by_seed.items()
            if seed != omitted
            for row in rows
        ]
        leave_one_out[str(omitted)] = (
            _difference_from_rows(retained) if retained else None
        )
    sign = _sign(overall)
    preserves = sign != 0 and all(
        value is not None and _sign(value) == sign
        for value in leave_one_out.values()
    )
    return {
        "overall_difference_pp": overall,
        "per_seed_difference_pp": per_seed,
        "leave_one_seed_out_difference_pp": leave_one_out,
        "leave_one_seed_out_preserves_sign": preserves,
    }


def analyze_pairs(
    pairs: Sequence[Mapping[str, Any]],
    *,
    bootstrap_resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Compute the complete CAP-01 paired statistical summary."""
    first = [bool(row["first_solved"]) for row in pairs]
    second = [bool(row["second_solved"]) for row in pairs]
    if not first:
        raise ValueError("at least one paired observation is required")
    return {
        "n_task_seed_pairs": len(pairs),
        "n_tasks": len({str(row["task_id"]) for row in pairs}),
        "n_seeds": len({int(row["seed"]) for row in pairs}),
        "first_solve_rate": sum(first) / len(first),
        "second_solve_rate": sum(second) / len(second),
        "difference_pp": paired_solve_rate_difference_pp(first, second),
        "mcnemar": mcnemar_exact_two_sided(first, second),
        "bca_ci": clustered_bca_interval(
            pairs,
            resamples=bootstrap_resamples,
            random_seed=bootstrap_seed,
        ),
        "seed_sensitivity": seed_sensitivity(pairs),
    }


def _clusters(
    pairs: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    clusters: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, int]] = set()
    for row in pairs:
        task_id = str(row["task_id"])
        seed = int(row["seed"])
        key = (task_id, seed)
        if key in seen:
            raise ValueError(f"duplicate paired observation for {task_id}, seed {seed}")
        seen.add(key)
        clusters[task_id].append(row)
    return dict(clusters)


def _difference_from_rows(rows: Sequence[Mapping[str, Any]]) -> float:
    if not rows:
        raise ValueError("cannot compute an effect from no observations")
    return 100.0 * sum(
        int(bool(row["first_solved"])) - int(bool(row["second_solved"]))
        for row in rows
    ) / len(rows)


def _jackknife_acceleration(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    differences = [mean - value for value in values]
    denominator = 6.0 * sum(value * value for value in differences) ** 1.5
    if denominator == 0.0:
        return 0.0
    return sum(value**3 for value in differences) / denominator


def _bca_probability(alpha: float, z0: float, acceleration: float) -> float:
    z_alpha = NormalDist().inv_cdf(alpha)
    denominator = 1.0 - acceleration * (z0 + z_alpha)
    if denominator == 0.0:
        adjusted = -math.inf if z0 + z_alpha < 0 else math.inf
    else:
        adjusted = z0 + (z0 + z_alpha) / denominator
    return min(1.0, max(0.0, NormalDist().cdf(adjusted)))


def _quantile(ordered: Sequence[float], probability: float) -> float:
    if not ordered:
        raise ValueError("cannot take a quantile of no values")
    if len(ordered) == 1:
        return float(ordered[0])
    position = min(1.0, max(0.0, probability)) * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction)


def _sign(value: float) -> int:
    return (value > 0.0) - (value < 0.0)
