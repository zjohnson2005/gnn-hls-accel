"""B1-B3 core experiment: the single comparative table for a fixed EGNN.

Runs the three arms on one EGNN kernel graph and reports all four metrics:

  flat_2d   -- 2D reference (no stacking)
  blind_3d  -- stacked but partition-blind (all logic on the logic tier)
  aware_3d  -- HLS-level partition: memory-bound k_magg on the memory tier
  best_3d   -- constrained search optimum (energy min s.t. TSV + temp ceiling)

The staged rungs share one computation (the metrics are coupled); B1 reads the
latency column, B2 adds energy, B3 adds peak_temp + TSV. The headline the
roadmap predicts: blind_3d can hurt (hotspot / TSV blowout) while aware_3d turns
3D into an energy win without sacrificing latency.

    python -m cost_model_3d.experiment

Replace the analytical kernel-graph numbers with csynth/activity values from a
real per-tier HLS run to harden the table; the arms and metrics are unchanged.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .kernel_graph import (
    KernelGraph,
    egnn_kernel_graph,
    egnn_kernel_graph_measured,
)
from .partition import aware_3d, blind_3d, flat_2d, best_aware_partition, evaluate_arm
from .tech import DEFAULT_TECH, TechConfig
from .tier_model import LOGIC_TIER, MEMORY_TIER, Metrics


_COLS = ["latency_ns", "energy_nj", "peak_temp_c", "tsv_count", "tsv_over_budget"]


def run_arms(graph: KernelGraph, tech: TechConfig) -> Dict[str, Metrics]:
    arms = {
        "flat_2d": flat_2d(graph),
        "blind_3d": blind_3d(graph),
        "aware_3d": aware_3d(graph),
    }
    out: Dict[str, Metrics] = {name: evaluate_arm(graph, arm, tech)
                               for name, arm in arms.items()}
    (best_assign, _), best_m = best_aware_partition(graph, tech)
    out["best_3d"] = best_m
    out["_best_assign"] = best_assign  # type: ignore[assignment]
    return out


def _fmt_table(results: Dict[str, Metrics]) -> str:
    names = [n for n in ("flat_2d", "blind_3d", "aware_3d", "best_3d") if n in results]
    w = 12
    head = "arm".ljust(10) + "".join(c.rjust(w) for c in _COLS)
    lines = [head, "-" * len(head)]
    for n in names:
        row = results[n].as_row()
        line = n.ljust(10) + "".join(str(row[c]).rjust(w) for c in _COLS)
        lines.append(line)
    return "\n".join(lines)


def _headline(results: Dict[str, Metrics]) -> str:
    flat = results["flat_2d"]
    blind = results["blind_3d"]
    aware = results["aware_3d"]

    def ratio(a: float, b: float) -> float:
        return a / b if b else float("inf")

    e_blind = ratio(blind.energy_per_inf_nj, flat.energy_per_inf_nj)
    e_aware = ratio(aware.energy_per_inf_nj, flat.energy_per_inf_nj)
    l_aware = ratio(aware.latency_ns, flat.latency_ns)
    msgs = [
        f"energy vs 2D:  3D-blind x{e_blind:.2f},  3D-aware x{e_aware:.2f} "
        f"(<1.0 = win)",
        f"latency vs 2D: 3D-aware x{l_aware:.2f}",
        f"peak temp:     2D {flat.peak_temp_c:.1f}C, blind {blind.peak_temp_c:.1f}C, "
        f"aware {aware.peak_temp_c:.1f}C",
        f"TSV:           blind {blind.tsv_count} (over_budget={int(blind.tsv_over_budget)}), "
        f"aware {aware.tsv_count} (over_budget={int(aware.tsv_over_budget)})",
    ]
    verdict = (
        "FINDING: 3D-aware HLS partition converts 3D into an energy win"
        if e_aware < 1.0 and l_aware <= 1.05
        else "FINDING: 3D-aware advantage is marginal for this configuration"
    )
    if e_blind >= 1.0 or blind.tsv_over_budget:
        verdict += "; 3D-blind partitioning hurts (the HLS-level decision is what matters)"
    return "\n".join(msgs + ["", verdict])


def main() -> None:
    tech = DEFAULT_TECH
    graph = egnn_kernel_graph_measured()
    print("=== B1-B3 fixed-EGNN 3D partition comparison ===")
    print(f"per-kernel QoR source: {graph.meta.get('qor_source', 'analytical')}")
    print(f"compute/memory ratio = {graph.compute_memory_ratio():.3f} "
          f"(MAC per memory byte)\n")
    results = run_arms(graph, tech)
    print(_fmt_table(results))
    print()
    print(_headline(results))
    best_assign = results.get("_best_assign")
    if best_assign:
        placement = {n: ("mem" if t == MEMORY_TIER else "logic")
                     for n, t in best_assign.items()}  # type: ignore[union-attr]
        print(f"\nbest_3d placement: {placement}")


if __name__ == "__main__":
    main()
