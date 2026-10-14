"""DEMO-1 V5 addendum (2026-10-14): V5a/V5b recomputed with the sealed V5-CAL points.

Sealed data only; no model, no device, no API. Uses tools/demo1_v5_predict.py
(amendment 2026-10-13c) unchanged, adding the sealed V5-CAL warm points:
u8 a178e9c5, u4 e1ed06b4 (measured P = common prefix, D = measured delta,
TTFT = turn-2 median). 15993163 (V5-path, UNGUARDED) is not used.

Two predictions:
1. registered_per_step: the amendment's method (every step; monotone bound;
   block bounds 0 / +256), with the cold bound dropped: V5-CAL measured
   delta prefill slower than cold prefill of the same full prompt (u8
   P 2,194 D 8,511: 22.4 s against about 11 s cold for 10,705 tokens), so
   "a delta prefill does no more work than a cold prefill" is false here.
2. runner_trigger_per_turn: the H1 runner escalates on step 0 of each user
   turn only (tools/bfcl_feasibility_probe.py: turn_ttft_s is taken at
   step == 0; tools/run_h1_hybrid.py decide_slo_escalate reads it). Entry
   step 0 is cold; step 0 of a later turn is a delta prefill of the
   turn-boundary D on the cached prefix (RESIDENT). Within-turn steps are
   not checked by the runner; their predicted TTFT is reported, not used.

  python tools/demo1_v5_addendum.py --out analysis/demo1/V5_ADDENDUM_PREDICTIONS.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo1_v5_predict as base  # noqa: E402

V5CAL_RUNS = {
    "u8": "a178e9c5-193e-4221-8f22-d4ffe0803749",
    "u4": "e1ed06b4-a2c2-4de2-b27b-b7b5e3190122",
}


def v5cal_points(kv: str) -> list[dict[str, Any]]:
    run = V5CAL_RUNS[kv]
    doc = json.loads(
        (ROOT / "derived" / "delta_prefill" / f"sealed_{run}" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    if doc.get("arm") != f"gpu_only_{kv}" or doc.get("status") != "complete":
        raise SystemExit(f"REFUSED -- {run} is not a complete gpu_only_{kv} V5-CAL run")
    pts = []
    for p in doc["points"]:
        if p.get("outcome") != "pass" or p.get("turn2_median_prefill_s") is None:
            continue
        pts.append(
            {
                "P": int(min(p["common_prefix_tokens"])),
                "D": int(max(p["measured_delta_tokens"])),
                "ttft_s": float(p["turn2_median_prefill_s"]),
                "run": run[:8],
            }
        )
    return pts


def _cell_summary(per: list[dict[str, Any]]) -> dict[str, Any]:
    n_turns = sum(p["n_turns"] for p in per)
    local = sum(p["local_turns"] for p in per)
    usd = sum(p["usd"] for p in per)
    return {
        "local_share": round(local / n_turns, 3),
        "usd": round(usd, 2),
        "usd_per_task": round(usd / len(per), 3),
        "escalations": sum(1 for p in per if p["escalate_step"] is not None),
        "escalations_outside_grid": sum(1 for p in per if p["escalate_reason"] == "outside_grid"),
        "escalating_entries": [
            (p["entry_id"], p["escalate_turn"]) for p in per if p["escalate_step"] is not None
        ],
    }


def per_step(entries: list[dict[str, Any]], kv: str) -> dict[str, Any]:
    cold = base.cold_medians(kv)
    warm = base.warm_points(kv) + v5cal_points(kv)
    out: dict[str, Any] = {}
    for name, block in (("block_low", 0), ("block_high", base.BLOCK_BOUND)):
        per = [
            base.predict_entry(e, kv, cold, warm, block=block, resident=True, cold_bound=False)
            for e in entries
        ]
        out[name] = {**_cell_summary(per), "entries": per}
    return out


def per_turn_entry(
    entry: dict[str, Any], kv: str, cold: Any, warm: list[dict[str, Any]], *, block: int
) -> dict[str, Any]:
    full = base.predict_entry(entry, kv, cold, warm, block=block, resident=True, cold_bound=False)
    turns = entry["step_turn"]
    first = {}
    for k, t in enumerate(turns):
        first.setdefault(t, k)
    checked = [full["steps"][k] for k in sorted(first.values())]
    esc = next((s for s in checked if s["escalates"]), None)
    n_turns = max(turns) + 1
    local_turns = n_turns if esc is None else esc["turn"]
    turn_nctx = [entry["step_prompt_tokens"][first[t]] for t in range(n_turns)]
    usd = sum(
        n * base.CLOUD_TOKENS_PER_LOCAL_NCTX * base.USD_PER_INPUT_TOKEN
        for n in turn_nctx[local_turns:]
    )
    unchecked = [s for s in full["steps"] if s["step"] not in set(first.values())]
    return {
        "entry_id": entry["entry_id"],
        "n_turns": n_turns,
        "escalate_step": None if esc is None else esc["step"],
        "escalate_turn": None if esc is None else esc["turn"],
        "escalate_reason": None
        if esc is None
        else ("outside_grid" if esc["outside_grid"] else "ttft_gt_10s"),
        "local_turns": local_turns,
        "usd": round(usd, 4),
        "checked_steps": checked,
        "unchecked_within_turn_max_ttft_s": max(
            (s["ttft_s"] for s in unchecked if s["ttft_s"] is not None), default=None
        ),
        "unchecked_within_turn_over_10s": sum(1 for s in unchecked if s["escalates"]),
    }


def per_turn(entries: list[dict[str, Any]], kv: str) -> dict[str, Any]:
    cold = base.cold_medians(kv)
    warm = base.warm_points(kv) + v5cal_points(kv)
    out: dict[str, Any] = {}
    for name, block in (("block_low", 0), ("block_high", base.BLOCK_BOUND)):
        per = [per_turn_entry(e, kv, cold, warm, block=block) for e in entries]
        out[name] = {**_cell_summary(per), "entries": per}
    return out


def predictions() -> dict[str, Any]:
    prefix = json.loads(base.PREFIX.read_text(encoding="utf-8"))
    entries = prefix["entries"]
    boundary_d = [
        t["next_prompt_tokens"] - t["common_prefix_tokens"]
        for e in entries
        for t in e["transitions"]
        if t["boundary"] == "new_user_turn"
    ]
    return {
        "kind": "demo1_v5_addendum_predictions",
        "addendum": "DEMO-1 V5 addendum 2026-10-14",
        "v5cal_points": {kv: v5cal_points(kv) for kv in ("u8", "u4")},
        "turn_boundary_D": {
            "n": len(boundary_d),
            "min": min(boundary_d),
            "median": statistics.median(boundary_d),
            "max": max(boundary_d),
        },
        "registered_per_step": {
            "V5a_u8": per_step(entries, "u8"),
            "V5b_u4": per_step(entries, "u4"),
        },
        "runner_trigger_per_turn": {
            "V5a_u8": per_turn(entries, "u8"),
            "V5b_u4": per_turn(entries, "u4"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    doc = predictions()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    for method in ("registered_per_step", "runner_trigger_per_turn"):
        for cell, c in doc[method].items():
            lo, hi = c["block_low"], c["block_high"]
            print(
                f"{method} {cell}: local_share {lo['local_share']}..{hi['local_share']} "
                f"usd/task {lo['usd_per_task']}..{hi['usd_per_task']} "
                f"escalations {lo['escalations']}..{hi['escalations']} "
                f"(outside grid {lo['escalations_outside_grid']}..{hi['escalations_outside_grid']})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
