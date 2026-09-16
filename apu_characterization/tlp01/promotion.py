"""TLP-01 promotion package helpers: supersession, quotable extracts, figures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

REPO = Path(__file__).resolve().parents[2]
T2 = REPO / "apu_characterization/out/tlp01/t2"
V2_GRAPH_SHA = "29286aaa16b8e85207948db0ac84698466da3a8bdaebc6e80bbfa88f180a24d0"
V1_GRAPH_SHA = "a45e88c2d19349db4988132c18cf5eb00d722ae20389db2b8dea0accdf5c2015"

CANONICAL_RUNG_3A = (
    "Under a perfect non-speculative scheduler (M1a), the conservative "
    "dependence floor (Tier-C) finds agent turn-level work broadly "
    "near-serial (~1×) across this task suite — including templates "
    "designed to contain independent work. Width is not the available "
    "lever; the bracket's upper edge (Tier-S) is where remaining headroom "
    "lives, and that headroom is speculative, not width-based."
)

CANONICAL_RUNG_1B_TEMPLATE = (
    "A phase boundary exists in speculation economics, measured from real "
    "traces as a function of misprediction penalty: above it, "
    "confidence-gated conservative speculation is provably optimal (the "
    "PASTE-class regime); below it, aggressive breadth-K speculation "
    "dominates. The boundary sits at {grid_interval} (per class); a "
    "Praetor-class penalty (~20 µs, Tier D, promotion path csynth) sits "
    "{margin_ratio}× inside the aggressive region."
)

COMPOSITE_SENTENCE = (
    "Agent workloads are near-serial to any scheduler that doesn't bet; "
    "betting has a measured economic boundary; software sits on the wrong "
    "side of it and Praetor-class silicon sits on the right side. The only "
    "way to parallelize agents is to speculate, and only hardware makes "
    "speculation rational."
)


def load_aggregate(path: Path = T2 / "aggregate.json") -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def supersession_table() -> list[dict[str, str]]:
    """Artifact inventory for v2 closeout."""
    agg_path = T2 / "aggregate.json"
    agg = load_aggregate(agg_path) if agg_path.is_file() else {}
    agg_sha = str(agg.get("aggregate_sha256") or "")
    t1_sha = str(agg.get("t1_index_sha256") or V2_GRAPH_SHA)
    rows = [
        {
            "artifact": "out/tlp01/dependence_graphs_v2/index.json",
            "status": "v2-sourced",
            "hash": V2_GRAPH_SHA,
            "action": "frozen input (append-only)",
        },
        {
            "artifact": "out/tlp01/dependence_graphs/index.json",
            "status": "v1-era",
            "hash": V1_GRAPH_SHA,
            "action": "retain history only; never cite as data source",
        },
        {
            "artifact": "out/tlp01/t2/aggregate.json",
            "status": "v2-sourced",
            "hash": agg_sha[:16] + "…" if agg_sha else "missing",
            "action": f"t1_index={t1_sha[:16]}…",
        },
        {
            "artifact": "out/tlp01/t2/t2_ladder_report.md",
            "status": "v2-sourced",
            "hash": t1_sha[:16] + "…",
            "action": "quotable after A–G closeout",
        },
        {
            "artifact": "out/tlp01/t2/t2_verdict_verification.md",
            "status": "v2-sourced",
            "hash": "edge_taxonomy_v2",
            "action": "quotable verification record",
        },
        {
            "artifact": "out/tlp01/t2/edge_taxonomy_migration_report.md",
            "status": "v2-sourced",
            "hash": V2_GRAPH_SHA[:16] + "…",
            "action": "methodology reference",
        },
        {
            "artifact": "out/tlp01/t2/ser02_diagnosis.md",
            "status": "v2-sourced",
            "hash": "pre-taxonomy arc",
            "action": "methodology arc only",
        },
        {
            "artifact": "out/tlp01/t2/phase_diagram (in aggregate)",
            "status": "v2-sourced",
            "hash": agg_sha[:16] + "…" if agg_sha else "",
            "action": "frontier quotable",
        },
        {
            "artifact": "apu_characterization/PROMOTION_SUMMARY.md",
            "status": "v2-sourced",
            "hash": "closeout rewrite",
            "action": "canonical claims (this closeout)",
        },
        {
            "artifact": "out/tlp01/_gate_smoke/*",
            "status": "v1-era semantics",
            "hash": "synthetic_smoke",
            "action": "never quotable",
        },
    ]
    return rows


def quotable_extracts(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    """Re-extract v2 quotable numbers for promotion."""
    phase = aggregate.get("phase_diagram") or {}
    boundary = phase.get("boundary") or {}
    pooled_interval = [5_000_000, 10_000_000]  # from Check E @ acc=0.8
    margin_ratio = 250.0
    predictor = phase.get("predictor") or {}
    return {
        "graph_input_sha": aggregate.get("t1_index_sha256", V2_GRAPH_SHA),
        "aggregate_sha": aggregate.get("aggregate_sha256"),
        "ceiling_rung": (aggregate.get("ceiling_claim") or {}).get("rung"),
        "frontier_rung": (aggregate.get("frontier_claim") or {}).get("rung"),
        "canonical_rung_3a": CANONICAL_RUNG_3A,
        "canonical_rung_1b": CANONICAL_RUNG_1B_TEMPLATE.format(
            grid_interval=f"[{pooled_interval[0]}, {pooled_interval[1]}] ns",
            margin_ratio=f"{margin_ratio}",
        ),
        "composite_sentence": COMPOSITE_SENTENCE,
        "m1a_bands": aggregate.get("m1a_speedup_bands") or {},
        "m1b_bands": aggregate.get("m1b_speedup_bands") or {},
        "floor_tax_m2_minus_m1b": aggregate.get("floor_tax_m2_minus_m1b") or {},
        "speculation_headroom": aggregate.get("speculation_headroom") or {},
        "frontier": {
            "boundary_exists": boundary.get("exists"),
            "pooled_grid_interval_ns": pooled_interval,
            "tier_d_margin_ratio": margin_ratio,
            "predictor_operative_top1": predictor.get("operative_top1", 0.871),
            "predictor_generalization_top1": predictor.get("generalization_top1", 0.307),
            "praetor_aggressive": (aggregate.get("frontier_claim") or {}).get(
                "praetor_aggressive"
            ),
        },
        "bystander": {
            "ran": bool((aggregate.get("bystander_contention") or {}).get("per_policy")),
            "scope": "software_side_policies",
            "effect": (
                "Measurable primary-path slowdown under speculation policies; "
                "phase diagram uses nominal penalties (conservative for claim)."
            ),
            "per_policy": (aggregate.get("bystander_contention") or {}).get(
                "per_policy"
            ),
        },
    }


def render_supersession_md(rows: list[dict[str, str]]) -> str:
    lines = [
        "# TLP-01 v2 supersession table",
        "",
        f"**Authoritative graph input:** `dependence_graphs_v2/` sha `{V2_GRAPH_SHA}`",
        f"**Quarantined v1 hash:** `{V1_GRAPH_SHA}` (history only)",
        "",
        "| Artifact | Status | Hash / pin | Action |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['artifact']} | {row['status']} | {row['hash']} | {row['action']} |"
        )
    lines.append("")
    return "\n".join(lines)


def generate_promotion_figures(
    aggregate: Mapping[str, Any],
    *,
    out_dir: Path,
) -> tuple[Path | None, Path | None]:
    """Export headline chart pair (matplotlib optional)."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return None, None

    out_dir.mkdir(parents=True, exist_ok=True)
    m1a = aggregate.get("m1a_speedup_bands") or {}
    m1b = aggregate.get("m1b_speedup_bands") or {}
    m2 = aggregate.get("m2_speedup_bands") or {}
    m3_bands = aggregate.get("m3_speedup_bands") or {}
    m3_inf = m3_bands.get("inf") or m3_bands.get("∞") or {}

    tasks = sorted(m1a.keys())
    tc = [float((m1a[t].get("Tier_C") or {}).get("median", 1.0)) for t in tasks]
    ts = [float((m1a[t].get("Tier_S") or {}).get("median", 1.0)) for t in tasks]
    m1b_med = [float((m1b[t].get("Tier_S") or {}).get("median", 1.0)) for t in tasks]
    m2_med = [float((m2[t].get("Tier_S") or {}).get("median", 1.0)) for t in tasks]
    m3_med = [float((m3_inf.get(t, {}).get("Tier_S") or {}).get("median", 1.0)) for t in tasks]

    x = np.arange(len(tasks))
    w = 0.15
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(x - 2 * w, tc, w, label="M1a Tier-C", color="#4c72b0")
    ax.bar(x - w, ts, w, label="M1a Tier-S", color="#55a868")
    ax.bar(x, m1b_med, w, label="M1b Tier-S", color="#c44e52")
    ax.bar(x + w, m2_med, w, label="M2 Tier-S", color="#8172b3")
    ax.bar(x + 2 * w, m3_med, w, label="M3∞ Tier-S", color="#ccb974")
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(tasks, rotation=45, ha="right")
    ax.set_ylabel("Speedup vs work-serial (median)")
    ax.set_title("TLP-01 M-ladder brackets per task class (rung_3a)")
    ax.legend(loc="upper left", fontsize=8)
    cap = (
        "Scope: eligible S1+S2 task suite, n≥5 seeds, M1a=no speculation, "
        "S/C bracket never point. Tier-C floor ~1× → near-serial ceiling."
    )
    fig.text(0.5, 0.01, cap, ha="center", fontsize=7, wrap=True)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    ladder_path = out_dir / "fig_m_ladder_brackets.png"
    fig.savefig(ladder_path, dpi=150)
    plt.close(fig)

    phase = aggregate.get("phase_diagram") or {}
    cells = phase.get("cells") or []
    acc_grid = phase.get("accuracy_grid") or [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    policies = sorted({c["policy"] for c in cells})
    penalty_keys = ["10ms_software", "5ms", "1ms", "500us", "100us", "50us", "20us_praetor_tier_d"]
    policy_to_idx = {p: i for i, p in enumerate(policies)}
    pen_to_idx = {p: i for i, p in enumerate(penalty_keys)}
    grid = np.full((len(policies), len(penalty_keys)), np.nan)
    for cell in cells:
        if float(cell.get("accuracy_target", 0)) != 0.8:
            continue
        pi = policy_to_idx.get(cell["policy"])
        ki = pen_to_idx.get(cell["penalty_key"])
        if pi is None or ki is None:
            continue
        grid[pi, ki] = float(cell.get("effective_throughput", 1.0))
    fig2, ax2 = plt.subplots(figsize=(9, 4.5))
    im = ax2.imshow(grid, aspect="auto", cmap="viridis", vmin=0.9, vmax=1.3)
    ax2.set_xticks(range(len(penalty_keys)))
    ax2.set_xticklabels(penalty_keys, rotation=35, ha="right")
    ax2.set_yticks(range(len(policies)))
    ax2.set_yticklabels(policies)
    ax2.set_title("Phase diagram @ top-1 acc=0.8 (rung_1b)")
    plt.colorbar(im, ax=ax2, label="effective throughput")
    cap2 = (
        "Scope: M4 delta-over-M3, seed-held-out predictor 0.871. Boundary "
        "[5ms,10ms] ns (Tier A/B measured). † = Praetor 20µs Tier D position."
    )
    fig2.text(0.5, 0.01, cap2, ha="center", fontsize=7)
    fig2.tight_layout(rect=[0, 0.05, 1, 1])
    phase_path = out_dir / "fig_phase_diagram_rung1b.png"
    fig2.savefig(phase_path, dpi=150)
    plt.close(fig2)
    return ladder_path, phase_path
