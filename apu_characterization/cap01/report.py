"""Markdown reporting and append-only claim-death ledger for CAP-01."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import PROTOCOL_VERSION


def render_report(
    aggregate: Mapping[str, Any],
    *,
    died_ledger: Mapping[str, Any] | None = None,
    aggregate_name: str = "cap01.analysis.json",
) -> str:
    """Render a complete, scoped CAP-01 report from an analysis aggregate."""
    claim = aggregate.get("claim_rung") or {}
    positive = aggregate.get("positive_control") or {}
    primary = aggregate.get("primary_result")
    lines = [
        "# CAP-01 capability scaling report",
        "",
        f"- Protocol: `{aggregate.get('protocol_version')}`",
        f"- Immutable source artifacts: **{aggregate.get('source_artifact_count', 0)}**",
        f"- Normalized task cells: **{aggregate.get('task_cell_count', 0)}**",
        f"- Source aggregate: `{aggregate_name}`",
        "",
        "## Promotion summary",
        "",
        str(aggregate.get("promotion_summary", "No promotion summary available.")),
        "",
        f"- Selected claim rung: **{claim.get('name', 'unearned')}**",
        f"- Frozen protocol language: {claim.get('protocol_language', 'not available')}",
        f"- Headline blocked: **{'YES' if aggregate.get('headline_blocked') else 'NO'}**",
        "",
        "The primary scope is exactly 5ms model latency, each domain at its "
        "frozen primary resource tier, SCALING tasks pooled across all five "
        "domains, LangGraph versus rust, with alpha 0.05. No broader scope is "
        "implied.",
        "",
        "## Domain primary resource tiers",
        "",
    ]
    lines.extend(_domain_tier_table(aggregate.get("domain_budget_tiers") or {}))
    lines.extend(["", "## Primary result", ""])
    lines.extend(_primary_lines(primary))
    lines.extend(["", "## Positive control at 4000ms", ""])
    lines.extend(_positive_control_lines(positive))
    lines.extend(["", "## Holm-corrected pre-registered secondaries", ""])
    lines.extend(_secondary_table(aggregate.get("secondary_results") or []))
    lines.extend(["", "## Descriptive statistical cells", ""])
    lines.extend(_statistics_table(aggregate.get("statistics") or []))
    lines.extend(["", "## Seed sensitivity", ""])
    lines.extend(_seed_sensitivity_lines(primary))
    lines.extend(["", "## Descriptive capability versus host-measured floor fit", ""])
    lines.extend(_fit_lines(aggregate.get("capability_floor_fit") or {}))
    lines.extend(["", "## Gate matrix", ""])
    lines.extend(_gate_matrix(aggregate.get("gate_matrix") or {}))
    lines.extend(["", "## Classification counts", ""])
    lines.extend(_classification_table(aggregate.get("classification_counts") or {}))
    lines.extend(["", "## Abandonment tails", ""])
    lines.extend(_abandonment_table(aggregate.get("abandonment_tails") or []))
    lines.extend(["", "## Expectation: actual versus predicted", ""])
    lines.extend(
        _expectation_table(aggregate.get("expectation_actual_vs_predicted") or [])
    )
    lines.extend(
        [
            "",
            "Predicted candidate throughput uses the measured terms "
            "`latency_draw_wall + host_measured_harness_floor + "
            "measured_verifier_wall`. It is a consistency expectation, not a "
            "capability result.",
            "",
            "## Figure scope and projection honesty",
            "",
            "The solve-rate figure contains three measured harness curves versus "
            "model latency. The capability-versus-floor panel is separate and "
            "contains only the three host-measured harness points.",
            "",
            "Tier D design target - projection from measured relationship, not a "
            "result. Promotion path: csynth.",
            "",
            "The dashed Tier D extension is extrapolation beyond the measured raw "
            "Python point. With only three measured x points, projection uncertainty "
            "is not inferentially estimable. It is not a measured arm and supports "
            "no performance claim.",
            "",
            "## Died ledger",
            "",
        ]
    )
    lines.extend(_ledger_lines(died_ledger or {"entries": []}))
    return "\n".join(lines).rstrip() + "\n"


def write_report(
    path: Path,
    aggregate: Mapping[str, Any],
    *,
    died_ledger_path: Path | None = None,
    aggregate_name: str = "cap01.analysis.json",
) -> None:
    ledger = (
        json.loads(died_ledger_path.read_text(encoding="utf-8"))
        if died_ledger_path and died_ledger_path.is_file()
        else {"entries": []}
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_report(
            aggregate, died_ledger=ledger, aggregate_name=aggregate_name
        ),
        encoding="utf-8",
    )


def append_died_claim(
    ledger_path: Path,
    *,
    claim: str,
    reason: str,
    evidence: Sequence[str] = (),
) -> dict[str, Any]:
    """Append one ledger entry while preserving all existing entries."""
    ledger = (
        json.loads(ledger_path.read_text(encoding="utf-8"))
        if ledger_path.is_file()
        else {
            "protocol_version": PROTOCOL_VERSION,
            "entries": [],
            "policy": (
                "Append-only. Retire unsupported CAP-01 claims with evidence; "
                "never delete prior entries."
            ),
        }
    )
    entries = ledger.setdefault("entries", [])
    entry = {
        "id": len(entries) + 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "claim": claim,
        "reason": reason,
        "evidence": list(evidence),
    }
    entries.append(entry)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return entry


def _primary_lines(primary: Mapping[str, Any] | None) -> list[str]:
    if not primary:
        return [
            "**NOT EVALUATED.** The exact frozen primary cell is absent. No primary "
            "headline is allowed."
        ]
    ci = primary["bca_ci"]
    test = primary["mcnemar"]
    sensitivity = primary["seed_sensitivity"]
    return [
        f"- Paired task-seed observations: **{primary['n_task_seed_pairs']}**",
        f"- LangGraph solve rate: **{100 * primary['first_solve_rate']:.2f}%**",
        f"- rust solve rate: **{100 * primary['second_solve_rate']:.2f}%**",
        f"- Paired difference, LangGraph minus rust: "
        f"**{primary['difference_pp']:+.2f} pp**",
        f"- Task-clustered BCa 95% CI: "
        f"**[{ci['low_pp']:+.2f}, {ci['high_pp']:+.2f}] pp** "
        f"({ci['resamples']} deterministic resamples)",
        f"- Exact two-sided McNemar p: **{test['p_value']:.6g}** "
        f"(discordant {test['discordant']})",
        f"- Leave-one-seed-out preserves sign: "
        f"**{'YES' if sensitivity['leave_one_seed_out_preserves_sign'] else 'NO'}**",
    ]


def _positive_control_lines(positive: Mapping[str, Any]) -> list[str]:
    lines = [
        f"- Expected: `{positive.get('expected')}`",
        f"- Tests evaluated: **{positive.get('tests_evaluated', 0)} / "
        f"{positive.get('tests_expected', 0)}**",
        f"- Null holds: **{'YES' if positive.get('holds') else 'NO'}**",
    ]
    failures = positive.get("failures") or []
    for failure in failures:
        lines.append(
            f"- FAILURE: domain {failure.get('domain')}, "
            f"{' vs '.join(failure.get('contrast') or [])}, "
            f"raw p={float(failure.get('raw_p_value', 1)):.6g}, "
            f"Holm p={float(failure.get('holm_adjusted_p_value', 1)):.6g}"
        )
    if not positive.get("holds"):
        lines.append(
            "**STOP BEFORE HEADLINE FOR DIAGNOSIS.** The positive-control null "
            "failed or was incomplete."
        )
    return lines


def _statistics_table(cells: Sequence[Mapping[str, Any]]) -> list[str]:
    if not cells:
        return ["No paired statistical cells available."]
    lines = [
        "| Population | Budget ms | Latency ms | Contrast | n pairs | "
        "Difference pp | BCa 95% CI pp | McNemar p |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for cell in sorted(
        cells,
        key=lambda item: (
            str(item["population"]),
            int(item["wall_budget_ms"]),
            -int(item["latency_scale_ms"]),
            str(item["contrast"]),
        ),
    ):
        ci = cell["bca_ci"]
        lines.append(
            f"| {cell['population']} | {cell['wall_budget_ms']} | "
            f"{cell['latency_scale_ms']} | {' vs '.join(cell['contrast'])} | "
            f"{cell['n_task_seed_pairs']} | {cell['difference_pp']:+.2f} | "
            f"[{ci['low_pp']:+.2f}, {ci['high_pp']:+.2f}] | "
            f"{cell['mcnemar']['p_value']:.6g} |"
        )
    return lines


def _secondary_table(cells: Sequence[Mapping[str, Any]]) -> list[str]:
    if not cells:
        return ["No complete pre-registered secondary tests available."]
    lines = [
        "| Test | Domain | Contrast | Difference pp | Raw p | Holm p | Reject |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for cell in cells:
        holm = cell["holm"]
        lines.append(
            f"| {cell['test_id']} | {cell.get('domain', 'POOLED')} | "
            f"{' vs '.join(cell['contrast'])} | {cell['difference_pp']:+.2f} | "
            f"{holm['raw_p_value']:.6g} | {holm['adjusted_p_value']:.6g} | "
            f"{'YES' if holm['reject'] else 'NO'} |"
        )
    return lines


def _domain_tier_table(tiers: Mapping[str, Mapping[str, Any]]) -> list[str]:
    if not tiers:
        return ["Domain budget tiers unavailable."]
    lines = ["| Domain | Primary tier ms | Rationale |", "|---|---:|---|"]
    for domain, details in tiers.items():
        lines.append(
            f"| {domain} | {details.get('primary_tier_ms')} | "
            f"{details.get('rationale')} |"
        )
    return lines


def _seed_sensitivity_lines(primary: Mapping[str, Any] | None) -> list[str]:
    if not primary:
        return ["Primary seed sensitivity is unavailable."]
    sensitivity = primary["seed_sensitivity"]
    lines = [
        "| Omitted seed | Difference pp |",
        "|---:|---:|",
    ]
    for seed, value in sensitivity["leave_one_seed_out_difference_pp"].items():
        rendered = "not estimable" if value is None else f"{value:+.2f}"
        lines.append(f"| {seed} | {rendered} |")
    lines.append(
        f"Sign preserved across every leave-one-seed-out analysis: "
        f"**{'YES' if sensitivity['leave_one_seed_out_preserves_sign'] else 'NO'}**."
    )
    return lines


def _fit_lines(fit_summary: Mapping[str, Any]) -> list[str]:
    lines = [
        f"**{fit_summary.get('label', 'DESCRIPTIVE ONLY, NON-INFERENTIAL')}**",
        "",
    ]
    points = fit_summary.get("points") or []
    if not points:
        return lines + ["No complete host-measured floor points."]
    lines.extend(
        [
            "| Harness | Host-measured floor ms | Solve rate % | Residual pp |",
            "|---|---:|---:|---:|",
        ]
    )
    residuals = {
        item["harness"]: item["residual_pp"]
        for item in fit_summary.get("residuals") or []
    }
    for point in points:
        residual = residuals.get(point["harness"])
        lines.append(
            f"| {point['harness']} | {point['floor_ms']:.6g} | "
            f"{point['solve_rate_pct']:.2f} | "
            f"{'not fit' if residual is None else f'{residual:+.3f}'} |"
        )
    fitted = fit_summary.get("fit")
    if fitted:
        lines.append(
            f"Descriptive line: solve rate = {fitted['intercept_pp']:.3f} "
            f"{fitted['slope_pp_per_ms']:+.3f} x floor_ms. "
            "This three-point fit has no inferential interpretation."
        )
    else:
        lines.append(str(fit_summary.get("reason", "Fit not available.")))
    return lines


def _gate_matrix(gates: Mapping[str, Mapping[str, Any]]) -> list[str]:
    lines = ["| Gate | Evaluated | Result | Violations |", "|---|---|---|---:|"]
    for gate_name in (f"G{index}" for index in range(1, 9)):
        gate = gates.get(gate_name) or {}
        lines.append(
            f"| {gate_name} | {'YES' if gate.get('evaluated') else 'NO'} | "
            f"{'PASS' if gate.get('pass') else 'FAIL'} | "
            f"{len(gate.get('errors') or [])} |"
        )
    return lines


def _classification_table(counts: Mapping[str, Any]) -> list[str]:
    lines = [
        "| Domain | SCALING | SATURATED | DEAD | ALL |",
        "|---|---:|---:|---:|---:|",
    ]
    for domain, domain_counts in (counts.get("by_domain") or {}).items():
        lines.append(
            f"| {domain} | {int(domain_counts.get('SCALING', 0))} | "
            f"{int(domain_counts.get('SATURATED', 0))} | "
            f"{int(domain_counts.get('DEAD', 0))} | "
            f"{int(domain_counts.get('ALL', 0))} |"
        )
    lines.extend(["", "| Overall classification | Tasks |", "|---|---:|"])
    for name in ("SCALING", "SATURATED", "DEAD", "ALL"):
        lines.append(f"| {name} | {int(counts.get(name, 0))} |")
    return lines


def _abandonment_table(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    if not rows:
        return ["No abandonment summaries available."]
    lines = [
        "| Harness | Latency ms | Budget ms | Abandoned | Started | "
        "Fraction | Tail p95 ms | Tail max ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['harness']} | {row['latency_scale_ms']} | "
            f"{row['wall_budget_ms']} | {row['abandoned_candidates']} | "
            f"{row['started_candidates']} | {row['abandoned_fraction']:.4f} | "
            f"{_number(row.get('tail_p95_ms'))} | "
            f"{_number(row.get('tail_max_ms'))} |"
        )
    return lines


def _expectation_table(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    if not rows:
        return ["No expectation summaries available."]
    lines = [
        "| Harness | Latency ms | Budget ms | Actual candidates | "
        "Predicted candidates | Actual / predicted |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['harness']} | {row['latency_scale_ms']} | "
            f"{row['wall_budget_ms']} | "
            f"{_number(row.get('actual_candidates_mean'))} | "
            f"{_number(row.get('predicted_candidates_mean'))} | "
            f"{_number(row.get('actual_over_predicted'))} |"
        )
    return lines


def _ledger_lines(ledger: Mapping[str, Any]) -> list[str]:
    entries = ledger.get("entries") or []
    if not entries:
        return ["No retired CAP-01 claims recorded."]
    lines = ["| ID | Claim | Reason | Evidence |", "|---:|---|---|---|"]
    for entry in entries:
        evidence = ", ".join(str(item) for item in entry.get("evidence") or []) or "none"
        lines.append(
            f"| {entry.get('id')} | {entry.get('claim')} | "
            f"{entry.get('reason')} | {evidence} |"
        )
    return lines


def _number(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.4g}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("aggregate", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--died-ledger",
        type=Path,
        default=Path("apu_characterization/cap01/died_ledger.json"),
    )
    args = parser.parse_args()
    aggregate = json.loads(args.aggregate.read_text(encoding="utf-8"))
    write_report(
        args.output,
        aggregate,
        died_ledger_path=args.died_ledger,
        aggregate_name=args.aggregate.name,
    )
    print(args.output)


if __name__ == "__main__":
    main()
