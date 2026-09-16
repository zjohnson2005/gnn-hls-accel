"""Merge v1 MATH + v2 FC/CODE + v3 SQL/EXT → Decision Packet v2."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/cap01"
V1 = OUT / "pools_triage/triage_report.json"
V2 = OUT / "pools_triage/triage_report_v2_post_verifier_fix.json"
V3 = OUT / "pools_triage/triage_report_v3_post_prompt_fix.json"
AUDIT = OUT / "verifier_ground_truth_audit.json"
FRONTIER = OUT / "frontier_probe_sql_ext.json"
EXCL = OUT / "excluded_tasks.json"
PACKET = OUT / "DECISION_PACKET_v2.md"

INPUT_USD = 0.15
OUTPUT_USD = 0.60
TRIPWIRE = 20


def _hist(rows: list) -> dict[str, int]:
    hist: dict[str, int] = {}
    for row in rows:
        key = str(row.get("n_correct"))
        hist[key] = hist.get(key, 0) + 1
    return dict(sorted(hist.items(), key=lambda i: int(i[0]) if i[0].isdigit() else 99))


def _stats(rows: list) -> dict:
    measurable = [r for r in rows if r.get("phat") is not None]
    prompt = sum(r["prompt_tokens"] for r in rows)
    completion = sum(r["completion_tokens"] for r in rows)
    n_cands = sum(r["n"] for r in rows)
    return {
        "tasks": len(rows),
        "candidates": n_cands,
        "per_candidate_prompt_tokens": prompt / max(1, n_cands),
        "per_candidate_completion_tokens": completion / max(1, n_cands),
        "band_counts": {
            band: sum(1 for r in rows if r["band"] == band)
            for band in sorted({r["band"] for r in rows})
        },
        "mean_phat": (
            sum(float(r["phat"]) for r in measurable) / len(measurable)
            if measurable
            else None
        ),
        "hit_histogram": _hist(rows),
        "scaling": sum(1 for r in rows if r["band"] == "SCALING_band"),
    }


def main() -> None:
    v1 = json.loads(V1.read_text(encoding="utf-8"))
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    v3 = json.loads(V3.read_text(encoding="utf-8"))
    excl = json.loads(EXCL.read_text(encoding="utf-8"))
    frontier = json.loads(FRONTIER.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8")).get("summary", {})

    rows_by_domain: dict[str, list] = {}
    for row in v1["rows"]:
        if row["domain"] == "MATH":
            rows_by_domain.setdefault("MATH", []).append(row)
    for row in v2["rows"]:
        if row["domain"] in {"FUNCTION_CALLING", "CODE"}:
            rows_by_domain.setdefault(row["domain"], []).append(row)
    for row in v3["rows"]:
        if row["domain"] in {"TEXT_TO_SQL", "STRUCTURED_EXTRACTION"}:
            rows_by_domain.setdefault(row["domain"], []).append(row)

    domain_stats = {d: _stats(rs) for d, rs in sorted(rows_by_domain.items())}
    all_rows = [r for rs in rows_by_domain.values() for r in rs]

    projected_prompt = projected_completion = 0.0
    projected_candidates = 0
    for row in all_rows:
        depth = int(row["generation_depth"])
        stats = domain_stats[row["domain"]]
        projected_candidates += depth
        projected_prompt += depth * float(stats["per_candidate_prompt_tokens"])
        projected_completion += depth * float(
            stats["per_candidate_completion_tokens"]
        )
    projected_usd = (
        projected_prompt / 1e6 * INPUT_USD + projected_completion / 1e6 * OUTPUT_USD
    )
    uniform_prompt = uniform_completion = 0.0
    for row in all_rows:
        stats = domain_stats[row["domain"]]
        uniform_prompt += 2048 * float(stats["per_candidate_prompt_tokens"])
        uniform_completion += 2048 * float(stats["per_candidate_completion_tokens"])
    uniform_usd = (
        uniform_prompt / 1e6 * INPUT_USD + uniform_completion / 1e6 * OUTPUT_USD
    )

    under = {
        d: s["scaling"] for d, s in domain_stats.items() if s["scaling"] < TRIPWIRE
    }

    lines: list[str] = []
    lines.append("# CAP-01 Decision Packet v2")
    lines.append("")
    lines.append(
        "Corpus-wide tripwire framing. Agent decides nothing on expansion/spend."
    )
    lines.append("")
    lines.append("## 1. Five-domain bands (post prompt+verifier repairs)")
    lines.append("")
    lines.append(
        "| Domain | SCALING | SATURATED | DEAD | mean p̂ | "
        "Gold audit | vs tripwire ≥20 |"
    )
    lines.append("|---|---:|---:|---:|---:|---|---|")
    for domain, stats in domain_stats.items():
        bc = stats["band_counts"]
        mean = stats["mean_phat"]
        mean_s = f"{mean:.3f}" if mean is not None else "—"
        a = audit.get(domain, {})
        gold = f"{a.get('gold_pass', '?')}/50"
        flag = "UNDER" if stats["scaling"] < TRIPWIRE else "met"
        lines.append(
            f"| {domain} | {bc.get('SCALING_band', 0)} | "
            f"{bc.get('probable_SATURATED', 0)} | {bc.get('probable_DEAD', 0)} | "
            f"{mean_s} | {gold} | **{flag}** ({stats['scaling']}) |"
        )
    lines.append("")
    lines.append(
        f"**Before this round all five were under ≥20** "
        f"(MATH 15, FC 16, CODE 18, SQL 0, EXT 0). "
        f"Domains still under: `{sorted(under)}`."
    )
    lines.append("")
    lines.append("Sources: MATH from v1; FC/CODE from v2 verify-only; "
                 "SQL/EXT from v3 regenerate after prompt+SQL-match fixes.")
    lines.append("")
    lines.append("### Hit texture")
    for domain, stats in domain_stats.items():
        lines.append(f"- **{domain}**: `{stats['hit_histogram']}`")
    lines.append("")

    lines.append("## 2. What changed this round")
    lines.append("")
    lines.append(
        "- **Prompt completeness:** SQL lacked schema DDL; EXT lacked target "
        "JSON schema in `task.prompt` (corpus wiring gaps). Both repaired "
        "(same task_ids; ledger #12)."
    )
    lines.append(
        "- **Perturbed gold:** all five domains PASS canonicalization "
        "(EXT key-shuffle OK — not raw-string compare)."
    )
    lines.append(
        "- **SQL column-alias bug:** `_result_equal` required column-name "
        "identity; BIRD-equivalent queries failed. Fixed (ledger #14). "
        "Frontier re-score of same gpt-4o staging: SQL 0/20 → **9/20**."
    )
    lines.append(
        f"- **Frontier probe (gpt-4o, 5×4):** "
        f"SQL mean_phat post-fix≈0.45 (after alias fix); "
        f"EXT mean_phat={frontier['summary']['STRUCTURED_EXTRACTION']['mean_phat']} "
        f"(schema in prompt). Pre-registered reading: when frontier scores "
        "and mini stays near-zero → model-relative DEAD; when both near-zero "
        "after fixes → continue diagnosis (not accept)."
    )
    lines.append(
        "- **EXT exact-match:** prior keep-exact recommendation was against "
        "schema-less prompts; re-opened. With schema in prompt, frontier "
        "solves several tasks under the same pinned exact-match verifier → "
        "**exact-match stands** as the pass criterion; remaining mini DEAD "
        "(if any) is model-relative."
    )
    lines.append("")

    lines.append("## 3. Corpus-wide tripwire options (Zach decides)")
    lines.append("")
    lines.append(
        "One coherent decision across under-tripwire domains — not five "
        "sequential MATH-only calls."
    )
    lines.append("")
    for domain, n_scale in under.items():
        lines.append(f"### {domain} (SCALING_band={n_scale})")
        lines.append(
            f"- **(b) Blind expansion (recommended where source remains):** "
            f"add next ~30 tasks by original selection rule; triage n=16; "
            f"accept bands. Blind-by-construction."
        )
        lines.append(
            "- **(a) Global/domain tripwire amendment (ledgered)** if expansion "
            "impractical."
        )
        lines.append("- **(c) Proceed-with-disclosure** as fallback.")
        lines.append("")
    lines.append(
        "**Agent recommendation (not a decision):** Prefer **(b)** blind "
        "expansion for every under-tripwire domain that still has unused "
        "source rows (MATH, and SQL/EXT/FC/CODE if still under after v3). "
        "Use **(c)** over **(a)** when expansion is skipped — do not move "
        "the goalpost after seeing counts."
    )
    lines.append("")

    lines.append("## 4. Allowlist / exclusions (formalized)")
    lines.append("")
    lines.append(
        "Gold-failing tasks are **excluded from pools** (ledger #13), not "
        "scored as DEAD passengers:"
    )
    for tid, reason in excl["excluded_from_pools"].items():
        lines.append(f"- `{tid}`: {reason}")
    lines.append("")
    lines.append(
        f"Pool-eligible counts: `{excl['pool_eligible_counts_after_exclusion']}`"
    )
    lines.append("")

    lines.append("## 5. Recomputed projection")
    lines.append("")
    lines.append(f"- Depth-triage candidates: **{projected_candidates}**")
    lines.append(f"- Depth-triage USD: **${projected_usd:.2f}**")
    lines.append(f"- Uniform-2048 USD: **${uniform_usd:.2f}**")
    lines.append(
        "- Packet v1's $12.16 assumed SQL/EXT at confirmation depth (all-DEAD). "
        "If SQL/EXT flipped into SCALING_band, this number **rises** — that is "
        "the honest cost of a solvable corpus."
    )
    lines.append("")

    lines.append("## 6. Methodology")
    lines.append("")
    lines.append(
        "Uniform-zero protocol written into `METHODOLOGY_CAP01.md` "
        "(prompt-completeness → perturbed-gold → frontier probe)."
    )
    lines.append("")
    lines.append("## 7. Final line")
    lines.append("")
    lines.append(
        "**DECISION PACKET v2 READY — corpus-wide tripwire call and spend "
        "approval awaiting Zach**"
    )
    lines.append("")
    PACKET.write_text("\n".join(lines), encoding="utf-8")
    print(f"projected_usd={projected_usd:.2f}")
    print(json.dumps({d: s["band_counts"] for d, s in domain_stats.items()}, indent=2))
    print("wrote", PACKET)


if __name__ == "__main__":
    main()
