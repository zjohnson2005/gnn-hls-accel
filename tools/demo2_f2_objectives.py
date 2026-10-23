"""DEMO-2 confirmatory family F2 (non-dollar objectives), Task BH. Mac, no model, $0.

Registered in docs/amendments/DEMO2_AMEND_2026-10-23_OBJECTIVES.md ("OBJ"). F2 is NOT gated on
the dollar primary (PF 2); it has its own alpha 0.05, Holm within F2 per host.

Inputs per arm: the same local_only run dirs the iso-quality replay reads (hung runs and their
continuations included). Fields read, all already logged by tools/run_h1_hybrid.py:
- policies/local_only/turn_ledger.json: entries[].entry_id, local_pass, stop_reason,
  turns[].placement, turns[].turn, turns[].turn_wall_s;
- policies/local_only/entry_quality.json: rows with status "skipped_hang" (hang_ref.turn);
- hang_events.json: events[].entry_id, outcome (hang / stall / turn_budget_exceeded), elapsed_s;
- step_log.jsonl (-StepLog): "pre_generate" prompt_tokens; "post_generate" generated_tokens,
  ok, error, wall_s;
- plan.json: local_limits.context_window.tokens or context_window.tokens (the arm's window).

Per entry (OBJ section 2):
- positions of one local generate = prompt_tokens + generated_tokens (prompt_tokens alone when
  the generate has no post_generate row, i.e. it never returned);
- cap = min(40,960, the arm's window); overrun = any generate with positions > cap;
- loud = stop_reason generation_error or ctx_overflow, or any post_generate with ok false or an
  error, or a hang event / skipped_hang row for the entry;
- a. silent_overrun = overrun and not loud;
- b. wall_s = sum of the entry's local turn_wall_s. For a skipped_hang entry (no ledger row):
  the hang event's elapsed_s + the step_log wall_s of its turns before t_h (a lower bound,
  counted in wall_lower_bound);
- c. time_to_failure = wall_s on entries with local_pass false (skipped_hang counts as a fail);
- d. hang_loop = a hang event / skipped_hang row, or stop_reason max_steps.

Tests, contrast A vs X for X in (P, C):
- a, d: exact McNemar on the paired binary (b = A only, c = X only);
- b: Wilcoxon signed-rank, two-sided, on wall_A - wall_X over every pin entry;
- c: the same on the entries where both arms fail locally.
Family: (b, c, d) x (A vs P, A vs C) per host, m = 6, Holm at 0.05. Member a is "by
construction" for both contrasts (X's window refuses a generate past it, so X cannot overrun):
it is tested and reported as a mechanism check, outside the Holm family, and makes no claim.
An untestable member (no pairs) keeps p = 1, so m stays 6.

  python tools/demo2_f2_objectives.py --pin <pin.json> --arm A=<dir>[,<dir>] --arm P=<dir> \\
      --arm C=<dir> --host T2S --out <out.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.demo2_iso_quality_replay import (  # noqa: E402
    HANG_STATES,
    holm,
    mcnemar_exact,
    refuse,
)

MODEL_POSITIONS = 40_960
ALPHA = 0.05
F2_CONTRASTS: tuple[str, ...] = ("P", "C")
F2_TESTED: tuple[str, ...] = ("b_wall", "c_time_to_failure", "d_hang_loop")
BY_CONSTRUCTION: tuple[str, ...] = ("a_silent_overrun",)
LOUD_STOPS = ("generation_error", "ctx_overflow")


def _ledger(d: Path) -> list[dict[str, Any]]:
    for c in (d / "policies" / "local_only" / "turn_ledger.json", d / "turn_ledger.json"):
        if c.is_file():
            return list(json.loads(c.read_text(encoding="utf-8")).get("entries") or [])
    raise refuse(f"no turn_ledger.json under {d}")


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


def _steps(d: Path) -> list[dict[str, Any]]:
    p = d / "step_log.jsonl"
    if not p.is_file():
        raise refuse(f"no step_log.jsonl under {d} (F2 member a needs -StepLog)")
    lines = p.read_text(encoding="utf-8").splitlines()
    return [json.loads(x) for x in lines if x.strip()]


def arm_window(d: Path) -> int | None:
    p = d / "plan.json"
    if not p.is_file():
        return None
    plan = json.loads(p.read_text(encoding="utf-8"))
    for blk in ((plan.get("local_limits") or {}).get("context_window"), plan.get("context_window")):
        if isinstance(blk, dict) and blk.get("tokens") is not None:
            return int(blk["tokens"])
    return None


def generates(steps: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """entry_id -> one record per local generate: positions, ok, error, turn, wall_s."""
    pend: dict[tuple[str, int, int], dict[str, Any]] = {}
    out: dict[str, list[dict[str, Any]]] = {}
    for r in steps:
        if r.get("policy") not in (None, "local_only"):
            continue
        key = (str(r["entry_id"]), int(r["turn"]), int(r["step"]))
        if r.get("event") == "pre_generate":
            g: dict[str, Any] = {
                "turn": key[1],
                "prompt_tokens": int(r.get("prompt_tokens") or 0),
                "generated_tokens": None,
                "ok": None,
                "error": None,
                "wall_s": None,
            }
            pend[key] = g
            out.setdefault(key[0], []).append(g)
        elif r.get("event") == "post_generate":
            if key not in pend:
                raise refuse(f"post_generate without pre_generate for {key}")
            g = pend.pop(key)
            g["generated_tokens"] = int(r.get("generated_tokens") or 0)
            g["ok"] = r.get("ok")
            g["error"] = r.get("error")
            g["wall_s"] = r.get("wall_s")
    for gs in out.values():
        for g in gs:
            g["positions"] = int(g["prompt_tokens"]) + int(g["generated_tokens"] or 0)
    return out


def load_arm(dirs: Sequence[Path]) -> dict[str, dict[str, Any]]:
    """entry_id -> F2 per-entry fields (OBJ section 2)."""
    rows: dict[str, dict[str, Any]] = {}
    gens: dict[str, list[dict[str, Any]]] = {}
    hangs: dict[str, dict[str, Any]] = {}
    windows = {arm_window(d) for d in dirs}
    if len(windows) > 1:
        raise refuse(f"arm dirs disagree on the context window: {sorted(map(str, windows))}")
    window = windows.pop()
    cap = MODEL_POSITIONS if window is None else min(MODEL_POSITIONS, window)
    for d in dirs:
        for e in _ledger(d):
            eid = str(e["entry_id"])
            if eid in rows:
                raise refuse(f"{d}: duplicate entry {eid} across this arm's logs")
            if e.get("local_pass") is None:
                raise refuse(f"{d}: {eid} has local_pass None")
            turns = [t for t in e.get("turns") or [] if t.get("placement") == "local"]
            rows[eid] = {
                "local_pass": bool(e["local_pass"]),
                "stop_reason": e.get("stop_reason"),
                "wall_s": float(sum(float(t.get("turn_wall_s") or 0.0) for t in turns)),
                "skipped_hang": False,
            }
        for r in _quality_rows(d):
            if str(r.get("status")) != "skipped_hang":
                continue
            eid = str(r.get("entry_id"))
            if eid in rows:
                raise refuse(f"{d}: skipped_hang {eid} also has a ledger row")
            t_h = (r.get("hang_ref") or {}).get("turn")
            if t_h is None:
                raise refuse(f"{d}: skipped_hang {eid} has no hang_ref.turn")
            rows[eid] = {
                "local_pass": False,
                "stop_reason": None,
                "wall_s": None,
                "skipped_hang": True,
                "hang_turn": int(t_h),
            }
        for eid, gs in generates(_steps(d)).items():
            gens.setdefault(eid, []).extend(gs)
        for ev in _hang_events(d):
            hangs[str(ev.get("entry_id"))] = ev
    for eid in hangs:
        if eid not in rows:
            raise refuse(f"hang event for {eid} has no skipped_hang row and no ledger row")
    out: dict[str, dict[str, Any]] = {}
    for eid, r in rows.items():
        gs = gens.get(eid, [])
        hung = r["skipped_hang"] or eid in hangs
        loud = bool(
            hung
            or r["stop_reason"] in LOUD_STOPS
            or any(g["ok"] is False or g["error"] for g in gs)
        )
        overrun = any(g["positions"] > cap for g in gs)
        wall = r["wall_s"]
        lower = False
        if r["skipped_hang"]:
            hev = hangs.get(eid)
            if hev is None or hev.get("elapsed_s") is None:
                raise refuse(f"skipped_hang {eid}: no hang event with elapsed_s in this arm's logs")
            before = sum(
                float(g["wall_s"] or 0.0) for g in gs if int(g["turn"]) < int(r["hang_turn"])
            )
            wall = float(hev["elapsed_s"]) + before
            lower = True
        out[eid] = {
            "local_pass": r["local_pass"],
            "stop_reason": r["stop_reason"],
            "cap": cap,
            "max_positions": max((g["positions"] for g in gs), default=0),
            "n_generates_over_cap": sum(1 for g in gs if g["positions"] > cap),
            "overrun": overrun,
            "loud": loud,
            "a_silent_overrun": bool(overrun and not loud),
            "b_wall": float(wall or 0.0),
            "wall_lower_bound": lower,
            "d_hang_loop": bool(hung or r["stop_reason"] == "max_steps"),
        }
    return out


def wilcoxon(diffs: Sequence[float]) -> dict[str, Any]:
    """Two-sided Wilcoxon signed-rank (zeros dropped); p = 1 when nothing is left."""
    nz = [d for d in diffs if d != 0.0]
    if not nz:
        return {"n": len(diffs), "n_nonzero": 0, "p": 1.0, "r_plus": 0.0, "r_minus": 0.0}
    from scipy.stats import rankdata  # type: ignore[import-untyped]
    from scipy.stats import wilcoxon as sp_wilcoxon  # type: ignore[import-untyped]

    ranks = rankdata([abs(d) for d in nz])
    r_plus = float(sum(r for r, d in zip(ranks, nz, strict=True) if d > 0))
    r_minus = float(sum(r for r, d in zip(ranks, nz, strict=True) if d < 0))
    p = float(sp_wilcoxon(nz, zero_method="wilcox", alternative="two-sided").pvalue)
    return {"n": len(diffs), "n_nonzero": len(nz), "p": p, "r_plus": r_plus, "r_minus": r_minus}


def _favours(test: dict[str, Any], kind: str) -> str | None:
    """Which arm the data favour: 'X' (A worse), 'A' (X worse), or None (tie)."""
    if kind == "mcnemar":
        b, c = int(test["b"]), int(test["c"])
        return "X" if b > c else "A" if c > b else None
    rp, rm = float(test["r_plus"]), float(test["r_minus"])
    return "X" if rp > rm else "A" if rm > rp else None


def contrast(
    a: dict[str, dict[str, Any]], x: dict[str, dict[str, Any]], ids: list[str]
) -> dict[str, Any]:
    res: dict[str, Any] = {}
    for k in ("a_silent_overrun", "d_hang_loop"):
        va = [bool(a[i][k]) for i in ids]
        vx = [bool(x[i][k]) for i in ids]
        t = mcnemar_exact(va, vx)
        res[k] = {
            "test": "exact McNemar (b = A only, c = X only)",
            "A_count": sum(va),
            "X_count": sum(vx),
            "n": len(ids),
            **t,
            "favours": _favours(t, "mcnemar"),
        }
    d_all = [a[i]["b_wall"] - x[i]["b_wall"] for i in ids]
    t = wilcoxon(d_all)
    res["b_wall"] = {
        "test": "Wilcoxon signed-rank, two-sided, wall_A - wall_X",
        "median_A_s": statistics.median(a[i]["b_wall"] for i in ids) if ids else None,
        "median_X_s": statistics.median(x[i]["b_wall"] for i in ids) if ids else None,
        "median_paired_diff_s": statistics.median(d_all) if d_all else None,
        "wall_lower_bound_entries": {
            "A": sum(1 for i in ids if a[i]["wall_lower_bound"]),
            "X": sum(1 for i in ids if x[i]["wall_lower_bound"]),
        },
        **t,
        "favours": _favours(t, "wilcoxon"),
    }
    both = [i for i in ids if not a[i]["local_pass"] and not x[i]["local_pass"]]
    d_f = [a[i]["b_wall"] - x[i]["b_wall"] for i in both]
    t = wilcoxon(d_f)
    res["c_time_to_failure"] = {
        "test": "Wilcoxon signed-rank, two-sided, on entries where both fail locally",
        "n_fail_A": sum(1 for i in ids if not a[i]["local_pass"]),
        "n_fail_X": sum(1 for i in ids if not x[i]["local_pass"]),
        "n_both_fail": len(both),
        "median_ttf_A_s": statistics.median(a[i]["b_wall"] for i in both) if both else None,
        "median_ttf_X_s": statistics.median(x[i]["b_wall"] for i in both) if both else None,
        "median_paired_diff_s": statistics.median(d_f) if d_f else None,
        "testable": bool(both),
        **t,
        "favours": _favours(t, "wilcoxon"),
    }
    if not both:
        res["c_time_to_failure"]["note"] = "not testable: no entry fails in both arms; p = 1"
    return res


def family(per_contrast: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Holm over (b, c, d) x contrasts; claims by OBJ section 3."""
    ps = {
        f"{m} | A vs {x}": float(per_contrast[x][m]["p"]) for x in per_contrast for m in F2_TESTED
    }
    adj = holm(ps)
    claims: list[str] = []
    for key, p_adj in adj.items():
        m, c = key.split(" | ")
        x = c.split(" vs ")[1]
        rec = per_contrast[x][m]
        rec["p_holm"] = p_adj
        rec["rejects_holm_0.05"] = p_adj < ALPHA
        fav = rec["favours"]
        if p_adj < ALPHA and fav == "X":
            claims.append(f"{x} improves on A for {m}")
        elif p_adj < ALPHA and fav == "A":
            claims.append(f"A is better than {x} for {m}")
    for x in per_contrast:
        for m in BY_CONSTRUCTION:
            per_contrast[x][m]["role"] = (
                "by construction (X refuses a generate past its window): mechanism check, "
                "outside the Holm family, no empirical claim"
            )
    return {"m": len(ps), "alpha": ALPHA, "holm_adjusted": adj, "claims": claims}


def analyse(arms: dict[str, dict[str, dict[str, Any]]], ids: list[str]) -> dict[str, Any]:
    if "A" not in arms:
        raise refuse("F2 needs arm A")
    per: dict[str, dict[str, Any]] = {}
    for x in F2_CONTRASTS:
        if x not in arms:
            raise refuse(f"F2 needs arm {x} (contrasts A vs P and A vs C)")
        per[x] = contrast(arms["A"], arms[x], ids)
    fam = family(per)
    summary = {
        name: {
            "cap": next(iter(o.values()))["cap"] if o else None,
            "silent_overrun": sum(1 for i in ids if o[i]["a_silent_overrun"]),
            "overrun_loud": sum(1 for i in ids if o[i]["overrun"] and o[i]["loud"]),
            "generates_over_cap": sum(o[i]["n_generates_over_cap"] for i in ids),
            "hang_loop": sum(1 for i in ids if o[i]["d_hang_loop"]),
            "max_steps": sum(1 for i in ids if o[i]["stop_reason"] == "max_steps"),
            "local_fails": sum(1 for i in ids if not o[i]["local_pass"]),
        }
        for name, o in arms.items()
    }
    return {
        "n": len(ids),
        "arms": summary,
        "contrasts": {f"A vs {x}": per[x] for x in per},
        "F2": fam,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pin", type=Path, required=True)
    ap.add_argument("--arm", action="append", required=True, help="NAME=dir[,dir]")
    ap.add_argument("--host", choices=("T2S", "XPS"), required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    pin = json.loads(a.pin.read_text(encoding="utf-8"))
    ids = [str(e["id"]) for e in pin]
    arms: dict[str, dict[str, dict[str, Any]]] = {}
    for spec in a.arm:
        name, dirs = spec.split("=", 1)
        arm = load_arm([Path(x) for x in dirs.split(",")])
        missing = [i for i in ids if i not in arm]
        if missing:
            raise refuse(f"arm {name} lacks {len(missing)} pin ids")
        arms[name] = arm
    res = {
        "family": "F2 (OBJ): not gated on the dollar primary; own alpha 0.05; Holm per host",
        "host": a.host,
        "pin_sha256": hashlib.sha256(a.pin.read_bytes()).hexdigest(),
        **analyse(arms, ids),
        "inputs": {"pin": str(a.pin), "arms": a.arm},
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(res, indent=1, sort_keys=True, allow_nan=False)
    a.out.write_text(text + "\n", encoding="ascii")
    for k, v in res["contrasts"].items():
        print(k, {m: (v[m].get("p"), v[m].get("p_holm"), v[m]["favours"]) for m in v})
    print("claims:", res["F2"]["claims"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
