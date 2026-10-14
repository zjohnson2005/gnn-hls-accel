"""Score one budget of the P1 B sweep (LOCAL-QUALITY-AMENDMENT-8, slices per 9).

Sealed run dirs only. Registered rules, applied as written:
- Pairs: sweep A0 vs fixed A4, same seed, entries and budget, paired by
  entry id. b = A0 pass and A4 fail; c = A0 fail and A4 pass; p = two-sided
  exact binomial test on the b + c discordant pairs.
- Crossing at B: A4 in-budget passes exceed paired A0, and p < 0.05.
- Sweep floor: A4 in-budget count >= paired sweep A0 count; at B=10 on
  [:100] also >= the sealed A0 count 14 (8a529053).
- Close fraction: share of fixed-A4 steps whose thinking decode closed
  (</think>) and parsed as a tool call, inside B. Floor 160/489 (3b4d8207).

  python tools/score_p1_crossing.py --budget 10 --out derived/p1_quality/analysis/CROSSING_B10.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
P1 = ROOT / "derived" / "p1_quality"

# Budget -> (A0 run, [A4 runs covering lexicographic [:100]]). eb6cd6ce (A4
# B=10 [53:100], FAIL_CANARY_DRIFT at 28/47) is a refused record and is not used.
CELLS: dict[int, dict[str, Any]] = {
    10: {
        "a0": "bdc32a87-8f91-4cd5-9cb0-2daafe659fc8",
        "a4": (
            "a766bd0b-0f49-46af-be1f-af75f164e0ae",
            "78dbf4c3-d842-4909-a546-207b171de4a7",
        ),
        "sealed_a0_floor": 14,
        "not_used": {"eb6cd6ce-ad9f-4b61-898d-bde9585a56cb": "refused record, 28/47 entries"},
    },
}
ALPHA = 0.05
CLOSE_FLOOR = Fraction(160, 489)


def exact_binomial_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2.0 * tail)


def _points(run: str) -> dict[str, dict[str, Any]]:
    root = P1 / f"sealed_{run}"
    out = {}
    for f in sorted((root / "points").glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        out[doc["id"]] = doc
    return out


def _summary(run: str) -> dict[str, Any]:
    return json.loads((P1 / f"sealed_{run}" / "summary.json").read_text(encoding="utf-8"))


def score(budget: int) -> dict[str, Any]:
    cell = CELLS[budget]
    a0_sum = _summary(cell["a0"])
    a0 = _points(cell["a0"])
    a4: dict[str, dict[str, Any]] = {}
    a4_runs = []
    for run in cell["a4"]:
        s = _summary(run)
        pts = _points(run)
        overlap = set(pts) & set(a4)
        if overlap:
            raise SystemExit(f"REFUSED -- A4 runs overlap on {sorted(overlap)[:3]}")
        a4.update(pts)
        a4_runs.append(
            {
                "run_id": run,
                "status": s.get("status"),
                "entries": len(pts),
                "in_budget_passes": s.get("in_budget_passes"),
            }
        )
    if set(a0) != set(a4):
        raise SystemExit(
            f"REFUSED -- entries differ: A0 only {len(set(a0) - set(a4))}, "
            f"A4 only {len(set(a4) - set(a0))}"
        )
    for run_doc in [a0_sum] + [_summary(r) for r in cell["a4"]]:
        if run_doc.get("status") != "complete":
            raise SystemExit(f"REFUSED -- {run_doc.get('session_id')} is not complete")
    seeds = {a0_sum.get("seed")} | {_summary(r).get("seed") for r in cell["a4"]}
    if len(seeds) != 1:
        raise SystemExit(f"REFUSED -- seeds differ: {seeds}")
    ids = sorted(a0)
    pa0 = {i: bool(a0[i]["in_budget_pass"]) for i in ids}
    pa4 = {i: bool(a4[i]["in_budget_pass"]) for i in ids}
    b = sum(1 for i in ids if pa0[i] and not pa4[i])
    c = sum(1 for i in ids if not pa0[i] and pa4[i])
    n_a0, n_a4 = sum(pa0.values()), sum(pa4.values())
    p = exact_binomial_two_sided(b, c)
    crosses = n_a4 > n_a0 and p < ALPHA
    steps = [s for i in ids for s in a4[i].get("steps") or []]
    closed_parsed = sum(
        1 for s in steps if s.get("thinking_closed") and s.get("thinking_parseable")
    )
    accepted = sum(1 for s in steps if s.get("thinking_accepted"))
    closed = sum(1 for s in steps if s.get("thinking_closed"))
    floor_paired = n_a4 >= n_a0
    floor_sealed = None if cell.get("sealed_a0_floor") is None else n_a4 >= cell["sealed_a0_floor"]
    frac = Fraction(closed_parsed, len(steps)) if steps else None
    return {
        "kind": "p1_crossing_score",
        "amendments": ["LOCAL-QUALITY-AMENDMENT-8 (rules)", "LOCAL-QUALITY-AMENDMENT-9 (slices)"],
        "budget_s": budget,
        "seed": seeds.pop(),
        "n_entries": len(ids),
        "a0": {
            "run_id": cell["a0"],
            "in_budget_passes": n_a0,
            "summary_in_budget_passes": a0_sum.get("in_budget_passes"),
        },
        "a4": {"runs": a4_runs, "in_budget_passes": n_a4},
        "not_used": cell.get("not_used"),
        "mcnemar": {"b_a0_pass_a4_fail": b, "c_a0_fail_a4_pass": c, "p_two_sided_exact": p},
        "crossing_at_b": crosses,
        "crossing_rule": "A4 in-budget passes > paired A0 and p < 0.05",
        "sweep_floor": {
            "a4_ge_paired_a0": floor_paired,
            "a4_ge_sealed_a0_14": floor_sealed,
            "holds": bool(floor_paired and (floor_sealed is not False)),
        },
        "close_fraction": {
            "a4_steps": len(steps),
            "closed_and_parsed": closed_parsed,
            "closed": closed,
            "accepted": accepted,
            "fraction": None if frac is None else float(frac),
            "floor": "160/489",
            "floor_value": float(CLOSE_FLOOR),
            "at_or_above_floor": None if frac is None else frac >= CLOSE_FLOOR,
        },
        "discordant_entries": {
            "b": [i for i in ids if pa0[i] and not pa4[i]],
            "c": [i for i in ids if not pa0[i] and pa4[i]],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, required=True, choices=sorted(CELLS))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    doc = score(args.budget)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("a0", "a4", "mcnemar", "crossing_at_b", "sweep_floor")}))
    print(json.dumps(doc["close_fraction"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
