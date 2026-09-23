"""Fail-turn analysis for sealed run d482c621.

Rescores sealed hybrid trajectories with the committed bfcl_eval checker.
Does not import tools.run_h1_hybrid (uncommitted scoring diff).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "d482c621-4292-4281-b6a1-8635e5eeb6da"
PREREG = "a7af15efb78d5403180700082e01e48fe65db926"
SEAL = ROOT / "derived" / "h1_hybrid" / f"interleaved_{RUN_ID}"
OUT = ROOT / "derived" / "h1_hybrid" / "analysis_d482c621" / "failturn"
ENTRIES = (
    ROOT
    / "derived"
    / "bfcl_feasibility"
    / "w3_weight_quality"
    / "sealed_6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a"
    / "artifacts"
    / "multi_turn_probe_entries.json"
)
POLICIES = ("slo_escalate", "emission_escalate", "full_signal_bounceback")
BUCKETS = ("PASS", "MISMATCH", "EMPTY", "EXEC_RESP")
PAIRS = (
    ("slo_escalate", "emission_escalate"),
    ("slo_escalate", "full_signal_bounceback"),
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _bucket(valid: bool, error_type: str | None) -> str:
    if valid:
        return "PASS"
    text = error_type or ""
    if "instance_state_mismatch" in text:
        return "MISMATCH"
    if "empty_turn_model_response" in text:
        return "EMPTY"
    if "execution_response_mismatch" in text:
        return "EXEC_RESP"
    return f"UNMAPPED:{text or 'none'}"


def _checker():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.bfcl_feasibility_probe import inventory, score_multi_turn

    return inventory, score_multi_turn


def _score(
    entry: dict[str, Any],
    decoded: list[Any],
    *,
    name: str,
    ground: list[Any] | None = None,
) -> dict[str, Any]:
    _, score_fn = _checker()
    scored = score_fn(
        test_entry=entry["raw_entry"],
        ground_truth=ground if ground is not None else entry["reference"],
        model_result_decoded=decoded,
        test_category=str(entry.get("category") or "multi_turn_base"),
        model_name=name,
    )
    err = scored.get("error_type")
    valid = bool(scored.get("valid"))
    return {
        "valid": valid,
        "error_type": str(err) if err is not None else None,
        "bucket": _bucket(valid, str(err) if err is not None else None),
    }


def _rel(turn: int | None, mark: int | None) -> str:
    if turn is None:
        return "no_failure"
    if mark is None:
        return "no_mark"
    if turn < mark:
        return "before"
    if turn == mark:
        return "on"
    return "after"


def _blank() -> dict[str, dict[str, int]]:
    return {a: dict.fromkeys(BUCKETS, 0) for a in BUCKETS}


def main() -> None:
    inventory, _ = _checker()
    inv = inventory()
    plan = _load(SEAL / "plan.json")
    sealed_version = str(plan["scorer"]["bfcl_eval_version"])
    committed_version = str(inv.get("version"))
    if committed_version != sealed_version:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "STOPPED.json").write_text(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "prereg_commit": PREREG,
                    "status": "STOPPED",
                    "reason": "checker version differs from the seal or is not recoverable",
                    "sealed_bfcl_eval_version": sealed_version,
                    "committed_bfcl_eval_version": committed_version,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps({"stopped": "version", "sealed": sealed_version, "got": committed_version})
        )
        return

    pin = str(plan["w3_entry_pin"])
    digest = hashlib.sha256(ENTRIES.read_bytes()).hexdigest()
    if digest != pin:
        raise SystemExit(f"REFUSED -- entries sha256 {digest} != seal pin {pin}")
    by_id = {str(row["id"]): row for row in json.loads(ENTRIES.read_text(encoding="utf-8-sig"))}
    qualities = {
        p: {
            str(row["entry_id"]): row
            for row in _load(SEAL / "policies" / p / "entry_quality.json")["entries"]
        }
        for p in POLICIES
    }
    ledgers = {
        p: {
            str(row["entry_id"]): row
            for row in _load(SEAL / "policies" / p / "turn_ledger.json")["entries"]
        }
        for p in POLICIES
    }
    ids = sorted(qualities["slo_escalate"])

    disagreements: list[dict[str, Any]] = []
    per_entry: list[dict[str, Any]] = []
    for policy in POLICIES:
        for i, eid in enumerate(ids):
            q = qualities[policy][eid]
            led = ledgers[policy][eid]
            entry = by_id[eid]
            decoded = q["hybrid_model_result_decoded"]
            turns = led["turns"]
            full = _score(entry, decoded, name=f"failturn_{policy}_{eid}_full")
            sealed_valid = q.get("hybrid_pass") is True
            sealed_err = q.get("hybrid_score_error_type")
            sealed_err_s = str(sealed_err) if sealed_err is not None else None
            if full["valid"] != sealed_valid or (
                not sealed_valid and full["error_type"] != sealed_err_s
            ):
                disagreements.append(
                    {
                        "policy": policy,
                        "entry_id": eid,
                        "sealed_valid": sealed_valid,
                        "sealed_error_type": sealed_err_s,
                        "rescore_valid": full["valid"],
                        "rescore_error_type": full["error_type"],
                    }
                )
            first_turn: int | None = None
            first_bucket = "PASS"
            first_error = None
            if not full["valid"]:
                gold = entry["reference"]
                for t in range(len(gold)):
                    prefix = _score(
                        entry,
                        decoded[: t + 1],
                        name=f"failturn_{policy}_{eid}_t{t}",
                        ground=gold[: t + 1],
                    )
                    if not prefix["valid"]:
                        first_turn = t
                        first_bucket = prefix["bucket"]
                        first_error = prefix["error_type"]
                        break
                if first_turn is None:
                    first_bucket = full["bucket"]
                    first_error = full["error_type"]
            esc_turns = [int(t["turn"]) for t in turns if t.get("escalated") is True]
            first_esc = min(esc_turns) if esc_turns else None
            bounces = led.get("bounces") or []
            bounce_turns = [int(b["turn"]) for b in bounces if "turn" in b]
            last_bounce = max(bounce_turns) if bounce_turns else None
            served = None
            if first_turn is not None:
                match = [t for t in turns if int(t["turn"]) == first_turn]
                if match:
                    served = str(match[0].get("placement"))
            per_entry.append(
                {
                    "run_id": RUN_ID,
                    "entry_id": eid,
                    "policy": policy,
                    "outcome_bucket": full["bucket"],
                    "escalated": bool(esc_turns),
                    "n_escalated_turns": len(esc_turns),
                    "first_failing_turn": first_turn,
                    "first_fail_bucket": first_bucket,
                    "first_fail_error_type": first_error,
                    "served_by": served,
                    "first_escalation_turn": first_esc,
                    "last_bounce_turn": last_bounce,
                    "vs_first_escalation": _rel(first_turn, first_esc),
                    "vs_last_bounce": _rel(first_turn, last_bounce),
                }
            )
            if (i + 1) % 50 == 0:
                print(f"{policy} {i + 1}/{len(ids)} disagreements={len(disagreements)}", flush=True)

    if disagreements:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "STOPPED.json").write_text(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "prereg_commit": PREREG,
                    "status": "STOPPED",
                    "reason": (
                        "Committed checker 2025.12.17 reproduced a different "
                        "valid/error_type than the seal on at least one entry. "
                        "Per-turn questions were not scored."
                    ),
                    "n_disagreements": len(disagreements),
                    "disagreements": disagreements,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"stopped": "disagreement", "n": len(disagreements)}))
        return

    by_pol: dict[str, dict[str, dict[str, Any]]] = {p: {} for p in POLICIES}
    for row in per_entry:
        by_pol[row["policy"]][row["entry_id"]] = row

    def q1_rows() -> list[dict[str, Any]]:
        return [
            r
            for r in by_pol["full_signal_bounceback"].values()
            if r["escalated"] and r["outcome_bucket"] == "MISMATCH"
        ]

    def q2_rows() -> list[dict[str, Any]]:
        return [
            r
            for r in by_pol["emission_escalate"].values()
            if r["escalated"] and r["outcome_bucket"] == "MISMATCH"
        ]

    q1 = q1_rows()
    q1_hit_n = sum(1 for r in q1 if r["served_by"] == "local" and r["vs_last_bounce"] == "after")
    q1_rate = q1_hit_n / len(q1) if q1 else None
    q2 = q2_rows()
    q2_hit_n = sum(1 for r in q2 if r["served_by"] == "cloud")
    q2_rate = q2_hit_n / len(q2) if q2 else None

    both = [
        eid
        for eid in ids
        if by_pol["emission_escalate"][eid]["escalated"]
        and by_pol["full_signal_bounceback"][eid]["escalated"]
    ]
    both_matrix = {a: dict.fromkeys(("PASS", "non-PASS"), 0) for a in ("PASS", "non-PASS")}
    for eid in both:
        em = "PASS" if by_pol["emission_escalate"][eid]["outcome_bucket"] == "PASS" else "non-PASS"
        bb = (
            "PASS"
            if by_pol["full_signal_bounceback"][eid]["outcome_bucket"] == "PASS"
            else "non-PASS"
        )
        both_matrix[em][bb] += 1
    em_only = both_matrix["PASS"]["non-PASS"]
    bb_only = both_matrix["non-PASS"]["PASS"]
    q3_hit = em_only >= 3 * bb_only and em_only > 0

    unmapped = sorted(
        {r["outcome_bucket"] for r in per_entry if r["outcome_bucket"] not in BUCKETS}
    )
    transitions: dict[str, Any] = {}
    for src, dst in PAIRS:
        cells = {
            a: {b: {"n": 0, "escalated": 0, "not_escalated": 0} for b in BUCKETS} for a in BUCKETS
        }
        for eid in ids:
            a = by_pol[src][eid]["outcome_bucket"]
            b = by_pol[dst][eid]["outcome_bucket"]
            if a not in BUCKETS or b not in BUCKETS:
                continue
            cell = cells[a][b]
            cell["n"] += 1
            if by_pol[dst][eid]["escalated"]:
                cell["escalated"] += 1
            else:
                cell["not_escalated"] += 1
        transitions[f"{src}->{dst}"] = cells

    empty_rows = [r for r in per_entry if r["first_fail_bucket"] == "EMPTY"]
    emission_by_n: dict[str, dict[str, int]] = {}
    for r in by_pol["emission_escalate"].values():
        key = str(r["n_escalated_turns"])
        emission_by_n.setdefault(key, dict.fromkeys(BUCKETS, 0))
        bucket = r["outcome_bucket"]
        if bucket in emission_by_n[key]:
            emission_by_n[key][bucket] += 1

    q1_pred_hit = q1_rate is not None and q1_rate >= 0.70
    q2_pred_hit = q2_rate is not None and q2_rate >= 0.70
    kill = q1_rate is None or q1_rate < 0.50

    results = {
        "run_id": RUN_ID,
        "prereg_commit": PREREG,
        "checker": {
            "sealed_bfcl_eval_version": sealed_version,
            "committed_bfcl_eval_version": committed_version,
            "match": True,
            "per_turn_verdicts_sealed": False,
            "rescore": "tools.bfcl_feasibility_probe.score_multi_turn prefixes",
            "n_disagreements_vs_seal": 0,
            "unmapped_buckets": unmapped,
        },
        "per_entry": per_entry,
        "q1": {
            "n_bounceback_escalated_mismatch": len(q1),
            "n_local_and_after_last_bounce": q1_hit_n,
            "rate": q1_rate,
            "n_local": sum(1 for r in q1 if r["served_by"] == "local"),
            "n_after_last_bounce": sum(1 for r in q1 if r["vs_last_bounce"] == "after"),
        },
        "q2": {
            "n_emission_escalated_mismatch": len(q2),
            "n_cloud_served": q2_hit_n,
            "rate": q2_rate,
        },
        "q3": {
            "n_escalated_both": len(both),
            "matrix_emission_by_bounceback": both_matrix,
            "emission_pass_bounceback_nonpass": em_only,
            "emission_nonpass_bounceback_pass": bb_only,
        },
        "bucket_transitions": transitions,
        "empty_turn_failures": empty_rows,
        "emission_outcome_by_escalated_turns": {
            k: emission_by_n[k] for k in sorted(emission_by_n, key=int)
        },
        "kill_h_gran": kill,
        "verdicts": [
            {
                "prediction": "Q1",
                "predicted": ">= 70% local and after last bounce",
                "measured_text": f"{q1_hit_n}/{len(q1)} = {q1_rate}",
                "verdict": "HIT" if q1_pred_hit else "MISS",
            },
            {
                "prediction": "Q2",
                "predicted": ">= 70% cloud-served first failure",
                "measured_text": f"{q2_hit_n}/{len(q2)} = {q2_rate}",
                "verdict": "HIT" if q2_pred_hit else "MISS",
            },
            {
                "prediction": "Q3",
                "predicted": "(emission PASS, bounceback non-PASS) >= 3 x reverse",
                "measured_text": f"{em_only} : {bb_only}",
                "verdict": "HIT" if q3_hit else "MISS",
            },
            {
                "prediction": "Q4",
                "predicted": "exploratory, no prediction",
                "measured_text": f"{len(empty_rows)} empty-turn first failures",
                "verdict": "EXPLORATORY",
            },
            {
                "prediction": "KILL",
                "predicted": "KILL H-GRAN if Q1 < 50%",
                "measured_text": f"Q1 rate {q1_rate}",
                "verdict": "FIRED" if kill else "NOT_FIRED",
            },
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "FAILTURN_RESULTS.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "FAILTURN_RESULTS.md").write_text(_markdown(results), encoding="utf-8")
    print(
        json.dumps(
            {
                "q1": results["q1"],
                "q2": results["q2"],
                "q3": results["q3"],
                "empty": len(empty_rows),
                "kill": kill,
                "verdicts": [(v["prediction"], v["verdict"]) for v in results["verdicts"]],
            },
            indent=2,
        )
    )


def _cell_line(cells: dict[str, dict[str, dict[str, int]]], row: str) -> str:
    bits = []
    for col in BUCKETS:
        c = cells[row][col]
        bits.append(f"{c['escalated']}/{c['not_escalated']}")
    return f"| {row} | " + " | ".join(bits) + " |"


def _markdown(results: dict[str, Any]) -> str:
    lines = [
        f"# Fail-turn analysis ({RUN_ID})",
        "",
        f"Pre-registration `{results['prereg_commit']}`. Checker {results['checker']['committed_bfcl_eval_version']} matches the seal. Per-turn verdicts were not sealed; prefixes were rescored offline.",
        "",
        f"Disagreements versus sealed entry scores: {results['checker']['n_disagreements_vs_seal']}.",
        "",
        "## Q1 / Q2",
        "",
        "| question | n | meeting | rate |",
        "|---|---:|---:|---:|",
        (
            f"| Q1 bounceback escalated MISMATCH, first fail local and after last bounce | "
            f"{results['q1']['n_bounceback_escalated_mismatch']} | "
            f"{results['q1']['n_local_and_after_last_bounce']} | {results['q1']['rate']} |"
        ),
        (
            f"| Q2 emission escalated MISMATCH, first fail cloud-served | "
            f"{results['q2']['n_emission_escalated_mismatch']} | "
            f"{results['q2']['n_cloud_served']} | {results['q2']['rate']} |"
        ),
        "",
        "## Q3 entries escalated under both policies",
        "",
        f"n={results['q3']['n_escalated_both']}.",
        "",
        "| emission \\ bounceback | PASS | non-PASS |",
        "|---|---:|---:|",
    ]
    matrix = results["q3"]["matrix_emission_by_bounceback"]
    for row in ("PASS", "non-PASS"):
        lines.append(f"| {row} | {matrix[row]['PASS']} | {matrix[row]['non-PASS']} |")
    lines += ["", "## 2d. Bucket transitions (cell = escalated/not under the second policy)", ""]
    header = "| row \\ col | " + " | ".join(BUCKETS) + " |"
    sep = "|---|" + "|".join(["---:"] * len(BUCKETS)) + "|"
    for key, cells in results["bucket_transitions"].items():
        lines += [f"### {key}", "", header, sep]
        for row in BUCKETS:
            lines.append(_cell_line(cells, row))
        lines.append("")
    lines += ["## 2e. Empty-turn first failures", ""]
    lines.append(
        "| policy | entry_id | escalated | empty turn | first escalation | served_by | vs first escalation |"
    )
    lines.append("|---|---|---|---:|---:|---|---|")
    for row in results["empty_turn_failures"]:
        lines.append(
            f"| {row['policy']} | {row['entry_id']} | {row['escalated']} | "
            f"{row['first_failing_turn']} | {row['first_escalation_turn']} | "
            f"{row['served_by']} | {row['vs_first_escalation']} |"
        )
    lines += ["", "## 2f. Emission outcome by escalated-turn count", ""]
    lines.append("| n_escalated_turns | " + " | ".join(BUCKETS) + " |")
    lines.append("|---:|" + "|".join(["---:"] * len(BUCKETS)) + "|")
    for key, counts in results["emission_outcome_by_escalated_turns"].items():
        if key == "0":
            continue
        lines.append(f"| {key} | " + " | ".join(str(counts[b]) for b in BUCKETS) + " |")
    zero = results["emission_outcome_by_escalated_turns"].get("0")
    if zero:
        lines.append("")
        lines.append("Not escalated (0): " + ", ".join(f"{b} {zero[b]}" for b in BUCKETS) + ".")
    lines += [
        "",
        "## Verdicts",
        "",
        "| prediction | predicted | measured | verdict |",
        "|---|---|---|---|",
    ]
    for row in results["verdicts"]:
        lines.append(
            f"| {row['prediction']} | {row['predicted']} | {row['measured_text']} | {row['verdict']} |"
        )
    lines.append("")
    lines.append(f"KILL H-GRAN: {results['kill_h_gran']}.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
