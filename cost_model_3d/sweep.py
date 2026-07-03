"""B4: open the GNN architecture and emit the labeled 3D corpus.

Sweeps the EGNN architectural knobs the roadmap names -- message/hidden width,
graph density (edges per node = the memory/compute ratio knob), and datapath
precision -- and for each configuration evaluates all arms plus the constrained
best partition. Two products:

  1. a per-design record with graph features + per-arm metrics + the 3D benefit
     ratio (energy of its own 2D baseline / energy of its best 3D partition),
     measured relative to each design's own 2D baseline so "more 3D-friendly"
     is not confounded with "better GNN" (roadmap requirement);
  2. a CSV corpus (stdlib csv) that trains the surrogate (surrogate.py) and
     feeds the rule extraction (rules.py).

Accuracy enters as a constraint via an explicit, documented proxy
(`accuracy_proxy`) -- a stand-in for measured task accuracy from the trained PyG
model. Designs below `acc_floor` are flagged infeasible so the co-design holds
accuracy fixed rather than rewarding capacity cuts that would hurt the task.

    python -m cost_model_3d.sweep            # prints summary, writes corpus.csv
"""

from __future__ import annotations

import csv
import itertools
import os
from dataclasses import dataclass, asdict
from typing import Dict, List

from .kernel_graph import KernelGraph, egnn_kernel_graph
from .partition import best_aware_partition, evaluate_arm, flat_2d
from .tech import DEFAULT_TECH, TechConfig


@dataclass
class SweepRecord:
    # ---- design knobs ----
    num_nodes: int
    edges_per_node: int
    h_dim: int
    msg_dim: int
    hid: int
    data_bits: int
    # ---- graph features (surrogate inputs) ----
    compute_memory_ratio: float
    macs_total: int
    mem_bytes_total: int
    seam_bits_parallel: int
    seam_bits_total: int
    # ---- accuracy proxy / feasibility ----
    accuracy_proxy: float
    acc_feasible: int
    # ---- labels: 2D baseline ----
    energy2d_nj: float
    latency2d_ns: float
    temp2d_c: float
    # ---- labels: best 3D ----
    energy3d_nj: float
    latency3d_ns: float
    temp3d_c: float
    tsv3d: int
    # ---- the headline ratio (>1 => 3D-aware saves energy vs own 2D) ----
    energy_benefit: float
    latency_ratio: float


def accuracy_proxy(h_dim: int, msg_dim: int, hid: int, data_bits: int) -> float:
    """Documented stand-in for measured EGNN task accuracy in [0, 1].

    Monotone in capacity (widths) and precision; saturating. NOT a trained
    number -- replace with eval accuracy of the PyG model at this config when
    the training loop is wired in. Its only role is to keep the co-design from
    'winning' by shrinking the network below a usable point.
    """
    cap = (h_dim / 16.0) * (msg_dim / 16.0) ** 0.5 * (hid / 32.0) ** 0.5
    cap = min(1.0, cap)
    prec = min(1.0, (data_bits / 16.0))
    return round(0.55 + 0.4 * cap * prec, 4)


def _features(graph: KernelGraph) -> Dict[str, float]:
    seam_par = sum(e.payload_bits_parallel for e in graph.edges)
    seam_tot = sum(e.payload_bits_total for e in graph.edges)
    return {
        "compute_memory_ratio": graph.compute_memory_ratio(),
        "macs_total": sum(n.macs for n in graph.nodes),
        "mem_bytes_total": sum(n.mem_bytes for n in graph.nodes),
        "seam_bits_parallel": seam_par,
        "seam_bits_total": seam_tot,
    }


def run_sweep(
    tech: TechConfig = DEFAULT_TECH,
    num_nodes_opts=(64,),
    edges_per_node_opts=(2, 4, 8, 16),
    width_opts=(4, 8, 16),
    hid_opts=(16, 32),
    bits_opts=(8, 12, 16),
    acc_floor: float = 0.70,
) -> List[SweepRecord]:
    records: List[SweepRecord] = []
    for nn, epn, w, hid, bits in itertools.product(
        num_nodes_opts, edges_per_node_opts, width_opts, hid_opts, bits_opts
    ):
        ne = nn * epn
        graph = egnn_kernel_graph(
            num_nodes=nn, num_edges=ne, h_dim=w, msg_dim=w, hid=hid, data_bits=bits
        )
        feats = _features(graph)

        flat_m = evaluate_arm(graph, flat_2d(graph), tech)
        (_, _), best_m = best_aware_partition(graph, tech)

        acc = accuracy_proxy(w, w, hid, bits)
        energy_benefit = (flat_m.energy_per_inf_nj / best_m.energy_per_inf_nj
                          if best_m.energy_per_inf_nj else 0.0)
        latency_ratio = (best_m.latency_ns / flat_m.latency_ns
                         if flat_m.latency_ns else 0.0)

        records.append(SweepRecord(
            num_nodes=nn, edges_per_node=epn, h_dim=w, msg_dim=w, hid=hid,
            data_bits=bits,
            compute_memory_ratio=round(feats["compute_memory_ratio"], 4),
            macs_total=int(feats["macs_total"]),
            mem_bytes_total=int(feats["mem_bytes_total"]),
            seam_bits_parallel=int(feats["seam_bits_parallel"]),
            seam_bits_total=int(feats["seam_bits_total"]),
            accuracy_proxy=acc,
            acc_feasible=int(acc >= acc_floor),
            energy2d_nj=round(flat_m.energy_per_inf_nj, 4),
            latency2d_ns=round(flat_m.latency_ns, 3),
            temp2d_c=round(flat_m.peak_temp_c, 3),
            energy3d_nj=round(best_m.energy_per_inf_nj, 4),
            latency3d_ns=round(best_m.latency_ns, 3),
            temp3d_c=round(best_m.peak_temp_c, 3),
            tsv3d=best_m.tsv_count,
            energy_benefit=round(energy_benefit, 4),
            latency_ratio=round(latency_ratio, 4),
        ))
    return records


def write_corpus(records: List[SweepRecord], path: str) -> None:
    if not records:
        return
    fields = list(asdict(records[0]).keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=fields)
        wr.writeheader()
        for r in records:
            wr.writerow(asdict(r))


def main() -> None:
    recs = run_sweep()
    feasible = [r for r in recs if r.acc_feasible]
    out = os.path.join(os.path.dirname(__file__), "corpus.csv")
    write_corpus(recs, out)

    print(f"=== B4 architecture sweep: {len(recs)} designs "
          f"({len(feasible)} accuracy-feasible) ===")
    print(f"corpus written: {out}\n")

    # Show the trend the roadmap predicts: benefit grows as density (memory
    # pressure) rises, i.e. as edges_per_node grows / compute_memory_ratio falls.
    print("edges/node  ->  mean energy_benefit (feasible designs, x vs own 2D)")
    by_epn: Dict[int, List[float]] = {}
    for r in feasible:
        by_epn.setdefault(r.edges_per_node, []).append(r.energy_benefit)
    for epn in sorted(by_epn):
        vals = by_epn[epn]
        print(f"  {epn:>3}        {sum(vals) / len(vals):.3f}   (n={len(vals)})")


if __name__ == "__main__":
    main()
