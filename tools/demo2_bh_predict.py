"""DEMO-2 Task BH predictions (DERIVED, before any held-out run): confirmatory family F2.

Writes derived/h1_hybrid/demo2/DEMO2_BH_F2_PREDICTIONS.json, registered by
docs/amendments/DEMO2_AMEND_2026-10-23_OBJECTIVES.md ("OBJ"). The BF0 predictions are not
changed (OBJ section 1: the identical P vs I-4K / C vs I-4K values are not a bug).

Inputs are pre-held-out records only, all committed (none from DEMO2_HELDOUT_60):
- calibration, DEMO2_CALIB_30 (base entries; already read in BF, disclosed in OBJ):
  T2S A 75fa4d1c, C dd62e520, P c91bc055 (8B INT8); XPS A 7cf9b18d, C a200bd1a, P' 4407accc
  (PSPEC selected at the freeze). Per entry: wall (sum of local turn_wall_s), local_pass,
  stop_reason; paired by entry.
- long-context pilots, arm A (true default) on the disjoint DEMO2_HELDOUT_60_B long half:
  T2S 1a634610 + daa6c026 (29 entries), XPS 15367c3a (15 entries); per entry wall, turn
  n_ctx (step-0 prompt per turn), local_pass, stop_reason; max prompt per entry from
  analysis/demo2_pilots/BB/context_over_limit.json (Task BB replay).
- entry 123 (the 30th long entry, not in those runs): T2S A = cddcd9fd (21 steps to max_steps,
  26.2 min, no watchdog fire: a silent loop); T2S X = e66a2a89 (ctx_overflow at step 1);
  XPS A = a stall (841b84e4, unsealed; X0-XPS d0dd5a37 pending), modelled as a stall fire at
  the held-out XPS stall limit 3,600 s (loud), X as on the T2S.

Model (per host, per contrast A vs X, NSIM draws, seed SEED):
- 30 base entries drawn with replacement from the 30 calibration pairs (A and X walls, passes,
  stops as measured);
- 30 long entries drawn with replacement from the host's long pool. A as measured. X stops at
  the first turn whose n_ctx + 512 > W (W = the X arm's window: XPS 8,704, T2S 16,896; the
  queue scripts' W) and counts only the turns before it; if no turn's step-0 prompt crosses W
  but the entry's max prompt + 512 does, X runs half of A's wall (stated assumption). X's run
  part is scaled by a ratio drawn from the calibration X/A per-entry wall ratios (P is a
  slower model, C is the same model). X fails locally wherever it overflowed, else as A.
  X takes A's path on long entries (assumption: P's own path is not known).
- members: a (A silent overrun: max prompt + 512 > 40,960 and no loud end), b (median paired
  wall difference, Wilcoxon), c (both-fail subset), d (hang/loop: 123-like or max_steps);
  X's a and d events are 0 (window refusal; e66a2a89 shows the cap converts the loop).
- reported per member: point = median over draws, band = 5th-95th percentile over draws,
  P(p < 0.05) and P(p < 0.05 / 6) (Holm's smallest threshold for m = 6).
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.demo2_f2_objectives import wilcoxon  # noqa: E402
from tools.demo2_iso_quality_replay import mcnemar_exact  # noqa: E402

NSIM = 2000
SEED = 20261023
MAX_NEW = 512
M_F2 = 6
WIN = {"XPS": 8704, "T2S": 16896}
STALL_S_XPS = 3600.0
W = "derived/demo2_pilots/windows_20261022/"
CAL = {
    "T2S": {
        "A": W
        + "t2s_1012_be/cal_a1/derived__h1_hybrid__interleaved_75fa4d1c-3b4a-47fc-b238-d288dfef036f",
        "C": W
        + "t2s_1012_be/cal_c/derived__h1_hybrid__interleaved_dd62e520-4284-4e5b-9e44-d92c46070f14",
        "P": W
        + "t2s_1012_be/cal_p/derived__h1_hybrid__interleaved_c91bc055-2978-4816-89fb-c81523bff8a6",
    },
    "XPS": {
        "A": W
        + "xps_1012_be/cal_a1/derived__h1_hybrid__interleaved_7cf9b18d-ffab-4833-bd29-44b7e553455f",
        "C": W
        + "xps_1149_be/cal_c/derived__h1_hybrid__interleaved_a200bd1a-b80b-432d-bdd5-2b1d6cab01f7",
        "P": W
        + "xps_1149_be/cal_pp/derived__h1_hybrid__interleaved_4407accc-77c2-4891-8669-4951e8ffc49e",
    },
}
LONG = {
    "T2S": [
        "derived/h1_hybrid/interleaved_1a634610-a762-4710-8bbe-08edd4665067",
        "derived/h1_hybrid/interleaved_daa6c026-ff57-4b19-a9c9-832dc2a48261",
    ],
    "XPS": ["derived/h1_hybrid/interleaved_15367c3a-5b8d-4be0-9db5-a6538b6e8c56"],
}
E123 = {
    "T2S_A": "derived/demo2_pilots/windows_20261021/t2s_1925_p11b/p11b_x0_armA/"
    "derived__h1_hybrid__interleaved_cddcd9fd-60aa-41cf-8d9e-b8b170f8a876",
    "T2S_X": "derived/demo2_pilots/windows_20261021/t2s_1925_p11b/p11b_x1_cap40960/"
    "derived__h1_hybrid__interleaved_e66a2a89-d3e7-4e64-ac90-cc4d3643c0f1",
}
OVER = "analysis/demo2_pilots/BB/context_over_limit.json"


def _entries(d: str) -> dict[str, dict[str, Any]]:
    p = ROOT / d / "policies" / "local_only" / "turn_ledger.json"
    out: dict[str, dict[str, Any]] = {}
    for e in json.loads(p.read_text(encoding="utf-8"))["entries"]:
        ts = sorted(
            (t for t in e["turns"] if t.get("placement") == "local"), key=lambda t: int(t["turn"])
        )
        out[str(e["entry_id"])] = {
            "wall": float(sum(float(t["turn_wall_s"]) for t in ts)),
            "turns": [(int(t["n_ctx"]), float(t["turn_wall_s"])) for t in ts],
            "pass": bool(e["local_pass"]),
            "stop": e.get("stop_reason"),
        }
    return out


def _max_prompts() -> dict[str, dict[str, int]]:
    doc = json.loads((ROOT / OVER).read_text(encoding="utf-8"))
    out: dict[str, dict[str, int]] = {}
    for r in doc["runs"]:
        if "entries" in r:
            out[str(r["run_id"])[:8]] = {
                str(e["entry_id"]): int(e.get("max_prompt") or 0) for e in r["entries"]
            }
    return out


def calib_pairs(host: str, x: str) -> list[dict[str, Any]]:
    a, xx = _entries(CAL[host]["A"]), _entries(CAL[host][x])
    return [
        {
            "wa": a[i]["wall"],
            "wx": xx[i]["wall"],
            "pa": a[i]["pass"],
            "px": xx[i]["pass"],
            "da": a[i]["stop"] == "max_steps",
            "dx": xx[i]["stop"] == "max_steps",
        }
        for i in sorted(a)
    ]


def long_pool(host: str) -> list[dict[str, Any]]:
    mp = _max_prompts()
    pool: list[dict[str, Any]] = []
    for d in LONG[host]:
        rid = d.split("interleaved_")[1][:8]
        for eid, e in _entries(d).items():
            pool.append({"id": eid, "run": rid, "max_prompt": mp[rid][eid], **e})
    a123: dict[str, Any]
    if host == "T2S":
        ea = _entries(E123["T2S_A"])["multi_turn_long_context_123"]
        a123 = {"wall": ea["wall"], "silent": ea["stop"] == "max_steps", "event": True}
    else:
        a123 = {"wall": STALL_S_XPS, "silent": False, "event": True}
    ex = _entries(E123["T2S_X"])["multi_turn_long_context_123"]
    pool.append(
        {
            "id": "multi_turn_long_context_123",
            "run": "cddcd9fd/e66a2a89" if host == "T2S" else "stall@3600/e66a2a89",
            "max_prompt": 98_165,
            "wall": a123["wall"],
            "turns": [],
            "pass": False,
            "stop": "max_steps" if a123["silent"] else "stall",
            "x_wall_123": ex["wall"],
            "a_silent_123": a123["silent"],
        }
    )
    return pool


def x_long(e: dict[str, Any], win: int, ratio: float) -> tuple[float, bool, bool]:
    """(X wall, X overflowed, X passes) for a long pool entry."""
    if "x_wall_123" in e:
        return float(e["x_wall_123"]) * ratio, True, False
    if e["max_prompt"] + MAX_NEW <= win:
        return e["wall"] * ratio, False, bool(e["pass"])
    run = 0.0
    for n_ctx, wall in e["turns"]:
        if n_ctx + MAX_NEW > win:
            return run * ratio, True, False
        run += wall
    return 0.5 * e["wall"] * ratio, True, False


def a_silent(e: dict[str, Any]) -> bool:
    if "a_silent_123" in e:
        return bool(e["a_silent_123"])
    return e["max_prompt"] + MAX_NEW > 40_960 and e["stop"] not in ("generation_error",)


def a_event(e: dict[str, Any]) -> bool:
    return "x_wall_123" in e or e["stop"] == "max_steps"


def _summ(vals: list[float]) -> dict[str, float]:
    s = sorted(vals)
    n = len(s)
    return {
        "point": round(statistics.median(s), 3),
        "band_p05": round(s[int(0.05 * (n - 1))], 3),
        "band_p95": round(s[int(0.95 * (n - 1))], 3),
    }


def simulate(host: str, x: str) -> dict[str, Any]:
    rng = random.Random(f"{SEED}:{host}:{x}")
    base = calib_pairs(host, x)
    ratios = [p["wx"] / p["wa"] for p in base if p["wa"] > 0]
    pool = long_pool(host)
    win = WIN[host]
    acc: dict[str, list[float]] = {
        k: []
        for k in (
            "a_A",
            "a_p",
            "b_med",
            "b_p",
            "c_med",
            "c_p",
            "c_n",
            "d_A",
            "d_p",
            "x_overflow",
        )
    }
    for _ in range(NSIM):
        diffs: list[float] = []
        fails: list[float] = []
        ev_a: list[bool] = []
        ev_x: list[bool] = []
        sil_a: list[bool] = []
        n_ovf = 0
        for _k in range(30):
            p = base[rng.randrange(len(base))]
            diffs.append(p["wa"] - p["wx"])
            if not p["pa"] and not p["px"]:
                fails.append(p["wa"] - p["wx"])
            ev_a.append(bool(p["da"]))
            ev_x.append(bool(p["dx"]))
            sil_a.append(False)
        for _k in range(30):
            e = pool[rng.randrange(len(pool))]
            wx, ovf, px = x_long(e, win, ratios[rng.randrange(len(ratios))])
            n_ovf += int(ovf)
            diffs.append(e["wall"] - wx)
            if not e["pass"] and not px:
                fails.append(e["wall"] - wx)
            ev_a.append(a_event(e))
            ev_x.append(False)
            sil_a.append(a_silent(e))
        acc["a_A"].append(float(sum(sil_a)))
        acc["a_p"].append(mcnemar_exact(sil_a, [False] * 60)["p"])
        acc["b_med"].append(statistics.median(diffs))
        acc["b_p"].append(wilcoxon(diffs)["p"])
        acc["c_med"].append(statistics.median(fails) if fails else 0.0)
        acc["c_p"].append(wilcoxon(fails)["p"])
        acc["c_n"].append(float(len(fails)))
        acc["d_A"].append(float(sum(ev_a)))
        acc["d_p"].append(mcnemar_exact(ev_a, ev_x)["p"])
        acc["x_overflow"].append(float(n_ovf))

    def rej(k: str, thr: float) -> float:
        return round(sum(1 for v in acc[k] if v < thr) / NSIM, 3)

    return {
        "x_window": win,
        "x_overflowed_long_entries": _summ(acc["x_overflow"]),
        "a_silent_overrun": {
            "label": "by construction on the X side (X = 0): mechanism check, outside Holm",
            "A_count_of_60": _summ(acc["a_A"]),
            "X_count_of_60": 0,
            "P_mcnemar_p_lt_0.05": rej("a_p", 0.05),
        },
        "b_wall": {
            "statistic": "median paired wall_A - wall_X, s (positive = X faster)",
            **_summ(acc["b_med"]),
            "P_p_lt_0.05": rej("b_p", 0.05),
            "P_p_lt_0.05_over_6": rej("b_p", 0.05 / M_F2),
        },
        "c_time_to_failure": {
            "statistic": "median paired wall_A - wall_X on both-fail entries, s",
            **_summ(acc["c_med"]),
            "n_both_fail": _summ(acc["c_n"]),
            "P_p_lt_0.05": rej("c_p", 0.05),
            "P_p_lt_0.05_over_6": rej("c_p", 0.05 / M_F2),
        },
        "d_hang_loop": {
            "A_count_of_60": _summ(acc["d_A"]),
            "X_count_of_60": 0,
            "P_p_lt_0.05": rej("d_p", 0.05),
            "note": "exact McNemar cannot reach p < 0.05 unless A-only discordant >= 6",
        },
    }


def verdict(m: dict[str, Any]) -> str:
    p = m["P_p_lt_0.05_over_6"]
    if p >= 0.5:
        return "REJECT (direction of the point)"
    return "NOT REJECT"


def build() -> dict[str, Any]:
    table: dict[str, Any] = {}
    for host in ("T2S", "XPS"):
        table[host] = {}
        for x in ("P", "C"):
            s = simulate(host, x)
            for k in ("b_wall", "c_time_to_failure"):
                s[k]["predicted_test_outcome"] = verdict(s[k])
            s["d_hang_loop"]["predicted_test_outcome"] = (
                "REJECT" if s["d_hang_loop"]["P_p_lt_0.05"] >= 0.5 else "NOT REJECT"
            )
            table[host][f"A vs {x}"] = s
    return {
        "id": "DEMO2_BH_F2_PREDICTIONS",
        "status": "registered with docs/amendments/DEMO2_AMEND_2026-10-23_OBJECTIVES.md before "
        "any held-out run; DERIVED",
        "generator": "tools/demo2_bh_predict.py",
        "runner_must_not_read_this_file": True,
        "inputs": {
            "calibration": {
                h: {a: d.split("interleaved_")[1][:8] for a, d in v.items()} for h, v in CAL.items()
            },
            "long_pilots_arm_A": {
                h: [d.split("interleaved_")[1][:8] for d in v] for h, v in LONG.items()
            },
            "entry_123": {
                "T2S_A": "cddcd9fd",
                "T2S_X": "e66a2a89",
                "XPS_A": "stall at 3,600 s (841b84e4 unsealed; d0dd5a37 pending)",
            },
            "max_prompt_source": OVER,
            "x_windows": WIN,
            "nsim": NSIM,
            "seed": SEED,
            "m_F2": M_F2,
        },
        "scoring": "HIT if the measured statistic lies inside [band_p05, band_p95] (b, c: median "
        "paired difference; a, d: A's count of 60) and the measured test outcome equals "
        "predicted_test_outcome (b, c, d only); partial = one of the two",
        "predictions": table,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    doc = build()
    a.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="ascii")
    for h, t in doc["predictions"].items():
        for c, v in t.items():
            print(h, c, json.dumps({k: v[k] for k in v if k != "x_window"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
