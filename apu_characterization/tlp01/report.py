"""Markdown report and append-only died-ledger helpers for TLP-01 v2."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from apu_characterization.tlp01.analyze import bracket_line
from apu_characterization.tlp01.audit import format_gate_table
from apu_characterization.tlp01.contracts import (
    DIED_LEDGER_PATH,
    FORBIDDEN_CLAIM_FRAGMENTS,
    load_protocol,
)
from apu_characterization.tlp01.edge_taxonomy import assert_no_bare_m1
from apu_characterization.tlp01.labels import (
    assert_no_rung_labels_in_smoke_report,
    is_real_trace_source,
)
from apu_characterization.tlp01.phase_diagram import render_phase_diagram_markdown
from apu_characterization.validity import (
    TURN_LEVEL_PARALLELISM,
    validity_banner,
)


def append_died_claim(
    path: Path,
    *,
    claim: str,
    reason: str,
    evidence: list[str],
) -> dict[str, Any]:
    ledger = json.loads(path.read_text(encoding="utf-8"))
    entries = list(ledger.get("entries") or [])
    next_id = max((int(entry["id"]) for entry in entries), default=0) + 1
    entry = {
        "id": next_id,
        "timestamp_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "claim": claim,
        "reason": reason,
        "evidence": evidence,
    }
    entries.append(entry)
    ledger["entries"] = entries
    path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return entry


def _ledger_lines(died_ledger: Mapping[str, Any]) -> list[str]:
    lines = ["## Died ledger", ""]
    entries = list(died_ledger.get("entries") or [])
    if not entries:
        lines.append("No retired claims.")
        return lines
    for entry in entries:
        lines.append(
            f"- **#{entry['id']}** ({entry.get('timestamp_utc', '?')}): "
            f"{entry.get('claim')}"
        )
        lines.append(f"  - reason: {entry.get('reason')}")
    return lines


def _assert_no_forbidden_language(text: str) -> None:
    """Ban affirmative use of retired v1 framing in results/claim sections."""
    # Allow the Blocked claims / Related work sections to name the bans.
    claim_region = text.split("## Related work")[0].split("## Blocked claims")[0]
    lowered = claim_region.lower()
    for fragment in FORBIDDEN_CLAIM_FRAGMENTS:
        if fragment in lowered:
            raise ValueError(f"report contains forbidden claim language: {fragment}")


def _related_work_section(protocol: Mapping[str, Any]) -> list[str]:
    lines = [
        "## Related work",
        "",
        "Parallel / speculative agent execution already exists in the literature.",
        "TLP-01's ownable firsts are the limit study, the floor-coupled M2",
        "measurement, and the speculation-economics phase diagram — not a",
        "priority claim of pioneering parallel agent execution.",
        "",
    ]
    for item in protocol.get("related_work_required_citations") or []:
        lines.append(f"- **{item['key']}**: {item['role']}")
    lines.append("")
    return lines


def _bands_table(bands: Mapping[str, Any], title: str) -> list[str]:
    if not bands:
        return []
    lines = [
        f"## {title}",
        "",
        "| Task class | Tier-C floor median | Tier-S ceiling median | Bracket |",
        "|---|---:|---:|---|",
    ]
    for task_class, tiers in bands.items():
        c_med = (tiers.get("Tier_C") or {}).get("median")
        s_med = (tiers.get("Tier_S") or {}).get("median")
        if c_med is None or s_med is None:
            continue
        lines.append(
            f"| {task_class} | {c_med:.2f}x | {s_med:.2f}x | "
            f"{bracket_line(s_med, c_med)} |"
        )
    lines.append("")
    return lines


def render_report(
    aggregate: Mapping[str, Any],
    *,
    audit: Mapping[str, Any] | None = None,
    died_ledger: Mapping[str, Any] | None = None,
) -> str:
    protocol = load_protocol()
    ceiling = aggregate.get("ceiling_claim") or aggregate.get("claim") or {}
    frontier = aggregate.get("frontier_claim") or {}
    data_source = str(aggregate.get("data_source") or ceiling.get("data_source") or "")
    real = is_real_trace_source(data_source)

    def _claim_line(label: str, claim: Mapping[str, Any]) -> list[str]:
        if real:
            return [
                f"- {label}: **{claim.get('name', 'unearned')}** "
                f"(`{claim.get('rung', 'none')}`)",
                f"  - {claim.get('language', '')}",
            ]
        diagnostic = claim.get("smoke_diagnostic") or "smoke_diagnostic: unset"
        return [
            f"- {label}: **{diagnostic}** (not a claim rung; "
            f"data_source=`{data_source or 'synthetic_smoke'}`)",
            f"  - {claim.get('language', '')}",
        ]

    lines = [
        "# TLP-01 report: limits of turn-level parallelism (v2)",
        "",
        validity_banner(TURN_LEVEL_PARALLELISM),
        "",
        f"- Protocol: `{protocol['protocol_version']}` "
        f"(status={protocol.get('status')})",
        f"- Sessions: {aggregate.get('session_count', 0)}",
        f"- data_source: `{data_source or 'unset'}`",
    ]
    lines.extend(_claim_line("Ceiling track", ceiling))
    lines.extend(_claim_line("Frontier track", frontier))
    if not real:
        lines.extend(
            [
                "",
                "> **SMOKE / SYNTHETIC:** outputs use `smoke_diagnostic:*` labels only. "
                "Claim rungs (`rung_*`) are reserved for real T0 traces.",
            ]
        )
    lines.extend(
        [
            "",
            "## Ownable firsts",
            "",
        ]
    )
    for item in protocol.get("ownable_firsts") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Headline form", "",
        "All TLP numbers are S/C brackets. Never quote a point estimate.",
        "M1a = width ceiling (no speculation). M1b = perfect control speculation.",
        "Never quote an unqualified M1.",
        ""])

    lines.extend(
        _bands_table(
            aggregate.get("m1a_speedup_bands") or {},
            "Ceiling: M1a oracle width (no speculation)",
        )
    )
    lines.extend(
        _bands_table(
            aggregate.get("m1b_speedup_bands") or {},
            "Ceiling: M1b oracle + perfect control speculation",
        )
    )
    lines.extend(
        _bands_table(
            aggregate.get("m2_speedup_bands") or {},
            "Ceiling: M2 (+ measured T_orch) speedup bands",
        )
    )

    headroom = aggregate.get("speculation_headroom") or {}
    rows = headroom.get("rows") or []
    if rows:
        lines.extend(
            [
                "## Speculation headroom (M1b / M1a) — reported, unverdicted",
                "",
                "| Task id | Tier | n | median | min | max |",
                "|---|---|---:|---:|---:|---:|",
            ]
        )
        for row in rows:
            lines.append(
                f"| {row['task_id']} | {row['tier']} | {row['n']} | "
                f"{row['median_headroom']:.3f} | {row['min_headroom']:.3f} | "
                f"{row['max_headroom']:.3f} |"
            )
        lines.append("")

    tax = aggregate.get("floor_tax_m2_minus_m1b") or {}
    if tax:
        lines.extend(
            [
                "## Floor tax on parallelism (M2 − M1b speedup gap)",
                "",
                "| Task class | Tier-C gap | Tier-S gap |",
                "|---|---:|---:|",
            ]
        )
        for task_class, tiers in tax.items():
            lines.append(
                f"| {task_class} | {tiers.get('Tier_C', float('nan')):.2f} | "
                f"{tiers.get('Tier_S', float('nan')):.2f} |"
            )
        lines.append("")

    m3 = aggregate.get("m3_speedup_bands") or {}
    if m3:
        lines.extend(
            [
                "## M3 width knee (Tier-C median by width)",
                "",
                "| Width | Task class | Tier-C median |",
                "|---:|---|---:|",
            ]
        )
        for width_key, bands in m3.items():
            label = "inf" if width_key in ("None", None, "null") else str(width_key)
            for task_class, tiers in bands.items():
                med = (tiers.get("Tier_C") or {}).get("median")
                if med is None:
                    continue
                lines.append(f"| {label} | {task_class} | {med:.2f}x |")
        lines.append("")

    phase = aggregate.get("phase_diagram")
    if phase:
        lines.extend(render_phase_diagram_markdown(phase))
        natural = phase.get("natural_predictor_accuracy") or {}
        lines.extend(
            [
                "## Predictor accuracy",
                "",
                f"- Natural top-1 accuracy (held-out): "
                f"**{natural.get('top1_accuracy', float('nan')):.3f}** "
                f"(n={int(natural.get('n_predictions', 0))})",
                "",
            ]
        )

    bystander = aggregate.get("bystander_contention") or {}
    if bystander.get("per_policy"):
        lines.extend(
            [
                "## Bystander contention (secondary, software-side)",
                "",
                "| Policy | Median primary slowdown | N |",
                "|---|---:|---:|",
            ]
        )
        for policy, stats in (bystander.get("per_policy") or {}).items():
            lines.append(
                f"| {policy} | {stats.get('median_primary_slowdown', 0):.3f} | "
                f"{stats.get('n', 0)} |"
            )
        lines.append("")

    m5 = aggregate.get("m5_at_optimal_policy") or {}
    if m5.get("per_penalty"):
        lines.extend(
            [
                "## M5 at optimal policy per penalty regime",
                "",
                "| Penalty | Optimal policy | M5 Tier-C median speedup |",
                "|---|---|---:|",
            ]
        )
        for key, row in (m5.get("per_penalty") or {}).items():
            label = key + (" †Tier D" if row.get("praetor_tier_d") else "")
            lines.append(
                f"| {label} | {row.get('optimal_policy')} | "
                f"{row.get('m5_speedup_median', float('nan')):.2f}x |"
            )
        lines.append("")

    sparse = aggregate.get("sparse_descriptive") or {}
    sparse_ids = sparse.get("task_ids") or (
        (aggregate.get("replication_floor") or {}).get("sparse_task_ids") or []
    )
    if sparse_ids or sparse.get("m1_observations"):
        lines.extend(
            [
                "## Appendix — sparse task_ids (descriptive only, not banded)",
                "",
                "Excluded from all primary M1–M5 bands by the replication-floor "
                "gate (n < G-R required seeds).",
                "",
            ]
        )
        if sparse_ids:
            lines.extend(
                [
                    "| task_id | n | disposition |",
                    "|---|---:|---|",
                ]
            )
            for row in sparse_ids:
                if isinstance(row, Mapping):
                    lines.append(
                        f"| {row.get('task_id')} | {row.get('n')} | "
                        f"{row.get('disposition')} |"
                    )
                else:
                    lines.append(f"| {row} | ? | sparse |")
            lines.append("")
        obs = sparse.get("m1a_observations") or sparse.get("m1_observations") or []
        if obs:
            lines.extend(
                [
                    "| task_id | seed | Tier-C | Tier-S | tag |",
                    "|---|---:|---:|---:|---|",
                ]
            )
            for row in obs:
                sp = row.get("speedups") or {}
                lines.append(
                    f"| {row.get('task_id')} | {row.get('seed')} | "
                    f"{sp.get('Tier_C', float('nan')):.2f}x | "
                    f"{sp.get('Tier_S', float('nan')):.2f}x | "
                    f"{row.get('tag')} |"
                )
            lines.append("")

    if audit:
        lines.extend(["## Gates", ""])
        lines.extend(format_gate_table(audit))
        lines.append("")
        if not audit.get("tier_j_in_headline", False):
            lines.append(
                "Tier-J demoted from headline (G-J failed or kappa missing)."
            )
            lines.append("")

    lines.extend(_related_work_section(protocol))
    lines.extend(["## Blocked claims", ""])
    for claim_text in protocol.get("blocked_claims") or []:
        lines.append(f"- {claim_text}")
    lines.append("")
    lines.extend(_ledger_lines(died_ledger or {"entries": []}))
    lines.append("")
    text = "\n".join(lines)
    _assert_no_forbidden_language(text)
    assert_no_bare_m1(text, context="tlp01 report")
    if not real:
        assert_no_rung_labels_in_smoke_report(text, context="tlp01 report")
    return text


def write_report(
    aggregate: Mapping[str, Any],
    output: Path,
    *,
    audit: Mapping[str, Any] | None = None,
    died_ledger_path: Path | None = None,
) -> Path:
    path = died_ledger_path or DIED_LEDGER_PATH
    ledger = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.is_file()
        else {"entries": []}
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_report(aggregate, audit=audit, died_ledger=ledger),
        encoding="utf-8",
    )
    return output
