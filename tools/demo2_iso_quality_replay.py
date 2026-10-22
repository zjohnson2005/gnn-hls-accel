"""DEMO-2 iso-quality replay (Task BE, fixed in Task BF0): frontiers from local-only logs + one cloud log.

Registered in docs/amendments/DEMO2_ISO_QUALITY_2026-10-21.md as amended by
docs/amendments/DEMO2_PREFREEZE_2026-10-22.md (sections cited as PF n). Mac, no model, $0.

Inputs:
- per arm, one or more interleaved local_only run dirs (policies/local_only/turn_ledger.json),
  run with --passive-router (per-turn passive_triggers). Logs without passive_triggers are
  REFUSED; --derive-triggers rebuilds them from the ledger fields with the runner's own
  functions, and is itself REFUSED on DEMO2_HELDOUT_60 (PF 13);
- one cloud-only run (single-policy cloud_only turn_ledger.json), shared by every arm. Every
  turn is REPRICED from its cloud_requests with the cache-aware formula (PF 1); a billed request
  without cache fields is REFUSED;
- the entry pin (for the BFCL checker).

Replay policy family (identical for every arm):
1. base: escalate entry i at the first local turn t with a passive trigger (mechanical or
   quality). A hang / stall / turn-budget fire is a local error at its turn t_h (PF 7, from the
   skipped_hang row's hang_ref.turn); when the local turns [0, t_h) are not in the arm's logs
   the entry is escalated at turn 0 (counted in hang_prefix_missing). Sticky.
   Cost model (PF 5): "splice" (primary, cache-optimistic) = local turns [0, t) + cloud turns
   [t, end), scored with the BFCL checker, cost = repriced cloud turns t..end; "rerun" = the
   whole cloud entry (cloud pass, all turns' cost); "cold" = splice with the first cloud
   request of turn t (t > 0) pricing its cache reads at the write rate.
   Not triggered: the local-only outcome, cost 0.
2. Frontier = the analytic expectation over random orderings (PF 11): the segment from the base
   point to "every triggered entry kept local" (down) and the segment from the base point to
   "every untriggered entry escalated at turn 0" (up). C_X(Q) = min cost on the segments with
   pass >= Q (+inf if none); Q_X(c) = max pass with cost <= c.

Endpoints per contrast X vs R (R = --reference, default "A", plus --contrast X:R pairs):
- dC_iso = C_R(Q*) - C_X(Q*), Q* = R's base pass rate (positive = X cheaper); paired bootstrap
  (B, seed; same entry indices for every arm and the cloud log). -inf draws are KEPT and count
  as <= 0 (PF 3); a -inf point is "X does not reach Q*" and never rejects.
- dQ_iso = Q_X(C*) - Q* on the expected frontier; exact McNemar at the matched point pi (PF 11:
  k = floor(lambda* n_seg) entries moved in ascending sha256("20261023:" + id) order).
- $ per passed task at base points; area difference of Q_X(c) - Q_R(c) on a 50-point grid.
Family (PF 2): the contrast --primary (default P) vs A is the only confirmatory test per host;
everything else is labelled secondary (unadjusted CIs). Across hosts: the "family" subcommand
applies the fixed sequence T2S then XPS. Every CI is conditional on the one cloud log (PF 11).

  python tools/demo2_iso_quality_replay.py --pin <pin.json> --cloud <dir> \\
      --arm A=<dir>[,<dir>] --arm P=<dir> --bfcl-unpacked <dir> --host T2S --out <out.json>
  python tools/demo2_iso_quality_replay.py family --t2s <t2s.json> --xps <xps.json> --out <f.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import types
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HANG_STATES = ("hang", "stall", "turn_budget_exceeded")
MODES = ("splice", "rerun", "cold")
DEMO2_HELDOUT_60_SHA256 = "cc74a37ed84ed95b0f4dd4b8d7eb774f2737230dcfca01321fe136cdbfbca447"
LOW_MEM_MB = 1000.0
ALPHA = 0.05
PI_SALT = "20261023:"
ScoreFn = Callable[[dict[str, Any], list[list[list[str]]]], bool]
Seg = tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


def refuse(msg: str) -> SystemExit:
    return SystemExit(f"REFUSED -- {msg}")


# ------------------------------------------------------------------ loading
def _ledger_entries(d: Path) -> list[dict[str, Any]]:
    cands = [d / "policies" / "local_only" / "turn_ledger.json", d / "turn_ledger.json"]
    for c in cands:
        if c.is_file():
            return list(json.loads(c.read_text(encoding="utf-8")).get("entries") or [])
    raise refuse(f"no turn_ledger.json under {d}")


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


def _quality_rows(d: Path) -> list[dict[str, Any]]:
    for c in (d / "policies" / "local_only" / "entry_quality.json", d / "entry_quality.json"):
        if c.is_file():
            doc = json.loads(c.read_text(encoding="utf-8"))
            rows = doc.get("entries") if isinstance(doc, dict) else doc
            return list(rows or [])
    return []


def _hang_events(d: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in sorted(d.glob("**/hang_events.json")):
        doc = json.loads(c.read_text(encoding="utf-8-sig"))
        out.extend(ev for ev in doc.get("events") or [] if ev.get("outcome") in HANG_STATES)
    return out


def _low_mem_turns(d: Path) -> int:
    n = 0
    for c in sorted(d.glob("**/local_turn_telemetry.jsonl")):
        for line in c.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            mem = json.loads(line).get("memory") or {}
            v = mem.get("min_available_mb")
            if v is not None and float(v) < LOW_MEM_MB:
                n += 1
    return n


def load_arm(dirs: Sequence[Path], *, derive: bool) -> dict[str, dict[str, Any]]:
    """entry_id -> {decoded, trigger_turn, local_pass, derived_triggers, hang fields}."""
    out: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    for d in dirs:
        for e in _ledger_entries(d):
            eid = str(e["entry_id"])
            if eid in out:
                raise refuse(f"{d}: duplicate entry {eid} across this arm's logs")
            if e.get("local_pass") is None:
                raise refuse(f"{d}: {eid} has local_pass None")
            turns = [t for t in e.get("turns") or [] if t.get("placement") == "local"]
            turns.sort(key=lambda t: int(t["turn"]))
            trig: int | None = None
            derived = False
            for k, t in enumerate(turns):
                pt = t.get("passive_triggers")
                if pt is None:
                    if not derive:
                        raise refuse(
                            f"{d}: {eid} turn {t.get('turn')} has no passive_triggers "
                            "(run with --passive-router, or pass --derive-triggers)"
                        )
                    pt = derive_triggers(
                        t, last=k == len(turns) - 1, stop_reason=e.get("stop_reason")
                    )
                    derived = True
                if pt.get("mechanical") or pt.get("quality"):
                    trig = int(t["turn"])
                    break
            out[eid] = {
                "decoded": [list(t.get("decoded_steps") or []) for t in turns],
                "trigger_turn": trig,
                "local_pass": bool(e["local_pass"]),
                "derived_triggers": derived,
            }
        for r in _quality_rows(d):
            if str(r.get("status")) != "skipped_hang":
                continue
            eid = str(r.get("entry_id"))
            if eid in out:
                raise refuse(f"{d}: skipped_hang {eid} also has a ledger row")
            t_h = (r.get("hang_ref") or {}).get("turn")
            if t_h is None:
                raise refuse(f"{d}: skipped_hang {eid} has no hang_ref.turn")
            # PF 7: escalate at t_h; a fired worker writes no partial ledger row, so the local
            # prefix [0, t_h) is missing whenever t_h > 0 -> turn-0 escalation (conservative).
            out[eid] = {
                "decoded": [],
                "trigger_turn": 0,
                "local_pass": False,
                "derived_triggers": False,
                "skipped_hang": True,
                "hang_turn": int(t_h),
                "hang_prefix_missing": int(t_h) > 0,
            }
        events.extend(_hang_events(d))
    for ev in events:
        eid = str(ev.get("entry_id"))
        if eid not in out:
            raise refuse(
                f"hang event for {eid} ({ev.get('outcome')}, run {ev.get('run_id')}) has no "
                "skipped_hang row and no ledger row in this arm's logs"
            )
    return out


def price_date(dirs: Sequence[Path], override: str | None) -> date:
    if override:
        return date.fromisoformat(override)
    for d in dirs:
        for c in (d / "plan.json", d / "policies" / "cloud_only" / "plan.json"):
            if c.is_file():
                s = json.loads(c.read_text(encoding="utf-8")).get("started_utc")
                if s:
                    return date.fromisoformat(str(s)[:10])
    raise refuse("no started_utc in the cloud log's plan.json; pass --price-date")


def load_cloud(dirs: Sequence[Path], *, table: Any, when: date) -> dict[str, dict[str, Any]]:
    """entry_id -> per-turn decoded, repriced usd, cold-handoff delta, cloud pass."""
    from tools.h1_cloud_accounting import price_request

    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        for e in _ledger_entries(d):
            eid = str(e["entry_id"])
            if eid in out:
                raise refuse(f"{d}: duplicate cloud entry {eid}")
            if e.get("hybrid_pass") is None:
                raise refuse(f"{d}: cloud entry {eid} has hybrid_pass None")
            turns = sorted(e.get("turns") or [], key=lambda t: int(t["turn"]))
            usd: list[float] = []
            cold: list[float] = []
            for t in turns:
                reqs = t.get("cloud_requests")
                if reqs is None:
                    if float(t.get("cloud_usd") or 0.0) > 0:
                        raise refuse(f"{d}: {eid} turn {t.get('turn')} has cost but no requests")
                    reqs = []
                usd.append(sum(price_request(r, table=table, when=when) for r in reqs))
                billed = [r for r in reqs if r.get("ok") is not False]
                if billed:
                    first = dict(billed[0])
                    hot = price_request(first, table=table, when=when)
                    first["cache_creation_input_tokens"] = int(
                        first["cache_creation_input_tokens"]
                    ) + int(first["cache_read_input_tokens"])
                    first["cache_read_input_tokens"] = 0
                    cold.append(price_request(first, table=table, when=when) - hot)
                else:
                    cold.append(0.0)
            out[eid] = {
                "decoded": [list(t.get("decoded_steps") or []) for t in turns],
                "usd": usd,
                "cold_delta": cold,
                "pass": bool(e["hybrid_pass"]),
            }
    return out


# ------------------------------------------------------------------ per-entry outcomes
def entry_outcomes(
    arm: dict[str, dict[str, Any]],
    cloud: dict[str, dict[str, Any]],
    ids: list[str],
    score: ScoreFn,
    entries: dict[str, dict[str, Any]],
    mode: str = "splice",
) -> dict[str, list[Any]]:
    """Vectors over ids: local (pass), base (pass, usd, triggered), full cloud (pass, usd)."""
    if mode not in MODES:
        raise ValueError(mode)
    lp, bp, bu, trig, cp, cu, late = [], [], [], [], [], [], []
    for i in ids:
        a, c = arm[i], cloud[i]
        usd = list(c["usd"])
        cold = list(c.get("cold_delta") or [0.0] * len(usd))
        lp.append(a["local_pass"])
        cp.append(c["pass"])
        cu.append(sum(usd))
        t = a["trigger_turn"]
        if t is None:
            trig.append(False)
            late.append(False)
            bp.append(a["local_pass"])
            bu.append(0.0)
            continue
        trig.append(True)
        late.append(t > 0)
        if mode == "rerun" or t == 0:
            bp.append(c["pass"])
            bu.append(sum(usd))
            continue
        merged = [list(x) for x in a["decoded"][:t]] + [list(x) for x in c["decoded"][t:]]
        bp.append(bool(score(entries[i], merged)))
        bu.append(sum(usd[t:]) + (cold[t] if mode == "cold" and t < len(cold) else 0.0))
    return {
        "ids": list(ids),
        "local": lp,
        "base_pass": bp,
        "base_usd": bu,
        "trig": trig,
        "late": late,
        "cloud_pass": cp,
        "cloud_usd": cu,
    }


# ------------------------------------------------------------------ analytic frontier (PF 11)
def segments(o: dict[str, list[Any]], idx: Sequence[int]) -> Seg:
    """(base, down end, up end) as (mean usd, pass rate) over the (resampled) indices."""
    n = len(idx)
    sp = su = dp = du = upp = upu = 0.0
    for k in idx:
        p, u = float(o["base_pass"][k]), float(o["base_usd"][k])
        sp += p
        su += u
        if o["trig"][k]:
            dp += float(o["local"][k]) - p
            du -= u
        else:
            upp += float(o["cloud_pass"][k]) - p
            upu += float(o["cloud_usd"][k]) - u
    base = (su / n, sp / n)
    return base, ((su + du) / n, (sp + dp) / n), ((su + upu) / n, (sp + upp) / n)


def _feasible(v0: float, v1: float, bound: float, ge: bool) -> tuple[float, float] | None:
    """lambda interval in [0, 1] where v0 + l (v1 - v0) >= bound (ge) or <= bound."""
    eps = 1e-12
    if abs(v1 - v0) < 1e-15:
        ok = v0 >= bound - eps if ge else v0 <= bound + eps
        return (0.0, 1.0) if ok else None
    lb = (bound - v0) / (v1 - v0)
    rising = v1 > v0
    lo, hi = (max(0.0, lb - eps), 1.0) if rising == ge else (0.0, min(1.0, lb + eps))
    return (lo, hi) if lo <= hi else None


def _seg_points(segs: Seg) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return [(segs[0], segs[1]), (segs[0], segs[2])]


def c_at(segs: Seg, q: float) -> float:
    best = math.inf
    for (c0, q0), (c1, q1) in _seg_points(segs):
        iv = _feasible(q0, q1, q, ge=True)
        if iv is not None:
            best = min(best, *(c0 + lam * (c1 - c0) for lam in iv))
    return best


def _q_at_lam(segs: Seg, c: float) -> tuple[float, int, float]:
    """(max pass with cost <= c, segment 0 down / 1 up, lambda)."""
    best = (-math.inf, 0, 0.0)
    for s, ((c0, q0), (c1, q1)) in enumerate(_seg_points(segs)):
        iv = _feasible(c0, c1, c, ge=False)
        if iv is not None:
            for lam in iv:
                q = q0 + lam * (q1 - q0)
                if q > best[0] + 1e-15:
                    best = (q, s, lam)
    return best


def q_at(segs: Seg, c: float) -> float:
    return _q_at_lam(segs, c)[0]


def _pi_order(ids: Sequence[str], members: Sequence[int]) -> list[int]:
    return sorted(members, key=lambda k: hashlib.sha256((PI_SALT + ids[k]).encode()).hexdigest())


def matched_point_passes(
    o: dict[str, list[Any]], c_star: float
) -> tuple[list[bool], dict[str, Any]]:
    """Per-entry passes at the realized matched point pi (PF 11) for McNemar."""
    n = len(o["trig"])
    segs = segments(o, range(n))
    _q, s, lam = _q_at_lam(segs, c_star)
    p = [bool(x) for x in o["base_pass"]]
    group = [k for k in range(n) if bool(o["trig"][k]) == (s == 0)]
    kk = math.floor(lam * len(group) + 1e-9)
    for k in _pi_order(o["ids"], group)[:kk]:
        p[k] = bool(o["local"][k]) if s == 0 else bool(o["cloud_pass"][k])
    return p, {"segment": "down" if s == 0 else "up", "lambda": lam, "moved": kk}


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
    """Kept for reference; PF 2 replaced the Holm family (not used in the output)."""
    order = sorted(ps.items(), key=lambda kv: kv[1])
    m = len(order)
    out: dict[str, float] = {}
    run = 0.0
    for rank, (k, p) in enumerate(order):
        run = max(run, min(1.0, (m - rank) * p))
        out[k] = run
    return out


def _num(x: float | None) -> float | str | None:
    if x is None:
        return None
    if math.isinf(x):
        return "-inf" if x < 0 else "inf"
    return x


def _boot_dc(
    x: dict[str, list[Any]], r: dict[str, list[Any]], boots: list[list[int]]
) -> dict[str, Any]:
    dcs: list[float] = []
    for idx in boots:
        sr, sx = segments(r, idx), segments(x, idx)
        qs = sr[0][1]
        dcs.append(c_at(sr, qs) - c_at(sx, qs))
    srt = sorted(dcs)
    nb = len(srt)
    lo, hi = srt[int(0.025 * nb)], srt[min(nb - 1, int(0.975 * nb))]
    le = sum(1 for v in srt if v <= 0) / nb
    ge = sum(1 for v in srt if v >= 0) / nb
    return {
        "ci95": [_num(lo), _num(hi)],
        "p_two_sided": min(1.0, 2 * min(le, ge)),
        "n_neg_inf_draws": sum(1 for v in srt if v == -math.inf),
        "_lo": lo,
        "_hi": hi,
    }


# ------------------------------------------------------------------ analysis
def contrast(
    x: dict[str, list[Any]], r: dict[str, list[Any]], boots: list[list[int]], *, grid_n: int = 50
) -> dict[str, Any]:
    n = len(r["trig"])
    full = list(range(n))
    sx, sr = segments(x, full), segments(r, full)
    c_star, q_star = sr[0]
    d_c = c_at(sr, q_star) - c_at(sx, q_star)
    d_q = q_at(sx, c_star) - q_star
    c_max = max(sum(o["cloud_usd"]) / n for o in (x, r))
    grid = [c_max * g / (grid_n - 1) for g in range(grid_n)]
    area = sum(q_at(sx, c) - q_at(sr, c) for c in grid) / grid_n
    bt = _boot_dc(x, r, boots)
    pi_pass, pi = matched_point_passes(x, c_star)
    rec: dict[str, Any] = {
        "Q_star": q_star,
        "C_star": c_star,
        "C_R_at_Q_star": c_at(sr, q_star),
        "dC_iso": _num(d_c),
        "dC_iso_rel": _num(d_c / c_at(sr, q_star)) if c_at(sr, q_star) > 0 else None,
        "dC_iso_ci95": bt["ci95"],
        "dC_iso_p_two_sided": bt["p_two_sided"],
        "dC_iso_boot_neg_inf": bt["n_neg_inf_draws"],
        "reaches_Q_star": math.isfinite(d_c),
        "dQ_iso": _num(d_q),
        "area_diff": area,
        "matched_point_pi": pi,
        "mcnemar_at_matched_cost": mcnemar_exact(pi_pass, [bool(v) for v in r["base_pass"]]),
    }
    rec["ci_excludes_0"] = bool(math.isfinite(d_c) and (bt["_lo"] > 0 or bt["_hi"] < 0))
    return rec


def arm_summary(o: dict[str, list[Any]]) -> dict[str, Any]:
    n = len(o["trig"])
    base_c, base_q = segments(o, range(n))[0]
    passes = sum(bool(v) for v in o["base_pass"])
    nt = sum(bool(v) for v in o["trig"])
    return {
        "base_point": {"usd_per_task": base_c, "pass_rate": base_q, "passes": passes},
        "usd_per_passed_task": (base_c * n / passes) if passes else None,
        "n_triggered": nt,
        "share_escalations_turn_gt0": (sum(bool(v) for v in o["late"]) / nt) if nt else None,
        "local_passes": sum(bool(v) for v in o["local"]),
    }


def analyse(
    arms_by_mode: dict[str, dict[str, dict[str, list[Any]]]],
    pairs: list[tuple[str, str]],
    *,
    primary: tuple[str, str] | None,
    boot: int,
    seed: int,
    subset: Sequence[int] | None = None,
) -> dict[str, Any]:
    """arms_by_mode[mode][arm] = outcome vectors; pairs = (X, R) contrasts."""
    any_mode = next(iter(arms_by_mode.values()))
    n_all = len(next(iter(any_mode.values()))["trig"])
    keep = list(subset) if subset is not None else list(range(n_all))

    def sub(o: dict[str, list[Any]]) -> dict[str, list[Any]]:
        return {k: [v[i] for i in keep] for k, v in o.items()}

    n = len(keep)
    rng = random.Random(seed + 1)
    boots = [[rng.randrange(n) for _ in range(n)] for _ in range(boot)]
    res: dict[str, Any] = {"n": n, "arms": {}, "contrasts": {}}
    splice = {a: sub(o) for a, o in arms_by_mode["splice"].items()}
    for a, o in splice.items():
        res["arms"][a] = arm_summary(o)
    for x, r in pairs:
        key = f"{x} vs {r}"
        role = "primary" if primary == (x, r) else "secondary"
        rec: dict[str, Any] = {"role": role}
        for mode, arms in arms_by_mode.items():
            rec[mode] = contrast(sub(arms[x]), sub(arms[r]), boots)
        s = rec["splice"]
        if role == "primary":
            dc = s["dC_iso"]
            rec["rejects_at_alpha_0.05"] = bool(
                s["reaches_Q_star"]
                and isinstance(dc, float)
                and dc > 0
                and s["dC_iso_p_two_sided"] < ALPHA
                and s["ci_excludes_0"]
            )
            if not s["reaches_Q_star"]:
                rec["note"] = f"{x} does not reach Q*"
        res["contrasts"][key] = rec
    res["bootstrap"] = {
        "B": boot,
        "seed": seed,
        "paired": "same entry indices for every arm and the cloud log",
        "conditional_on": "the one shared cloud-only log (cloud run-to-run variance not included)",
    }
    return res


def fixed_sequence(t2s: dict[str, Any], xps: dict[str, Any]) -> dict[str, Any]:
    """PF 2: T2S at alpha 0.05; XPS tested only if T2S rejects."""

    def prim(doc: dict[str, Any]) -> dict[str, Any] | None:
        for k, v in (doc.get("all") or {}).get("contrasts", {}).items():
            if v.get("role") == "primary":
                return {
                    "contrast": k,
                    "rejects": bool(v.get("rejects_at_alpha_0.05")),
                    **v["splice"],
                }
        return None

    pt, px = prim(t2s), prim(xps)
    out: dict[str, Any] = {"rule": "fixed sequence T2S then XPS, each at alpha 0.05 (PF 2)"}
    out["T2S"] = {"tested": pt is not None, "claim": bool(pt and pt["rejects"]), "primary": pt}
    xps_tested = bool(pt and pt["rejects"]) and px is not None
    out["XPS"] = {
        "tested": xps_tested,
        "claim": bool(xps_tested and px and px["rejects"]),
        "primary": px,
        "note": None if xps_tested else "not tested: T2S did not reject (or a log is missing)",
    }
    return out


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


def _clean(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    if isinstance(o, float) and math.isinf(o):
        return "-inf" if o < 0 else "inf"
    return o


def family_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="PF 2 fixed sequence across hosts")
    ap.add_argument("--t2s", type=Path, required=True)
    ap.add_argument("--xps", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    doc = fixed_sequence(
        json.loads(a.t2s.read_text(encoding="utf-8")), json.loads(a.xps.read_text(encoding="utf-8"))
    )
    a.out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="ascii")
    print(
        json.dumps(
            {h: {"tested": doc[h]["tested"], "claim": doc[h]["claim"]} for h in ("T2S", "XPS")}
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["family"]:
        return family_main(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pin", type=Path, required=True)
    ap.add_argument("--cloud", required=True, help="cloud-only run dir(s), comma-separated")
    ap.add_argument("--arm", action="append", required=True, help="NAME=dir[,dir]")
    ap.add_argument("--reference", default="A")
    ap.add_argument("--contrast", action="append", default=[], help="X:R secondary contrast")
    ap.add_argument("--primary", default="P", help="arm whose contrast vs A is confirmatory")
    ap.add_argument("--host", choices=("T2S", "XPS"), default=None)
    ap.add_argument("--bfcl-unpacked", type=Path, required=True)
    ap.add_argument("--derive-triggers", action="store_true")
    ap.add_argument("--price-date", default=None, help="YYYY-MM-DD (default: cloud plan.json)")
    ap.add_argument("--no-split", action="store_true", help="skip the base / long halves")
    ap.add_argument("--boot", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=20261023)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    from tools.h1_cloud_accounting import load_price_table

    pin_sha = hashlib.sha256(a.pin.read_bytes()).hexdigest()
    if a.derive_triggers and pin_sha == DEMO2_HELDOUT_60_SHA256:
        raise refuse("--derive-triggers is not allowed on DEMO2_HELDOUT_60 (PF 13)")
    pin = json.loads(a.pin.read_text(encoding="utf-8"))
    entries = {str(e["id"]): e for e in pin}
    ids = [str(e["id"]) for e in pin]
    cdirs = [Path(x) for x in a.cloud.split(",")]
    when = price_date(cdirs, a.price_date)
    cloud = load_cloud(cdirs, table=load_price_table(), when=when)
    short = [
        i
        for i in ids
        if i in cloud and len(cloud[i]["decoded"]) < len(entries[i].get("question") or [])
    ]
    if short:
        raise refuse(f"cloud log has fewer turns than user turns for {short}")
    score = bfcl_score_fn(a.bfcl_unpacked)
    by_mode: dict[str, dict[str, dict[str, list[Any]]]] = {m: {} for m in MODES}
    meta: dict[str, Any] = {}
    for spec in a.arm:
        name, dirs = spec.split("=", 1)
        dl = [Path(x) for x in dirs.split(",")]
        arm = load_arm(dl, derive=a.derive_triggers)
        missing = [i for i in ids if i not in arm or i not in cloud]
        if missing:
            raise refuse(f"arm {name} or the cloud log lacks {len(missing)} pin ids")
        for m in MODES:
            by_mode[m][name] = entry_outcomes(arm, cloud, ids, score, entries, mode=m)
        meta[name] = {
            "derived_trigger_entries": sum(1 for i in ids if arm[i]["derived_triggers"]),
            "skipped_hang_entries": sum(1 for i in ids if arm[i].get("skipped_hang")),
            "hang_prefix_missing": sum(1 for i in ids if arm[i].get("hang_prefix_missing")),
            "low_mem_turns": sum(_low_mem_turns(d) for d in dl),
        }
    if a.reference not in by_mode["splice"]:
        raise refuse(f"reference arm {a.reference} not given")
    pairs = [(x, a.reference) for x in by_mode["splice"] if x != a.reference]
    for c in a.contrast:
        x, r = c.split(":", 1)
        if x not in by_mode["splice"] or r not in by_mode["splice"]:
            raise refuse(f"contrast {c} names an arm not given")
        if (x, r) not in pairs:
            pairs.append((x, r))
    primary = (a.primary, "A") if (a.primary, "A") in pairs else None
    res: dict[str, Any] = {
        "host": a.host,
        "price_date": when.isoformat(),
        "pin_sha256": pin_sha,
        "arm_meta": meta,
        "all": analyse(by_mode, pairs, primary=primary, boot=a.boot, seed=a.seed),
    }
    if not a.no_split:
        halves = {
            "base": [
                k
                for k, i in enumerate(ids)
                if "long_context" not in str(entries[i].get("category"))
            ],
            "long": [
                k for k, i in enumerate(ids) if "long_context" in str(entries[i].get("category"))
            ],
        }
        res["by_half"] = {
            h: analyse(
                {"splice": by_mode["splice"]},
                pairs,
                primary=None,
                boot=a.boot,
                seed=a.seed,
                subset=k,
            )
            for h, k in halves.items()
            if k
        }
    res["inputs"] = {"pin": str(a.pin), "cloud": a.cloud, "arms": a.arm, "contrasts": a.contrast}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(_clean(res), indent=1, sort_keys=True) + "\n", encoding="ascii")
    for k, v in res["all"]["contrasts"].items():
        s = v["splice"]
        print(k, v["role"], {x: _clean(s.get(x)) for x in ("dC_iso", "dC_iso_ci95", "dQ_iso")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
