#!/usr/bin/env python3
"""DEMO-2 freeze values (Task BF): compute the values the registered rules name.

Rules (no rule is set here; each value cites its rule):
- P' rule: docs/amendments/DEMO2_PREFREEZE_2026-10-22.md section 6 ("PF 6");
- A/A noise terms: PF 8 (d_lat here; d_usd from the replay output);
- held-out cloud cap: PF 9;
- LOW_MEM turns: PF 10;
- run-level per-entry facts: local pass count, statuses, skipped_hang rows.

Inputs are sealed interleaved local-only run dirs and the cloud-only run dir.
Nothing is written into any run dir.

Usage:
  python tools/demo2_freeze_values.py --cloud <dir> --run NAME=HOST:ROLE:<dir> ...
      [--replay HOST=<replay.json>] --out <values.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TTFT_MARK = "ttft>10.0"  # PF 6 (c)
DECODE_P5_MIN = 12.0  # PF 6 (b), tok/s
LOW_MEM_MB = 1000.0  # PF 10
CAP_FLOOR_USD = 20.0  # PF 9
CAP_FACTOR = 2.0 * 1.1  # PF 9: 2 x cost x 1.1


def nearest_rank(xs: list[float], q: float) -> float | None:
    """Nearest-rank quantile: sort ascending, element ceil(q n), 1-based (PF 6 b)."""
    if not xs:
        return None
    s = sorted(xs)
    k = max(1, math.ceil(q * len(s)))
    return s[k - 1]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def run_facts(run_dir: Path) -> dict[str, Any]:
    pol = run_dir / "policies" / "local_only"
    eq = _load(pol / "entry_quality.json")["entries"]
    tl = _load(pol / "turn_ledger.json")["entries"]
    summary = _load(pol / "summary.json")
    passes = 0
    skipped = 0
    statuses: dict[str, int] = {}
    for e in eq:
        st = str(e.get("status"))
        statuses[st] = statuses.get(st, 0) + 1
        if st == "skipped_hang":
            skipped += 1
            continue
        if e.get("local_pass") is True:
            passes += 1
    decode: list[float] = []
    t_gen: list[float] = []
    ttft_entries: list[str] = []
    for e in tl:
        hit = False
        for t in e.get("turns") or []:
            if t.get("placement") != "local":
                continue
            if t.get("decode_tok_s") is not None:
                decode.append(float(t["decode_tok_s"]))
            if t.get("t_generate") is not None:
                t_gen.append(float(t["t_generate"]))
            mech = (t.get("passive_triggers") or {}).get("mechanical")
            if mech is not None and TTFT_MARK in str(mech):
                hit = True
        if hit:
            ttft_entries.append(str(e["entry_id"]))
    low_mem = 0
    n_tel = 0
    tel = run_dir / "local_turn_telemetry.jsonl"
    if tel.is_file():
        for line in tel.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            n_tel += 1
            m = (json.loads(line).get("memory") or {}).get("min_available_mb")
            if m is not None and float(m) < LOW_MEM_MB:
                low_mem += 1
    seal = _load(run_dir / ".sealed")
    return {
        "run_id": seal.get("run_id"),
        "seal_status": seal.get("status"),
        "git_head": (seal.get("git") or {}).get("git_head"),
        "n_entries": len(eq),
        "n_completed": summary.get("n_entries_completed"),
        "statuses": statuses,
        "local_pass_count": passes,
        "skipped_hang_rows": skipped,
        "n_local_turns_decode": len(decode),
        "decode_p5_nearest_rank": nearest_rank(decode, 0.05),
        "t_generate_p50": statistics.median(t_gen) if t_gen else None,
        "n_local_turns_t_generate": len(t_gen),
        "ttft10_entries": sorted(ttft_entries),
        "n_ttft10_entries": len(ttft_entries),
        "telemetry_turns": n_tel,
        "low_mem_turns": low_mem,
        "_eq": {str(e["entry_id"]): e for e in eq},
        "_tl": {str(e["entry_id"]): e for e in tl},
    }


def aa_floor(a1: dict[str, Any], a2: dict[str, Any]) -> dict[str, Any]:
    """Per-entry pass discordance and the step-level decoded-call mismatch rate.

    Steps are aligned by (entry, turn, step index). A position present in only
    one run counts as a mismatch; the denominator is the union of positions.
    """
    ids = sorted(set(a1["_eq"]) & set(a2["_eq"]))
    disc = [i for i in ids if a1["_eq"][i].get("local_pass") != a2["_eq"][i].get("local_pass")]
    n_pos = 0
    n_mis = 0
    for i in ids:
        t1 = {int(t["turn"]): t for t in a1["_tl"][i].get("turns") or []}
        t2 = {int(t["turn"]): t for t in a2["_tl"][i].get("turns") or []}
        for turn in sorted(set(t1) | set(t2)):
            s1 = list((t1.get(turn) or {}).get("decoded_steps") or [])
            s2 = list((t2.get(turn) or {}).get("decoded_steps") or [])
            n = max(len(s1), len(s2))
            n_pos += n
            for k in range(n):
                if k >= len(s1) or k >= len(s2) or s1[k] != s2[k]:
                    n_mis += 1
    p1, p2 = a1["t_generate_p50"], a2["t_generate_p50"]
    d_lat = abs(p1 - p2) / ((p1 + p2) / 2.0) if p1 is not None and p2 is not None else None
    return {
        "n_paired": len(ids),
        "discordant_entries": disc,
        "n_discordant": len(disc),
        "step_positions": n_pos,
        "step_mismatches": n_mis,
        "step_mismatch_rate": (n_mis / n_pos) if n_pos else None,
        "t_generate_p50_a1": p1,
        "t_generate_p50_a2": p2,
        "d_lat": d_lat,
    }


def p_prime_rule(a: dict[str, Any] | None, p: dict[str, Any] | None) -> dict[str, Any]:
    if a is None or p is None:
        return {"status": "NOT YET MEASURED", "reason": "cal_a1 or cal_p missing"}
    for r in (a, p):
        if r["n_completed"] != 30 or r["n_entries"] != 30:
            return {"status": "NOT YET MEASURED", "reason": f"{r['run_id']} incomplete"}
    crit_a = p["local_pass_count"] < a["local_pass_count"]
    p5 = p["decode_p5_nearest_rank"]
    crit_b = p5 is not None and p5 < DECODE_P5_MIN
    crit_c = p["n_ttft10_entries"] > a["n_ttft10_entries"]
    select = crit_a or crit_b or crit_c
    return {
        "status": "COMPUTED",
        "a_pass_count_P": p["local_pass_count"],
        "a_pass_count_A": a["local_pass_count"],
        "a_holds": crit_a,
        "b_decode_p5_P": p5,
        "b_n_turns": p["n_local_turns_decode"],
        "b_holds": crit_b,
        "c_ttft10_entries_P": p["n_ttft10_entries"],
        "c_ttft10_entries_A": a["n_ttft10_entries"],
        "c_holds": crit_c,
        "select_p_prime": select,
        "PSPEC": (
            r"configs\models\Qwen3-4B-int8-ov.yaml"
            if select
            else r"configs\models\Qwen3-8B-int4-ov.v2.yaml"
        ),
    }


def cloud_cap(cloud_dir: Path) -> dict[str, Any]:
    from tools.demo2_iso_quality_replay import load_cloud
    from tools.h1_cloud_accounting import load_price_table

    plan = _load(cloud_dir / "plan.json")
    when = date.fromisoformat(str(plan["started_utc"])[:10])
    c = load_cloud([cloud_dir], table=load_price_table(), when=when)
    total = sum(sum(v["usd"]) for v in c.values())
    logged = float(_load(cloud_dir / "summary.json").get("running_usd") or 0.0)
    cap = max(CAP_FLOOR_USD, CAP_FACTOR * total)
    return {
        "run_id": plan.get("run_id"),
        "cloud_price_formula": plan.get("cloud_price_formula"),
        "price_date": when.isoformat(),
        "n_entries": len(c),
        "n_cloud_pass": sum(1 for v in c.values() if v["pass"]),
        "repriced_total_usd": total,
        "logged_running_usd": logged,
        "cap_usd": cap,
        "cap_cents_up": math.ceil(cap * 100.0) / 100.0,
        "needs_approval": cap > CAP_FLOOR_USD,
    }


def d_usd(replay: Path) -> dict[str, Any]:
    d = _load(replay)
    c = d["all"]["contrasts"]["A2 vs A"]["splice"]
    dc = c["dC_iso"]
    base = c["C_R_at_Q_star"]
    val = abs(float(dc)) / float(base) if isinstance(dc, (int, float)) and base else None
    return {"dC_iso_A2_vs_A": dc, "C_A1_at_Q_star": base, "d_usd": val}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cloud", type=Path, required=True)
    ap.add_argument("--run", action="append", default=[], help="NAME=HOST:ROLE:dir")
    ap.add_argument("--replay", action="append", default=[], help="HOST=replay.json")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)

    runs: dict[str, dict[str, Any]] = {}
    roles: dict[tuple[str, str], dict[str, Any]] = {}
    inputs: dict[str, str] = {}
    for spec in a.run:
        name, rest = spec.split("=", 1)
        host, role, d = rest.split(":", 2)
        f = run_facts(Path(d))
        f["host"], f["role"] = host, role
        runs[name] = f
        roles[(host, role)] = f
        for rel in (".sealed", "policies/local_only/.sealed"):
            inputs[f"{name}/{rel}"] = sha256_file(Path(d) / rel)
    hosts = sorted({h for h, _ in roles})
    out: dict[str, Any] = {"runs": {}, "aa": {}, "p_prime_xps": None, "inputs_sha256": inputs}
    for name, f in runs.items():
        out["runs"][name] = {k: v for k, v in f.items() if not k.startswith("_")}
    for h in hosts:
        if (h, "a1") in roles and (h, "a2") in roles:
            out["aa"][h] = aa_floor(roles[(h, "a1")], roles[(h, "a2")])
    out["p_prime_xps"] = p_prime_rule(roles.get(("XPS", "a1")), roles.get(("XPS", "p")))
    out["cloud"] = cloud_cap(a.cloud)
    inputs["cloud/.sealed"] = sha256_file(a.cloud / ".sealed")
    for spec in a.replay:
        h, p = spec.split("=", 1)
        out["aa"].setdefault(h, {}).update(d_usd(Path(p)))
        inputs[f"replay_{h}"] = sha256_file(Path(p))
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("aa", "p_prime_xps", "cloud")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
