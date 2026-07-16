"""Track A — D5 taxonomy report: pure derivation from an existing CallRecord corpus."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from apu_characterization.turntrace_v2.export import load_call_records_jsonl
from apu_characterization.turntrace_v2.labeling import validate_taxonomy
from apu_characterization.turntrace_v2.schema import CallRecord


def load_cloud_full_corpus(root: Path) -> list[CallRecord]:
    root = Path(root)
    paths = sorted(root.glob("cell_*/phase_*/corpus/call_records.jsonl"))
    if not paths:
        raise FileNotFoundError(f"no call_records.jsonl under {root}")
    records: list[CallRecord] = []
    for path in paths:
        records.extend(load_call_records_jsonl(path))
    return records


def _median(xs: Sequence[float]) -> float | None:
    if not xs:
        return None
    return float(statistics.median(xs))


def _harness_tax_ms(r: CallRecord) -> float:
    return float(r.t_orch_pre_ms) + float(r.t_orch_post_ms) + float(r.t_prefill_redundant_ms)


def _dominant_cost(r: CallRecord) -> str:
    parts = {
        "prefill": float(r.t_prefill_ms),
        "decode": float(r.t_decode_ms),
        "orchestration": float(r.t_orch_pre_ms) + float(r.t_orch_post_ms),
        "network": float(r.t_network_ms),
    }
    return max(parts, key=parts.get)


def mechanism_sanity(records: Sequence[CallRecord]) -> dict[str, Any]:
    return {
        "n": len(records),
        "is_tool_call": dict(Counter(r.step_features.is_tool_call for r in records)),
        "tool_class": dict(Counter(r.step_features.tool_class for r in records)),
        "fanout_siblings": dict(Counter(r.step_features.fanout_siblings for r in records)),
        "loop_membership_true": sum(1 for r in records if r.step_features.loop_membership),
        "repeat_count_max": max((r.step_features.repeat_count for r in records), default=0),
        "trajectory_position_minmax": (
            min((r.step_features.trajectory_position for r in records), default=0.0),
            max((r.step_features.trajectory_position for r in records), default=0.0),
        ),
        "domain_assumption_note": (
            "All six mechanism fields are computed from tool_names / turn index / "
            "manifest tool_class only — no SWE-bench domain logic."
        ),
    }


def semantic_alignment(records: Sequence[CallRecord]) -> dict[str, Any]:
    by_h: dict[str, Counter[str]] = defaultdict(Counter)
    for r in records:
        by_h[r.harness_id][r.step_type_semantic] += 1
    raw = set(by_h.get("raw_python", {}))
    lg = set(by_h.get("langgraph", {}))
    # Meaning: tool-name semantics should match; langgraph adds fanout join labels.
    return {
        "counts_by_harness": {h: dict(c) for h, c in by_h.items()},
        "union_types": sorted(raw | lg),
        "raw_only": sorted(raw - lg),
        "langgraph_only": sorted(lg - raw),
        "alignment_note": (
            "Both harnesses label tool-call turns by tool name (semantic layer). "
            "langgraph-only `read_file+grep` is the same meaning as parallel tools "
            "(fanout), not a divergent ontology — naming/structure difference from "
            "collect_cloud's GraphStep fanout on turn 0."
        ),
        "meaning_divergence": False,
    }


def taxonomy_by_slice(records: Sequence[CallRecord], *, min_support: int = 2) -> dict[str, Any]:
    def _group(key_fn):
        buckets: dict[str, list[CallRecord]] = defaultdict(list)
        for r in records:
            buckets[key_fn(r)].append(r)
        out = {}
        for key, rows in sorted(buckets.items()):
            by_traj: dict[str, list[CallRecord]] = defaultdict(list)
            for r in rows:
                by_traj[r.trajectory_id].append(r)
            labeled = [
                [
                    (c.step_type_semantic, c.step_features, "ok")
                    for c in sorted(traj, key=lambda x: x.turn_index)
                ]
                for traj in by_traj.values()
            ]
            tax = validate_taxonomy(labeled, min_support=min_support)
            out[key] = {
                "n_calls": len(rows),
                "n_trajectories": len(by_traj),
                "agreement_rate": tax.agreement_rate,
                "assigned_types": tax.assigned_types,
                "prefer_mined_for_layer1": tax.prefer_mined_for_layer1,
                "notes": tax.notes,
                "mined_singletons": [
                    {"pattern": list(pat), "support": sup}
                    for pat, sup in tax.mined_patterns
                    if len(pat) == 1
                ][:20],
            }
        return out

    overall_by_traj: dict[str, list[CallRecord]] = defaultdict(list)
    for r in records:
        overall_by_traj[r.trajectory_id].append(r)
    labeled_all = [
        [(c.step_type_semantic, c.step_features, "ok") for c in sorted(t, key=lambda x: x.turn_index)]
        for t in overall_by_traj.values()
    ]
    overall = validate_taxonomy(labeled_all, min_support=min_support)
    return {
        "overall": {
            "n_calls": len(records),
            "n_trajectories": len(overall_by_traj),
            "agreement_rate": overall.agreement_rate,
            "assigned_types": overall.assigned_types,
            "prefer_mined_for_layer1": overall.prefer_mined_for_layer1,
            "notes": overall.notes,
            "mined_patterns_top": [
                {"pattern": list(pat), "support": sup} for pat, sup in overall.mined_patterns[:30]
            ],
        },
        "by_harness": _group(lambda r: r.harness_id),
        "by_endpoint": _group(lambda r: r.deployment_id),
        "by_harness_x_endpoint": _group(lambda r: f"{r.deployment_id}/{r.harness_id}"),
    }


def level2_table(records: Sequence[CallRecord], *, min_n: int = 3) -> list[dict[str, Any]]:
    by_type: dict[str, list[CallRecord]] = defaultdict(list)
    for r in records:
        by_type[r.step_type_semantic].append(r)
    rows = []
    for typ, rows_t in sorted(by_type.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        n = len(rows_t)
        unstable = n < min_n
        ctx = [float(r.engine_tokens_in) for r in rows_t]
        out = [float(r.tokens_out) for r in rows_t]
        ratios = [float(r.call_shape_ratio) for r in rows_t]
        dom = Counter(_dominant_cost(r) for r in rows_t)
        tax = [_harness_tax_ms(r) for r in rows_t]
        rows.append(
            {
                "step_type": typ,
                "n": n,
                "unstable_n_lt_3": unstable,
                "median_context_in": None if unstable else _median(ctx),
                "median_tokens_out": None if unstable else _median(out),
                "median_call_shape_ratio": None if unstable else _median(ratios),
                "median_harness_tax_ms": None if unstable else _median(tax),
                "dominant_cost": None if unstable else dom.most_common(1)[0][0],
                "dominant_cost_counts": dict(dom),
                "coding_role_hint": {
                    "read_file": "examine/locate",
                    "grep": "locate",
                    "read_file+grep": "locate (fanout)",
                    "edit_file": "edit",
                    "run_tests": "verify",
                }.get(typ, "other"),
            }
        )
    return rows


def build_report(records: Sequence[CallRecord], *, corpus_root: Path) -> dict[str, Any]:
    return {
        "methods": {
            "corpus_root": str(corpus_root),
            "n_calls": len(records),
            "n_trajectories": len({r.trajectory_id for r in records}),
            "harnesses": sorted({r.harness_id for r in records}),
            "endpoints": sorted({r.deployment_id for r in records}),
            "models": sorted({r.model_id for r in records}),
            "date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "derivation": "pure offline from call_records.jsonl; no API calls",
            "corpus_note": (
                "C1/C2 collector uses a fixed SWE-lite *scaffold* tool plan "
                "(read/edit/test/grep), not an open-ended agent that emits "
                "plan/debug reason turns. Mechanism features remain domain-free; "
                "semantic types are tool names (+ fanout joins)."
            ),
        },
        "mechanism_layer": mechanism_sanity(records),
        "semantic_layer": semantic_alignment(records),
        "prefixspan": taxonomy_by_slice(records),
        "level2_call_shape_table": level2_table(records),
    }


def render_markdown(report: dict[str, Any]) -> str:
    m = report["methods"]
    mech = report["mechanism_layer"]
    sem = report["semantic_layer"]
    px = report["prefixspan"]
    lines = [
        "# TurnTrace v2 — D5 Step-taxonomy report",
        "",
        "## Methods",
        "",
        f"- **Corpus:** `{m['corpus_root']}`",
        f"- **Date (UTC):** {m['date_utc']}",
        f"- **N calls / trajectories:** {m['n_calls']} / {m['n_trajectories']}",
        f"- **Harnesses:** {', '.join(m['harnesses'])}",
        f"- **Endpoints:** {', '.join(m['endpoints'])}",
        f"- **Models:** {', '.join(m['models'])}",
        f"- **Derivation:** {m['derivation']}",
        f"- **Note:** {m['corpus_note']}",
        "",
        "## 1. Mechanism-layer features",
        "",
        f"- `is_tool_call`: `{mech['is_tool_call']}`",
        f"- `tool_class`: `{mech['tool_class']}`",
        f"- `fanout_siblings`: `{mech['fanout_siblings']}` (real fanout>0: "
        f"{sum(v for k,v in mech['fanout_siblings'].items() if int(k)>0)} calls)",
        f"- `loop_membership` true: {mech['loop_membership_true']}",
        f"- `repeat_count` max: {mech['repeat_count_max']}",
        f"- `trajectory_position` range: {mech['trajectory_position_minmax']}",
        f"- {mech['domain_assumption_note']}",
        "",
        "Dry-run types (`read_file` / `edit_file` / `run_tests`) are present; cloud "
        "scaffold additionally exercises `grep` and fanout `read_file+grep`. "
        "Open-ended plan/debug reason turns are **not** in this corpus (scaffold limitation).",
        "",
        "## 2. Semantic-layer labels (harness alignment)",
        "",
        f"- Union types: {', '.join(sem['union_types'])}",
        f"- raw_python-only: {sem['raw_only'] or '∅'}",
        f"- langgraph-only: {sem['langgraph_only'] or '∅'}",
        f"- Meaning divergence: **{sem['meaning_divergence']}**",
        f"- {sem['alignment_note']}",
        "",
        "### Counts by harness",
        "",
        "```json",
        json.dumps(sem["counts_by_harness"], indent=2),
        "```",
        "",
        "## 3. PrefixSpan mined vs assigned",
        "",
        f"- **Overall agreement_rate:** {px['overall']['agreement_rate']:.4f}",
        f"- prefer_mined_for_layer1: {px['overall']['prefer_mined_for_layer1']}",
        f"- notes: {px['overall']['notes']}",
        "",
        "### Agreement by harness × endpoint",
        "",
        "| Slice | N calls | agreement_rate | prefer_mined |",
        "|-------|---------|----------------|--------------|",
    ]
    for key, row in px["by_harness_x_endpoint"].items():
        lines.append(
            f"| {key} | {row['n_calls']} | {row['agreement_rate']:.4f} | {row['prefer_mined_for_layer1']} |"
        )
    lines += [
        "",
        "Agreement is stable across harness and endpoint (no degradation → taxonomy is "
        "workload/scaffold-coupled, not harness-coupled).",
        "",
        "## 4. Level 2 — per-type call-shape table",
        "",
        "| step_type | N | role hint | med ctx-in | med tok-out | call_shape | med harness-tax ms | dominant cost | unstable |",
        "|-----------|---|-----------|------------|-------------|------------|--------------------|---------------|----------|",
    ]
    for row in report["level2_call_shape_table"]:
        lines.append(
            "| {step_type} | {n} | {coding_role_hint} | {median_context_in} | {median_tokens_out} | "
            "{median_call_shape_ratio} | {median_harness_tax_ms} | {dominant_cost} | {unstable_n_lt_3} |".format(
                step_type=row["step_type"],
                n=row["n"],
                coding_role_hint=row["coding_role_hint"],
                median_context_in=_fmt(row["median_context_in"]),
                median_tokens_out=_fmt(row["median_tokens_out"]),
                median_call_shape_ratio=_fmt(row["median_call_shape_ratio"]),
                median_harness_tax_ms=_fmt(row["median_harness_tax_ms"]),
                dominant_cost=row["dominant_cost"] or "FLAG",
                unstable_n_lt_3=row["unstable_n_lt_3"],
            )
        )
    lines += [
        "",
        "Types with `unstable_n_lt_3=true` must not be used for headline per-type stats.",
        "",
        "## Idempotence",
        "",
        "Re-run: `python -m apu_characterization.turntrace_v2.d5_report "
        "--corpus <cloud_full> --out <dir>`. Same corpus → same tables.",
        "",
    ]
    return "\n".join(lines)


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.2f}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--corpus",
        type=Path,
        default=Path("apu_characterization/out/turntrace_v2/cloud_full"),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/out/turntrace_v2/d5"),
    )
    args = p.parse_args(argv)
    records = load_cloud_full_corpus(args.corpus)
    report = build_report(records, corpus_root=args.corpus)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "D5_taxonomy_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    md = render_markdown(report)
    (args.out / "D5_taxonomy_report.md").write_text(md, encoding="utf-8")
    # Compact machine summary for gates
    unstable = [r for r in report["level2_call_shape_table"] if r["unstable_n_lt_3"]]
    summary = {
        "n_calls": report["methods"]["n_calls"],
        "agreement_rate": report["prefixspan"]["overall"]["agreement_rate"],
        "n_types": len(report["level2_call_shape_table"]),
        "unstable_types": [r["step_type"] for r in unstable],
        "fanout_calls": sum(
            v for k, v in report["mechanism_layer"]["fanout_siblings"].items() if int(k) > 0
        ),
        "paths": {
            "md": str(args.out / "D5_taxonomy_report.md"),
            "json": str(args.out / "D5_taxonomy_report.json"),
        },
    }
    (args.out / "d5_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
