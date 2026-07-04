"""Kernel-graph representation of a GNN accelerator (Phase B).

An HLS design is a graph: nodes are kernels (with QoR attributes from csynth),
edges are inter-kernel data volumes. This is both the thing a 3D partitioner
cuts and the input the graph-regression surrogate (B4) learns from.

The attributes a node carries are exactly what HLS csynth + an activity model
provide, so a real flow can populate them from
egnn_proj/sol1/syn/report/*.rpt instead of the analytical defaults here.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class KernelNode:
    name: str
    category: str          # "compute" | "memory"
    compute_cycles: int    # latency contribution (csynth)
    macs: int              # multiply-accumulates per inference (activity)
    mem_bytes: int         # off-chip/local memory traffic per inference
    luts: int = 0
    dsps: int = 0
    bram: int = 0
    activity: float = 0.5  # average switching activity in [0,1]


@dataclass
class KernelEdge:
    src: str
    dst: str
    payload_bits_total: int   # total bits transferred per inference
    payload_bits_parallel: int  # simultaneous bus width (sets TSV count if cut)


@dataclass
class KernelGraph:
    nodes: List[KernelNode] = field(default_factory=list)
    edges: List[KernelEdge] = field(default_factory=list)
    # design metadata used by the sweep / rules
    meta: Dict[str, float] = field(default_factory=dict)

    def node(self, name: str) -> KernelNode:
        for n in self.nodes:
            if n.name == name:
                return n
        raise KeyError(name)

    def compute_memory_ratio(self) -> float:
        """sum(compute MACs) / sum(memory bytes) -- the knob the sweep varies.

        High ratio = compute-dominated (dense); low ratio = memory-dominated
        (the regime the roadmap predicts 3D-aware HLS helps most).
        """
        macs = sum(n.macs for n in self.nodes)
        bytes_ = max(1, sum(n.mem_bytes for n in self.nodes))
        return macs / bytes_

    def seam_edges(self) -> List[KernelEdge]:
        """The aggregate<->combine boundary edges (lowest-bandwidth cut)."""
        return [e for e in self.edges if self.meta.get("seam_tag", "") in (e.src, e.dst)] or self.edges


def egnn_kernel_graph(
    num_nodes: int = 64,
    num_edges: int = 512,
    h_dim: int = 8,
    msg_dim: int = 8,
    hid: int = 16,
    coord_dim: int = 3,
    data_bits: int = 16,
) -> KernelGraph:
    """Build the EGNN kernel graph (k_mlp1 / k_magg / k_mlp2) from A5.

    Cycle/MAC/byte counts follow the structure of src/egnn_layer.cpp so the
    graph tracks the real kernel; replace with csynth numbers when available.
    """
    e_in = 2 * h_dim + 1
    h_in = h_dim + msg_dim

    # ---- k_mlp1: per-edge edge-MLP (compute-bound) ----
    mlp1_macs = num_edges * (e_in * hid + hid * msg_dim + msg_dim)  # +phi_x gate
    mlp1_cycles = num_edges * (hid + msg_dim)                       # II=1 inner pipelines
    mlp1_bytes = num_edges * (2 * h_dim) * data_bits // 8           # reads h_i,h_j

    # ---- k_magg: scatter aggregation (memory-bound) ----
    magg_macs = num_edges * (msg_dim + coord_dim)                   # adds, light compute
    magg_cycles = num_edges + num_nodes                             # scatter + clear
    magg_bytes = (num_edges * (msg_dim + coord_dim)
                  + num_nodes * (msg_dim + coord_dim)) * data_bits // 8

    # ---- k_mlp2: per-node node-MLP (compute-bound) ----
    mlp2_macs = num_nodes * (h_in * hid + hid * h_dim)
    mlp2_cycles = num_nodes * (hid + h_dim)
    mlp2_bytes = num_nodes * (h_dim + msg_dim) * data_bits // 8

    nodes = [
        KernelNode("k_mlp1", "compute", mlp1_cycles, mlp1_macs, mlp1_bytes,
                   luts=4000, dsps=hid, activity=0.6),
        KernelNode("k_magg", "memory", magg_cycles, magg_macs, magg_bytes,
                   luts=1500, dsps=0, activity=0.45),
        KernelNode("k_mlp2", "compute", mlp2_cycles, mlp2_macs, mlp2_bytes,
                   luts=3500, dsps=hid, activity=0.6),
    ]

    # seam payloads: msg+gate from mlp1->magg, m_node+dx from magg->mlp2
    p1_par = (msg_dim + 1) * data_bits
    p1_tot = num_edges * p1_par
    p2_par = (msg_dim + coord_dim) * data_bits
    p2_tot = num_nodes * p2_par

    edges = [
        KernelEdge("k_mlp1", "k_magg", p1_tot, p1_par),
        KernelEdge("k_magg", "k_mlp2", p2_tot, p2_par),
    ]

    g = KernelGraph(nodes=nodes, edges=edges)
    g.meta.update(
        num_nodes=num_nodes, num_edges=num_edges, h_dim=h_dim, msg_dim=msg_dim,
        hid=hid, coord_dim=coord_dim, data_bits=data_bits, seam_tag="k_magg",
    )
    return g


# Measured csynth numbers (Vitis 2025.2.1, xczu3eg-sbva484-1-e, 3.33 ns target)
# for the DEFAULT EGNN config (nodes=64, edges=512, h=msg=8, hid=16, 16-bit),
# which is exactly what src/egnn_layer.h synthesizes.
# Source: egnn_proj/sol1/syn/report/csynth.rpt. Notable: k_mlp1 dominates
# latency (the per-edge edge-MLP is not pipelined across edges) and k_magg hits
# an II=4 scatter resource limitation -- the memory-bound behavior the 3D-aware
# partition targets.
MEASURED_EGNN = {
    "k_mlp1": dict(compute_cycles=30218, dsps=44, luts=4034, bram=0),
    "k_magg": dict(compute_cycles=2122, dsps=3, luts=2507, bram=0),
    "k_mlp2": dict(compute_cycles=2889, dsps=32, luts=3716, bram=0),
}


def egnn_kernel_graph_measured() -> KernelGraph:
    """Default EGNN kernel graph with per-kernel latency/resources overridden by
    measured csynth numbers (see MEASURED_EGNN). MAC/byte/activity fields keep
    their analytical values (csynth does not report them). Use this for the
    fixed-design B1-B3 experiment; the sweep stays analytical so it can scale to
    unsynthesized configurations.
    """
    g = egnn_kernel_graph()
    for n in g.nodes:
        m = MEASURED_EGNN.get(n.name)
        if m:
            n.compute_cycles = m["compute_cycles"]
            n.dsps = m["dsps"]
            n.luts = m["luts"]
            n.bram = m["bram"]
    g.meta["qor_source"] = "csynth-2025.2.1"
    return g
