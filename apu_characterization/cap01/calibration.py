"""Deterministic 50-shuffle task calibration for CAP-01."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Collection, Mapping, Sequence

from .contracts import CandidateRecord, PoolMetadata, TaskClass, sha256_json

CorrectnessSource = (
    Mapping[str, bool]
    | Collection[str]
    | Sequence[bool]
    | Callable[[CandidateRecord], bool]
)


@dataclass(frozen=True)
class CalibrationResult:
    task_id: str
    task_class: TaskClass
    shuffles: int
    saturated_n: int
    dead_n: int
    legacy_dead_n: int
    solved_probability_n4: float
    solved_probability_n2048: float
    solved_probability_n128: float
    legacy_dead_at_128: bool
    secondary_labels: tuple[str, ...]
    pool_sha256: str
    correctness_sha256: str
    digest: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _correctness_lookup(
    pool: PoolMetadata,
    source: CorrectnessSource,
) -> tuple[bool, ...]:
    if callable(source):
        return tuple(bool(source(candidate)) for candidate in pool.candidates)
    if isinstance(source, Mapping):
        missing = [
            candidate.candidate_id
            for candidate in pool.candidates
            if candidate.candidate_id not in source
        ]
        if missing:
            raise ValueError(f"correctness mapping is missing {len(missing)} candidates")
        return tuple(bool(source[candidate.candidate_id]) for candidate in pool.candidates)
    if isinstance(source, (set, frozenset)):
        return tuple(candidate.candidate_id in source for candidate in pool.candidates)
    values = tuple(source)
    if len(values) == len(pool.candidates) and all(
        isinstance(item, bool) for item in values
    ):
        return values
    solved_ids = set(values)
    if not all(isinstance(item, str) for item in solved_ids):
        raise ValueError("correctness must be booleans or solved candidate IDs")
    return tuple(candidate.candidate_id in solved_ids for candidate in pool.candidates)


def solved_probability(
    pool: PoolMetadata,
    correctness: Sequence[bool],
    n: int,
    *,
    shuffles: int = 50,
) -> float:
    """Estimate P(solved by N) over deterministic seeded pool shuffles."""
    if shuffles < 1:
        raise ValueError("shuffles must be positive")
    if n < 1 or n > len(pool.candidates):
        raise ValueError(f"N={n} is outside pool size {len(pool.candidates)}")
    if len(correctness) != len(pool.candidates):
        raise ValueError("correctness length does not match pool")
    solved = 0
    for seed in range(shuffles):
        order = pool.seed_order(seed)
        solved += any(correctness[index] for index in order[:n])
    return solved / shuffles


def classify_probabilities(
    probability_n4: float,
    probability_n2048: float,
) -> TaskClass:
    """Apply the frozen primary classification thresholds."""
    if probability_n4 > 0.9:
        return "SATURATED"
    if probability_n2048 < 0.05:
        return "DEAD"
    return "SCALING"


def calibrate_pool(
    pool: PoolMetadata,
    correctness: CorrectnessSource,
    *,
    shuffles: int = 50,
    saturated_n: int = 4,
    dead_n: int = 2048,
    legacy_dead_n: int = 128,
) -> CalibrationResult:
    """Classify one task and retain the legacy DEAD@128 context label."""
    if (shuffles, saturated_n, dead_n, legacy_dead_n) != (50, 4, 2048, 128):
        raise ValueError("CAP-01 calibration coordinates are frozen")
    pool.validate(dead_n)
    truth = _correctness_lookup(pool, correctness)
    probability_n4 = solved_probability(
        pool, truth, saturated_n, shuffles=shuffles
    )
    probability_n2048 = solved_probability(
        pool, truth, dead_n, shuffles=shuffles
    )
    probability_n128 = solved_probability(
        pool, truth, legacy_dead_n, shuffles=shuffles
    )
    task_class = classify_probabilities(probability_n4, probability_n2048)
    legacy_dead = probability_n128 < 0.05
    labels = ("DEAD@128",) if legacy_dead else ()
    correctness_hash = sha256_json(
        [
            {
                "candidate_id": candidate.candidate_id,
                "solved": truth[index],
            }
            for index, candidate in enumerate(pool.candidates)
        ]
    )
    payload = {
        "task_id": pool.task_id,
        "task_class": task_class,
        "shuffles": shuffles,
        "saturated_n": saturated_n,
        "dead_n": dead_n,
        "legacy_dead_n": legacy_dead_n,
        "solved_probability_n4": probability_n4,
        "solved_probability_n2048": probability_n2048,
        "solved_probability_n128": probability_n128,
        "legacy_dead_at_128": legacy_dead,
        "secondary_labels": labels,
        "pool_sha256": pool.pool_sha256(),
        "correctness_sha256": correctness_hash,
    }
    return CalibrationResult(**payload, digest=sha256_json(payload))


def classification_manifest(results: Sequence[CalibrationResult]) -> dict[str, object]:
    """Build a deterministic manifest ordered by task ID."""
    records = [result.to_dict() for result in sorted(results, key=lambda item: item.task_id)]
    return {
        "shuffles": 50,
        "tasks": records,
        "classification_manifest_sha256": sha256_json(records),
    }
