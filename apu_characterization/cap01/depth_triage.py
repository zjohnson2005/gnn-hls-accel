"""CAP-01 depth-triage policy and Axis-2 degeneracy helpers (protocol v2.2).

Frozen before full-corpus triage results are read against the rule.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping, Sequence

# Frozen thresholds (Stage-1 informed; Stage-2 table not yet applied).
TRIAGE_CANDIDATES = 16
UPPER_PHAT = 0.90
LOWER_PHAT = 0.02
CONFIRMATION_POOL_DEPTH = 256
SCALING_POOL_DEPTH = 2048
INCORRECT_DUPLICATE_RATE_MAX = 0.20

# Domains whose pinned verifier cannot execute on the current host sandbox
# must not be depth-reduced from triage (false DEAD risk). Cleared after
# CODE gold self-check PASS on host (died-ledger #11).
VERIFIER_BLOCKED_DOMAINS: frozenset[str] = frozenset()


def triage_band(phat: float, *, n: int) -> str:
    """Map probe p̂ to a generation-depth band. Not a frozen classification."""
    if n < TRIAGE_CANDIDATES:
        return "indeterminate_shallow_probe"
    if phat >= UPPER_PHAT:
        return "probable_SATURATED"
    if phat <= LOWER_PHAT:
        return "probable_DEAD"
    return "SCALING_band"


def generation_depth_for_band(band: str, *, domain: str) -> int:
    if domain in VERIFIER_BLOCKED_DOMAINS:
        return SCALING_POOL_DEPTH
    if band in {"probable_SATURATED", "probable_DEAD"}:
        return CONFIRMATION_POOL_DEPTH
    return SCALING_POOL_DEPTH


def incorrect_duplicate_rate(
    contents: Sequence[str],
    solved: Sequence[bool],
) -> float:
    """Duplicate rate over incorrect candidates only (Axis-2 retarget (a))."""
    if len(contents) != len(solved):
        raise ValueError("contents and solved must align")
    incorrect = [content for content, ok in zip(contents, solved) if not ok]
    if len(incorrect) < 2:
        return 0.0
    return 1.0 - (len(set(incorrect)) / len(incorrect))


def cross_task_identical_contents(
    task_contents: Mapping[str, Sequence[str]],
) -> dict[str, list[str]]:
    """Map content → task_ids when the same string appears across tasks (b)."""
    inverted: dict[str, set[str]] = defaultdict(set)
    for task_id, contents in task_contents.items():
        for content in contents:
            if content.strip():
                inverted[content].add(task_id)
    return {
        content: sorted(task_ids)
        for content, task_ids in inverted.items()
        if len(task_ids) > 1
    }


def axis2_degeneracy_failures(
    *,
    task_contents: Mapping[str, Sequence[str]],
    task_solved: Mapping[str, Sequence[bool]] | None = None,
    incorrect_duplicate_max: float = INCORRECT_DUPLICATE_RATE_MAX,
) -> list[str]:
    """Return Axis-2 failure strings under the retargeted degeneracy definition."""
    failures: list[str] = []
    cross = cross_task_identical_contents(task_contents)
    if cross:
        sample = next(iter(cross.items()))
        failures.append(
            "cross_task_identical_outputs: "
            f"{len(cross)} shared strings; e.g. task_ids={sample[1][:4]}"
        )
    if task_solved is not None:
        for task_id, contents in task_contents.items():
            solved = task_solved.get(task_id)
            if solved is None:
                continue
            rate = incorrect_duplicate_rate(contents, solved)
            if rate >= incorrect_duplicate_max:
                failures.append(
                    f"{task_id}: incorrect_duplicate_rate {rate:.3f} "
                    f">= {incorrect_duplicate_max}"
                )
    return failures


def depth_triage_policy_dict() -> dict[str, object]:
    return {
        "protocol_amendment": "cap01_v2.2_depth_triage",
        "triage_candidates": TRIAGE_CANDIDATES,
        "upper_phat": UPPER_PHAT,
        "lower_phat": LOWER_PHAT,
        "confirmation_pool_depth": CONFIRMATION_POOL_DEPTH,
        "scaling_pool_depth": SCALING_POOL_DEPTH,
        "verifier_blocked_domains_full_depth": sorted(VERIFIER_BLOCKED_DOMAINS),
        "classification_error_disclosure": (
            "Triage-by-probe has a classification error rate; true-SCALING tasks "
            "near thresholds can draw extreme probe results and receive shallow "
            "pools. Mitigations: conservative thresholds, 256-not-zero confirmation "
            "pools, and calibration-time reclassification with top-up to 2048 if "
            "a confirmation-pool task flips to SCALING."
        ),
        "calibration_escape_hatch": {
            "rule": (
                "Any confirmation-pool task whose calibration curve contradicts "
                "its triage band is flagged; if the class flips to SCALING, top "
                "the pool up to scaling_pool_depth before classification freezes."
            ),
            "bounded_second_spend": True,
        },
        "axis2_degeneracy": {
            "incorrect_duplicate_rate_max": INCORRECT_DUPLICATE_RATE_MAX,
            "definition": (
                "Degenerate generation = (a) incorrect-only duplicate rate "
                "exceeding threshold, or (b) cross-task identical outputs. "
                "Convergent CORRECT answers on a single task are excluded."
            ),
        },
        "stage1_informed_disclosure": (
            "Thresholds informed by Stage-1 probe verification "
            "(MATH-001 confidently-wrong identical; MATH-010 probable-SATURATED; "
            "MATH-025 intermediate). Full-corpus Stage-2 table was not read "
            "before this rule froze."
        ),
    }
