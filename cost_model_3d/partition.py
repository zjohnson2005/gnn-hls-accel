"""Tier-partitioning arms and search (Phase B).

Three arms, defined to isolate exactly what HLS-level 3D-awareness buys:

  flat_2d   reference: one planar die, DRAM off-chip (far memory), low thermal
            coupling. No vertical interconnect.

  blind_3d  the naive "3D = just stack DRAM on top" baseline: dies are stacked
            (cheap vertical access, but high coupling) yet NO kernel is moved
            down -- all logic stays on the logic tier. Every memory-bound
            kernel's traffic crosses TSVs (blowout) and all power lands on one
            tier (hotspot). This is 3D with no HLS-level semantic knowledge.

  aware_3d  the HLS-level decision: push memory-bound kernels onto the memory
            tier (near DRAM) and keep compute on the logic tier. Only the
            low-bandwidth aggregate<->combine seam crosses the TSVs, power is
            split across tiers, and memory traffic is local.

`best_aware_partition` enumerates assignments and picks the lowest-energy one
that respects the TSV budget and an accuracy-fixed peak-temp ceiling -- the
constrained (epsilon-constraint) form the roadmap calls out.
"""

from __future__ import annotations

import itertools
from typing import Dict, Optional, Tuple

from .kernel_graph import KernelGraph
from .tier_model import LOGIC_TIER, MEMORY_TIER, Metrics, evaluate
from .tech import TechConfig

Arm = Tuple[Dict[str, int], bool]   # (assignment, stacked)


def flat_2d(graph: KernelGraph) -> Arm:
    return ({n.name: LOGIC_TIER for n in graph.nodes}, False)


def blind_3d(graph: KernelGraph) -> Arm:
    # stacked, but nothing is repartitioned: all logic on the logic tier.
    return ({n.name: LOGIC_TIER for n in graph.nodes}, True)


def aware_3d(graph: KernelGraph) -> Arm:
    assign = {
        n.name: (MEMORY_TIER if n.category == "memory" else LOGIC_TIER)
        for n in graph.nodes
    }
    return (assign, True)


def best_aware_partition(
    graph: KernelGraph,
    tech: TechConfig,
    temp_ceiling_c: float = 95.0,
) -> Tuple[Arm, Metrics]:
    """Enumerate all stacked assignments; minimize energy s.t. TSV + temp.

    Small kernel counts make brute force exact and cheap; for larger graphs
    this is where the B4 surrogate replaces the inner evaluate() call.
    """
    names = [n.name for n in graph.nodes]
    best: Optional[Tuple[Arm, Metrics]] = None
    best_feasible: Optional[Tuple[Arm, Metrics]] = None

    for bits in itertools.product((LOGIC_TIER, MEMORY_TIER), repeat=len(names)):
        assign = dict(zip(names, bits))
        m = evaluate(graph, assign, tech, stacked=True)
        cand = ((assign, True), m)
        if best is None or m.energy_pj < best[1].energy_pj:
            best = cand
        feasible = (not m.tsv_over_budget) and (m.peak_temp_c <= temp_ceiling_c)
        if feasible and (best_feasible is None
                         or m.energy_pj < best_feasible[1].energy_pj):
            best_feasible = cand

    return best_feasible if best_feasible is not None else best


def evaluate_arm(graph: KernelGraph, arm: Arm, tech: TechConfig) -> Metrics:
    assign, stacked = arm
    return evaluate(graph, assign, tech, stacked)
