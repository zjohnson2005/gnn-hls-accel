"""T2: M0–M5 ladder over frozen T1 graphs / T0 traces (eligible task_ids only)."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from apu_characterization.tlp01.analyze import (
    analyze_experiment,
    bracket_line,
    speedup_bands,
)
from apu_characterization.tlp01.audit import audit_g_v
from apu_characterization.tlp01.contracts import sha256_json
from apu_characterization.tlp01.labels import DATA_SOURCE_REAL, find_rung_labels
from apu_characterization.tlp01.phase_diagram import render_phase_diagram_markdown
from apu_characterization.tlp01.replication_floor import (
    infer_source,
    infer_task_id,
    partition_by_replication_floor,
)
from apu_characterization.tlp01.t1_graphs import load_sessions_from_manifest

REPO = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO / "apu_characterization/out/tlp01/traces/manifest.json"
DEFAULT_T1_INDEX = (
    REPO / "apu_characterization/out/tlp01/dependence_graphs_v2/index.json"
)
DEFAULT_OUT = REPO / "apu_characterization/out/tlp01/t2"
EXPECTED_T1_SHA = (
    "29286aaa16b8e85207948db0ac84698466da3a8bdaebc6e80bbfa88f180a24d0"
)


def _load_gv_filtered(
    manifest_path: Path,
) -> tuple[list[list], list[dict[str, Any]], dict[str, Any]]:
    manifest, rows = load_sessions_from_manifest(manifest_path)
    kept: list[list] = []
    gv_fail: list[dict[str, Any]] = []
    for entry, events in rows:
        gate = audit_g_v(events)
        if not gate["pass"]:
            gv_fail.append(
                {
                    "session_id": events[0].session_id,
                    "task_id": entry.get("task_id") or infer_task_id(events),
                    "errors": gate["errors"],
                }
            )
            continue
        kept.append(list(events))
    return kept, gv_fail, manifest


def _bands_by_source(sessions: list[list], *, model: str) -> dict[str, Any]:
    by_src: dict[str, list] = defaultdict(list)
    for events in sessions:
        by_src[infer_source(events)].append(events)
    return {
        source: speedup_bands(group, model=model)
        for source, group in sorted(by_src.items())
    }


def _m0_table(sessions: list[list]) -> list[dict[str, Any]]:
    rows = []
    for events in sessions:
        gate = audit_g_v(events)
        rows.append(
            {
                "session_id": events[0].session_id,
                "task_id": infer_task_id(events),
                "source": infer_source(events),
                "pass": gate["pass"],
                "recorded_ns": gate.get("recorded_ns"),
                "replay_ns": gate.get("replay_ns"),
            }
        )
    return rows


def _fmt_bands(bands: dict[str, Any], title: str) -> list[str]:
    if not bands:
        return [f"## {title}", "", "_No eligible banded task_ids._", ""]
    lines = [
        f"## {title}",
        "",
        "| Task id | Source key | Tier-C floor med | Tier-S ceil med | Bracket |",
        "|---|---|---:|---:|---|",
    ]
    for task_id, tiers in bands.items():
        c_med = (tiers.get("Tier_C") or {}).get("median")
        s_med = (tiers.get("Tier_S") or {}).get("median")
        if c_med is None or s_med is None:
            continue
        lines.append(
            f"| {task_id} | — | {c_med:.2f}x | {s_med:.2f}x | "
            f"{bracket_line(s_med, c_med)} |"
        )
    lines.append("")
    return lines


def write_t2_report(
    *,
    stage1_path: Path,
    aggregate: dict[str, Any],
    gv_fail: list[dict[str, Any]],
    m0_rows: list[dict[str, Any]],
    bands_by_source: dict[str, dict[str, Any]],
    t1_sha: str,
    out_path: Path,
) -> None:
    floor = aggregate.get("replication_floor") or {}
    sparse = floor.get("sparse_task_ids") or []
    phase = aggregate.get("phase_diagram") or {}
    natural = phase.get("natural_predictor_accuracy") or {}
    bystander = aggregate.get("bystander_contention") or {}
    m5 = aggregate.get("m5_at_optimal_policy") or {}
    ceiling = aggregate.get("ceiling_claim") or {}
    frontier = aggregate.get("frontier_claim") or {}

    lines = [
        "# TLP-01 T2 ladder report",
        "",
        "## Stage 1 disposition",
        "",
        "**STAGE 1 FIXED** — hard replication-floor gate added "
        "(exclusion-with-separate-section). See "
        f"`{stage1_path.as_posix()}` for the full named sparse list.",
        "",
        f"- T1 graph index (frozen input): `{t1_sha}`",
        f"- Behavior: `{floor.get('behavior')}`",
        f"- Required seeds: **{floor.get('required_seeds')}**",
        f"- Banded sessions: **{aggregate.get('banded_session_count')}** / "
        f"{aggregate.get('session_count')} (after per-trace G-V)",
        f"- G-V per-trace failures excluded: **{len(gv_fail)}**",
        "",
        "### Sparse S1 task_ids (excluded from all bands)",
        "",
        "| task_id | n | seeds | disposition |",
        "|---|---:|---|---|",
    ]
    for row in sparse:
        lines.append(
            f"| {row['task_id']} | {row['n']} | "
            f"{','.join(str(s) for s in row['seeds'])} | {row['disposition']} |"
        )
    if not sparse:
        lines.append("| _(none)_ | | | |")

    lines.extend(
        [
            "",
            "## M0 baseline + G-V (per-trace)",
            "",
            f"- Traces passing G-V (±5%): "
            f"**{sum(1 for r in m0_rows if r['pass'])}/{len(m0_rows)}**",
            "",
        ]
    )

    # Intermediate results — no rung labels until claim section.
    for source in ("S1", "S2"):
        for model_key, title in (
            ("M1a", "M1a width ceiling (no speculation)"),
            ("M1b", "M1b + perfect control speculation"),
        ):
            src_bands = (bands_by_source.get(model_key) or {}).get(source) or {}
            lines.extend(
                _fmt_bands(
                    src_bands,
                    f"{title} — source {source} (eligible only)",
                )
            )

    lines.extend(
        _fmt_bands(
            aggregate.get("m2_speedup_bands") or {},
            "M2 (+ measured T_orch) speedup bands — eligible only",
        )
    )

    tax = aggregate.get("floor_tax_m2_minus_m1b") or {}
    if tax:
        lines.extend(
            [
                "## Floor tax (M2 − M1b median speedup gap)",
                "",
                "| Task id | Tier-C gap | Tier-S gap |",
                "|---|---:|---:|",
            ]
        )
        for task_id, tiers in tax.items():
            lines.append(
                f"| {task_id} | {tiers.get('Tier_C', float('nan')):.2f} | "
                f"{tiers.get('Tier_S', float('nan')):.2f} |"
            )
        lines.append("")

    m3 = aggregate.get("m3_speedup_bands") or {}
    if m3:
        lines.extend(
            [
                "## M3 width sweep (Tier-C median, eligible only)",
                "",
                "| Width | Task id | Tier-C median |",
                "|---:|---|---:|",
            ]
        )
        for width_key, bands in m3.items():
            label = "inf" if width_key in ("None", None, "null") else str(width_key)
            for task_id, tiers in bands.items():
                med = (tiers.get("Tier_C") or {}).get("median")
                if med is None:
                    continue
                lines.append(f"| {label} | {task_id} | {med:.2f}x |")
        lines.append("")

    if phase:
        lines.extend(["## M4 phase diagram (flagship)", ""])
        lines.extend(render_phase_diagram_markdown(phase))
        lines.extend(
            [
                "",
                "### Predictor accuracy (eligible sessions, 80/20 split)",
                "",
                f"- Natural top-1: **{natural.get('top1_accuracy', float('nan')):.3f}** "
                f"(n_predictions={int(natural.get('n_predictions', 0))})",
                "",
            ]
        )

    if bystander.get("per_policy"):
        lines.extend(
            [
                "## Bystander contention (software-side policies)",
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

    if m5.get("per_penalty"):
        lines.extend(
            [
                "## M5 at optimal policy × rate-limit ceiling",
                "",
                "| Penalty | Optimal policy | M5 Tier-C median | Tier D? |",
                "|---|---|---:|---|",
            ]
        )
        for key, row in (m5.get("per_penalty") or {}).items():
            lines.append(
                f"| {key} | {row.get('optimal_policy')} | "
                f"{row.get('m5_speedup_median', float('nan')):.2f}x | "
                f"{'YES — position only' if row.get('praetor_tier_d') else 'no'} |"
            )
        lines.append("")

    # Claim rungs — only here.
    lines.extend(
        [
            "## Evaluated claim rungs (pre-registered criteria)",
            "",
            f"- Ceiling track: **{ceiling.get('name')}** (`{ceiling.get('rung')}`)",
            f"  - {ceiling.get('language', '')}",
            f"  - criterion: {ceiling.get('criterion', '')}",
            f"- Frontier track: **{frontier.get('name')}** (`{frontier.get('rung')}`)",
            f"  - {frontier.get('language', '')}",
            f"  - criterion: {frontier.get('criterion', '')}",
            "",
            "G-J remains demoted (no human κ).",
            "",
            "## Appendix — S1 sparse task_ids (descriptive only, not banded)",
            "",
            "These observations are single-seed / below-floor and **must not** "
            "feed any rung verdict or primary chart.",
            "",
        ]
    )
    obs = (aggregate.get("sparse_descriptive") or {}).get("m1_observations") or []
    if not obs:
        lines.append("_No sparse observations._")
    else:
        lines.extend(
            [
                "| task_id | seed | session_id | Tier-C | Tier-S | tag |",
                "|---|---:|---|---:|---:|---|",
            ]
        )
        for row in obs:
            sp = row.get("speedups") or {}
            lines.append(
                f"| {row.get('task_id')} | {row.get('seed')} | "
                f"{row.get('session_id')} | "
                f"{sp.get('Tier_C', float('nan')):.2f}x | "
                f"{sp.get('Tier_S', float('nan')):.2f}x | "
                f"{row.get('tag')} |"
            )
    lines.append("")
    lines.append(
        f"T2 COMPLETE — aggregate hash `{aggregate.get('aggregate_sha256', '')}`"
    )
    lines.append("")

    text = "\n".join(lines) + "\n"
    # Allow rung labels only in this final report (evaluated verdicts).
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--t1-index", type=Path, default=DEFAULT_T1_INDEX)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--expect-t1-sha",
        default=EXPECTED_T1_SHA,
        help="Refuse if T1 index sha mismatches (frozen corpus pin)",
    )
    args = parser.parse_args()

    t1 = json.loads(args.t1_index.read_text(encoding="utf-8"))
    t1_sha = t1.get("index_sha256")
    if args.expect_t1_sha and t1_sha != args.expect_t1_sha:
        raise SystemExit(
            f"T1 index sha mismatch: got {t1_sha}, expected {args.expect_t1_sha}"
        )

    sessions, gv_fail, _manifest = _load_gv_filtered(args.manifest)
    # Partition preview for Stage 1 inventory (also enforced inside analyze).
    partition = partition_by_replication_floor(sessions)

    aggregate = analyze_experiment(
        sessions, include_frontier=True, data_source=DATA_SOURCE_REAL
    )
    # Guard: intermediate artifact must not carry rung labels outside claims.
    slim_check = {
        k: v
        for k, v in aggregate.items()
        if k not in {"ceiling_claim", "frontier_claim", "claim"}
    }
    leaked = find_rung_labels(json.dumps(slim_check, sort_keys=True))
    if leaked:
        raise SystemExit(f"rung labels leaked into intermediate T2 fields: {leaked}")

    eligible = partition["eligible_sessions"]
    m0_rows = _m0_table(sessions)
    bands_by_source = {
        "M1a": _bands_by_source(eligible, model="M1a"),
        "M1b": _bands_by_source(eligible, model="M1b"),
        "M2": _bands_by_source(eligible, model="M2"),
    }

    aggregate["m0_g_v"] = {
        "pass_count": sum(1 for r in m0_rows if r["pass"]),
        "fail_count": len(gv_fail),
        "fails": gv_fail,
    }
    aggregate["m1a_speedup_bands_by_source"] = bands_by_source["M1a"]
    aggregate["m1b_speedup_bands_by_source"] = bands_by_source["M1b"]
    aggregate["m2_speedup_bands_by_source"] = bands_by_source["M2"]
    aggregate["t1_index_sha256"] = t1_sha
    aggregate["aggregate_sha256"] = sha256_json(
        {k: v for k, v in aggregate.items() if k != "aggregate_sha256"}
    )

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "aggregate.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out / "partition.json").write_text(
        json.dumps(
            {
                "required_seeds": partition["required_seeds"],
                "behavior": partition["behavior"],
                "sparse_task_ids": partition["sparse_task_ids"],
                "eligible_task_ids": partition["eligible_task_ids"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    stage1 = (
        REPO / "apu_characterization/out/tlp01/t1_t2_boundary_stage1.md"
    )
    write_t2_report(
        stage1_path=stage1.relative_to(REPO),
        aggregate=aggregate,
        gv_fail=gv_fail,
        m0_rows=m0_rows,
        bands_by_source=bands_by_source,
        t1_sha=t1_sha,
        out_path=args.out / "t2_ladder_report.md",
    )


if __name__ == "__main__":
    main()
