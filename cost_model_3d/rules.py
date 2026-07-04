"""B5: extract transferable 3D-friendly GNN design rules from the B4 sweep.

A rule (vs an observation) ties one architectural knob to the 3D benefit and
names a physical cause. We test the three the roadmap proposes, each as a
signed correlation plus a crossover threshold on accuracy-feasible designs, with
benefit always measured against each design's own 2D baseline:

  seam rule       benefit grows as the aggregate->combine seam bandwidth shrinks
                  relative to aggregate memory traffic. Cause: less payload over
                  the (latency/energy-cheap but count-limited) TSV cut.

  balance rule    the win survives only while per-tier power imbalance stays
                  below a threshold. Cause: a lopsided partition recreates the
                  single-tier hotspot 3D was meant to relieve.

  precision rule  lower datapath precision compounds the win. Cause: fewer bits
                  shrink both the TSV payload and per-tier dynamic power.

    python -m cost_model_3d.rules
"""

import math
from typing import Callable, List, Tuple

from .kernel_graph import egnn_kernel_graph
from .partition import best_aware_partition
from .sweep import SweepRecord, run_sweep
from .tech import DEFAULT_TECH


def _pearson(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    sxx = sum((xs[i] - mx) ** 2 for i in range(n))
    syy = sum((ys[i] - my) ** 2 for i in range(n))
    if sxx <= 1e-12 or syy <= 1e-12:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


def _crossover(records: List[SweepRecord], knob: Callable[[SweepRecord], float]
               ) -> Tuple[float, float]:
    """Return (knob value where mean benefit crosses 1.0, direction).

    Bins designs by the knob and reports the boundary between benefit<1 and
    benefit>=1 -- the conditional 'helps only when X' the roadmap wants.
    """
    pts = sorted(((knob(r), r.energy_benefit) for r in records), key=lambda t: t[0])
    cross = float("nan")
    for i in range(1, len(pts)):
        if (pts[i - 1][1] - 1.0) * (pts[i][1] - 1.0) < 0:
            cross = (pts[i - 1][0] + pts[i][0]) / 2.0
            break
    direction = 1.0 if pts[-1][1] >= pts[0][1] else -1.0
    return cross, direction


def _power_imbalance(r: SweepRecord) -> float:
    """Recompute the best-3D per-tier power imbalance for a design record."""
    g = egnn_kernel_graph(
        num_nodes=r.num_nodes, num_edges=r.num_nodes * r.edges_per_node,
        h_dim=r.h_dim, msg_dim=r.msg_dim, hid=r.hid, data_bits=r.data_bits,
    )
    (_, _), m = best_aware_partition(g, DEFAULT_TECH)
    p = list(m.power_w.values())
    tot = sum(p)
    return abs(p[0] - p[1]) / tot if tot > 0 else 0.0


def _seam_ratio(r: SweepRecord) -> float:
    """Seam bandwidth relative to aggregate memory traffic (both in bits)."""
    mem_bits = r.mem_bytes_total * 8
    return r.seam_bits_total / mem_bits if mem_bits else 0.0


def analyze(records: List[SweepRecord]) -> None:
    feasible = [r for r in records if r.acc_feasible]
    print(f"=== B5 design-rule extraction ({len(feasible)} accuracy-feasible "
          f"designs) ===\n")

    # ---- seam rule ----
    sr = [_seam_ratio(r) for r in feasible]
    ben = [r.energy_benefit for r in feasible]
    r_seam = _pearson(sr, ben)
    x_seam, _ = _crossover(feasible, _seam_ratio)
    print("[seam rule]")
    print(f"  corr(seam_ratio, energy_benefit) = {r_seam:+.3f} "
          f"(expect negative: less seam payload -> more benefit)")
    if not math.isnan(x_seam):
        print(f"  crossover: 3D-aware wins below seam_ratio ~ {x_seam:.3f}")
    print()

    # ---- balance rule ----
    imb = [_power_imbalance(r) for r in feasible]
    r_bal = _pearson(imb, ben)
    print("[balance rule]")
    print(f"  corr(power_imbalance, energy_benefit) = {r_bal:+.3f} "
          f"(expect negative: lopsided tiers -> hotspot erodes the win)")
    won = [imb[i] for i in range(len(feasible)) if ben[i] >= 1.0]
    if won:
        print(f"  wins concentrate where power imbalance <= {max(won):.2f}")
    print()

    # ---- precision rule ----
    bits = [float(r.data_bits) for r in feasible]
    r_prec = _pearson(bits, ben)
    print("[precision rule]")
    print(f"  corr(data_bits, energy_benefit) = {r_prec:+.3f} "
          f"(expect negative: fewer bits -> compounded win)")
    by_bits = {}
    for r in feasible:
        by_bits.setdefault(r.data_bits, []).append(r.energy_benefit)
    for b in sorted(by_bits):
        v = by_bits[b]
        print(f"    {b:>2}-bit: mean benefit {sum(v) / len(v):.3f}")
    print()

    print("Each rule is a correlation + crossover under the analytical model; "
          "fidelity is bounded by tech.py, so confirm signs/thresholds against "
          "real per-tier synthesis before quoting them as design rules.")


def main() -> None:
    analyze(run_sweep())


if __name__ == "__main__":
    main()
