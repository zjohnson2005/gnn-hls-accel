"""Score one sealed P1 sweep A0 boot against A0 8a529053 on the same entries.

Amendment 8 pairs fixed A4 against the sweep A0 at the same budget, seed and
entries; that crossing test needs the A4 boots and is not computed here.
This records the boot's in-budget count and an entry-by-entry determinism
check against the sealed A0 (budget 10 s). Reads only sealed point files and
opens no amendment. Does not start a measurement. --write saves
derived/p1_quality/analysis/SWEEP_A0_<run8>_SCORE.json.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
A0_ID = "8a529053-fc47-486d-8809-6c699d156b06"
# Amendment 8 predictions.sweep.b10_sealed_a0_in_budget_passes ([:100]).
SEALED_A0_B10_FIRST_100 = 14


def _read(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} is not an object")
    return data


def points(run_id: str, root: Path = ROOT) -> dict[str, dict[str, Any]]:
    directory = root / "derived" / "p1_quality" / f"sealed_{run_id}" / "points"
    found = [_read(path) for path in sorted(directory.glob("*.json"))]
    return {str(point["id"]): point for point in found}


def _tokens(step: dict[str, Any]) -> Any:
    return step.get("emitted_tokens", step.get("tokens"))


def score(run_id: str, root: Path = ROOT) -> dict[str, Any]:
    run_dir = root / "derived" / "p1_quality" / f"sealed_{run_id}"
    summary = _read(run_dir / "summary.json")
    plan = _read(run_dir / "plan.json")
    if summary.get("arm") != "A0":
        raise SystemExit(f"REFUSED -- {run_id} is not an A0 run")
    sweep = points(run_id, root)
    a0 = points(A0_ID, root)
    ids = sorted(sweep)
    missing = [i for i in ids if i not in a0]
    if missing:
        raise SystemExit(f"REFUSED -- entries not in {A0_ID}: {missing[:3]}")
    ordered = sorted(a0)
    window = None
    for start in (0, 100):
        if ids == ordered[start : start + 100]:
            window = f"lexicographic [{start}:{start + 100}]"
    steps = [s for i in ids for s in sweep[i]["steps"]]
    steps0 = [s for i in ids for s in a0[i]["steps"]]
    differ = [i for i in ids if sweep[i]["in_budget_pass"] != a0[i]["in_budget_pass"]]
    in_budget = sum(1 for i in ids if sweep[i]["in_budget_pass"])
    record: dict[str, Any] = {
        "run_id": run_id,
        "arm": "A0",
        "seed": summary.get("seed"),
        "budget_s": plan.get("budget_s"),
        "entries": window,
        "n_entries": len(ids),
        "status": summary.get("status"),
        "in_budget_passes": in_budget,
        "in_budget_passes_summary": summary.get("in_budget_passes"),
        "passes": sum(1 for i in ids if sweep[i]["passed"]),
        "reference": {
            "run_id": A0_ID,
            "in_budget_passes_same_entries": sum(1 for i in ids if a0[i]["in_budget_pass"]),
        },
        "determinism": {
            "in_budget_pass_agree": len(ids) - len(differ),
            "passed_agree": sum(1 for i in ids if sweep[i]["passed"] == a0[i]["passed"]),
            "same_step_count": sum(1 for i in ids if len(sweep[i]["steps"]) == len(a0[i]["steps"])),
            "same_tokens_every_step": sum(
                1
                for i in ids
                if [_tokens(s) for s in sweep[i]["steps"]] == [_tokens(s) for s in a0[i]["steps"]]
            ),
            "in_budget_pass_differs": differ,
        },
        "steps": {
            "n": len(steps),
            "n_reference": len(steps0),
            "tta_at_budget": sum(1 for s in steps if float(s["tta_s"]) >= 10.0),
            "tta_at_budget_reference": sum(1 for s in steps0 if float(s["tta_s"]) >= 10.0),
            "median_tta_s": statistics.median(float(s["tta_s"]) for s in steps),
            "median_tta_s_reference": statistics.median(float(s["tta_s"]) for s in steps0),
            "wall_s": sum(float(sweep[i]["wall_s"]) for i in ids),
            "wall_s_reference": sum(float(a0[i]["wall_s"]) for i in ids),
        },
        "crossing": "not computed: needs the fixed-A4 boots at this budget and entries",
    }
    if window == "lexicographic [0:100]" and plan.get("budget_s") == 10.0:
        record["a4_b10_floor"] = {
            "rule": "fixed A4 in-budget count >= max(paired sweep A0, sealed A0 14)",
            "value": max(in_budget, SEALED_A0_B10_FIRST_100),
        }
    return record


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("usage: score_p1_sweep_a0.py <run_id> [--write]")
    result = score(argv[1])
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "--write" in argv:
        out = ROOT / "derived" / "p1_quality" / "analysis" / f"SWEEP_A0_{argv[1][:8]}_SCORE.json"
        out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
