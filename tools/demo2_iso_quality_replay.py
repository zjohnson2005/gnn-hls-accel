"""DEMO-2 iso-quality replay (Task BE): cost-quality frontiers from local-only logs + one cloud log.

Registered in docs/amendments/DEMO2_ISO_QUALITY_2026-10-21.md. Mac, no model, $0.

Inputs:
- per arm, one or more interleaved local_only run dirs (policies/local_only/turn_ledger.json),
  run with --passive-router (per-turn passive_triggers). Logs without passive_triggers are
  REFUSED unless --derive-triggers (rebuilt from the ledger fields with the runner's own
  functions; n_steps = len(decoded_steps); recorded in the output);
- one cloud-only run (turn_ledger.json of a single-policy cloud_only run: per-turn decoded
  steps and cloud_usd), shared by every arm;
- the entry pin (for the BFCL checker).

Replay policy family (identical for every arm):
1. base: escalate entry i at the first local turn t with a passive trigger (mechanical or
   quality; a hang/stall/turn-budget record is a local error at its turn). Sticky. Then the
   merged trajectory = local decoded turns [0, t) + cloud decoded turns [t, end) is scored
   with the BFCL checker (score_multi_turn, as the live runner's score_hybrid_trajectory);
   cost = sum of the cloud log's cloud_usd for turns [t, end). Not triggered: the local-only
   outcome (local_pass), cost 0.
2. up: additional untriggered entries escalated at turn 0 (= the cloud-only outcome and
   cost), in a fixed random order (seed), j = 0..n_untriggered.
3. down: triggered entries thinned (kept local, local-only outcome), fixed random order,
   k = 0..n_triggered.
Frontier = all (mean $/task, pass rate) points of up and down; C_X(Q) = min cost with pass >= Q;
Q_X(c) = max pass with cost <= c.

Endpoints (reference arm R, default "A"; Q* = R's base pass rate, C* = R's base cost):
- primary dC_iso = C_R(Q*) - C_X(Q*) (positive = X cheaper), paired bootstrap CI;
- dQ_iso = Q_X(C*) - Q*, with exact McNemar at X's matched-cost point vs R's base point;
- $ per passed task at base points; area difference of Q_X(c) - Q_R(c) on a shared grid.
Paired bootstrap resamples entry indices with the same indices for every arm and the cloud
log (B, seed). Holm over all p-values in the output (McNemar per arm; bootstrap two-sided
p for dC_iso per arm).

  python tools/demo2_iso_quality_replay.py --pin <pin.json> --cloud <dir> \\
      --arm A=<dir>[,<dir>] --arm C=<dir> --bfcl-unpacked <dir> --out <out.json>
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import types
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HANG_STATES = ("hang", "stall", "turn_budget_exceeded")
ScoreFn = Callable[[dict[str, Any], list[list[list[str]]]], bool]


# ------------------------------------------------------------------ loading
def _ledger_entries(d: Path) -> list[dict[str, Any]]:
    cands = [d / "policies" / "local_only" / "turn_ledger.json", d / "turn_ledger.json"]
    for c in cands:
        if c.is_file():
            return list(json.loads(c.read_text(encoding="utf-8")).get("entries") or [])
    raise SystemExit(f"REFUSED -- no turn_ledger.json under {d}")


def derive_triggers(turn: dict[str, Any], *, last: bool, stop_reason: str | None) -> dict[str, Any]:
    """Rebuild passive_triggers from a ledger row with the runner's own decision functions."""
    from tools.run_h1_hybrid import decide_bounceback, decide_hybrid_mechanical

    gen_err = bool(last and stop_reason == "generation_error")
    if turn.get("ctx_overflow"):
        mech: str | None = "ctx_overflow"
    else:
        _m, mech = decide_hybrid_mechanical(
            ttft_s=turn.get("ttft_s"),
            decode_tok_s=turn.get("decode_tok_s"),
            generation_error=gen_err,
        )
    _q, qual = decide_bounceback(
        emitted_parseable_tool_call=bool(turn.get("emitted_parseable_tool_call")),
        n_steps=len(turn.get("decoded_steps") or []),
        tool_exec_error=bool(turn.get("tool_exec_error")),
    )
    return {"mechanical": mech, "quality": qual, "derived": True}


def load_arm(dirs: Sequence[Path], *, derive: bool) -> dict[str, dict[str, Any]]:
    """entry_id -> {turns: [decoded per turn], trigger_turn: int|None, local_pass: bool}."""
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        for e in _ledger_entries(d):
            eid = str(e["entry_id"])
            turns = [t for t in e.get("turns") or [] if t.get("placement") == "local"]
            turns.sort(key=lambda t: int(t["turn"]))
            trig: int | None = None
            derived = False
            for k, t in enumerate(turns):
                pt = t.get("passive_triggers")
                if pt is None:
                    if not derive:
                        raise SystemExit(
                            f"REFUSED -- {d}: {eid} turn {t.get('turn')} has no passive_triggers "
                            "(run with --passive-router, or pass --derive-triggers)"
                        )
                    pt = derive_triggers(
                        t, last=k == len(turns) - 1, stop_reason=e.get("stop_reason")
                    )
                    derived = True
                if pt.get("mechanical") or pt.get("quality"):
                    trig = int(t["turn"])
                    break
            state = str(e.get("status") or "")
            if trig is None and (state in HANG_STATES or str(e.get("stop_reason")) in HANG_STATES):
                trig = int(turns[-1]["turn"]) if turns else 0
            out[eid] = {
                "decoded": [list(t.get("decoded_steps") or []) for t in turns],
                "trigger_turn": trig,
                "local_pass": bool(e.get("local_pass")),
                "derived_triggers": derived,
            }
        eq = d / "policies" / "local_only" / "entry_quality.json"
        if eq.is_file():
            doc = json.loads(eq.read_text(encoding="utf-8"))
            rows = doc.get("entries") if isinstance(doc, dict) else doc
            for r in rows or []:
                eid = str(r.get("entry_id"))
                if str(r.get("status")) == "skipped_hang" and eid not in out:
                    # A hang/stall/budget fire is a local error; its partial local turns are
                    # not in this log, so the replay escalates it at turn 0 (recorded).
                    out[eid] = {
                        "decoded": [],
                        "trigger_turn": 0,
                        "local_pass": False,
                        "derived_triggers": False,
                        "skipped_hang": True,
                    }
    return out


def load_cloud(dirs: Sequence[Path]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        for e in _ledger_entries(d):
            turns = sorted(e.get("turns") or [], key=lambda t: int(t["turn"]))
            out[str(e["entry_id"])] = {
                "decoded": [list(t.get("decoded_steps") or []) for t in turns],
                "usd": [float(t.get("cloud_usd") or 0.0) for t in turns],
                "pass": bool(e.get("hybrid_pass")),
            }
    return out


# ------------------------------------------------------------------ per-entry outcomes
def entry_outcomes(
    arm: dict[str, dict[str, Any]],
    cloud: dict[str, dict[str, Any]],
    ids: list[str],
    score: ScoreFn,
    entries: dict[str, dict[str, Any]],
) -> dict[str, list[Any]]:
    """Vectors over ids: local (pass), base (pass, usd, triggered), full cloud (pass, usd)."""
    lp, bp, bu, trig, cp, cu = [], [], [], [], [], []
    for i in ids:
        a, c = arm[i], cloud[i]
        lp.append(a["local_pass"])
        cp.append(c["pass"])
        cu.append(sum(c["usd"]))
        t = a["trigger_turn"]
        if t is None:
            trig.append(False)
            bp.append(a["local_pass"])
            bu.append(0.0)
        else:
            trig.append(True)
            merged = [list(x) for x in a["decoded"][:t]] + [list(x) for x in c["decoded"][t:]]
            bp.append(c["pass"] if t == 0 else bool(score(entries[i], merged)))
            bu.append(sum(c["usd"][t:]))
    return {
        "local": lp,
        "base_pass": bp,
        "base_usd": bu,
        "trig": trig,
        "cloud_pass": cp,
        "cloud_usd": cu,
    }


def frontier(o: dict[str, list[Any]], idx: Sequence[int], seed: int) -> list[tuple[float, float]]:
    """(mean usd, pass rate) points of the up and down families on the resampled indices."""
    n = len(idx)
    rng = random.Random(seed)
    trig = [k for k in range(n) if o["trig"][idx[k]]]
    untrig = [k for k in range(n) if not o["trig"][idx[k]]]
    rng.shuffle(trig)
    rng.shuffle(untrig)
    p = [float(o["base_pass"][idx[k]]) for k in range(n)]
    u = [float(o["base_usd"][idx[k]]) for k in range(n)]
    sp, su = sum(p), sum(u)
    pts = [(su / n, sp / n)]
    tp, tu = sp, su
    for k in trig:  # thin: keep local
        tp += float(o["local"][idx[k]]) - p[k]
        tu -= u[k]
        pts.append((tu / n, tp / n))
    tp, tu = sp, su
    for k in untrig:  # escalate at turn 0
        tp += float(o["cloud_pass"][idx[k]]) - p[k]
        tu += float(o["cloud_usd"][idx[k]]) - u[k]
        pts.append((tu / n, tp / n))
    return pts


def c_at(pts: list[tuple[float, float]], q: float) -> float:
    ok = [c for c, qq in pts if qq >= q - 1e-12]
    return min(ok) if ok else math.inf


def q_at(pts: list[tuple[float, float]], c: float) -> float:
    ok = [qq for cc, qq in pts if cc <= c + 1e-12]
    return max(ok) if ok else -math.inf


def matched_point_passes(o: dict[str, list[Any]], c_star: float, seed: int) -> list[bool]:
    """Per-entry passes at X's best point with cost <= c_star (for McNemar)."""
    n = len(o["trig"])
    idx = list(range(n))
    rng = random.Random(seed)
    trig = [k for k in idx if o["trig"][k]]
    untrig = [k for k in idx if not o["trig"][k]]
    rng.shuffle(trig)
    rng.shuffle(untrig)
    cands: list[tuple[float, float, list[bool]]] = []
    p = [bool(x) for x in o["base_pass"]]
    u = [float(x) for x in o["base_usd"]]
    cands.append((sum(u) / n, sum(p) / n, list(p)))
    p2, u2 = list(p), list(u)
    for k in trig:
        p2[k], u2[k] = bool(o["local"][k]), 0.0
        cands.append((sum(u2) / n, sum(p2) / n, list(p2)))
    p3, u3 = list(p), list(u)
    for k in untrig:
        p3[k], u3[k] = bool(o["cloud_pass"][k]), float(o["cloud_usd"][k])
        cands.append((sum(u3) / n, sum(p3) / n, list(p3)))
    ok = [c for c in cands if c[0] <= c_star + 1e-12]
    best = max(ok, key=lambda c: (c[1], -c[0])) if ok else min(cands, key=lambda c: c[0])
    return best[2]


def mcnemar_exact(x: Sequence[bool], r: Sequence[bool]) -> dict[str, Any]:
    b = sum(1 for a, c in zip(x, r, strict=True) if a and not c)
    c = sum(1 for a, cc in zip(x, r, strict=True) if cc and not a)
    n = b + c
    if n == 0:
        return {"b": 0, "c": 0, "p": 1.0}
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return {"b": b, "c": c, "p": min(1.0, 2 * p)}


def holm(ps: dict[str, float]) -> dict[str, float]:
    order = sorted(ps.items(), key=lambda kv: kv[1])
    m = len(order)
    out: dict[str, float] = {}
    run = 0.0
    for rank, (k, p) in enumerate(order):
        run = max(run, min(1.0, (m - rank) * p))
        out[k] = run
    return out


# ------------------------------------------------------------------ analysis
def analyse(
    arms: dict[str, dict[str, list[Any]]], ref: str, *, boot: int, seed: int, grid_n: int = 50
) -> dict[str, Any]:
    n = len(arms[ref]["trig"])
    full = list(range(n))
    pts = {a: frontier(o, full, seed) for a, o in arms.items()}
    q_star = pts[ref][0][1]
    c_star = pts[ref][0][0]
    c_max = max(sum(o["cloud_usd"]) / n for o in arms.values())
    grid = [c_max * g / (grid_n - 1) for g in range(grid_n)]
    res: dict[str, Any] = {"n": n, "reference": ref, "Q_star": q_star, "C_star": c_star, "arms": {}}
    rng = random.Random(seed + 1)
    boots = [[rng.randrange(n) for _ in range(n)] for _ in range(boot)]
    pvals: dict[str, float] = {}
    for a, o in arms.items():
        base_c, base_q = pts[a][0]
        d_c = c_at(pts[ref], q_star) - c_at(pts[a], q_star)
        d_q = q_at(pts[a], c_star) - q_star
        area = sum(q_at(pts[a], c) - q_at(pts[ref], c) for c in grid) / grid_n
        passes = sum(bool(x) for x in o["base_pass"])
        rec: dict[str, Any] = {
            "base_point": {"usd_per_task": base_c, "pass_rate": base_q, "passes": passes},
            "usd_per_passed_task": (base_c * n / passes) if passes else None,
            "dC_iso": d_c,
            "dQ_iso": d_q,
            "area_diff": area,
            "n_triggered": sum(bool(x) for x in o["trig"]),
            "local_passes": sum(bool(x) for x in o["local"]),
            "frontier": [{"usd": c, "pass": q} for c, q in sorted(set(pts[a]))],
        }
        if a != ref:
            dcs, dqs = [], []
            for b, idx in enumerate(boots):
                pr = frontier(arms[ref], idx, seed + 7 + b)
                px = frontier(o, idx, seed + 7 + b)
                qs = pr[0][1]
                dcs.append(c_at(pr, qs) - c_at(px, qs))
                dqs.append(q_at(px, pr[0][0]) - qs)
            fin = sorted(x for x in dcs if math.isfinite(x))
            lo: float | None
            hi: float | None
            if fin:
                lo, hi = fin[int(0.025 * len(fin))], fin[min(len(fin) - 1, int(0.975 * len(fin)))]
                p_two = 2 * min(
                    sum(1 for x in fin if x <= 0) / len(fin),
                    sum(1 for x in fin if x >= 0) / len(fin),
                )
            else:
                lo = hi = None
                p_two = 1.0
            fq = sorted(x for x in dqs if math.isfinite(x))
            rec["dC_iso_ci95"] = [lo, hi]
            rec["dC_iso_boot_infinite"] = len(dcs) - len(fin)
            rec["dQ_iso_ci95"] = (
                [fq[int(0.025 * len(fq))], fq[min(len(fq) - 1, int(0.975 * len(fq)))]]
                if fq
                else None
            )
            mc = mcnemar_exact(
                matched_point_passes(o, c_star, seed), [bool(x) for x in arms[ref]["base_pass"]]
            )
            rec["mcnemar_at_matched_cost"] = mc
            pvals[f"{a}:dC_iso"] = min(1.0, p_two)
            pvals[f"{a}:mcnemar"] = mc["p"]
        res["arms"][a] = rec
    res["holm"] = holm(pvals) if pvals else {}
    res["bootstrap"] = {"B": boot, "seed": seed, "paired": "same entry indices for every arm"}
    return res


def bfcl_score_fn(bfcl_unpacked: Path) -> ScoreFn:
    if "openvino_genai" not in sys.modules:
        sys.modules["openvino_genai"] = types.ModuleType("openvino_genai")
    sys.path.insert(0, str(bfcl_unpacked))
    import tools.bfcl_feasibility_probe as probe

    probe.BFCL_UNPACKED = bfcl_unpacked

    def score(entry: dict[str, Any], merged: list[list[list[str]]]) -> bool:
        r = probe.score_multi_turn(
            test_entry=entry["raw_entry"],
            ground_truth=entry["reference"],
            model_result_decoded=merged,
            test_category=str(entry.get("category") or "multi_turn_base"),
            model_name=f"replay_{entry['id']}",
        )
        return bool(r.get("valid"))

    return score


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pin", type=Path, required=True)
    ap.add_argument("--cloud", required=True, help="cloud-only run dir(s), comma-separated")
    ap.add_argument("--arm", action="append", required=True, help="NAME=dir[,dir]")
    ap.add_argument("--reference", default="A")
    ap.add_argument("--bfcl-unpacked", type=Path, required=True)
    ap.add_argument("--derive-triggers", action="store_true")
    ap.add_argument("--boot", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=20261023)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    pin = json.loads(a.pin.read_text(encoding="utf-8"))
    entries = {str(e["id"]): e for e in pin}
    ids = [str(e["id"]) for e in pin]
    cloud = load_cloud([Path(x) for x in a.cloud.split(",")])
    score = bfcl_score_fn(a.bfcl_unpacked)
    arms: dict[str, dict[str, list[Any]]] = {}
    derived: dict[str, int] = {}
    for spec in a.arm:
        name, dirs = spec.split("=", 1)
        arm = load_arm([Path(x) for x in dirs.split(",")], derive=a.derive_triggers)
        missing = [i for i in ids if i not in arm or i not in cloud]
        if missing:
            raise SystemExit(f"REFUSED -- arm {name} or the cloud log lacks {len(missing)} pin ids")
        derived[name] = sum(1 for i in ids if arm[i]["derived_triggers"])
        arms[name] = entry_outcomes(arm, cloud, ids, score, entries)
    if a.reference not in arms:
        raise SystemExit(f"REFUSED -- reference arm {a.reference} not given")
    res = analyse(arms, a.reference, boot=a.boot, seed=a.seed)
    res["derived_trigger_entries"] = derived
    res["inputs"] = {"pin": str(a.pin), "cloud": a.cloud, "arms": a.arm}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="ascii")
    for k, v in res["arms"].items():
        print(k, {x: v.get(x) for x in ("base_point", "dC_iso", "dC_iso_ci95", "dQ_iso")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
