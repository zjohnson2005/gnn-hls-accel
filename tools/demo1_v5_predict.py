"""DEMO-1 amendment 2026-10-13c: V5a (RESIDENT u8) and V5b (RESIDENT u4) predictions.

Sealed data only. No model, no device, no API. Inputs:
- analysis/demo1/PREFIX_CHECK_K1024.json (7326990): per entry and step of the
  DEMO1_PAIRED_15 gold trajectories under OBS_MASK K=1024, the prompt tokens
  and the common token prefix with the previous step.
- sealed cold probe medians: u8 c2246b1f (+ CAP-4 2b3316b6 above 12,000),
  u4 c647f0c7 (+ 2b3316b6).
- sealed RESIDENT turn-2 (delta prefill on a cached prefix) points:
  u8 a784f5ec (D=150), 1587d2f4 (D=183), cf3555d5 (D=183), 48779b5a (D=400);
  u4 dd2b0779 (D=183), e4a22dac (D=183).

Prediction rule (amendment 2026-10-13c):
- Entry step 0: cold prefill at its prompt tokens. Between two measured cold
  medians: log-log interpolation. Below the smallest: bounded by it (prefill
  is non-decreasing in n). Above the largest: outside the grid, escalate,
  flagged.
- Later step: delta prefill of D = prompt - common prefix on a cached prefix
  of P = common prefix. TTFT is bounded by the smallest measured turn-2 TTFT
  among sealed points with P' >= P and D' >= D at the same KV precision
  (delta prefill is non-decreasing in P and D). No such point: outside the
  grid, escalate, flagged. The sealed warm points used exact prefixes; the
  reply and the 4 dropped think tokens are inside D here.
- Cold bound (variant "cold_bounded", the registered one): a delta prefill
  on a cached prefix does no more work than a cold prefill of the same full
  prompt, so a warm step outside the warm grid (or above 10 s there) is
  bounded by the cold TTFT of its full prompt from the sealed cold curve. It
  escalates only if that bound is also above 10 s or outside the cold grid.
  Such steps are flagged warm_grid_missing. Variant "literal" omits this
  bound (outside the warm grid always escalates) and is reported alongside.
- Bracket (reported for every step): a delta prefill of D tokens on a cached
  prefix costs at least a cold prefill of D tokens alone and at most a cold
  prefill of the full prompt, so TTFT lies in [cold(D), cold(P + D)] from
  the sealed cold curve (lower bound 0 when D is below the smallest cold
  point). An entry is "local" when every step's upper bound is <= 10 s,
  "escalates" when some step's lower bound is > 10 s, else "indeterminate".
- A step whose prompt exceeds the resident limit (u8 20,000 cf3555d5; u4
  26,500 e4a22dac) is a cold step at its prompt tokens.
- Escalate when TTFT > 10 s. Decode < 6 tok/s is not predicted to fire
  (sealed decode >= 14.4 tok/s in the limit runs, DEMO_PREREG_v2
  trigger_mix). slo_escalate is sticky per entry.
- Block rounding: the KV block size is not recorded in any sealed load meta,
  so the high bound recomputes one extra block of B = 256 tokens (D + B on a
  prefix of P - B), a cover-all value for GPU block sizes. Low bound: B = 0.
- Cost and local share as DEMO_PREREG_v2: per user turn; a turn is local if
  every step of it is local; cloud $ = 3.20e-6 x 7.11 x n_ctx per cloud turn
  (n_ctx = the turn's step-0 prompt tokens).

  python tools/demo1_v5_predict.py --out analysis/demo1/V5_PREDICTIONS.json
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREFIX = ROOT / "analysis" / "demo1" / "PREFIX_CHECK_K1024.json"
SLO_S = 10.0
USD_PER_INPUT_TOKEN = 3.20e-6
CLOUD_TOKENS_PER_LOCAL_NCTX = 7.11
LIVE_FACTOR_P90 = 1.083
BLOCK_BOUND = 256
RESIDENT_LIMIT = {"u8": (20_000, "cf3555d5"), "u4": (26_500, "e4a22dac")}
COLD_RUNS = {"u8": ("c2246b1f", "2b3316b6"), "u4": ("c647f0c7", "2b3316b6")}
WARM_MATRIX_RUNS = {"u8": ("a784f5ec", "48779b5a")}
WARM_POINT_RUNS = {"u8": ("1587d2f4", "cf3555d5"), "u4": ("dd2b0779", "e4a22dac")}
EXCLUDED = {
    "9f38eb15": "SUPERSEDED, KV not pinned (gpu_only)",
    "d5c98342": "SUPERSEDED, KV not pinned (gpu_only)",
}


def _sealed(run: str) -> Path:
    (path,) = (ROOT / "derived").glob(f"*/sealed_{run}*")
    return path


def cold_medians(kv: str) -> dict[int, tuple[float, str]]:
    from tools.demo1_atlas import probe_medians

    arm = f"gpu_only_{kv}"
    out: dict[int, tuple[float, str]] = {}
    for run in COLD_RUNS[kv]:
        for n, t in probe_medians(run, arm).items():
            out.setdefault(n, (t, run))
    return dict(sorted(out.items()))


def warm_points(kv: str) -> list[dict[str, Any]]:
    """(P, D, ttft, run) for sealed RESIDENT turn-2 points at this KV."""
    arm = f"gpu_only_{kv}"
    pts: list[dict[str, Any]] = []
    for run in WARM_MATRIX_RUNS.get(kv, ()):
        doc = json.loads((_sealed(run) / "summary.json").read_text(encoding="utf-8"))
        by: dict[tuple[int, int], list[float]] = {}
        for cell in doc["cells"]:
            if cell.get("arm_id") != arm or cell.get("mode") != "RESIDENT":
                continue
            if cell.get("turn2_prefill_s") is None:
                continue
            by.setdefault((int(cell["n_cached"]), int(cell["delta"])), []).append(
                float(cell["turn2_prefill_s"])
            )
        for (p, d), vals in sorted(by.items()):
            pts.append({"P": p, "D": d, "ttft_s": statistics.median(vals), "run": run})
    for run in WARM_POINT_RUNS.get(kv, ()):
        sealed = _sealed(run)
        doc = json.loads((sealed / "summary.json").read_text(encoding="utf-8"))
        plan = json.loads((sealed / "plan.json").read_text(encoding="utf-8"))
        delta = int(doc.get("delta_tokens") or plan.get("delta_tokens"))
        if doc.get("arm") != arm and plan.get("arm") != arm:
            raise SystemExit(f"REFUSED -- {run} is not {arm}")
        for point in doc.get("points") or []:
            if point.get("outcome") != "pass":
                continue
            ttft = point.get("turn2_ttft_s") or point.get("turn2_median_prefill_s")
            if ttft is None:
                continue
            pts.append({"P": int(point["n_cached"]), "D": delta, "ttft_s": float(ttft), "run": run})
    return pts


def cold_ttft(n: float, medians: dict[int, tuple[float, str]]) -> dict[str, Any]:
    items = sorted(medians.items())
    lo_n, (lo_t, lo_run) = items[0]
    if n <= lo_n:
        return {"ttft_s": lo_t, "basis": f"bound by {lo_n} ({lo_run})", "outside_grid": False}
    for (n0, (t0, r0)), (n1, (t1, r1)) in itertools.pairwise(items):
        if n0 <= n <= n1:
            if t1 <= t0 or n1 == n0:
                return {"ttft_s": t1, "basis": f"bound by {n1} ({r1})", "outside_grid": False}
            slope = math.log(t1 / t0) / math.log(n1 / n0)
            t = t0 * (n / n0) ** slope
            return {
                "ttft_s": t,
                "basis": f"log-log {n0} ({r0}) to {n1} ({r1})",
                "outside_grid": False,
            }
    hi_n = items[-1][0]
    return {"ttft_s": None, "basis": f"above measured {hi_n}", "outside_grid": True}


def cold_lower(n: float, medians: dict[int, tuple[float, str]]) -> float:
    """Lower bound on cold prefill of n tokens: 0 below the smallest measured point."""
    smallest = min(medians)
    if n < smallest:
        return 0.0
    got = cold_ttft(n, medians)
    if got["outside_grid"]:
        return float(max(t for t, _r in medians.values()))
    return float(got["ttft_s"])


def warm_ttft(p: float, d: float, points: list[dict[str, Any]]) -> dict[str, Any]:
    dom = [x for x in points if x["P"] >= p and x["D"] >= d]
    if not dom:
        return {
            "ttft_s": None,
            "basis": f"no sealed point with P'>={round(p)} and D'>={round(d)}",
            "outside_grid": True,
        }
    best = min(dom, key=lambda x: x["ttft_s"])
    return {
        "ttft_s": best["ttft_s"],
        "basis": f"bound by P={best['P']} D={best['D']} ({best['run']})",
        "outside_grid": False,
    }


def predict_entry(
    entry: dict[str, Any],
    kv: str,
    cold: dict[int, tuple[float, str]],
    warm: list[dict[str, Any]],
    *,
    block: int,
    resident: bool,
    cold_bound: bool = True,
) -> dict[str, Any]:
    limit, _ = RESIDENT_LIMIT[kv]
    steps = entry["step_prompt_tokens"]
    turns = entry["step_turn"]
    trans = entry["transitions"]
    rows = []
    escalate_step = None
    for k, n in enumerate(steps):
        if k == 0 or not resident:
            kind = "cold"
            p = 0
            d = n
            got = cold_ttft(n, cold)
        else:
            t = trans[k - 1]
            p = max(0, t["common_prefix_tokens"] - block)
            d = n - p
            if n > limit:
                kind = "cold_over_resident_limit"
                got = cold_ttft(n, cold)
            else:
                kind = "warm"
                got = warm_ttft(p, d, warm)
                fails = got["outside_grid"] or got["ttft_s"] > SLO_S
                if fails and cold_bound:
                    bound = cold_ttft(n, cold)
                    if not bound["outside_grid"] and bound["ttft_s"] <= SLO_S:
                        got = {
                            "ttft_s": bound["ttft_s"],
                            "basis": f"cold bound of full prompt: {bound['basis']}",
                            "outside_grid": False,
                            "warm_grid_missing": True,
                        }
                    else:
                        got = {**got, "warm_grid_missing": True}
        escalates = got["outside_grid"] or (got["ttft_s"] is not None and got["ttft_s"] > SLO_S)
        lower = cold_lower(d if kind == "warm" else n, cold)
        upper = cold_ttft(n, cold)
        bracket = [
            round(lower, 3),
            None if upper["outside_grid"] else round(upper["ttft_s"], 3),
        ]
        rows.append(
            {
                "step": k,
                "turn": turns[k],
                "kind": kind,
                "prompt_tokens": n,
                "P": p,
                "D": d,
                "ttft_s": None if got["ttft_s"] is None else round(got["ttft_s"], 3),
                "basis": got["basis"],
                "outside_grid": got["outside_grid"],
                "warm_grid_missing": bool(got.get("warm_grid_missing")),
                "ttft_bracket_s": bracket,
                "escalates": escalates,
            }
        )
        if escalates and escalate_step is None:
            escalate_step = k
    status = "local"
    for r in rows:
        lo, hi = r["ttft_bracket_s"]
        if lo > SLO_S:
            status = "escalates"
            break
        if hi is None or hi > SLO_S:
            status = "indeterminate"
    n_turns = max(turns) + 1
    esc_turn = None if escalate_step is None else turns[escalate_step]
    first_step_of_turn = {}
    for k, t in enumerate(turns):
        first_step_of_turn.setdefault(t, k)
    turn_nctx = [steps[first_step_of_turn[t]] for t in range(n_turns)]
    local_turns = n_turns if esc_turn is None else esc_turn
    cloud_nctx = turn_nctx[local_turns:]
    usd = sum(n * CLOUD_TOKENS_PER_LOCAL_NCTX * USD_PER_INPUT_TOKEN for n in cloud_nctx)
    local_rows = rows[: escalate_step if escalate_step is not None else len(rows)]
    warm_rows = [r for r in rows if r["kind"] == "warm"]
    jump = max(warm_rows, key=lambda r: r["D"]) if warm_rows else None
    return {
        "entry_id": entry["entry_id"],
        "bracket_status": status,
        "n_turns": n_turns,
        "escalate_step": escalate_step,
        "escalate_turn": esc_turn,
        "escalate_reason": None
        if escalate_step is None
        else ("outside_grid" if rows[escalate_step]["outside_grid"] else "ttft_gt_10s"),
        "local_turns": local_turns,
        "usd": round(usd, 4),
        "usd_live_factor": round(usd * LIVE_FACTOR_P90, 4),
        "local_prefill_s_bound": round(sum(r["ttft_s"] or 0.0 for r in local_rows), 2),
        "jump_step": None
        if jump is None
        else {k: jump[k] for k in ("step", "turn", "P", "D", "ttft_s", "basis", "outside_grid")},
        "steps": rows,
    }


def cell(
    entries: list[dict[str, Any]], kv: str, *, resident: bool, cold_bound: bool = True
) -> dict[str, Any]:
    cold = cold_medians(kv)
    warm = warm_points(kv)
    out: dict[str, Any] = {"variant": "cold_bounded" if cold_bound else "literal"}
    for name, block in (("block_low", 0), ("block_high", BLOCK_BOUND)):
        per = [
            predict_entry(e, kv, cold, warm, block=block, resident=resident, cold_bound=cold_bound)
            for e in entries
        ]
        n_turns = sum(p["n_turns"] for p in per)
        local = sum(p["local_turns"] for p in per)
        usd = sum(p["usd"] for p in per)
        out[name] = {
            "block_tokens": block,
            "local_share": round(local / n_turns, 3),
            "usd": round(usd, 2),
            "usd_per_task": round(usd / len(per), 3),
            "usd_per_task_live_factor": round(usd * LIVE_FACTOR_P90 / len(per), 3),
            "escalations": sum(1 for p in per if p["escalate_step"] is not None),
            "escalations_outside_grid": sum(
                1 for p in per if p["escalate_reason"] == "outside_grid"
            ),
            "local_prefill_s_bound_total": round(sum(p["local_prefill_s_bound"] for p in per), 1),
            "bracket_status": {
                s: sum(1 for p in per if p["bracket_status"] == s)
                for s in ("local", "indeterminate", "escalates")
            },
            "steps_warm_grid_missing": sum(
                1 for p in per for s in p["steps"] if s["warm_grid_missing"]
            ),
            "entries": per,
        }
    low = {p["entry_id"]: p for p in out["block_low"]["entries"]}
    high = {p["entry_id"]: p for p in out["block_high"]["entries"]}
    out["boundary_entries"] = sorted(
        eid
        for eid in low
        if (low[eid]["escalate_step"], low[eid]["escalate_turn"])
        != (high[eid]["escalate_step"], high[eid]["escalate_turn"])
    )
    out["grid"] = {
        "cold": {str(n): {"ttft_s": round(t, 3), "run": r} for n, (t, r) in cold.items()},
        "warm": warm,
        "resident_limit": {"tokens": RESIDENT_LIMIT[kv][0], "run": RESIDENT_LIMIT[kv][1]},
    }
    return out


def predictions() -> dict[str, Any]:
    prefix = json.loads(PREFIX.read_text(encoding="utf-8"))
    entries = prefix["entries"]
    v5a = cell(entries, "u8", resident=True)
    v5b = cell(entries, "u4", resident=True)
    v5a_lit = cell(entries, "u8", resident=True, cold_bound=False)
    v5b_lit = cell(entries, "u4", resident=True, cold_bound=False)
    ref = cell(entries, "u8", resident=False)
    return {
        "kind": "demo1_v5_predictions",
        "amendment": "DEMO-1 2026-10-13c",
        "inputs": {
            "prefix_check": PREFIX.relative_to(ROOT).as_posix(),
            "prefix_check_sha256": hashlib.sha256(PREFIX.read_bytes()).hexdigest(),
            "entries_sha256": prefix["entries_sha256"],
            "obs_mask_k": prefix["obs_mask_k"],
            "excluded_runs": EXCLUDED,
        },
        "rule": __doc__.split("Prediction rule (amendment 2026-10-13c):", 1)[1]
        .split("  python")[0]
        .strip(),
        "cells": {
            "V5a_xps_gpu_4b_RESIDENT_u8": v5a,
            "V5b_xps_gpu_4b_RESIDENT_u4": v5b,
        },
        "literal_variant_not_registered": {
            "V5a_xps_gpu_4b_RESIDENT_u8": v5a_lit,
            "V5b_xps_gpu_4b_RESIDENT_u4": v5b_lit,
        },
        "reference_not_a_prediction": {
            "V4_xps_step_model_NON_RESIDENT_u8": ref,
            "note": (
                "Every step cold at u8 under the same per-step model; V4 XPS is measured "
                "(a678926e), so this is only the like-for-like baseline for the residency effect."
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    doc = predictions()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    shown = {
        **doc["cells"],
        **{f"{k} (literal)": v for k, v in doc["literal_variant_not_registered"].items()},
        "V4 step-model reference": doc["reference_not_a_prediction"][
            "V4_xps_step_model_NON_RESIDENT_u8"
        ],
    }
    for name, c in shown.items():
        lo, hi = c["block_low"], c["block_high"]
        print(
            f"{name}: local_share {lo['local_share']}..{hi['local_share']} "
            f"usd/task {lo['usd_per_task']}..{hi['usd_per_task']} "
            f"escalations {lo['escalations']}..{hi['escalations']} "
            f"(outside grid {lo['escalations_outside_grid']}..{hi['escalations_outside_grid']}) "
            f"boundary {len(c['boundary_entries'])} "
            f"warm-grid-missing steps {lo['steps_warm_grid_missing']}..{hi['steps_warm_grid_missing']} "
            f"bracket {lo['bracket_status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
