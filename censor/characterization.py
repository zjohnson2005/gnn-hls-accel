"""Characterization Items C and D: corpus outcomes, observability,
reversibility, fast-path cross-tab, and prompt-head stability.

Sources, all already on disk:
  - apu_characterization/out/oa01/OA01_behavioral_atlas.json     turn metadata
  - apu_characterization/out/oa01/oa01-*.oa01.json               SWE-bench report
  - analysis/index_probe/phase1/oa01_verb_turns.jsonl            full command strings
  - apu_characterization/out/oa01/runs/**/*.traj.json            messages + tool payloads
"""

from __future__ import annotations

import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from censor.shell_semantics import classify, classify_turn

ROOT = Path(__file__).resolve().parents[1]
OA01 = ROOT / "apu_characterization" / "out" / "oa01"
OUT = ROOT / "analysis" / "characterization"
OUT.mkdir(parents=True, exist_ok=True)

RETURNCODE_RE = re.compile(r"<returncode>(-?\d+)</returncode>")
OUTPUT_RE = re.compile(r"<output>\n?(.*?)\n?</output>", re.DOTALL)
ERROR_MARKERS = (
    "Traceback (most recent call last)", "command not found",
    "No such file or directory", "SyntaxError", "AssertionError",
    "ModuleNotFoundError", "ImportError", "Permission denied",
    "fatal:", "error:", "FAILED", "cannot ", "Segmentation fault",
)


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
def load_atlas() -> dict[str, Any]:
    return json.loads((OA01 / "OA01_behavioral_atlas.json").read_text(encoding="utf-8"))


def load_swebench() -> dict[str, Any]:
    path = next(OA01.glob("*.oa01.json"))
    return json.loads(path.read_text(encoding="utf-8")) | {"_path": str(path.relative_to(ROOT))}


def load_verb_turns() -> dict[tuple[str, int], dict[str, Any]]:
    p = ROOT / "analysis" / "index_probe" / "phase1" / "oa01_verb_turns.jsonl"
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out[(r["trajectory_id"], int(r["turn_index"]))] = r
    return out


def load_trajs() -> dict[str, dict[str, Any]]:
    """trajectory_id -> parsed .traj.json (absent for runs that never wrote one)."""
    out: dict[str, dict[str, Any]] = {}
    runs = OA01 / "runs"
    if not runs.is_dir():
        return out
    for d in sorted(runs.iterdir()):
        if not d.is_dir():
            continue
        files = list(d.rglob("*.traj.json"))
        if files:
            out[d.name] = json.loads(files[0].read_text(encoding="utf-8"))
    return out


def tool_payloads_by_turn(traj: dict[str, Any]) -> dict[int, list[str]]:
    """Map assistant-message ordinal (== turn_index) to its tool result payloads."""
    msgs = traj.get("messages") or []
    by_turn: dict[int, list[str]] = defaultdict(list)
    turn = -1
    for m in msgs:
        role = m.get("role")
        if role == "assistant":
            turn += 1
        elif role == "tool" and turn >= 0:
            by_turn[turn].append(m.get("content") or "")
    return dict(by_turn)


# ---------------------------------------------------------------------------
# Item C
# ---------------------------------------------------------------------------
def item_c(atlas: dict[str, Any], swe: dict[str, Any], trajs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    resolved = set(swe.get("resolved_ids") or [])
    unresolved = set(swe.get("unresolved_ids") or [])
    empty = set(swe.get("empty_patch_ids") or [])
    errored = set(swe.get("error_ids") or [])
    completed = set(swe.get("completed_ids") or [])
    submitted = set(swe.get("submitted_ids") or [])

    rows: list[dict[str, Any]] = []
    for o in atlas["outcomes"]:
        tid = o["trajectory_id"]
        task = o["task"]
        flags = list(o.get("flags") or [])
        traj = trajs.get(tid)
        exit_status = (traj or {}).get("info", {}).get("exit_status")

        if o.get("censored"):
            cls, prov, detail = "CENSORED", "unlabeled", (
                f"censor_reason={o.get('censor_reason')}; outcome never evaluated"
            )
        elif task in resolved:
            cls, prov, detail = "RESOLVED", "test_execution", "SWE-bench FAIL_TO_PASS + PASS_TO_PASS satisfied"
        elif task in unresolved:
            cls, prov, detail = "FAILED", "test_execution", "SWE-bench harness ran tests; not resolved"
        elif task in empty:
            cls, prov, detail = "FAILED", "exact_match", (
                "empty diff: harness structural check, no tests executed"
            )
        elif task in errored:
            cls, prov, detail = "CENSORED", "unlabeled", "harness error"
        else:
            cls, prov, detail = "CENSORED", "unlabeled", "not present in SWE-bench report"

        rows.append({
            "trajectory_id": tid,
            "task_id": task,
            "outcome_class": cls,
            "label_provenance": prov,
            "provenance_detail": detail,
            "atlas_outcome": o.get("outcome"),
            "atlas_success": o.get("success"),
            "atlas_censored": o.get("censored"),
            "censor_reason": o.get("censor_reason"),
            "swebench_submitted": task in submitted,
            "swebench_completed": task in completed,
            "swebench_resolved": task in resolved,
            "swebench_unresolved": task in unresolved,
            "swebench_empty_patch": task in empty,
            "traj_exit_status": exit_status,
            "turns": o.get("turns"),
            "cost_usd": o.get("cost_usd"),
            "flags": ";".join(flags),
        })

    _write_csv(OUT / "corpus_outcomes.csv", rows)
    counts = Counter(r["outcome_class"] for r in rows)
    prov = Counter((r["outcome_class"], r["label_provenance"]) for r in rows)
    return {"rows": rows, "counts": counts, "provenance": prov, "swe": swe}


# ---------------------------------------------------------------------------
# Item D1 -- observability
# ---------------------------------------------------------------------------
def _payload_signal(payloads: list[str]) -> tuple[bool, str]:
    """Does the tool output itself reveal failure? (T2)"""
    if not payloads:
        return (False, "")
    for pay in payloads:
        m = RETURNCODE_RE.search(pay)
        if m and int(m.group(1)) != 0:
            return (True, f"returncode={m.group(1)}")
    for pay in payloads:
        om = OUTPUT_RE.search(pay)
        body = om.group(1) if om else pay
        if not body.strip():
            return (True, "empty tool output")
    for pay in payloads:
        om = OUTPUT_RE.search(pay)
        body = om.group(1) if om else pay
        for marker in ERROR_MARKERS:
            if marker in body:
                return (True, f"error text in output: {marker!r}")
    return (False, "")


def item_d1(turns: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen_cmds: dict[str, set[str]] = defaultdict(set)

    for t in turns:
        tid = t["trajectory_id"]
        cmds = t["commands"]
        payloads = t["payloads"]
        tier = evidence = ""

        # T1 STRUCTURAL -- parser-detectable, pre-execution.
        if not t["is_tool_call"] and not t["is_last_turn"]:
            tier, evidence = "T1_STRUCTURAL", "no tool call emitted on a non-terminal turn (scaffold requires one)"
        elif t["tool_names"] and any(n != "bash" for n in t["tool_names"]):
            tier, evidence = "T1_STRUCTURAL", f"non-bash tool name: {t['tool_names']}"
        elif t["fanout_mismatch"]:
            tier, evidence = "T1_STRUCTURAL", "tool-call count disagrees with parsed command count"

        # T2 ENVIRONMENTAL -- from tool output.
        if not tier:
            hit, why = _payload_signal(payloads)
            if hit:
                tier, evidence = "T2_ENVIRONMENTAL", why
            elif t["atlas_status"] == "error":
                tier, evidence = "T2_ENVIRONMENTAL", "atlas turn status=error"

        # T3 PROGRESS -- trajectory shape over a window.
        if not tier:
            dup = [c for c in cmds if c in seen_cmds[tid]]
            if dup:
                tier, evidence = "T3_PROGRESS", f"exact repeat of an earlier command: {dup[0][:70]!r}"
            elif t["loop_membership"]:
                tier, evidence = "T3_PROGRESS", "atlas loop_membership=true (action-shape cycle)"

        # T4 SEMANTIC / UNOBSERVABLE.
        if not tier:
            if payloads:
                tier, evidence = "T4_SEMANTIC", "clean exit, non-empty output, no repetition: needs judge or ground truth"
            elif cmds:
                tier, evidence = "T4_SEMANTIC", "commands ran but no payload retained: cannot see effect without a judge"
            else:
                tier, evidence = "UNOBSERVABLE", "terminal turn with no tool call and no payload"

        for c in cmds:
            seen_cmds[tid].add(c)

        rows.append({
            "trajectory_id": tid,
            "turn_index": t["turn_index"],
            "task_id": t["task_id"],
            "tier": tier,
            "free_observable": tier in {"T1_STRUCTURAL", "T2_ENVIRONMENTAL", "T3_PROGRESS"},
            "evidence": evidence,
            "payload_available": bool(payloads),
            "n_commands": len(cmds),
            "step_type_semantic": t["step_type_semantic"],
            "atlas_status": t["atlas_status"],
            "loop_membership": t["loop_membership"],
            "repeat_count": t["repeat_count"],
            "command_source": t["source"],
        })

    _write_csv(OUT / "observability.csv", rows)
    dist = Counter(r["tier"] for r in rows)
    free = sum(1 for r in rows if r["free_observable"])
    # Turns with no retained payload cannot be tested for T2, so the true T2
    # count is bounded below by what we can see.
    nopay = [r for r in rows if not r["payload_available"]]
    nopay_not_free = sum(1 for r in nopay if not r["free_observable"])
    return {
        "rows": rows,
        "dist": dist,
        "n": len(rows),
        "free": free,
        "free_frac": free / max(1, len(rows)),
        "free_frac_upper": (free + nopay_not_free) / max(1, len(rows)),
        "n_no_payload": len(nopay),
    }


# ---------------------------------------------------------------------------
# Item D2 -- reversibility
# ---------------------------------------------------------------------------
def item_d2(turns: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    per_command: list[dict[str, Any]] = []
    for t in turns:
        cls, why = classify_turn(t["commands"])
        for c in t["commands"]:
            ccls, cwhy, _ = classify(c)
            per_command.append({
                "trajectory_id": t["trajectory_id"],
                "turn_index": t["turn_index"],
                "command": c,
                "command_class": ccls,
                "rationale": cwhy,
            })
        rows.append({
            "trajectory_id": t["trajectory_id"],
            "turn_index": t["turn_index"],
            "task_id": t["task_id"],
            "reversibility": cls,
            "rationale": why,
            "n_commands": len(t["commands"]),
            "commands": " ;; ".join(c.replace("\n", "\\n") for c in t["commands"]),
            "step_type_semantic": t["step_type_semantic"],
            "verb_first": (t["verbs"] or [""])[0],
            "command_source": t["source"],
        })
    _write_csv(OUT / "reversibility.csv", rows)
    _write_csv(OUT / "reversibility_per_command.csv", per_command)
    return {
        "rows": rows,
        "dist": Counter(r["reversibility"] for r in rows),
        "cmd_dist": Counter(r["command_class"] for r in per_command),
        "per_command": per_command,
    }


# ---------------------------------------------------------------------------
# Item D3 -- joint table + trajectory-level bootstrap
# ---------------------------------------------------------------------------
def item_d3(d1: dict[str, Any], d2: dict[str, Any], seed: int = 20260727,
            iters: int = 10000) -> dict[str, Any]:
    obs = {(r["trajectory_id"], r["turn_index"]): r for r in d1["rows"]}
    rev = {(r["trajectory_id"], r["turn_index"]): r for r in d2["rows"]}
    keys = sorted(set(obs) & set(rev))

    cross: Counter[tuple[str, str]] = Counter()
    by_traj: dict[str, list[tuple[bool, str]]] = defaultdict(list)
    for k in keys:
        tier = obs[k]["tier"]
        rcls = rev[k]["reversibility"]
        cross[(rcls, tier)] += 1
        by_traj[k[0]].append((obs[k]["free_observable"], rcls))

    rows = []
    tiers = ["T1_STRUCTURAL", "T2_ENVIRONMENTAL", "T3_PROGRESS", "T4_SEMANTIC", "UNOBSERVABLE"]
    classes = ["READ_ONLY", "RECOVERABLE", "IRREVERSIBLE", "AMBIGUOUS", "NO_COMMAND"]
    for rcls in classes:
        row: dict[str, Any] = {"reversibility": rcls}
        tot = 0
        for tier in tiers:
            row[tier] = cross.get((rcls, tier), 0)
            tot += row[tier]
        row["free_observable"] = sum(cross.get((rcls, t), 0) for t in tiers[:3])
        row["total"] = tot
        rows.append(row)
    total_turns = len(keys)
    fast = cross_fast(cross, tiers)
    rows.append({
        "reversibility": "__TOTAL__",
        **{t: sum(cross.get((c, t), 0) for c in classes) for t in tiers},
        "free_observable": sum(cross.get((c, t), 0) for c in classes for t in tiers[:3]),
        "total": total_turns,
    })

    # Trajectory-level bootstrap: resample whole trajectories with replacement.
    rng = random.Random(seed)
    traj_ids = sorted(by_traj)
    samples: list[float] = []
    for _ in range(iters):
        pick = [rng.choice(traj_ids) for _ in traj_ids]
        num = den = 0
        for tid in pick:
            for free, rcls in by_traj[tid]:
                den += 1
                if free and rcls == "READ_ONLY":
                    num += 1
        if den:
            samples.append(num / den)
    samples.sort()

    def pct(q: float) -> float:
        if not samples:
            return float("nan")
        return samples[min(len(samples) - 1, int(q * len(samples)))]

    point = fast / max(1, total_turns)
    out_rows = rows + [{
        "reversibility": "__FAST_PATH__",
        "T1_STRUCTURAL": "", "T2_ENVIRONMENTAL": "", "T3_PROGRESS": "",
        "T4_SEMANTIC": "", "UNOBSERVABLE": "",
        "free_observable": fast,
        "total": total_turns,
    }]
    _write_csv(OUT / "fast_path.csv", out_rows)

    summary = {
        "fast_path_n": fast,
        "total_turns": total_turns,
        "fast_path_frac": point,
        "ci_lo": pct(0.025),
        "ci_hi": pct(0.975),
        "n_trajectories": len(traj_ids),
        "iters": iters,
        "cross": cross,
    }
    with (OUT / "fast_path_summary.json").open("w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in summary.items() if k != "cross"}, fh, indent=2)
    return summary


def cross_fast(cross: Counter, tiers: list[str]) -> int:
    return sum(cross.get(("READ_ONLY", t), 0) for t in tiers[:3])


# ---------------------------------------------------------------------------
# Item D4 -- prompt-head stability
# ---------------------------------------------------------------------------
def _serialize(msg: dict[str, Any]) -> str:
    parts = [f"<<{msg.get('role')}>>", str(msg.get("content") or "")]
    for tc in msg.get("tool_calls") or []:
        fn = (tc or {}).get("function") or {}
        parts.append(f"<<tool_call:{fn.get('name')}>>{fn.get('arguments')}")
    return "\n".join(parts)


def item_d4(atlas: dict[str, Any], trajs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    atlas_tids = {o["trajectory_id"] for o in atlas["outcomes"]}
    results: list[dict[str, Any]] = []
    configs: dict[str, Any] = {}

    for tid, traj in sorted(trajs.items()):
        if tid not in atlas_tids:
            continue
        msgs = traj.get("messages") or []
        cfg = (traj.get("info") or {}).get("config") or {}
        configs[tid] = cfg
        # Prompt as assembled at each assistant turn = everything before it.
        prompts: list[str] = []
        acc: list[str] = []
        for m in msgs:
            if m.get("role") == "assistant":
                prompts.append("\n".join(acc))
            if m.get("role") != "exit":
                acc.append(_serialize(m))
        pairs = []
        for i in range(1, len(prompts)):
            a, b = prompts[i - 1], prompts[i]
            is_ext = b.startswith(a)
            lcp = len(a) if is_ext else _lcp_len(a, b)
            pairs.append({
                "turn": i,
                "append_only": is_ext,
                "lcp_chars": lcp,
                "prev_len": len(a),
                "cur_len": len(b),
                "stable_prefix_frac_of_current": lcp / max(1, len(b)),
                "divergence_context": "" if is_ext else _context(a, b, lcp),
            })
        results.append({"trajectory_id": tid, "n_prompts": len(prompts), "pairs": pairs})

    all_pairs = [p for r in results for p in r["pairs"]]
    n_ext = sum(1 for p in all_pairs if p["append_only"])
    fracs = sorted(p["stable_prefix_frac_of_current"] for p in all_pairs)

    # Corroborating evidence from the atlas: local LCP token counts and the
    # provider prefix-cache reconciliation. Compare against the previous turn's
    # LOCALLY serialized length, and report a ratio rather than a binary --
    # tokenizer and template-boundary effects move this by a token or two, which
    # a >= test would misread as head mutation.
    sp = atlas["spaghetti"]
    ratios: list[float] = []
    lcp_ge99 = 0
    for turns in sp.values():
        ts = sorted(turns, key=lambda t: t["turn_index"])
        for i in range(1, len(ts)):
            prev = ts[i - 1]["local_serialized_tokens"]
            if prev <= 0:
                continue
            ratio = ts[i]["local_lcp_tokens"] / prev
            ratios.append(ratio)
            if ratio >= 0.99:
                lcp_ge99 += 1
    ratios.sort()

    return {
        "per_trajectory": results,
        "n_pairs": len(all_pairs),
        "n_append_only": n_ext,
        "append_only_frac": n_ext / max(1, len(all_pairs)),
        "min_stable_frac": fracs[0] if fracs else float("nan"),
        "median_stable_frac": fracs[len(fracs) // 2] if fracs else float("nan"),
        "lcp_ge99": lcp_ge99,
        "lcp_total": len(ratios),
        "lcp_ratio_min": ratios[0] if ratios else float("nan"),
        "lcp_ratio_p05": ratios[int(0.05 * len(ratios))] if ratios else float("nan"),
        "lcp_ratio_median": ratios[len(ratios) // 2] if ratios else float("nan"),
        "provider_cache": atlas["provider_cache"],
        "configs": configs,
        "n_traj_with_messages": len(results),
    }


def _lcp_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _context(a: str, b: str, lcp: int) -> str:
    return f"prev={a[lcp:lcp + 60]!r} cur={b[lcp:lcp + 60]!r}"


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------
def build_turns(atlas: dict[str, Any], verb_turns: dict[tuple[str, int], dict[str, Any]],
                trajs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    payload_cache = {tid: tool_payloads_by_turn(tr) for tid, tr in trajs.items()}
    turns: list[dict[str, Any]] = []
    for tid, raw in atlas["spaghetti"].items():
        ts = sorted(raw, key=lambda t: t["turn_index"])
        last = ts[-1]["turn_index"] if ts else -1
        for t in ts:
            idx = t["turn_index"]
            vt = verb_turns.get((tid, idx), {})
            cmds = list(vt.get("commands") or [])
            tool_names = list(t.get("tool_names") or [])
            turns.append({
                "trajectory_id": tid,
                "turn_index": idx,
                "task_id": t.get("task_id"),
                "commands": cmds,
                "verbs": list(vt.get("verbs") or []),
                "is_tool_call": bool(t.get("is_tool_call")),
                "tool_names": tool_names,
                "fanout_mismatch": bool(cmds) and bool(tool_names) and len(cmds) != len(tool_names),
                "payloads": payload_cache.get(tid, {}).get(idx, []),
                "atlas_status": t.get("status"),
                "loop_membership": bool(t.get("loop_membership")),
                "repeat_count": t.get("repeat_count"),
                "step_type_semantic": t.get("step_type_semantic"),
                "is_last_turn": idx == last,
                "source": vt.get("source", "missing"),
            })
    return turns


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})


def run() -> dict[str, Any]:
    atlas = load_atlas()
    swe = load_swebench()
    verb_turns = load_verb_turns()
    trajs = load_trajs()
    turns = build_turns(atlas, verb_turns, trajs)

    c = item_c(atlas, swe, trajs)
    d1 = item_d1(turns)
    d2 = item_d2(turns)
    d3 = item_d3(d1, d2)
    d4 = item_d4(atlas, trajs)
    return {"atlas": atlas, "swe": swe, "turns": turns, "c": c, "d1": d1, "d2": d2, "d3": d3, "d4": d4}


def main() -> None:
    r = run()
    c, d1, d2, d3, d4 = r["c"], r["d1"], r["d2"], r["d3"], r["d4"]

    print("=" * 78)
    print("ITEM C -- corpus outcomes")
    print("=" * 78)
    for k, v in c["counts"].most_common():
        print(f"  {k:<10} {v}")
    print("  provenance:")
    for (cls, prov), v in sorted(c["provenance"].items()):
        print(f"    {cls:<10} {prov:<16} {v}")
    swe = c["swe"]
    print(f"  SWE-bench report ({swe['_path']}): submitted={swe['submitted_instances']} "
          f"completed={swe['completed_instances']} resolved={swe['resolved_instances']} "
          f"unresolved={swe['unresolved_instances']} empty_patch={swe['empty_patch_instances']} "
          f"error={swe['error_instances']}")

    print()
    print("=" * 78)
    print("ITEM D1 -- observability")
    print("=" * 78)
    for k, v in d1["dist"].most_common():
        print(f"  {k:<18} {v:>4}  ({100*v/d1['n']:.1f}%)")
    print(f"  free-observable (T1+T2+T3): {d1['free']}/{d1['n']} = {100*d1['free_frac']:.1f}%")
    print(f"  turns with no retained payload: {d1['n_no_payload']} "
          f"(upper bound on free-observable if all were T2: {100*d1['free_frac_upper']:.1f}%)")
    print(f"  KILL THRESHOLD (<50%): {'FIRES' if d1['free_frac'] < 0.5 else 'does not fire'}")

    print()
    print("=" * 78)
    print("ITEM D2 -- reversibility (from full command strings)")
    print("=" * 78)
    for k, v in d2["dist"].most_common():
        print(f"  turn-level  {k:<14} {v:>4}  ({100*v/len(d2['rows']):.1f}%)")
    print()
    for k, v in d2["cmd_dist"].most_common():
        print(f"  cmd-level   {k:<14} {v:>4}")

    print()
    print("=" * 78)
    print("ITEM D3 -- fast path")
    print("=" * 78)
    print(f"  READ_ONLY and free-observable: {d3['fast_path_n']}/{d3['total_turns']} "
          f"= {100*d3['fast_path_frac']:.1f}%")
    print(f"  trajectory bootstrap 95% CI: [{100*d3['ci_lo']:.1f}%, {100*d3['ci_hi']:.1f}%] "
          f"({d3['n_trajectories']} trajectories, {d3['iters']} iters)")

    print()
    print("=" * 78)
    print("ITEM D4 -- prompt-head stability")
    print("=" * 78)
    print(f"  trajectories with message logs: {d4['n_traj_with_messages']}")
    print(f"  consecutive prompt pairs: {d4['n_pairs']}")
    print(f"  append-only (prev prompt is an exact prefix of next): "
          f"{d4['n_append_only']}/{d4['n_pairs']} = {100*d4['append_only_frac']:.1f}%")
    print(f"  atlas local LCP / previous serialized length: "
          f"min={d4['lcp_ratio_min']:.4f} p05={d4['lcp_ratio_p05']:.4f} median={d4['lcp_ratio_median']:.4f}")
    print(f"  pairs with LCP >= 99% of previous prompt: {d4['lcp_ge99']}/{d4['lcp_total']}")
    pc = d4["provider_cache"]
    print(f"  provider prefix-cache recovery: {100*pc['recovery_fraction_of_structural']:.2f}% "
          f"of structurally redundant tokens, {pc['provider_cache_reconciliation_violations']} violations")

    print()
    print("=" * 78)
    print("SAMPLES -- reversibility classes (audit the classifier by eye)")
    print("=" * 78)
    by_cls: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pc_row in d2["per_command"]:
        by_cls[pc_row["command_class"]].append(pc_row)
    for cls in ("IRREVERSIBLE", "AMBIGUOUS", "RECOVERABLE", "READ_ONLY"):
        rows_ = by_cls.get(cls, [])
        print(f"\n  --- {cls} ({len(rows_)}) ---")
        for row in rows_[:8]:
            cmd = row["command"].replace("\n", "\\n")[:100]
            print(f"    {cmd}")
            print(f"       -> {row['rationale'][:90]}")

    print()
    print("  --- turns where step_type_semantic disagrees with measured reversibility ---")
    rev_by_key = {(x["trajectory_id"], x["turn_index"]): x for x in d2["rows"]}
    shown = 0
    for k, row in sorted(rev_by_key.items()):
        sem = row["step_type_semantic"]
        cls = row["reversibility"]
        if sem.startswith("inspect") and cls in {"IRREVERSIBLE", "RECOVERABLE"}:
            print(f"    {k[0]} t{k[1]}: semantic={sem} but measured={cls}")
            print(f"       {row['commands'][:110]}")
            shown += 1
            if shown >= 6:
                break


if __name__ == "__main__":
    main()
