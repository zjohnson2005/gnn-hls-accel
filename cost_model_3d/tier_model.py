"""Per-tier 3D cost model (Phase B, B1-B3).

Given a kernel graph, a tier assignment, and a TechConfig, produce the four
roadmap metrics: latency, energy/inference, peak temperature, TSV count.

The objectives are computed together because they are coupled (latency tuning
can create hotspots; energy tuning can blow the TSV budget) -- the staged
rungs B1/B2/B3 just decide which fields the caller looks at, not how they are
computed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

from .kernel_graph import KernelGraph
from .tech import TechConfig

LOGIC_TIER = 0
MEMORY_TIER = 1


@dataclass
class Metrics:
    latency_cycles: float
    latency_ns: float
    energy_pj: float
    energy_per_inf_nj: float
    peak_temp_c: float
    tsv_count: int
    tsv_over_budget: bool
    power_w: Dict[int, float]

    def as_row(self) -> Dict[str, float]:
        return {
            "latency_ns": round(self.latency_ns, 2),
            "energy_nj": round(self.energy_per_inf_nj, 3),
            "peak_temp_c": round(self.peak_temp_c, 2),
            "tsv_count": self.tsv_count,
            "tsv_over_budget": int(self.tsv_over_budget),
        }


def _pj_per_mac(tech: TechConfig, data_bits: int) -> float:
    return tech.pj_per_mac_ref * (data_bits / tech.ref_data_bits) ** tech.mac_precision_exp


def evaluate(
    graph: KernelGraph,
    assignment: Dict[str, int],
    tech: TechConfig,
    stacked: bool,
) -> Metrics:
    data_bits = int(graph.meta.get("data_bits", 16))
    pj_mac = _pj_per_mac(tech, data_bits)

    # ---------- energy + power bookkeeping ----------
    tier_energy: Dict[int, float] = {LOGIC_TIER: 0.0, MEMORY_TIER: 0.0}

    for n in graph.nodes:
        tier = assignment[n.name]
        compute_e = n.macs * pj_mac * n.activity
        # memory traffic: cheap only if a memory kernel lives on the memory tier
        on_mem_tier = stacked and (tier == MEMORY_TIER)
        byte_coeff = tech.pj_per_byte_near_mem if on_mem_tier else tech.pj_per_byte_far_mem
        mem_e = n.mem_bytes * byte_coeff
        tier_energy[tier] += compute_e + mem_e

    # ---------- seam transport ----------
    latency_cycles = sum(n.compute_cycles for n in graph.nodes)
    tsv_count = 0
    seam_energy = 0.0

    for e in graph.edges:
        cut = assignment[e.src] != assignment[e.dst]
        if stacked and cut:
            bit_coeff = tech.pj_per_bit_tsv
            latency_cycles += tech.intertier_latency_cycles
            latency_cycles += math.ceil(e.payload_bits_total / max(1, e.payload_bits_parallel))
            tsv_count += e.payload_bits_parallel
        elif stacked and not cut:
            bit_coeff = tech.pj_per_bit_tsv          # local short wire
        else:
            bit_coeff = tech.pj_per_bit_2d_wire      # flat-2D planar route
            latency_cycles += math.ceil(e.payload_bits_total / max(1, e.payload_bits_parallel))
        edge_e = e.payload_bits_total * bit_coeff
        seam_energy += edge_e
        # attribute seam energy to the endpoints' tiers
        tier_energy[assignment[e.src]] += edge_e / 2.0
        tier_energy[assignment[e.dst]] += edge_e / 2.0

    energy_pj = tier_energy[LOGIC_TIER] + tier_energy[MEMORY_TIER]

    # ---------- latency / throughput ----------
    latency_s = latency_cycles / tech.f_clk_hz
    f_inf = 1.0 / latency_s if latency_s > 0 else 0.0

    # ---------- thermal (compact RC) ----------
    r_couple = tech.r_couple_3d if stacked else tech.r_couple_2d
    power_w = {t: tier_energy[t] * 1e-12 * f_inf for t in (LOGIC_TIER, MEMORY_TIER)}
    t0 = tech.ambient_c + tech.r_self * power_w[LOGIC_TIER] + r_couple * power_w[MEMORY_TIER]
    t1 = tech.ambient_c + tech.r_self * power_w[MEMORY_TIER] + r_couple * power_w[LOGIC_TIER]
    peak_temp = max(t0, t1)

    return Metrics(
        latency_cycles=latency_cycles,
        latency_ns=latency_s * 1e9,
        energy_pj=energy_pj,
        energy_per_inf_nj=energy_pj * 1e-3,
        peak_temp_c=peak_temp,
        tsv_count=tsv_count,
        tsv_over_budget=tsv_count > tech.tsv_budget,
        power_w=power_w,
    )
