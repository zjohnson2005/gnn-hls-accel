"""Hardware vs optimized-software crossover surface (concurrency × out-degree)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from orchestration_engine.characterization.langgraph_react.timing import timing_for_preset
from orchestration_engine.characterization.phase1_gate.metrics import (
    cores_equivalent,
    orchestration_decisions,
    orchestration_us,
    wall_batch_us,
)
from orchestration_engine.characterization.phase1_gate.software_baseline import (
    compare_schedulers,
    hardware_scatter_us,
    optimized_software_us,
)
from orchestration_engine.characterization.taxonomy import WorkloadProfile

SWEEP_CONCURRENCY = [1, 10, 100, 500, 1000, 5000]
SWEEP_OUT_DEGREE = [1.0, 1.5, 4.0, 8.0, 16.0, 64.0, 256.0]
OPT_SPEEDUP = 4.0
BATCH_WIDTH = 8


@dataclass
class CrossoverCell:
    concurrency: int
    out_degree: float
    wall_batch_us: int
    decisions: int
    cores_langgraph: float
    cores_optimized_4x: float
    cores_hw_flat: float
    cores_hw_batched: float
    hw_flat_beats_opt4: bool
    hw_batched_beats_opt4: bool


@dataclass
class CrossoverSummary:
    min_concurrency_hw_flat_beats_opt4_at_react: int | None
    min_concurrency_hw_flat_beats_opt4_at_degree: dict[str, int | None]
    max_out_degree_hw_flat_beats_opt4_at_c500: float | None
    max_out_degree_hw_batched_beats_opt4_at_c500: float | None
    react_degree: float
    headline: str


def _cell(
    profile: WorkloadProfile,
    preset: str,
    out_degree: float,
) -> CrossoverCell:
    wall = wall_batch_us(profile)
    decisions = max(1, orchestration_decisions(profile))
    measured = orchestration_us(profile)
    opt4 = optimized_software_us(measured, OPT_SPEEDUP)
    hw_flat = hardware_scatter_us(preset, decisions, out_degree, calibrated=True)
    hw_batched = hardware_scatter_us(
        preset,
        decisions,
        out_degree,
        calibrated=True,
        batch_width=BATCH_WIDTH,
    )
    cores_lg = measured / wall if wall else 0.0
    cores_opt = opt4 / wall if wall else 0.0
    cores_flat = hw_flat / wall if wall else 0.0
    cores_batched = hw_batched / wall if wall else 0.0
    return CrossoverCell(
        concurrency=profile.concurrency,
        out_degree=out_degree,
        wall_batch_us=wall,
        decisions=decisions,
        cores_langgraph=round(cores_lg, 4),
        cores_optimized_4x=round(cores_opt, 4),
        cores_hw_flat=round(cores_flat, 4),
        cores_hw_batched=round(cores_batched, 4),
        hw_flat_beats_opt4=cores_flat < cores_opt,
        hw_batched_beats_opt4=cores_batched < cores_opt,
    )


def build_crossover_grid(
    profiles: dict[tuple[str, int], WorkloadProfile],
    preset: str = "action_heavy",
) -> dict:
    """Grid over measured concurrency sweeps × parametric out-degree."""
    react_degree = 1.5
    by_conc: list[dict] = []
    grid: list[dict] = []

    for conc in SWEEP_CONCURRENCY:
        prof = profiles.get((preset, conc))
        if not prof:
            continue
        row_cells = []
        for deg in SWEEP_OUT_DEGREE:
            cell = _cell(prof, preset, deg)
            row_cells.append(asdict(cell))
            grid.append(asdict(cell))
        by_conc.append(
            {
                "concurrency": conc,
                "cores_langgraph": row_cells[0]["cores_langgraph"],
                "cells": row_cells,
            }
        )

    # Analytical crossover: (base + p*d) < (base + p*L(c)) / 4  using avg live-task model
    t = timing_for_preset(preset, calibrated=True)
    base = t.orchestration_per_step_us
    pen = t.orchestration_live_task_penalty_us

    def avg_live_tasks(conc: int) -> float:
        """Mean live_tasks at orchestration steps across staggered agents (mock model)."""
        if conc <= 1:
            return 1.0
        total = 0.0
        steps = max(1, t.react_steps)
        tool_steps = max(1, steps // 2)
        for idx in range(conc):
            live = 1 + idx // 2
            for _ in range(steps):
                total += live
                live = min(live + 1, 512)
        return total / (conc * steps)

    analytic_rows = []
    for conc in SWEEP_CONCURRENCY:
        live = avg_live_tasks(conc)
        lg_per = base + pen * live
        opt4_per = lg_per / OPT_SPEEDUP
        cross_deg_flat = None
        if pen > 0:
            cross_deg_flat = (opt4_per - base) / pen
        cross_deg_batched = None
        if pen > 0:
            cross_deg_batched = (opt4_per - base) / pen * BATCH_WIDTH
        cross_conc = None
        if pen > 0:
            # base + pen*d = (base + pen*live(conc))/4  solve conc implicitly via live(conc)
            for trial in SWEEP_CONCURRENCY:
                if avg_live_tasks(trial) * pen + base > 4 * (base + pen * react_degree):
                    cross_conc = trial
                    break
        analytic_rows.append(
            {
                "concurrency": conc,
                "avg_live_tasks": round(live, 1),
                "langgraph_us_per_decision": round(lg_per, 1),
                "opt4_us_per_decision": round(opt4_per, 1),
                "analytic_out_degree_hw_beats_opt4_flat": (
                    round(cross_deg_flat, 2) if cross_deg_flat is not None else None
                ),
                "analytic_out_degree_hw_beats_opt4_batched_w8": (
                    round(cross_deg_batched, 2) if cross_deg_batched is not None else None
                ),
            }
        )

    summary = _summarize(grid, react_degree)
    return {
        "sweep_concurrency": SWEEP_CONCURRENCY,
        "sweep_out_degree": SWEEP_OUT_DEGREE,
        "opt_speedup": OPT_SPEEDUP,
        "batch_width": BATCH_WIDTH,
        "react_avg_out_degree": react_degree,
        "by_concurrency": by_conc,
        "grid": grid,
        "analytic_live_task_model": analytic_rows,
        "summary": asdict(summary),
    }


def _summarize(grid: list[dict], react_degree: float) -> CrossoverSummary:
    react_cells = [c for c in grid if abs(c["out_degree"] - react_degree) < 0.01]
    min_conc = None
    for c in sorted(react_cells, key=lambda x: x["concurrency"]):
        if c["hw_flat_beats_opt4"]:
            min_conc = c["concurrency"]
            break

    by_degree: dict[str, int | None] = {}
    for deg in (1.0, 4.0, 8.0, 16.0):
        cells = [c for c in grid if c["out_degree"] == deg]
        found = None
        for c in sorted(cells, key=lambda x: x["concurrency"]):
            if c["hw_flat_beats_opt4"]:
                found = c["concurrency"]
                break
        by_degree[str(int(deg) if deg == int(deg) else deg)] = found

    c500 = [c for c in grid if c["concurrency"] == 500]
    max_flat = None
    max_batched = None
    for c in sorted(c500, key=lambda x: x["out_degree"]):
        if c["hw_flat_beats_opt4"]:
            max_flat = c["out_degree"]
        if c["hw_batched_beats_opt4"]:
            max_batched = c["out_degree"]

    if min_conc is None:
        headline = (
            "At ReAct out-degree (~1.5), flat hardware scatter does NOT beat 4× optimized "
            "software in the measured sweep — narrow hardware case."
        )
    elif min_conc <= 10:
        headline = (
            f"Flat hardware scatter beats 4× optimized software at concurrency ≥ {min_conc} "
            f"for ReAct-scale out-degree (~{react_degree})."
        )
    else:
        headline = (
            f"Hardware crossover begins at concurrency ~{min_conc} (ReAct out-degree). "
            "Below that, optimized software on a spare core wins."
        )

    return CrossoverSummary(
        min_concurrency_hw_flat_beats_opt4_at_react=min_conc,
        min_concurrency_hw_flat_beats_opt4_at_degree=by_degree,
        max_out_degree_hw_flat_beats_opt4_at_c500=max_flat,
        max_out_degree_hw_batched_beats_opt4_at_c500=max_batched,
        react_degree=react_degree,
        headline=headline,
    )


def render_crossover_markdown(data: dict) -> str:
    summary = data["summary"]
    lines = [
        "## 7. Trace-calibrated crossover (LangGraph projection)",
        "",
        "_Secondary evidence — calibrates mock scaling against traces; primary proof is check 9._",
        "",
        f"**Headline:** {summary['headline']}",
        "",
        f"- ReAct avg out-degree: **{data['react_avg_out_degree']}**",
        f"- Optimized software model: LangGraph measured / **{data['opt_speedup']:.0f}×**",
        f"- Hardware batched scatter: **{data['batch_width']}** successors/cycle",
        "",
        "### Crossover at ReAct out-degree (cores equivalent)",
        "",
        "| c | LangGraph | 4× opt | HW flat | HW batched | HW flat wins? |",
        "|---|-----------|--------|---------|------------|---------------|",
    ]
    for row in data["by_concurrency"]:
        react_cell = next(
            (c for c in row["cells"] if abs(c["out_degree"] - data["react_avg_out_degree"]) < 0.01),
            None,
        )
        if not react_cell:
            continue
        win = "yes" if react_cell["hw_flat_beats_opt4"] else "no"
        lines.append(
            f"| {row['concurrency']} | {react_cell['cores_langgraph']:.3f} | "
            f"{react_cell['cores_optimized_4x']:.3f} | {react_cell['cores_hw_flat']:.3f} | "
            f"{react_cell['cores_hw_batched']:.3f} | {win} |"
        )

    lines.extend(
        [
            "",
            "### Max out-degree where hardware beats 4× opt at c=500",
            "",
            f"- Flat scatter: out-degree ≤ **{summary['max_out_degree_hw_flat_beats_opt4_at_c500']}**",
            f"- 8-wide batched scatter: out-degree ≤ **{summary['max_out_degree_hw_batched_beats_opt4_at_c500']}**",
            "",
            "### Full grid (HW flat beats 4× opt?)",
            "",
            "| c \\ out-deg | "
            + " | ".join(str(int(d) if d == int(d) else d) for d in data["sweep_out_degree"])
            + " |",
            "|---|" + "|".join("---" for _ in data["sweep_out_degree"]) + "|",
        ]
    )
    for conc in data["sweep_concurrency"]:
        cells = [c for c in data["grid"] if c["concurrency"] == conc]
        if not cells:
            continue
        marks = []
        for deg in data["sweep_out_degree"]:
            cell = next(c for c in cells if c["out_degree"] == deg)
            marks.append("✓" if cell["hw_flat_beats_opt4"] else "·")
        lines.append(f"| {conc} | " + " | ".join(marks) + " |")

    lines.append("")
    lines.append("_✓ = flat hardware cores < 4× optimized cores_")
    return "\n".join(lines)
