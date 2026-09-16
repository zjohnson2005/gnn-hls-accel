"""Idempotent OA-01 behavioral-atlas derivation from the retained corpus."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

from apu_characterization.oa01.runner import DEFAULT_OUT
from apu_characterization.oa01.schema import TurnRecord
from apu_characterization.turntrace_v2.labeling import validate_taxonomy
from apu_characterization.turntrace_v2.schema import StepFeatures

FIXED_SCAFFOLD_TYPES = {
    "read_file",
    "grep",
    "read_file+grep",
    "edit_file",
    "run_tests",
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_turns(path: Path) -> list[TurnRecord]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(TurnRecord(**json.loads(line)))
    return rows


def load_corpus(
    out_root: Path, *, allow_incomplete: bool = False
) -> tuple[list[dict[str, Any]], list[TurnRecord]]:
    trajectories = []
    turns = []
    for path in sorted((out_root / "runs").glob("OA01-[PM]-*/trajectory_record.json")):
        trajectories.append(_load(path))
        turn_path = path.parent / "derived" / "turn_records.jsonl"
        if turn_path.is_file():
            turns.extend(_load_turns(turn_path))
    if not allow_incomplete and len(trajectories) != 15:
        raise RuntimeError(f"atlas requires all 15 retained trajectories; found {len(trajectories)}")
    return trajectories, turns


def _mean(values: Sequence[float]) -> float | None:
    return float(statistics.fmean(values)) if values else None


def _by_turn(turns: Sequence[TurnRecord]) -> list[dict[str, Any]]:
    buckets: dict[int, list[TurnRecord]] = defaultdict(list)
    for turn in turns:
        buckets[turn.turn_index].append(turn)
    rows = []
    for index, values in sorted(buckets.items()):
        rows.append(
            {
                "turn_index": index,
                "n": len(values),
                "mean_t_orch_gap_ms": _mean([v.t_orch_gap_ms for v in values]),
                "mean_t_model_observed_ms": _mean(
                    [v.t_model_observed_ms for v in values]
                ),
                "mean_t_prefill_ms": _mean(
                    [v.t_prefill_ms for v in values if v.t_prefill_ms is not None]
                ),
                "mean_t_decode_ms": _mean(
                    [v.t_decode_ms for v in values if v.t_decode_ms is not None]
                ),
                "mean_t_network_ms": _mean(
                    [v.t_network_ms for v in values if v.t_network_ms is not None]
                ),
                "mean_t_tool_ms": _mean([v.t_tool_ms for v in values]),
                "mean_necessary_prefill_tokens": _mean(
                    [float(v.necessary_prefill_tokens) for v in values]
                ),
                "mean_structurally_redundant_tokens": _mean(
                    [float(v.structurally_redundant_tokens) for v in values]
                ),
                "mean_provider_recovered_tokens": _mean(
                    [float(v.provider_recovered_tokens) for v in values]
                ),
                "mean_actually_recomputed_redundant_tokens": _mean(
                    [float(v.actually_recomputed_redundant_tokens) for v in values]
                ),
            }
        )
    return rows


def _cache_summary(turns: Sequence[TurnRecord]) -> dict[str, Any]:
    structural = sum(t.structurally_redundant_tokens for t in turns)
    recovered_raw = sum(t.provider_recovered_tokens for t in turns)
    recovered_bounded = sum(
        min(t.provider_recovered_tokens, t.structurally_redundant_tokens) for t in turns
    )
    leaked = sum(t.actually_recomputed_redundant_tokens for t in turns)
    violations = sum(
        "provider_cache_reconciliation" in t.audit_flags for t in turns
    )
    return {
        "structurally_redundant_tokens": structural,
        "provider_recovered_tokens_raw": recovered_raw,
        "provider_recovered_tokens_bounded_to_structural": recovered_bounded,
        "actually_recomputed_redundant_tokens": leaked,
        "recovery_fraction_of_structural": (
            recovered_bounded / structural if structural else None
        ),
        "leak_fraction_of_structural": leaked / structural if structural else None,
        "raw_provider_to_structural_ratio": (
            recovered_raw / structural if structural else None
        ),
        "provider_cache_reconciliation_violations": violations,
    }


def _behavior(turns: Sequence[TurnRecord]) -> dict[str, Any]:
    by_trajectory: dict[str, list[TurnRecord]] = defaultdict(list)
    for turn in turns:
        by_trajectory[turn.trajectory_id].append(turn)
    labeled = []
    for trajectory in by_trajectory.values():
        labeled.append(
            [
                (
                    turn.step_type_semantic,
                    StepFeatures(
                        is_tool_call=turn.is_tool_call,
                        tool_class="state_mutating",
                        repeat_count=turn.repeat_count,
                        loop_membership=turn.loop_membership,
                        fanout_siblings=turn.fanout_siblings,
                        trajectory_position=(
                            turn.turn_index / max(1, len(trajectory) - 1)
                        ),
                    ),
                    turn.status,
                )
                for turn in sorted(trajectory, key=lambda value: value.turn_index)
            ]
        )
    taxonomy = validate_taxonomy(labeled, min_support=2)
    types = sorted({turn.step_type_semantic for turn in turns})
    return {
        "loop_membership": dict(Counter(turn.loop_membership for turn in turns)),
        "repeat_count": dict(Counter(turn.repeat_count for turn in turns)),
        "fanout_siblings": dict(Counter(turn.fanout_siblings for turn in turns)),
        "fanout_occurrences": sum(turn.fanout_siblings > 0 for turn in turns),
        "semantic_type_counts": dict(Counter(turn.step_type_semantic for turn in turns)),
        "d5": {
            "agreement_rate": taxonomy.agreement_rate,
            "assigned_types": taxonomy.assigned_types,
            "prefer_mined_for_layer1": taxonomy.prefer_mined_for_layer1,
            "notes": taxonomy.notes,
            "mined_patterns_top": [
                {"pattern": list(pattern), "support": support}
                for pattern, support in taxonomy.mined_patterns[:50]
            ],
            "new_types_vs_fixed_scaffold": sorted(set(types) - FIXED_SCAFFOLD_TYPES),
            "fixed_scaffold_reference_types": sorted(FIXED_SCAFFOLD_TYPES),
            "semantic_method": (
                "bash command-shape classification from archived function arguments; "
                "the upstream subject exposes a generic bash tool"
            ),
        },
    }


def build_atlas(
    trajectories: Sequence[dict[str, Any]], turns: Sequence[TurnRecord]
) -> dict[str, Any]:
    trajectories = sorted(trajectories, key=lambda row: row["trajectory_id"])
    total_spend = sum(float(row["cost_usd"]) for row in trajectories)
    by_trajectory: dict[str, list[TurnRecord]] = defaultdict(list)
    for turn in turns:
        by_trajectory[turn.trajectory_id].append(turn)
    outcomes = []
    for row in trajectories:
        outcomes.append(
            {
                "trajectory_id": row["trajectory_id"],
                "task": row["task_id"],
                "turns": row["turns"],
                "outcome": row["outcome"],
                "success": row.get("success"),
                "censored": row["censored"],
                "censor_reason": row.get("censor_reason"),
                "wall_clock_ms": row["wall_clock_ms"],
                "cost_usd": row["cost_usd"],
                "flags": row.get("flags") or [],
            }
        )
    return {
        "schema_version": "oa01_behavioral_atlas_v1",
        "actual_spend_usd": total_spend,
        "n_trajectories": len(trajectories),
        "n_turns": len(turns),
        "censored_count": sum(bool(row["censored"]) for row in trajectories),
        "outcomes": outcomes,
        "trajectory_lengths": [
            {
                "trajectory_id": row["trajectory_id"],
                "turns": row["turns"],
                "censored": row["censored"],
            }
            for row in trajectories
        ],
        "per_turn": _by_turn(turns),
        "spaghetti": {
            trajectory_id: [
                turn.to_dict()
                for turn in sorted(values, key=lambda value: value.turn_index)
            ]
            for trajectory_id, values in sorted(by_trajectory.items())
        },
        "provider_cache": _cache_summary(turns),
        "behavioral_structure": _behavior(turns),
        "timing_availability": {
            "methods": dict(Counter(turn.timing_method for turn in turns)),
            "prefill_values": sum(turn.t_prefill_ms is not None for turn in turns),
            "decode_values": sum(turn.t_decode_ms is not None for turn in turns),
            "network_values": sum(turn.t_network_ms is not None for turn in turns),
            "authenticity_rule": (
                "null model-internal timing is retained when the shipped nonstreaming "
                "subject does not expose a valid isolate"
            ),
        },
        "honest_scope": (
            "One scaffold, one model, one benchmark, n=15; typical means "
            "typical-of-this-configuration. Censoring is explicit. T_orch is "
            "gap-derived and coarse. Sampling is nondeterministic."
        ),
    }


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _svg(
    *,
    trajectories: dict[str, list[dict[str, Any]]],
    per_turn: Sequence[dict[str, Any]],
    field: str,
    mean_field: str,
    title: str,
    y_label: str,
) -> str:
    width, height = 900, 430
    left, right, top, bottom = 75, 25, 45, 55
    all_points = [
        (int(turn["turn_index"]), float(turn[field]))
        for values in trajectories.values()
        for turn in values
        if turn.get(field) is not None
    ]
    if not all_points:
        return ""
    max_x = max(x for x, _ in all_points) or 1
    max_y = max(y for _, y in all_points) or 1.0

    def xy(x: float, y: float) -> tuple[float, float]:
        px = left + x / max_x * (width - left - right)
        py = top + (1.0 - y / max_y) * (height - top - bottom)
        return px, py

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="24" text-anchor="middle" '
        f'font-family="sans-serif" font-size="16">{title}</text>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" '
        f'y2="{height-bottom}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#333"/>',
    ]
    for values in trajectories.values():
        points = [
            xy(float(turn["turn_index"]), float(turn[field]))
            for turn in values
            if turn.get(field) is not None
        ]
        if points:
            lines.append(
                '<polyline fill="none" stroke="#9aa0a6" stroke-opacity="0.35" '
                'stroke-width="1" points="'
                + " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
                + '"/>'
            )
    mean_points = [
        xy(float(row["turn_index"]), float(row[mean_field]))
        for row in per_turn
        if row.get(mean_field) is not None
    ]
    lines.append(
        '<polyline fill="none" stroke="#1a73e8" stroke-width="3" points="'
        + " ".join(f"{x:.1f},{y:.1f}" for x, y in mean_points)
        + '"/>'
    )
    lines += [
        f'<text x="{width/2}" y="{height-12}" text-anchor="middle" '
        'font-family="sans-serif" font-size="12">Turn index</text>',
        f'<text x="17" y="{height/2}" text-anchor="middle" '
        f'transform="rotate(-90 17 {height/2})" font-family="sans-serif" '
        f'font-size="12">{y_label}</text>',
        '<line x1="690" y1="18" x2="720" y2="18" stroke="#9aa0a6" stroke-opacity="0.5"/>',
        '<text x="725" y="22" font-family="sans-serif" font-size="11">trajectories</text>',
        '<line x1="790" y1="18" x2="820" y2="18" stroke="#1a73e8" stroke-width="3"/>',
        '<text x="825" y="22" font-family="sans-serif" font-size="11">mean</text>',
        "</svg>",
    ]
    return "\n".join(lines)


def write_figures(atlas: dict[str, Any], out_dir: Path) -> list[str]:
    specs = [
        (
            "t_orch_gap_ms",
            "mean_t_orch_gap_ms",
            "Gap-derived orchestration by turn",
            "T_orch gap (ms)",
            "oa01_orch_spaghetti.svg",
        ),
        (
            "t_prefill_ms",
            "mean_t_prefill_ms",
            "Provider-isolated prefill by turn",
            "Prefill (ms)",
            "oa01_prefill_spaghetti.svg",
        ),
        (
            "t_decode_ms",
            "mean_t_decode_ms",
            "Observed streaming decode by turn",
            "Decode (ms)",
            "oa01_decode_spaghetti.svg",
        ),
        (
            "t_network_ms",
            "mean_t_network_ms",
            "Network residual by turn",
            "Network (ms)",
            "oa01_network_spaghetti.svg",
        ),
        (
            "necessary_prefill_tokens",
            "mean_necessary_prefill_tokens",
            "Necessary prefill tokens by turn",
            "Tokens",
            "oa01_necessary_spaghetti.svg",
        ),
        (
            "structurally_redundant_tokens",
            "mean_structurally_redundant_tokens",
            "Structurally redundant prefill by turn",
            "Tokens",
            "oa01_structural_spaghetti.svg",
        ),
        (
            "provider_recovered_tokens",
            "mean_provider_recovered_tokens",
            "Provider-recovered prompt tokens by turn",
            "Tokens",
            "oa01_recovered_spaghetti.svg",
        ),
        (
            "actually_recomputed_redundant_tokens",
            "mean_actually_recomputed_redundant_tokens",
            "Actually recomputed redundant prefill by turn",
            "Tokens",
            "oa01_recomputed_spaghetti.svg",
        ),
    ]
    written = []
    for field, mean_field, title, ylabel, filename in specs:
        svg = _svg(
            trajectories=atlas["spaghetti"],
            per_turn=atlas["per_turn"],
            field=field,
            mean_field=mean_field,
            title=title,
            y_label=ylabel,
        )
        if svg:
            (out_dir / filename).write_text(svg, encoding="utf-8")
            written.append(filename)
    return written


def render_markdown(atlas: dict[str, Any], figure_names: Sequence[str]) -> str:
    cache = atlas["provider_cache"]
    behavior = atlas["behavioral_structure"]
    timing = atlas["timing_availability"]
    lines = [
        "# OA-01 behavioral atlas",
        "",
        f"**Actual API spend: ${atlas['actual_spend_usd']:.4f}.** "
        f"Retained trajectories: {atlas['n_trajectories']}; "
        f"censored: {atlas['censored_count']}.",
        "",
        "## Outcome table",
        "",
        "| Task | Turns | Outcome | Censor reason | Wall min | Cost USD | Flags |",
        "|---|---:|---|---|---:|---:|---|",
    ]
    for row in atlas["outcomes"]:
        lines.append(
            f"| {row['task']} | {row['turns']} | {row['outcome']} | "
            f"{row['censor_reason'] or '—'} | {row['wall_clock_ms']/60000:.2f} | "
            f"{row['cost_usd']:.4f} | {', '.join(row['flags']) or '—'} |"
        )
    lines += [
        "",
        "All fifteen pre-registered rows are shown. Agent crashes, bad/empty patches, "
        "native limits, evaluation errors, and censoring are retained.",
        "",
        "## Per-turn boundary decomposition",
        "",
    ]
    for name in figure_names:
        lines.append(f"![OA-01 per-turn plot]({name})")
        lines.append("")
    lines += [
        "| Turn | N | Orch gap ms | Model observed ms | Necessary tok | Structural tok | Recovered tok | Recomputed tok |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in atlas["per_turn"]:
        lines.append(
            f"| {row['turn_index']} | {row['n']} | "
            f"{_fmt(row['mean_t_orch_gap_ms'], 1)} | "
            f"{_fmt(row['mean_t_model_observed_ms'], 1)} | "
            f"{_fmt(row['mean_necessary_prefill_tokens'], 1)} | "
            f"{_fmt(row['mean_structurally_redundant_tokens'], 1)} | "
            f"{_fmt(row['mean_provider_recovered_tokens'], 1)} | "
            f"{_fmt(row['mean_actually_recomputed_redundant_tokens'], 1)} |"
        )
    lines += [
        "",
        "| Turn | N | Prefill ms | Decode ms | Network ms | Tool ms |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in atlas["per_turn"]:
        lines.append(
            f"| {row['turn_index']} | {row['n']} | "
            f"{_fmt(row['mean_t_prefill_ms'], 1)} | "
            f"{_fmt(row['mean_t_decode_ms'], 1)} | "
            f"{_fmt(row['mean_t_network_ms'], 1)} | "
            f"{_fmt(row['mean_t_tool_ms'], 1)} |"
        )
    lines += [
        "",
        f"Timing methods: `{json.dumps(timing['methods'], sort_keys=True)}`. "
        f"Valid prefill/decode/network isolates: "
        f"{timing['prefill_values']}/{timing['decode_values']}/{timing['network_values']}.",
        "",
        timing["authenticity_rule"],
        "",
        "## Provider-cache three-way split",
        "",
        f"- Structurally redundant tokens: {cache['structurally_redundant_tokens']}",
        f"- Provider recovered (raw): {cache['provider_recovered_tokens_raw']}",
        f"- Actually recomputed redundant: {cache['actually_recomputed_redundant_tokens']}",
        f"- Recovery fraction of structural: {_fmt(cache['recovery_fraction_of_structural'])}",
        f"- Leak fraction of structural: {_fmt(cache['leak_fraction_of_structural'])}",
        f"- Reconciliation violations: {cache['provider_cache_reconciliation_violations']}",
        "",
        "The bounded recovery fraction uses `min(provider recovered, structural)` per "
        "call. Raw provider counts and every reconciliation violation remain in JSON.",
        "",
        "## Behavioral structure and D5",
        "",
        f"- Loop-membership distribution: `{behavior['loop_membership']}`",
        f"- Repeat-count distribution: `{behavior['repeat_count']}`",
        f"- Fanout distribution: `{behavior['fanout_siblings']}`",
        f"- Semantic types: `{behavior['semantic_type_counts']}`",
        f"- D5 agreement rate: {_fmt(behavior['d5']['agreement_rate'])}",
        f"- New types vs fixed scaffold: "
        f"`{behavior['d5']['new_types_vs_fixed_scaffold']}`",
        f"- Semantic derivation: {behavior['d5']['semantic_method']}",
        "",
        "## Honest scope",
        "",
        atlas["honest_scope"],
        "",
        "The complete per-turn rows, spaghetti series, mined patterns, trajectory "
        "lengths, and raw-vs-bounded cache arithmetic are in "
        "`OA01_behavioral_atlas.json`.",
        "",
    ]
    return "\n".join(lines)


def generate(out_root: Path, *, allow_incomplete: bool = False) -> dict[str, Path]:
    trajectories, turns = load_corpus(out_root, allow_incomplete=allow_incomplete)
    atlas = build_atlas(trajectories, turns)
    out_root.mkdir(parents=True, exist_ok=True)
    json_path = out_root / "OA01_behavioral_atlas.json"
    json_path.write_text(
        json.dumps(atlas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    figures = write_figures(atlas, out_root)
    md_path = out_root / "OA01_behavioral_atlas.md"
    md_path.write_text(render_markdown(atlas, figures), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            {
                key: str(value)
                for key, value in generate(
                    args.out, allow_incomplete=args.allow_incomplete
                ).items()
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

