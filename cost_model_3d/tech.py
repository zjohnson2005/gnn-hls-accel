"""3D-IC technology configuration (Phase B).

All coefficients are illustrative, analytical-model values -- NOT silicon
measurements. They are chosen to be internally consistent and to encode the
first-order physics the roadmap names:

  * vertical interconnect (TSV / hybrid bond) is cheap in latency and energy
    per bit but costs area and is count-limited;
  * a memory-bound stage sitting on the memory tier avoids a long/expensive
    trip to memory (the core 3D-aware win);
  * stacked dies trap heat -> inter-tier thermal coupling is first-order.

Every number is a single place to retune, so a "crude model -> crude rules"
risk is explicit and auditable (see roadmap risks).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TechConfig:
    # ---- clocking ----
    f_clk_hz: float = 300e6              # 3.33 ns target

    # ---- compute energy ----
    pj_per_mac_ref: float = 0.30         # at the reference 16-bit datapath
    ref_data_bits: int = 16              # precision the coefficient is calibrated at
    mac_precision_exp: float = 1.6       # energy ~ (bits/ref)^exp (precision rule)

    # ---- memory energy (per byte of off-chip / cross-die traffic) ----
    pj_per_byte_near_mem: float = 4.0    # kernel on the memory tier
    pj_per_byte_far_mem: float = 20.0    # kernel must reach memory from logic tier

    # ---- inter-tier (seam) transport ----
    intertier_latency_cycles: int = 2    # TSV/hybrid-bond crossing pipeline depth
    pj_per_bit_tsv: float = 0.05         # vertical, short
    pj_per_bit_2d_wire: float = 0.50     # long planar route (flat-2D seam)
    tsv_area_um2: float = 25.0           # area per TSV (count-limited budget)
    tsv_budget: int = 4096               # max TSVs available across the seam

    # ---- thermal (compact RC, K/W) ----
    ambient_c: float = 25.0
    r_self: float = 0.45                 # tier self-heating
    r_couple_3d: float = 0.22            # stacked: neighbor heats this tier
    r_couple_2d: float = 0.02            # side-by-side dies barely couple

    # ---- area ----
    die_area_budget_um2: float = 4.0e6   # per-tier logic area budget


DEFAULT_TECH = TechConfig()
