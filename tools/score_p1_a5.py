"""Score sealed P1 A5 (both halves of seed 20260930) against amendment 7.

Reads only the sealed point files. Does not open any amendment file; the
registered numbers are copied here with their source. Does not start a
measurement. Writes derived/p1_quality/analysis/A5_SCORE.json with --write.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from math import comb
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
A0_ID = "8a529053-fc47-486d-8809-6c699d156b06"
HALVES = (
    ("lexicographic [:100]", "e31a0a89-862e-444a-b197-0c8d61cbb0e1"),
    ("lexicographic [100:200]", "824cad12-662f-485d-a832-0f7f25ee4dcd"),
)
SEED = 20260930
# Amendment 7, predictions.A5.in_budget_passes_per_seed
# (sha256 fc58a6abb1c253ceabf01483e0ff3186247716c939c3c86866c37c3a7ce15983).
PRED_LOW = 23
PRED_HIGH = 28.06
RULE = (
    "MATCH when the seed's in-budget passes on 200 entries lie in [23, 28.06] "
    "(amendment 7 in_budget_passes_per_seed low/high); otherwise MISS."
)
OUT = ROOT / "derived" / "p1_quality" / "analysis" / "A5_SCORE.json"


def _read(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} is not an object")
    return data


def points(run_id: str, root: Path = ROOT) -> dict[str, dict[str, Any]]:
    directory = root / "derived" / "p1_quality" / f"sealed_{run_id}" / "points"
    found = [_read(path) for path in sorted(directory.glob("*.json"))]
    return {str(point["id"]): point for point in found}


def mcnemar_exact_p(b: int, c: int) -> float:
    """Two-sided exact binomial test on the discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2.0 * tail)


def paired(a0: dict[str, dict[str, Any]], arm: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ids = sorted(arm)
    b_ids = [i for i in ids if a0[i]["in_budget_pass"] and not arm[i]["in_budget_pass"]]
    c_ids = [i for i in ids if not a0[i]["in_budget_pass"] and arm[i]["in_budget_pass"]]
    return {
        "a0_in_budget_passes": sum(1 for i in ids if a0[i]["in_budget_pass"]),
        "b_a0_pass_a5_fail": len(b_ids),
        "c_a0_fail_a5_pass": len(c_ids),
        "p_two_sided": mcnemar_exact_p(len(b_ids), len(c_ids)),
        "b_ids": b_ids,
        "c_ids": c_ids,
    }


def step_profile(arm: dict[str, dict[str, Any]]) -> dict[str, Any]:
    steps = [step for point in arm.values() for step in point["steps"]]
    first = Counter(str((step.get("checks") or ["none"])[0]) for step in steps)
    final = Counter(str(step.get("check_result")) for step in steps)
    retried = [step for step in steps if int(step.get("attempts") or 1) > 1]
    return {
        "n_steps": len(steps),
        "first_check": dict(sorted(first.items())),
        "final_check": dict(sorted(final.items())),
        "source": dict(sorted(Counter(str(step.get("source")) for step in steps).items())),
        "n_steps_with_feedback_retry": len(retried),
        "n_retried_steps_tta_ge_9_9": sum(1 for s in retried if float(s["tta_s"]) >= 9.9),
        "n_entries_with_feedback_retry": sum(
            1
            for point in arm.values()
            if any(int(step.get("attempts") or 1) > 1 for step in point["steps"])
        ),
    }


def score(root: Path = ROOT) -> dict[str, Any]:
    a0 = points(A0_ID, root)
    ordered = sorted(a0)
    halves: list[dict[str, Any]] = []
    merged: dict[str, dict[str, Any]] = {}
    for (label, run_id), expected in zip(HALVES, (ordered[:100], ordered[100:]), strict=True):
        arm = points(run_id, root)
        if sorted(arm) != expected:
            raise SystemExit(f"REFUSED -- {run_id} entries are not {label}")
        if {int(point["seed"]) for point in arm.values()} != {SEED}:
            raise SystemExit(f"REFUSED -- {run_id} seed is not {SEED}")
        merged.update(arm)
        halves.append(
            {
                "entries": label,
                "run_id": run_id,
                "in_budget_passes": sum(1 for p in arm.values() if p["in_budget_pass"]),
                "passes": sum(1 for p in arm.values() if p["passed"]),
                "paired_vs_a0": paired(a0, arm),
                "steps": step_profile(arm),
            }
        )
    total = sum(half["in_budget_passes"] for half in halves)
    verdict = "MATCH" if PRED_LOW <= total <= PRED_HIGH else "MISS"
    return {
        "arm": "A5",
        "seed": SEED,
        "a0_run_id": A0_ID,
        "prediction": {"low": PRED_LOW, "high": PRED_HIGH, "rule": RULE},
        "halves": halves,
        "total": {
            "entries": len(merged),
            "in_budget_passes": total,
            "passes": sum(half["passes"] for half in halves),
            "paired_vs_a0": paired(a0, merged),
            "steps": step_profile(merged),
        },
        "verdict": verdict,
        "seed_20261001": "not run; amendment 8 run_order schedules only seed 20260930",
    }


def main(argv: list[str]) -> int:
    result = score()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "--write" in argv:
        OUT.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
