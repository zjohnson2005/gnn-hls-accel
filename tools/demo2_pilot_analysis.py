"""DEMO-2 pilot decision rules (docs/amendments/DEMO2_PILOTS_2026-10-16.md), as code.

Reads run_h1_hybrid output directories only (turn_ledger.json and, with
--debug-raw-text / --mem-telemetry, local_turn_telemetry.jsonl). Runs nothing.
Prints one JSON verdict per call:

  python tools/demo2_pilot_analysis.py p1 <run_dir> [<run_dir> ...]
  python tools/demo2_pilot_analysis.py p4 <off_dir> <on_dir>
  python tools/demo2_pilot_analysis.py p5 <k512_dir> <k1024_dir> <k2048_dir>
  python tools/demo2_pilot_analysis.py p6 <run_dir>
  python tools/demo2_pilot_analysis.py p7 <a1_dir> <a2_dir>
  python tools/demo2_pilot_analysis.py p8 <i8_dir> <u4_dir>
  python tools/demo2_pilot_analysis.py p9 <sealed run_decode_match --pilot p9 dir>

A run dir may be an interleaved run root: when it has no turn_ledger.json, the
one policy subdir policies/<policy>/ is read (refused if there are several).

P1 splits output by characters (tool-call blocks, think blocks, the rest) and
apportions each step's generated_tokens by those shares; it is an estimate,
labeled as such.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import aq_sealed_analyses as aq  # noqa: E402

TOOL_RE = re.compile(r"<tool_call>.*?</tool_call>", re.S)
THINK_RE = re.compile(r"<think>.*?</think>", re.S)
TELEMETRY = "local_turn_telemetry.jsonl"
P1_LEVER_SHARE = 0.50
P4_MIN_SPEEDUP = 1.10
P7_DISCORDANT_SHARE = 0.25
NCTX_BUCKETS = (8_000, 16_000, 24_000, 32_000, 40_960)
P9_MAX_DRIFT = 0.05


def _telemetry(run_dir: Path) -> list[dict[str, Any]]:
    path = Path(run_dir) / TELEMETRY
    if not path.is_file():
        raise SystemExit(f"REFUSED -- {path} missing (run with --debug-raw-text / --mem-telemetry)")
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _ledger_path(run_dir: Path) -> Path:
    path = Path(run_dir) / "turn_ledger.json"
    if path.is_file():
        return path
    found = sorted((Path(run_dir) / "policies").glob("*/turn_ledger.json"))
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        raise SystemExit(f"REFUSED -- {run_dir} has several policies; pass policies/<policy>")
    raise SystemExit(f"REFUSED -- no turn_ledger.json under {run_dir}")


def _entries(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(_ledger_path(run_dir).read_text(encoding="utf-8"))[
        "entries"
    ]
    return rows


def split_text(text: str) -> dict[str, int]:
    tool = sum(len(m) for m in TOOL_RE.findall(text or ""))
    think = sum(len(m) for m in THINK_RE.findall(text or ""))
    return {"tool_call": tool, "think": think, "other": max(0, len(text or "") - tool - think)}


def p1(run_dirs: list[Path]) -> dict[str, Any]:
    tokens = {"tool_call": 0.0, "think": 0.0, "other": 0.0}
    eot_prose = 0.0
    n_steps = 0
    for d in run_dirs:
        for row in _telemetry(d):
            steps = row.get("steps") or []
            for i, st in enumerate(steps):
                if "raw_text" not in st:
                    continue
                n = float(st.get("generated_tokens") or 0)
                parts = split_text(str(st["raw_text"]))
                total = sum(parts.values()) or 1
                for k, v in parts.items():
                    tokens[k] += n * v / total
                if i == len(steps) - 1 and parts["tool_call"] == 0:
                    eot_prose += n
                n_steps += 1
    out_total = sum(tokens.values())
    non_tool = (tokens["think"] + tokens["other"]) / out_total if out_total else None
    return {
        "pilot": "P1",
        "basis": "ESTIMATE: tokens apportioned by character share per step",
        "n_steps": n_steps,
        "output_tokens": round(out_total, 1),
        "share": {k: round(v / out_total, 3) if out_total else None for k, v in tokens.items()},
        "end_of_turn_prose_share": round(eot_prose / out_total, 3) if out_total else None,
        "rule": f"output-length lever exists if non-tool-call share >= {P1_LEVER_SHARE}",
        "lever_exists": None if non_tool is None else non_tool >= P1_LEVER_SHARE,
    }


def _step_map(run_dir: Path) -> dict[tuple[str, str, int, int], dict[str, Any]]:
    out = {}
    for row in _telemetry(run_dir):
        for st in row.get("steps") or []:
            out[(row["entry_id"], row["policy"], int(row["turn"]), int(st.get("step", 0)))] = st
    return out


def p4(off_dir: Path, on_dir: Path) -> dict[str, Any]:
    off, on = _step_map(off_dir), _step_map(on_dir)
    keys = sorted(set(off) & set(on))
    identical = (
        bool(keys)
        and set(off) == set(on)
        and all(off[k].get("raw_text") == on[k].get("raw_text") for k in keys)
    )
    ratios = [
        float(on[k]["decode_tok_s"]) / float(off[k]["decode_tok_s"])
        for k in keys
        if off[k].get("decode_tok_s") and on[k].get("decode_tok_s")
    ]
    writes = sum(int(on[k].get("streamer_writes") or 0) for k in keys)
    toks = sum(int(on[k].get("streamer_tokens") or 0) for k in keys)
    speedup = statistics.median(ratios) if ratios else None
    return {
        "pilot": "P4",
        "matched_steps": len(keys),
        "outputs_identical": identical,
        "decode_speedup_median": None if speedup is None else round(speedup, 3),
        "tokens_per_streamer_write_on": round(toks / writes, 3) if writes else None,
        "rule": f"adopt if speedup >= {P4_MIN_SPEEDUP} and outputs identical",
        "adopt": bool(identical and speedup is not None and speedup >= P4_MIN_SPEEDUP),
    }


def _cell(run_dir: Path) -> dict[str, Any]:
    ents = _entries(run_dir)
    return {
        "n": len(ents),
        "passes": sum(bool(e.get("hybrid_pass")) for e in ents),
        "usd_per_task": sum(float(e.get("cloud_usd_entry") or 0) for e in ents) / len(ents),
        "by_entry": {e["entry_id"]: bool(e.get("hybrid_pass")) for e in ents},
    }


def p5(k512: Path, k1024: Path, k2048: Path) -> dict[str, Any]:
    cells = {512: _cell(k512), 1024: _cell(k1024), 2048: _cell(k2048)}
    ok = [k for k, c in cells.items() if c["passes"] >= cells[1024]["passes"]]
    chosen = min(ok, key=lambda k: (cells[k]["usd_per_task"], k))
    return {
        "pilot": "P5",
        "cells": {
            k: {"passes": c["passes"], "usd_per_task": round(c["usd_per_task"], 4)}
            for k, c in cells.items()
        },
        "rule": "lowest $/task among K with passes >= K=1024 (ties: smaller K)",
        "chosen_k": chosen,
    }


def _local_turns(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for e in entries for t in e.get("turns") or [] if t.get("placement") == "local"]


def p6(run_dir: Path) -> dict[str, Any]:
    ents = _entries(run_dir)
    buckets: dict[str, list[bool]] = {}
    reasons: dict[str, int] = {}
    for e in ents:
        n = max((int(t.get("n_ctx") or 0) for t in e.get("turns") or []), default=0)
        label = next((f"<{b}" for b in NCTX_BUCKETS if n < b), f">={NCTX_BUCKETS[-1]}")
        buckets.setdefault(label, []).append(bool(e.get("local_pass") or e.get("hybrid_pass")))
        r = aq.cause_bucket(aq.first_escalation_reason(e))
        if r == "none":
            r = aq.classify_local(e)
        reasons[r] = reasons.get(r, 0) + 1
    return {
        "pilot": "P6",
        "local_pass_by_max_n_ctx": {
            k: {"n": len(v), "pass": sum(v)} for k, v in sorted(buckets.items())
        },
        "first_reason_or_local_class": reasons,
        "n_ctx_tail": sorted(int(t.get("n_ctx") or 0) for t in _local_turns(ents))[-5:],
    }


def p7(a1: Path, a2: Path) -> dict[str, Any]:
    c1, c2 = _cell(a1), _cell(a2)
    ids = sorted(set(c1["by_entry"]) & set(c2["by_entry"]))
    disc = sum(c1["by_entry"][i] != c2["by_entry"][i] for i in ids)
    mean_usd = (c1["usd_per_task"] + c2["usd_per_task"]) / 2
    g1 = [float(t["t_generate"]) for t in _local_turns(_entries(a1)) if t.get("t_generate")]
    g2 = [float(t["t_generate"]) for t in _local_turns(_entries(a2)) if t.get("t_generate")]
    p1_, p2_ = (statistics.median(g1) if g1 else None), (statistics.median(g2) if g2 else None)
    d_lat = abs(p1_ - p2_) / ((p1_ + p2_) / 2) if p1_ and p2_ else None
    return {
        "pilot": "P7",
        "n_paired": len(ids),
        "discordant": disc,
        "d_usd": round(abs(c1["usd_per_task"] - c2["usd_per_task"]) / mean_usd, 4)
        if mean_usd
        else 0.0,
        "d_lat": None if d_lat is None else round(d_lat, 4),
        "rule": f"2 replicates per arm if discordant > {P7_DISCORDANT_SHARE} x n_paired",
        "replicates": 2 if disc > P7_DISCORDANT_SHARE * len(ids) else 1,
        "material_win_floors": {
            "usd": round(
                max(
                    0.25,
                    2
                    * (
                        abs(c1["usd_per_task"] - c2["usd_per_task"]) / mean_usd if mean_usd else 0.0
                    ),
                ),
                4,
            ),
            "latency": None if d_lat is None else round(max(0.20, 2 * d_lat), 4),
        },
    }


def p8(i8_dir: Path, u4_dir: Path) -> dict[str, Any]:
    a, b = aq.per_entry(_entries(i8_dir)), aq.per_entry(_entries(u4_dir))
    ids = sorted(set(a) & set(b))
    agree = total = 0
    for i in ids:
        ta = {t["turn"]: t.get("decoded_steps") for t in a[i].get("turns") or []}
        tb = {t["turn"]: t.get("decoded_steps") for t in b[i].get("turns") or []}
        for turn in set(ta) & set(tb):
            total += 1
            agree += ta[turn] == tb[turn]

    def silent_share(d: dict[str, Any]) -> float | None:
        cls = [aq.classify_local(d[i]) for i in ids]
        non_esc = [c for c in cls if c != "escalated"]
        return (non_esc.count("silent") / len(non_esc)) if non_esc else None

    s8, s4 = silent_share(a), silent_share(b)
    return {
        "pilot": "P8",
        "n_paired": len(ids),
        "turn_agreement": round(agree / total, 3) if total else None,
        "silent_share_i8": s8,
        "silent_share_u4": s4,
        "rule": "keep u4 if the silent-failure share does not rise",
        "keep_u4": None if s8 is None or s4 is None else s4 <= s8,
    }


def p9(run_dir: Path) -> dict[str, Any]:
    """Drift: median decode tok/s of the last third of points vs the first third."""
    pts = [
        json.loads(f.read_text(encoding="utf-8"))
        for f in sorted((Path(run_dir) / "points").glob("*.json"))
    ]
    pts.sort(key=lambda d: int(d["point_index"]))
    if len(pts) < 3:
        raise SystemExit(f"REFUSED -- p9 needs at least 3 points, found {len(pts)}")
    third = len(pts) // 3
    first, last = pts[:third], pts[-third:]

    def drift(a: list[float], b: list[float]) -> float:
        return (statistics.median(b) - statistics.median(a)) / statistics.median(a)

    by_point = drift(
        [float(d["median_decode_tok_s"]) for d in first],
        [float(d["median_decode_tok_s"]) for d in last],
    )
    by_repeat = drift(
        [float(r["decode_tok_s"]) for d in first for r in d["repeats"]],
        [float(r["decode_tok_s"]) for d in last for r in d["repeats"]],
    )
    return {
        "pilot": "P9",
        "n_points": len(pts),
        "third": third,
        "drift_point_medians": round(by_point, 4),
        "drift_all_repeats": round(by_repeat, 4),
        "rule": f"warm-up rule for every cell if |drift| > {P9_MAX_DRIFT}",
        "warmup_rule": abs(by_point) > P9_MAX_DRIFT or abs(by_repeat) > P9_MAX_DRIFT,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pilot", choices=("p1", "p4", "p5", "p6", "p7", "p8", "p9"))
    ap.add_argument("dirs", nargs="+", type=Path)
    args = ap.parse_args(argv)
    arity = {"p4": 2, "p5": 3, "p6": 1, "p7": 2, "p8": 2, "p9": 1}
    if args.pilot in arity and len(args.dirs) != arity[args.pilot]:
        raise SystemExit(f"REFUSED -- {args.pilot} takes {arity[args.pilot]} run dirs")
    fn = {
        "p1": lambda d: p1(d),
        "p4": lambda d: p4(*d),
        "p5": lambda d: p5(*d),
        "p6": lambda d: p6(*d),
        "p7": lambda d: p7(*d),
        "p8": lambda d: p8(*d),
        "p9": lambda d: p9(*d),
    }[args.pilot]
    print(json.dumps(fn(list(args.dirs)), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
