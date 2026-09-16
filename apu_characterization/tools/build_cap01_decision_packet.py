"""Merge v1 MATH triage with v2 post-fix domains → five-domain decision packet."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/cap01"
V1 = OUT / "pools_triage/triage_report.json"
V2 = OUT / "pools_triage/triage_report_v2_post_verifier_fix.json"
AUDIT = OUT / "verifier_ground_truth_audit.json"
EXT_MISS = OUT / "ext_near_miss_audit.json"
PACKET = OUT / "DECISION_PACKET_v1.md"

INPUT_USD_PER_MTOK = 0.15
OUTPUT_USD_PER_MTOK = 0.60


def main() -> None:
    v1 = json.loads(V1.read_text(encoding="utf-8"))
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))["summary"]
    ext = json.loads(EXT_MISS.read_text(encoding="utf-8")) if EXT_MISS.is_file() else {}

    math_rows = [r for r in v1["rows"] if r["domain"] == "MATH"]
    other_rows = list(v2["rows"])
    rows = math_rows + other_rows

    by_domain: dict[str, list] = {}
    for row in rows:
        by_domain.setdefault(row["domain"], []).append(row)

    domain_stats: dict[str, dict] = {}
    for domain, domain_rows in sorted(by_domain.items()):
        measurable = [r for r in domain_rows if r.get("phat") is not None]
        prompt = sum(r["prompt_tokens"] for r in domain_rows)
        completion = sum(r["completion_tokens"] for r in domain_rows)
        n_cands = sum(r["n"] for r in domain_rows)
        domain_stats[domain] = {
            "tasks": len(domain_rows),
            "candidates": n_cands,
            "per_candidate_prompt_tokens": prompt / max(1, n_cands),
            "per_candidate_completion_tokens": completion / max(1, n_cands),
            "band_counts": {
                band: sum(1 for r in domain_rows if r["band"] == band)
                for band in sorted({r["band"] for r in domain_rows})
            },
            "mean_phat": (
                sum(float(r["phat"]) for r in measurable) / len(measurable)
                if measurable
                else None
            ),
            "hit_histogram": _hit_hist(domain_rows),
        }

    projected_prompt = 0.0
    projected_completion = 0.0
    projected_candidates = 0
    for row in rows:
        depth = int(row["generation_depth"])
        stats = domain_stats[row["domain"]]
        projected_candidates += depth
        projected_prompt += depth * float(stats["per_candidate_prompt_tokens"])
        projected_completion += depth * float(stats["per_candidate_completion_tokens"])
    projected_usd = (
        projected_prompt / 1e6 * INPUT_USD_PER_MTOK
        + projected_completion / 1e6 * OUTPUT_USD_PER_MTOK
    )
    uniform_prompt = 0.0
    uniform_completion = 0.0
    for row in rows:
        stats = domain_stats[row["domain"]]
        uniform_prompt += 2048 * float(stats["per_candidate_prompt_tokens"])
        uniform_completion += 2048 * float(stats["per_candidate_completion_tokens"])
    uniform_usd = (
        uniform_prompt / 1e6 * INPUT_USD_PER_MTOK
        + uniform_completion / 1e6 * OUTPUT_USD_PER_MTOK
    )

    lines: list[str] = []
    lines.append("# CAP-01 Decision Packet v1")
    lines.append("")
    lines.append("Status: assembled for Zach. Agent decides nothing on tripwire or spend.")
    lines.append("")
    lines.append("## 1. Five-domain band table (post-fix) + verifier-audit status")
    lines.append("")
    lines.append(
        "| Domain | SCALING_band | probable_SATURATED | probable_DEAD | other | "
        "mean p̂ | Gold pass | Garbage fail | Audit |"
    )
    lines.append("|---|---:|---:|---:|---|---:|---:|---:|---|")
    for domain, stats in domain_stats.items():
        bc = stats["band_counts"]
        a = audit.get(domain, {})
        other = {
            k: v
            for k, v in bc.items()
            if k not in {"SCALING_band", "probable_SATURATED", "probable_DEAD"}
        }
        other_s = ", ".join(f"{k}={v}" for k, v in other.items()) or "—"
        mean = stats["mean_phat"]
        mean_s = f"{mean:.3f}" if mean is not None else "—"
        healthy = a.get("healthy")
        audit_s = "PASS" if healthy else "allowlisted defects"
        lines.append(
            f"| {domain} | {bc.get('SCALING_band', 0)} | "
            f"{bc.get('probable_SATURATED', 0)} | {bc.get('probable_DEAD', 0)} | "
            f"{other_s} | {mean_s} | {a.get('gold_pass', '?')}/50 | "
            f"{a.get('garbage_fail', '?')}/50 | {audit_s} |"
        )
    lines.append("")
    lines.append("Verifier-audit notes:")
    lines.append("- FUNCTION_CALLING / CODE: 50/50 gold + 50/50 garbage (healthy).")
    lines.append("- MATH: 49/50 — MATH-019 truncated gold extract (corpus defect).")
    lines.append("- TEXT_TO_SQL: 49/50 — SQL-041 gold timeout (exclusion candidate).")
    lines.append(
        "- STRUCTURED_EXTRACTION: 45/50 — EXT-017/027/030/032/034 schema-inference "
        "defects (exclusion candidates)."
    )
    lines.append("- MATH was **not** re-triaged; bands carried from v1 report.")
    lines.append(
        "- FC/SQL/EXT/CODE bands from `triage_report_v2_post_verifier_fix.json` "
        "(verify-only re-score of existing n=16 staging)."
    )
    lines.append("")
    lines.append("### Per-domain hit texture (n_correct out of 16)")
    lines.append("")
    for domain, stats in domain_stats.items():
        lines.append(f"- **{domain}**: `{stats['hit_histogram']}`")
    lines.append("")
    lines.append("## 2. Recomputed refined projection")
    lines.append("")
    lines.append(f"- Depth-triage projected candidates: **{projected_candidates}**")
    lines.append(f"- Depth-triage projected USD: **${projected_usd:.2f}**")
    lines.append(f"- Uniform-2048 projected USD (contrast): **${uniform_usd:.2f}**")
    lines.append(
        "- Prior conditional $12.84 assumed broken-verifier cheap DEAD bands on "
        "FC/SQL/EXT; this number replaces it under frozen depth rule + post-fix bands."
    )
    lines.append("")
    lines.append("## 3. MATH tripwire options (Zach decides)")
    lines.append("")
    math_bc = domain_stats["MATH"]["band_counts"]
    scaling = math_bc.get("SCALING_band", 0)
    lines.append(
        f"Current MATH SCALING_band count under ≥20 tripwire framing: **{scaling}** "
        "(provisional triage bands, not calibration verdicts)."
    )
    lines.append("")
    lines.append(
        "**(a) Ledgered tripwire amendment to ≥15** — accepts current MATH draw; "
        "documents that the tripwire moved after seeing the count. Process wound; "
        "transparent."
    )
    lines.append(
        "**(b) Blind corpus expansion** — add the next ~30 MATH tasks by original "
        "task_id order from remaining competition-math rows; triage them; accept "
        "whatever bands result. Blind-by-construction; cannot be accused of shopping "
        "for SCALING. Costs triage tokens + lock/amendment work."
    )
    lines.append(
        "**(c) Proceed at 15 with disclosure** — keep tripwire ≥20 unmet; disclose "
        "MATH D4 below tripwire for this corpus draw; do not amend."
    )
    lines.append("")
    lines.append(
        "**Agent recommendation (not a decision):** **(b)** if budget/time allow a "
        "small MATH triage top-up; else **(c)** over **(a)**. Reasoning: (a) moves "
        "the goalpost after seeing the number; (c) is honest about under-tripwire; "
        "(b) preserves pre-registration spirit by expanding blind rather than "
        "lowering the bar."
    )
    lines.append("")
    lines.append("## 4. Per-domain disposition")
    lines.append("")
    lines.append(
        "| Domain | What was broken | What was fixed | Ledgered | Deferred |"
    )
    lines.append("|---|---|---|---|---|")
    lines.append(
        "| FC | tree_sitter/env + gold materialization for audit; OpenAI→BFCL "
        "format; pin coverage hole | shims + wrapper + pin adapters; golds 50/50 | "
        "#11 | — |"
    )
    lines.append(
        "| SQL | Mostly nothing (fixtures resolve; golds 49/50) | — | SQL-041 "
        "exclusion candidate | SQL-041 |"
    )
    lines.append(
        "| EXT | 5 schema-defective golds; exact-match strictness real | keep "
        "exact-match (rec. a); near-miss: JSON-ish but 0/20 exact | #11 + "
        f"near-miss `{EXT_MISS.name}` | 5 EXT exclusions; Zach may still pick field-F1 |"
    )
    lines.append(
        "| CODE | `-S` blocked numpy; runner never called `check(entry_point)`; "
        "5s wall timed out CODE-046 | drop `-S`, invoke check, wall=30s; golds "
        "50/50; CODE unblocked from forced-2048 | #11 | — |"
    )
    lines.append(
        "| MATH | MATH-019 truncated extract only | not re-touched | allowlist | "
        "tripwire call |"
    )
    lines.append("")
    if ext:
        lines.append("### EXT near-miss evidence (5×4)")
        lines.append("")
        lines.append(
            f"Recommendation in audit file: `{ext.get('recommendation')}` — "
            f"{ext.get('recommendation_rationale', '')[:240]}"
        )
        lines.append("")
    lines.append("## 5. Final line")
    lines.append("")
    lines.append(
        "**DECISION PACKET READY — awaiting tripwire call and spend approval**"
    )
    lines.append("")
    PACKET.write_text("\n".join(lines), encoding="utf-8")
    print(f"projected_usd={projected_usd:.2f} uniform={uniform_usd:.2f}")
    print(json.dumps({k: v["band_counts"] for k, v in domain_stats.items()}, indent=2))
    print("wrote", PACKET)


def _hit_hist(rows: list) -> dict[str, int]:
    hist: dict[str, int] = {}
    for row in rows:
        key = str(row.get("n_correct"))
        hist[key] = hist.get(key, 0) + 1
    return dict(sorted(hist.items(), key=lambda item: int(item[0]) if item[0].isdigit() else 99))


if __name__ == "__main__":
    main()
