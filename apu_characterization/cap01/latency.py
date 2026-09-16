"""Deterministic wall-only latency plans for CAP-01."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable

from .contracts import PROTOCOL_VERSION, canonical_json_bytes, stable_seed

LOGNORMAL_SIGMA = 0.6


def latency_draw_ns(
    task_id: str,
    seed: int,
    ordinal: int,
    median_scale_ms: float,
    *,
    sigma: float = LOGNORMAL_SIGMA,
) -> int:
    """Return one deterministic lognormal draw, rounded to integer nanoseconds.

    A draw is coordinate-addressed instead of depending on mutable RNG state.
    Harnesses therefore receive the same value even when one stops early.
    """
    if not task_id:
        raise ValueError("task_id is required")
    if ordinal < 0:
        raise ValueError("ordinal cannot be negative")
    if median_scale_ms < 0:
        raise ValueError("median_scale_ms cannot be negative")
    if sigma < 0:
        raise ValueError("sigma cannot be negative")
    if median_scale_ms == 0:
        return 0
    rng = random.Random(
        stable_seed(PROTOCOL_VERSION, "latency", task_id, int(seed), int(ordinal))
    )
    multiplier = math.exp(sigma * rng.normalvariate(0.0, 1.0))
    return max(0, int(round(median_scale_ms * 1_000_000.0 * multiplier)))


@dataclass(frozen=True)
class LatencyPlan:
    task_id: str
    seed: int
    median_scale_ms: float
    draws_ns: tuple[int, ...]
    sigma: float = LOGNORMAL_SIGMA

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(
            {
                "draws_ns": list(self.draws_ns),
                "median_scale_ms": self.median_scale_ms,
                "seed": self.seed,
                "sigma": self.sigma,
                "task_id": self.task_id,
            }
        )


def make_latency_plan(
    task_id: str,
    seed: int,
    median_scale_ms: float,
    count: int,
    *,
    sigma: float = LOGNORMAL_SIGMA,
) -> LatencyPlan:
    if count < 0:
        raise ValueError("count cannot be negative")
    return LatencyPlan(
        task_id=task_id,
        seed=int(seed),
        median_scale_ms=median_scale_ms,
        sigma=sigma,
        draws_ns=tuple(
            latency_draw_ns(task_id, seed, ordinal, median_scale_ms, sigma=sigma)
            for ordinal in range(count)
        ),
    )


def encode_execution_plan(
    task_id: str,
    seed: int,
    candidate_ids: Iterable[str],
    latency_ns: Iterable[int],
) -> bytes:
    """Encode the exact order and waits consumed by every harness."""
    ids = tuple(candidate_ids)
    waits = tuple(int(value) for value in latency_ns)
    if len(ids) != len(waits):
        raise ValueError("candidate and latency plan lengths differ")
    return canonical_json_bytes(
        {
            "candidates": [
                {"candidate_id": candidate_id, "latency_ns": wait_ns}
                for candidate_id, wait_ns in zip(ids, waits)
            ],
            "seed": int(seed),
            "task_id": task_id,
        }
    )
