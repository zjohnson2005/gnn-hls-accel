"""Transition analysis for sealed run d482c621. Read-only on the seal."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "d482c621-4292-4281-b6a1-8635e5eeb6da"
PREREG = "2f1b8047652e4388878076ebc09a8551d837e888"
SEAL = ROOT / "derived" / "h1_hybrid" / f"interleaved_{RUN_ID}"
OUT = ROOT / "derived" / "h1_hybrid" / "analysis_d482c621" / "transition"
POLICIES = ("slo_escalate", "emission_escalate", "full_signal_bounceback")
CLASSES = ("PASS", "MISMATCH", "OTHER")
PAIRS = (
    ("slo_escalate", "emission_escalate"),
    ("slo_escalate", "full_signal_bounceback"),
    ("emission_escalate", "full_signal_bounceback"),
)
REQUEST_KEY_HINTS = (
    "request",
    "messages",
    "system_prompt",
    "tool_schema",
    "input_text",
    "prompt_body",
    "raw_request",
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _keys(obj: Any, found: set[str], *, depth: int) -> None:
    if depth > 6:
        return
    if isinstance(obj, dict):
        for key, val in obj.items():
            found.add(str(key))
            _keys(val, found, depth=depth + 1)
    elif isinstance(obj, list) and obj:
        _keys(obj[0], found, depth=depth + 1)


def _ism_flag(row: dict[str, Any]) -> bool:
    err = row.get("hybrid_score_error_type")
    return err is not None and "instance_state_mismatch" in str(err)


def _outcome(row: dict[str, Any]) -> str:
    if row.get("hybrid_pass") is True:
        return "PASS"
    if _ism_flag(row):
        return "MISMATCH"
    return "OTHER"


def _matrix(
    left: dict[str, str], right: dict[str, str], ids: list[str]
) -> dict[str, dict[str, int]]:
    cells = {a: dict.fromkeys(CLASSES, 0) for a in CLASSES}
    for eid in ids:
        cells[left[eid]][right[eid]] += 1
    return cells


def _dist(values: list[int]) -> dict[str, int]:
    counts = Counter(values)
    return {str(k): counts[k] for k in sorted(counts)}


def main() -> None:
    qualities = {
        p: _load(SEAL / "policies" / p / "entry_quality.json")["entries"] for p in POLICIES
    }
    ledgers = {
        p: {
            str(row["entry_id"]): row
            for row in _load(SEAL / "policies" / p / "turn_ledger.json")["entries"]
        }
        for p in POLICIES
    }
    ids = sorted(str(row["entry_id"]) for row in qualities["slo_escalate"])
    for policy in POLICIES:
        got = {str(row["entry_id"]) for row in qualities[policy]}
        if got != set(ids) or len(ids) != 200:
            raise SystemExit(f"entry id set mismatch for {policy}: {len(got)}")

    overlap: list[dict[str, str]] = []
    outcome: dict[str, dict[str, str]] = {p: {} for p in POLICIES}
    bucket: dict[str, dict[str, str | None]] = {p: {} for p in POLICIES}
    for policy in POLICIES:
        for row in qualities[policy]:
            eid = str(row["entry_id"])
            if row.get("hybrid_pass") is True and _ism_flag(row):
                overlap.append(
                    {
                        "policy": policy,
                        "entry_id": eid,
                        "hybrid_score_error_type": row.get("hybrid_score_error_type"),
                    }
                )
            outcome[policy][eid] = _outcome(row)
            err = row.get("hybrid_score_error_type")
            bucket[policy][eid] = str(err) if err is not None else None

    if overlap:
        payload = {
            "run_id": RUN_ID,
            "prereg_commit": PREREG,
            "assert_pass_intersect_mismatch": "FAIL",
            "n": len(overlap),
            "entries": overlap,
        }
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "ASSERT_FAIL.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"stopped": True, "n_overlap": len(overlap)}))
        return

    escalated: dict[str, dict[str, bool]] = {p: {} for p in POLICIES}
    n_esc_turns: dict[str, dict[str, int]] = {p: {} for p in POLICIES}
    first_esc: dict[str, dict[str, int | None]] = {p: {} for p in POLICIES}
    n_bounces: dict[str, int] = {}
    for policy in POLICIES:
        for eid in ids:
            turns = ledgers[policy][eid]["turns"]
            flags = [t.get("escalated") is True for t in turns]
            escalated[policy][eid] = any(flags)
            n_esc_turns[policy][eid] = sum(1 for f in flags if f)
            first = next(
                (int(t["turn"]) for t, f in zip(turns, flags, strict=True) if f),
                None,
            )
            first_esc[policy][eid] = first
            if policy == "full_signal_bounceback":
                n_bounces[eid] = len(ledgers[policy][eid].get("bounces") or [])

    def cell(src: str, dst: str, a: str, b: str) -> int:
        return sum(1 for eid in ids if outcome[src][eid] == a and outcome[dst][eid] == b)

    other_mismatch_bb = cell("slo_escalate", "full_signal_bounceback", "OTHER", "MISMATCH")
    other_pass_bb = cell("slo_escalate", "full_signal_bounceback", "OTHER", "PASS")
    other_mismatch_em = cell("slo_escalate", "emission_escalate", "OTHER", "MISMATCH")
    other_pass_em = cell("slo_escalate", "emission_escalate", "OTHER", "PASS")
    p1_hit = other_mismatch_bb >= 2 * other_pass_bb
    p2_hit = other_pass_em > other_mismatch_em

    bb_esc_ids = [eid for eid in ids if escalated["full_signal_bounceback"][eid]]
    bb_multi = [eid for eid in bb_esc_ids if n_bounces[eid] >= 2]
    p3_frac = (len(bb_multi) / len(bb_esc_ids)) if bb_esc_ids else None
    p3_hit = p3_frac is not None and p3_frac >= 0.30

    regressions: dict[str, list[dict[str, Any]]] = {}
    p4_detail: dict[str, Any] = {}
    for policy in ("emission_escalate", "full_signal_bounceback"):
        rows = []
        for eid in ids:
            if outcome["slo_escalate"][eid] != "PASS":
                continue
            if outcome[policy][eid] == "PASS":
                continue
            rows.append(
                {
                    "run_id": RUN_ID,
                    "entry_id": eid,
                    "policy": policy,
                    "escalated": escalated[policy][eid],
                    "n_escalated_turns": n_esc_turns[policy][eid],
                    "outcome": outcome[policy][eid],
                }
            )
        n_reg = len(rows)
        n_not = sum(1 for r in rows if not r["escalated"])
        frac_not = (n_not / n_reg) if n_reg else None
        regressions[policy] = rows
        p4_detail[policy] = {
            "n_regressions": n_reg,
            "n_not_escalated": n_not,
            "fraction_not_escalated": frac_not,
            "hit": frac_not is not None and frac_not >= 0.5,
        }
    p4_hit = all(v["hit"] for v in p4_detail.values())

    always = [eid for eid in ids if all(outcome[p][eid] == "MISMATCH" for p in POLICIES)]
    n_always_em = sum(1 for eid in always if escalated["emission_escalate"][eid])
    n_always_bb = sum(1 for eid in always if escalated["full_signal_bounceback"][eid])
    p5_frac = n_always_em / 91
    p5_hit = len(always) == 91 and p5_frac < 0.25

    # OTHER-row flows named by P1/P2: slo OTHER to {PASS, MISMATCH}.
    flow_rows: list[dict[str, Any]] = []
    for dst, flows in (
        (
            "full_signal_bounceback",
            (("OTHER", "MISMATCH"), ("OTHER", "PASS")),
        ),
        (
            "emission_escalate",
            (("OTHER", "MISMATCH"), ("OTHER", "PASS")),
        ),
    ):
        for src_c, dst_c in flows:
            members = [
                eid
                for eid in ids
                if outcome["slo_escalate"][eid] == src_c and outcome[dst][eid] == dst_c
            ]
            n_not = sum(1 for eid in members if not escalated[dst][eid])
            flow_rows.append(
                {
                    "destination": dst,
                    "flow": f"{src_c}->{dst_c}",
                    "n": len(members),
                    "n_not_escalated": n_not,
                    "n_escalated": len(members) - n_not,
                }
            )
    flow_n = sum(r["n"] for r in flow_rows)
    flow_not = sum(r["n_not_escalated"] for r in flow_rows)
    other_flows_mostly_non_escalated = flow_n > 0 and flow_not > (flow_n - flow_not)
    kill = (not p1_hit) or other_flows_mostly_non_escalated

    matrices = {}
    matrices_split: dict[str, Any] = {}
    for src, dst in PAIRS:
        key = f"{src}->{dst}"
        matrices[key] = _matrix(outcome[src], outcome[dst], ids)
        esc_ids = [eid for eid in ids if escalated[dst][eid]]
        stay_ids = [eid for eid in ids if not escalated[dst][eid]]
        matrices_split[key] = {
            "escalated_under_second": _matrix(outcome[src], outcome[dst], esc_ids),
            "not_escalated_under_second": _matrix(outcome[src], outcome[dst], stay_ids),
            "n_escalated_under_second": len(esc_ids),
            "n_not_escalated_under_second": len(stay_ids),
        }

    per_policy_esc: dict[str, Any] = {}
    for policy in POLICIES:
        esc_ids = [eid for eid in ids if escalated[policy][eid]]
        per_policy_esc[policy] = {
            "run_id": RUN_ID,
            "n_escalated_entries": len(esc_ids),
            "escalated_turns_per_entry": _dist([n_esc_turns[policy][eid] for eid in esc_ids]),
            "first_escalation_turn": _dist(
                [
                    int(first_esc[policy][eid])
                    for eid in esc_ids
                    if first_esc[policy][eid] is not None
                ]
            ),
        }
    bounce_by_count: dict[str, dict[str, int]] = {}
    for eid in ids:
        k = str(n_bounces[eid])
        bounce_by_count.setdefault(k, dict.fromkeys(CLASSES, 0))
        bounce_by_count[k][outcome["full_signal_bounceback"][eid]] += 1
    bounce_vs_esc_disagree = sum(
        1 for eid in ids if n_bounces[eid] != n_esc_turns["full_signal_bounceback"][eid]
    )

    other_buckets = {}
    for policy in POLICIES:
        counts: Counter[str] = Counter()
        for eid in ids:
            if outcome[policy][eid] != "OTHER":
                continue
            counts[bucket[policy][eid] or "(none)"] += 1
        other_buckets[policy] = dict(counts.most_common())

    class_counts = {
        p: {c: sum(1 for eid in ids if outcome[p][eid] == c) for c in CLASSES} for p in POLICIES
    }

    # Step 4: request bodies. Key scan only. Do not reconstruct prompts.
    found_keys: set[str] = set()
    for path in SEAL.rglob("*.json"):
        _keys(_load(path), found_keys, depth=0)
    request_keys = sorted(k for k in found_keys if any(h in k.lower() for h in REQUEST_KEY_HINTS))
    step4 = {
        "run_id": RUN_ID,
        "status": "STOPPED",
        "reason": (
            "Sealed artifacts have no cloud request or response bodies. "
            "The only key matching a request hint is plan.json openvino "
            "kv_cache_precision.requested (value u8), which is the KV setting, "
            "not an API payload. Token counts were not decomposed."
        ),
        "files_scanned": [
            str(p.relative_to(ROOT)).replace("\\", "/") for p in SEAL.rglob("*.json")
        ],
        "keys_matching_request_hints": request_keys,
        "cloud_turn_fields_present": [
            "cloud_tokens_in",
            "cloud_tokens_out",
            "cloud_usd",
            "decoded_steps",
            "n_ctx",
            "placement",
        ],
    }

    verdicts = [
        {
            "prediction": "P1",
            "predicted": "slo->bounceback OTHER->MISMATCH >= 2 x OTHER->PASS",
            "measured": {
                "OTHER->MISMATCH": other_mismatch_bb,
                "OTHER->PASS": other_pass_bb,
                "ratio": (other_mismatch_bb / other_pass_bb) if other_pass_bb else None,
            },
            "verdict": "HIT" if p1_hit else "MISS",
            "measured_text": f"{other_mismatch_bb} vs 2 x {other_pass_bb}",
        },
        {
            "prediction": "P2",
            "predicted": "slo->emission OTHER->PASS > OTHER->MISMATCH",
            "measured": {
                "OTHER->PASS": other_pass_em,
                "OTHER->MISMATCH": other_mismatch_em,
            },
            "verdict": "HIT" if p2_hit else "MISS",
            "measured_text": f"OTHER->PASS {other_pass_em}, OTHER->MISMATCH {other_mismatch_em}",
        },
        {
            "prediction": "P3",
            "predicted": ">= 30% of bounceback-escalated entries have >= 2 bounces",
            "measured": {
                "n_bounceback_escalated": len(bb_esc_ids),
                "n_with_ge_2_bounces": len(bb_multi),
                "fraction": p3_frac,
            },
            "verdict": "HIT" if p3_hit else "MISS",
            "measured_text": f"{len(bb_multi)}/{len(bb_esc_ids)} = {p3_frac}",
        },
        {
            "prediction": "P4",
            "predicted": (
                "under emission and bounceback, >= half of slo PASS -> non-PASS "
                "regressions are on entries that policy did not escalate"
            ),
            "measured": p4_detail,
            "verdict": "HIT" if p4_hit else "MISS",
            "measured_text": (
                "emission "
                f"{p4_detail['emission_escalate']['n_not_escalated']}/"
                f"{p4_detail['emission_escalate']['n_regressions']}; "
                "bounceback "
                f"{p4_detail['full_signal_bounceback']['n_not_escalated']}/"
                f"{p4_detail['full_signal_bounceback']['n_regressions']}"
            ),
        },
        {
            "prediction": "P5",
            "predicted": "< 25% of the 91 always-MISMATCH entries escalated under emission",
            "measured": {
                "n_always_mismatch": len(always),
                "n_escalated_emission": n_always_em,
                "fraction_of_91": p5_frac,
            },
            "verdict": "HIT" if p5_hit else "MISS",
            "measured_text": f"{n_always_em}/91",
        },
    ]

    results = {
        "run_id": RUN_ID,
        "prereg_commit": PREREG,
        "assert_pass_intersect_instance_state_mismatch": {
            "empty": True,
            "n": 0,
        },
        "class_counts": class_counts,
        "other_failure_buckets": other_buckets,
        "matrices": matrices,
        "matrices_by_second_policy_escalation": matrices_split,
        "escalation": per_policy_esc,
        "bounceback": {
            "run_id": RUN_ID,
            "bounces_per_entry": _dist([n_bounces[eid] for eid in ids]),
            "outcome_by_bounce_count": {
                k: bounce_by_count[k] for k in sorted(bounce_by_count, key=int)
            },
            "n_entries_bounces_ne_escalated_turns": bounce_vs_esc_disagree,
        },
        "regressions": regressions,
        "always_mismatch": {
            "run_id": RUN_ID,
            "n": len(always),
            "n_escalated_emission": n_always_em,
            "n_escalated_bounceback": n_always_bb,
            "entry_ids": always,
        },
        "step4_escalated_payload": step4,
        "kill_operationalization": (
            "OTHER-row flows are the slo OTHER -> {PASS, MISMATCH} cells on "
            "slo->bounceback and slo->emission. Mostly non-escalated means "
            "not-escalated count under the destination policy exceeds escalated count "
            "in that pooled set."
        ),
        "other_row_flows": flow_rows,
        "other_row_flows_mostly_non_escalated": other_flows_mostly_non_escalated,
        "kill_fired": kill,
        "h_gran": "REJECTED" if kill else "NOT_REJECTED",
        "verdicts": verdicts,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "TRANSITION_RESULTS.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "TRANSITION_RESULTS.md").write_text(_markdown(results), encoding="utf-8")
    print(
        json.dumps(
            {
                "classes": class_counts,
                "p1": [other_mismatch_bb, other_pass_bb, p1_hit],
                "p2": [other_pass_em, other_mismatch_em, p2_hit],
                "p3": [len(bb_esc_ids), len(bb_multi), p3_frac],
                "p4": p4_detail,
                "p5": [len(always), n_always_em, n_always_bb],
                "kill": kill,
                "request_keys": request_keys,
                "bounce_disagree": bounce_vs_esc_disagree,
            },
            indent=2,
        )
    )


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def _matrix_md(cells: dict[str, dict[str, int]]) -> list[str]:
    lines = ["| row \\ col | PASS | MISMATCH | OTHER |", "|---|---:|---:|---:|"]
    for row in CLASSES:
        lines.append(
            f"| {row} | {cells[row]['PASS']} | {cells[row]['MISMATCH']} | {cells[row]['OTHER']} |"
        )
    return lines


def _markdown(results: dict[str, Any]) -> str:
    run = RUN_ID
    lines = [
        f"# Transition analysis ({run})",
        "",
        f"Pre-registration commit `{results['prereg_commit']}`. Every count is from run_id `{run}`.",
        "",
        "PASS = hybrid_pass. MISMATCH = hybrid error type contains instance_state_mismatch and not PASS. OTHER = everything else.",
        "",
        f"PASS intersect instance_state_mismatch is empty (n={results['assert_pass_intersect_instance_state_mismatch']['n']}).",
        "",
        "## Class counts",
        "",
        "| policy | PASS | MISMATCH | OTHER |",
        "|---|---:|---:|---:|",
    ]
    for policy, counts in results["class_counts"].items():
        lines.append(f"| {policy} | {counts['PASS']} | {counts['MISMATCH']} | {counts['OTHER']} |")
    lines += ["", "## OTHER failure buckets", ""]
    for policy, buckets in results["other_failure_buckets"].items():
        lines.append(f"### {policy}")
        lines.append("")
        lines.append("| failure_bucket | n |")
        lines.append("|---|---:|")
        for name, n in buckets.items():
            lines.append(f"| {name} | {n} |")
        lines.append("")
    lines.append("## 3a. Transition matrices")
    lines.append("")
    for key, cells in results["matrices"].items():
        lines.append(f"### {key}")
        lines.append("")
        lines.extend(_matrix_md(cells))
        lines.append("")
    lines.append("## 3b. Split by escalation under the second policy")
    lines.append("")
    for key, block in results["matrices_by_second_policy_escalation"].items():
        lines.append(f"### {key} escalated under second (n={block['n_escalated_under_second']})")
        lines.append("")
        lines.extend(_matrix_md(block["escalated_under_second"]))
        lines.append("")
        lines.append(
            f"### {key} not escalated under second (n={block['n_not_escalated_under_second']})"
        )
        lines.append("")
        lines.extend(_matrix_md(block["not_escalated_under_second"]))
        lines.append("")
    lines.append("## 3c. Escalation")
    lines.append("")
    for policy, block in results["escalation"].items():
        lines.append(
            f"- {policy}: {block['n_escalated_entries']} escalated entries. "
            f"Escalated turns per entry: {block['escalated_turns_per_entry']}. "
            f"First escalation turn: {block['first_escalation_turn']}."
        )
    bb = results["bounceback"]
    lines += [
        "",
        f"Bounceback bounces per entry: {bb['bounces_per_entry']}.",
        f"Entries where bounce count differs from escalated-turn count: {bb['n_entries_bounces_ne_escalated_turns']}.",
        "",
        "| bounces | PASS | MISMATCH | OTHER |",
        "|---:|---:|---:|---:|",
    ]
    for k, counts in bb["outcome_by_bounce_count"].items():
        lines.append(f"| {k} | {counts['PASS']} | {counts['MISMATCH']} | {counts['OTHER']} |")
    lines += ["", "## 3d. Regressions (slo PASS to policy non-PASS)", ""]
    for policy, rows in results["regressions"].items():
        lines.append(f"### {policy} (n={len(rows)})")
        lines.append("")
        lines.append("| entry_id | escalated | n_escalated_turns | outcome |")
        lines.append("|---|---|---:|---|")
        for row in rows:
            lines.append(
                f"| {row['entry_id']} | {row['escalated']} | {row['n_escalated_turns']} | {row['outcome']} |"
            )
        lines.append("")
    always = results["always_mismatch"]
    lines += [
        "## 3e. Always-MISMATCH",
        "",
        f"n={always['n']}. Escalated under emission: {always['n_escalated_emission']}. "
        f"Escalated under bounceback: {always['n_escalated_bounceback']}.",
        "",
        "## 4. Escalated payload",
        "",
        results["step4_escalated_payload"]["reason"],
        "",
        "## 5. Verdicts",
        "",
        f"KILL fired: {results['kill_fired']}. H-GRAN: {results['h_gran']}.",
        "",
        results["kill_operationalization"],
        "",
        "| prediction | predicted | measured | verdict |",
        "|---|---|---|---|",
    ]
    for row in results["verdicts"]:
        lines.append(
            f"| {row['prediction']} | {row['predicted']} | {row['measured_text']} | {row['verdict']} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
