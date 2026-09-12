"""DISPATCH F2 — per-turn scoring + first-divergence profile (READ-ONLY).

Reads sealed multi_turn_gpu_probe_report.json + multi_turn_probe_entries.json.
Does not re-run GPU generation or modify the agent loop.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REPORT_PATH = OUT / "multi_turn_gpu_probe_report.json"
ENTRIES_PATH = OUT / "multi_turn_probe_entries.json"


def parse_execute(s: str) -> tuple[str, dict[str, Any]] | None:
    """Parse an execute-string into (func_name, kwargs+positional)."""
    s = s.strip()
    try:
        node = ast.parse(s, mode="eval").body
    except SyntaxError:
        # Fallback: name(...)
        m = re.match(r"([A-Za-z_]\w*)\s*\(", s)
        if not m:
            return None
        return m.group(1), {"__raw__": s}
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None
    name = node.func.id
    args: dict[str, Any] = {}
    for i, a in enumerate(node.args):
        try:
            args[f"#{i}"] = ast.literal_eval(a)
        except Exception:
            args[f"#{i}"] = ast.dump(a)
    for kw in node.keywords:
        key = kw.arg if kw.arg is not None else "**"
        try:
            args[key] = ast.literal_eval(kw.value)
        except Exception:
            args[key] = ast.dump(kw.value)
    return name, args


def flatten_turn_decoded(turn_steps: list[list[str]]) -> list[str]:
    out: list[str] = []
    for step in turn_steps:
        out.extend(step)
    return out


def call_sig(s: str) -> tuple[str, tuple[tuple[str, str], ...]] | None:
    parsed = parse_execute(s)
    if parsed is None:
        return None
    name, args = parsed
    items = tuple(sorted((k, repr(v)) for k, v in args.items()))
    return name, items


def compare_turn(
    model_calls: list[str], gold_calls: list[str]
) -> dict[str, Any]:
    """Structural per-turn comparison of execute lists (unordered multiset of sigs)."""
    m_sigs = [call_sig(c) for c in model_calls]
    g_sigs = [call_sig(c) for c in gold_calls]
    if any(s is None for s in m_sigs + g_sigs):
        # Fall back to normalized string equality
        def norm(x: str) -> str:
            return re.sub(r"\s+", "", x)

        m_bag = Counter(norm(c) for c in model_calls)
        g_bag = Counter(norm(c) for c in gold_calls)
        exact = m_bag == g_bag
        return {
            "correct": exact,
            "model_n": len(model_calls),
            "gold_n": len(gold_calls),
            "model_calls": model_calls,
            "gold_calls": gold_calls,
            "compare_mode": "normalized_string",
        }

    m_bag = Counter(m_sigs)
    g_bag = Counter(g_sigs)
    exact = m_bag == g_bag

    # Ordered name sequence for divergence typing
    m_names = [s[0] for s in m_sigs if s is not None]
    g_names = [s[0] for s in g_sigs if s is not None]
    m_by_name: dict[str, list] = {}
    g_by_name: dict[str, list] = {}
    for s in m_sigs:
        if s is not None:
            m_by_name.setdefault(s[0], []).append(s[1])
    for s in g_sigs:
        if s is not None:
            g_by_name.setdefault(s[0], []).append(s[1])

    missing_names = [n for n in g_names if n not in m_names]
    # count-aware missing
    missing_count = []
    for n, cnt in Counter(g_names).items():
        if Counter(m_names)[n] < cnt:
            missing_count.append(n)
    extra_count = []
    for n, cnt in Counter(m_names).items():
        if Counter(g_names)[n] < cnt:
            extra_count.append(n)

    wrong_args = []
    for n in set(g_names) & set(m_names):
        # compare arg bags for this name
        if Counter(m_by_name.get(n, [])) != Counter(g_by_name.get(n, [])):
            wrong_args.append(n)

    wrong_function = False
    # If names differ beyond missing/extra (different function used in place)
    if not exact and m_names and g_names:
        # Heuristic: same length but different name multiset → wrong function
        if Counter(m_names) != Counter(g_names) and (
            len(m_names) == len(g_names) or (missing_count and extra_count)
        ):
            wrong_function = bool(
                set(m_names) - set(g_names) and set(g_names) - set(m_names)
            )

    return {
        "correct": exact,
        "model_n": len(model_calls),
        "gold_n": len(gold_calls),
        "model_calls": model_calls,
        "gold_calls": gold_calls,
        "model_names": m_names,
        "gold_names": g_names,
        "missing_required": sorted(set(missing_count)),
        "extra_calls": sorted(set(extra_count)),
        "wrong_args_funcs": sorted(set(wrong_args)),
        "wrong_function": wrong_function,
        "compare_mode": "parsed_sig_multiset",
    }


def classify_divergence(cmp: dict[str, Any]) -> str:
    if cmp["correct"]:
        return "none"
    # Priority for primary label (most specific first for report)
    missing = cmp.get("missing_required") or []
    extra = cmp.get("extra_calls") or []
    wrong_args = cmp.get("wrong_args_funcs") or []
    wrong_fn = cmp.get("wrong_function", False)

    # empty model
    if cmp["model_n"] == 0 and cmp["gold_n"] > 0:
        return "missing_required_call"
    if wrong_fn:
        return "wrong_function"
    if wrong_args and not missing and not extra:
        return "wrong_arguments"
    if missing and not extra and not wrong_args:
        return "missing_required_call"
    if extra and not missing and not wrong_args:
        return "extra_call"
    # compound — pick dominant
    if missing and extra:
        return "wrong_function"  # substituted / different plan
    if wrong_args and missing:
        return "wrong_arguments"  # often wrong path args + skipped cd
    if wrong_args and extra:
        return "wrong_arguments"
    if missing:
        return "missing_required_call"
    if extra:
        return "extra_call"
    if wrong_args:
        return "wrong_arguments"
    return "wrong_arguments"


def official_first_fail_turn(
    model_decoded: list, gold: list, test_entry: dict, entry_id: str
) -> dict[str, Any]:
    """Re-invoke official checker; recover turn index from early-exit error."""
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    unpacked = (
        ROOT
        / "apu_characterization/out/cap01/live_sources/bfcl-wheel/unpacked"
    )
    if str(unpacked) not in sys.path:
        sys.path.insert(0, str(unpacked))
    from apu_characterization.cap01.bfcl_cap01_multi_turn_checker import check

    # Pad / trim model to gold turn count for checker indexing
    md = list(model_decoded)
    while len(md) < len(gold):
        md.append([])
    md = md[: len(gold)]
    try:
        score = check(
            test_entry=test_entry,
            ground_truth=gold,
            model_result_decoded=md,
            test_category="multi_turn_base",
            model_name=f"f2_analysis_{entry_id}",
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "official_valid": False,
            "official_error_type": f"exception:{type(exc).__name__}",
            "official_error_message": str(exc),
            "official_fail_turn": None,
        }

    msg = score.get("error_message") or score.get("error") or ""
    et = score.get("error_type")
    fail_turn = None
    m = re.search(r"for turn (\d+)", str(msg))
    if m:
        fail_turn = int(m.group(1))
    elif et == "multi_turn:instance_state_mismatch":
        # Official message omits turn index; binary-search via prefixes
        fail_turn = _first_fail_via_prefixes(md, gold, test_entry, entry_id)
    elif score.get("valid"):
        fail_turn = None
    return {
        "official_valid": bool(score.get("valid")),
        "official_error_type": et,
        "official_error_message": msg if msg else None,
        "official_fail_turn": fail_turn,
    }


def _first_fail_via_prefixes(
    md: list, gold: list, test_entry: dict, entry_id: str
) -> int | None:
    from apu_characterization.cap01.bfcl_cap01_multi_turn_checker import check

    for t in range(len(gold)):
        score = check(
            test_entry=test_entry,
            ground_truth=gold[: t + 1],
            model_result_decoded=md[: t + 1],
            test_category="multi_turn_base",
            model_name=f"f2_prefix_{entry_id}_t{t}",
        )
        if not score.get("valid"):
            return t
    return None


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    entries = json.loads(ENTRIES_PATH.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in entries}
    per_entry = report["gpu_probe"]["per_entry"]

    rows: list[dict[str, Any]] = []
    total_correct_turns = 0
    total_turns = 0
    div_type_counts: Counter[str] = Counter()
    first_div_turn_hist: Counter[str] = Counter()

    for pe in per_entry:
        eid = pe["id"]
        entry = by_id[eid]
        gold = entry["reference"]
        model_decoded = pe.get("model_result_decoded") or []
        n_turns = len(gold)
        turn_results = []
        first_div = None
        first_div_type = None
        first_div_detail = None

        for t in range(n_turns):
            if t < len(model_decoded):
                model_calls = flatten_turn_decoded(model_decoded[t])
            else:
                model_calls = []
            gold_calls = list(gold[t])
            cmp = compare_turn(model_calls, gold_calls)
            turn_results.append({"turn": t, **cmp, "label": classify_divergence(cmp)})
            total_turns += 1
            if cmp["correct"]:
                total_correct_turns += 1
            elif first_div is None:
                first_div = t
                first_div_type = classify_divergence(cmp)
                first_div_detail = {
                    "missing_required": cmp.get("missing_required"),
                    "extra_calls": cmp.get("extra_calls"),
                    "wrong_args_funcs": cmp.get("wrong_args_funcs"),
                    "wrong_function": cmp.get("wrong_function"),
                    "model_names": cmp.get("model_names"),
                    "gold_names": cmp.get("gold_names"),
                    "model_calls": model_calls,
                    "gold_calls": gold_calls,
                }

        n_correct = sum(1 for tr in turn_results if tr["correct"])
        prompts = pe.get("prompt_tokens_first_step_per_turn") or []

        # Official checker re-score for fail-turn signal (uses sealed decoded)
        raw = entry.get("raw_entry") or {}
        test_entry = {
            "id": raw.get("id", eid),
            "initial_config": raw.get("initial_config", {}),
            "involved_classes": raw.get("involved_classes", []),
        }
        official = official_first_fail_turn(
            model_decoded, gold, test_entry, eid
        )

        if first_div is None:
            first_div_turn_hist["none(all_correct)"] += 1
            div_type_counts["none"] += 1
        else:
            first_div_turn_hist[str(first_div)] += 1
            div_type_counts[first_div_type or "unknown"] += 1

        rows.append(
            {
                "id": eid,
                "n_user_turns": n_turns,
                "n_correct_turns": n_correct,
                "per_turn_correct": [tr["correct"] for tr in turn_results],
                "per_turn_labels": [tr["label"] for tr in turn_results],
                "first_divergence_turn": first_div,
                "first_divergence_type": first_div_type,
                "first_divergence_detail": first_div_detail,
                "prompt_tokens_first_step_per_turn_measured": prompts,
                "context_growth_delta_tokens_measured": pe.get(
                    "context_growth_delta_tokens"
                ),
                "trajectory_valid": pe.get("score", {}).get("valid"),
                "trajectory_error_type": pe.get("score", {}).get("error_type"),
                "wall_s": pe.get("wall_s"),
                "force_quit": pe.get("force_quit"),
                "official_rescore": official,
                "turns": [
                    {
                        "turn": tr["turn"],
                        "correct": tr["correct"],
                        "label": tr["label"],
                        "model_names": tr.get("model_names"),
                        "gold_names": tr.get("gold_names"),
                        "model_calls": tr["model_calls"],
                        "gold_calls": tr["gold_calls"],
                    }
                    for tr in turn_results
                ],
            }
        )

    summary = {
        "source_report": str(REPORT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "source_entries": str(ENTRIES_PATH.relative_to(ROOT)).replace("\\", "/"),
        "trajectory_level": report["gpu_probe"]["accuracy_overall"],
        "wall_clock_s": report["gpu_probe"]["wall_clock_s"],
        "per_turn_accuracy": {
            "correct_turns": total_correct_turns,
            "total_turns": total_turns,
            "accuracy": total_correct_turns / total_turns if total_turns else 0.0,
            "definition": (
                "Structural multiset equality of parsed execute-call signatures "
                "(function name + normalized args) per user turn. "
                "bfcl_eval.multi_turn_checker does NOT expose a per-turn accuracy "
                "aggregate; it returns a single valid bool and short-circuits on "
                "first failure (state/response checks). Per-turn figures here are "
                "DERIVED from sealed model_result_decoded vs gold reference."
            ),
        },
        "first_divergence_turn_histogram": dict(sorted(first_div_turn_hist.items())),
        "first_divergence_type_counts": dict(div_type_counts),
        "n_entries_diverge_turn0": first_div_turn_hist.get("0", 0),
        "passing_entry_ids": [r["id"] for r in rows if r["trajectory_valid"]],
        "entries": rows,
    }

    out_json = OUT / "dispatch_f2_per_turn_analysis.json"
    out_json.write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in summary if k != "entries"}, indent=2))
    print("--- per-entry ---")
    for r in rows:
        print(
            f"{r['id']}: {r['n_correct_turns']}/{r['n_user_turns']} "
            f"first_div={r['first_divergence_turn']} type={r['first_divergence_type']} "
            f"traj_valid={r['trajectory_valid']} "
            f"official_fail_t={r['official_rescore'].get('official_fail_turn')} "
            f"prompts={r['prompt_tokens_first_step_per_turn_measured']}"
        )


if __name__ == "__main__":
    main()
