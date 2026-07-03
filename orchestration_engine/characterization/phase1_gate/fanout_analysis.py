"""Wide fan-out (planner) analysis: adapt scatter vs scope the hardware claim."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from orchestration_engine.characterization.langgraph_react.timing import timing_for_preset
from orchestration_engine.characterization.phase1_gate.software_baseline import (
    hardware_scatter_us,
    optimized_software_us,
)

OPT_SPEEDUP = 4.0
BATCH_WIDTH = 8
V1_MAX_OUT_DEGREE = 8
PLANNER_FANOUTS = (64, 256)


@dataclass
class FanoutStrategy:
    name: str
    effective_out_degree: float
    per_completion_us: float
    notes: str
    v1_feasible: bool


@dataclass
class PlannerComparison:
    fanout: int
    decisions_per_wave: int
    langgraph_us_per_decision: float
    strategies: list[FanoutStrategy]
    verdict: str


def _per_completion_us(base: int, pen: int, out_degree: float, batch_width: int = 1) -> float:
    if batch_width <= 1:
        edges = out_degree
    else:
        edges = (out_degree + batch_width - 1) // batch_width
    return base + pen * edges


def analyze_planner_fanout(
    *,
    fanout: int,
    preset: str = "action_heavy",
    langgraph_us_per_decision: float = 1746.0,
    decisions_per_wave: int = 1,
) -> PlannerComparison:
    """Compare scatter strategies for a single planner → N workers completion wave."""
    t = timing_for_preset(preset, calibrated=True)
    base = t.orchestration_per_step_us
    pen = t.orchestration_live_task_penalty_us
    opt4_per = langgraph_us_per_decision / OPT_SPEEDUP

    strategies = [
        FanoutStrategy(
            name="flat_csr_scatter",
            effective_out_degree=float(fanout),
            per_completion_us=_per_completion_us(base, pen, fanout),
            notes=f"Current HLS loop: O({fanout}) edge updates at II=1.",
            v1_feasible=fanout <= V1_MAX_OUT_DEGREE,
        ),
        FanoutStrategy(
            name="pipelined_batch_scatter",
            effective_out_degree=fanout / BATCH_WIDTH,
            per_completion_us=_per_completion_us(base, pen, fanout, BATCH_WIDTH),
            notes=f"{BATCH_WIDTH} successors/cycle via partitioned pred RAM + unrolled decrement.",
            v1_feasible=fanout <= 64,
        ),
        FanoutStrategy(
            name="barrier_graph_rewrite",
            effective_out_degree=1.0,
            per_completion_us=_per_completion_us(base, pen, 1.0)
            + fanout * _per_completion_us(base, pen, 1.0),
            notes=(
                "Planner→barrier (1 edge); each worker completion scatter-to-barrier (1 edge). "
                "Amortizes wide launch without one O(N) scatter; needs compiler/graph lowering."
            ),
            v1_feasible=True,
        ),
        FanoutStrategy(
            name="tree_launch (8×8 for 64, 16×16 for 256)",
            effective_out_degree=8.0 if fanout == 64 else 16.0,
            per_completion_us=_per_completion_us(
                base, pen, 8.0 if fanout == 64 else 16.0
            ),
            notes="Restructure planner into two-level coordinator tree; bounded per-node degree.",
            v1_feasible=True,
        ),
    ]

    beats_opt4 = [
        s
        for s in strategies
        if s.per_completion_us < opt4_per
    ]
    if fanout <= V1_MAX_OUT_DEGREE:
        verdict = (
            f"Fan-out {fanout} is within v1 flat-scatter scope (≤{V1_MAX_OUT_DEGREE}). "
            "No special unit required."
        )
    else:
        batched = next(s for s in strategies if s.name == "pipelined_batch_scatter")
        flat = next(s for s in strategies if s.name == "flat_csr_scatter")
        tree = next(s for s in strategies if s.name.startswith("tree_launch"))
        winners = [s for s in (batched, tree) if s.per_completion_us < opt4_per]
        if batched.per_completion_us < opt4_per:
            verdict = (
                f"Fan-out {fanout} exceeds flat v1 scope (>{V1_MAX_OUT_DEGREE}) but **8-wide "
                f"batched scatter** ({batched.per_completion_us:.0f} µs) beats 4× optimized "
                f"({opt4_per:.0f} µs). Phase 2 should add a pipelined batch scatter unit — "
                "not a thesis scope exclusion."
            )
        elif tree.per_completion_us < opt4_per:
            verdict = (
                f"Fan-out {fanout}: 8-wide batch ({batched.per_completion_us:.0f} µs) loses to "
                f"4× opt ({opt4_per:.0f} µs), but **tree-launch lowering** "
                f"({tree.per_completion_us:.0f} µs, max degree {tree.effective_out_degree:.0f}) "
                "wins. Requires host-side graph rewrite before hardware; flat/batch silicon unchanged."
            )
        elif flat.per_completion_us < opt4_per:
            verdict = (
                f"Fan-out {fanout}: flat scatter ({flat.per_completion_us:.0f} µs) beats "
                f"4× opt ({opt4_per:.0f} µs) per completion but needs graph lowering for v1."
            )
        else:
            verdict = (
                f"Fan-out {fanout}: no practical scatter variant beats 4× optimized software "
                f"({opt4_per:.0f} µs/decision) at c≈500. Explicit limitation / future work."
            )
        _ = winners

    return PlannerComparison(
        fanout=fanout,
        decisions_per_wave=decisions_per_wave,
        langgraph_us_per_decision=langgraph_us_per_decision,
        strategies=strategies,
        verdict=verdict,
    )


def build_fanout_resolution(
    *,
    langgraph_us_per_decision_at_c500: float = 1746.0,
) -> dict:
    planners = [
        analyze_planner_fanout(
            fanout=f,
            langgraph_us_per_decision=langgraph_us_per_decision_at_c500,
        )
        for f in PLANNER_FANOUTS
    ]

    return {
        "v1_product_scope_max_out_degree": V1_MAX_OUT_DEGREE,
        "batch_width": BATCH_WIDTH,
        "design_decision": (
            "Phase 2 v1: flat CSR scatter for out-degree ≤ 8 (ReAct chains, modest trees). "
            "Planner fan-out 64: extend routing unit with 8-wide pipelined batch scatter "
            "(same pred-decrement semantics, inner loop unroll factor 8). "
            "Fan-out 256: unstructured single-step planner launch is out of v1 silicon; "
            "use tree-launch graph lowering (max degree 16) or 16-wide batch in a later revision."
        ),
        "routing_unit_implications": [
            "Flat scatter: single pred_remaining[] port, II=1 per edge — sufficient for d≤8.",
            "8-wide batch unit: unroll inner scatter loop factor=8, cyclic partition preds — "
            "extends reach to d≤64 without changing O(out-degree) asymptotics.",
            "Barrier lowering (software): converts planner→N into N+1 single-edge scatters — "
            "same hardware, different graph IR; belongs in host compiler pass.",
        ],
        "planner_comparisons": [asdict(p) for p in planners],
    }


def render_fanout_markdown(data: dict) -> str:
    lines = [
        "## 8. Fan-out resolution (planner stress cases)",
        "",
        f"**Design decision:** {data['design_decision']}",
        "",
        f"V1 scope: out-degree ≤ **{data['v1_product_scope_max_out_degree']}** (flat scatter).",
        "",
        "### Routing unit implications",
        "",
    ]
    for item in data["routing_unit_implications"]:
        lines.append(f"- {item}")

    for block in data["planner_comparisons"]:
        lines.extend(["", f"### planner_fanout_{block['fanout']}", ""])
        lines.append(f"_LangGraph ≈ {block['langgraph_us_per_decision']:.0f} µs/decision; "
                      f"4× opt ≈ {block['langgraph_us_per_decision']/OPT_SPEEDUP:.0f} µs/decision_")
        lines.append("")
        lines.append("| strategy | eff. degree | µs/completion | v1? |")
        lines.append("|----------|-------------|---------------|-----|")
        for s in block["strategies"]:
            v1 = "yes" if s["v1_feasible"] else "no"
            lines.append(
                f"| {s['name']} | {s['effective_out_degree']:.1f} | "
                f"{s['per_completion_us']:.0f} | {v1} |"
            )
        lines.extend(["", f"**Verdict:** {block['verdict']}"])

    return "\n".join(lines)
