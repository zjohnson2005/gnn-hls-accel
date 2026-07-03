"""cost_model_3d -- HLS-level 3D-IC tier-partition cost model for GNNs (Phase B).

An HLS GNN accelerator is a kernel graph (kernel_graph.py). Given a candidate
tier assignment and a 3D technology config (tech.py), tier_model.py produces the
four roadmap metrics -- latency, energy/inference, peak temperature, TSV count --
together, because they are coupled. partition.py defines the three comparison
arms (flat-2D / 3D-blind / 3D-aware) and a constrained search; experiment.py is
the B1-B3 driver; sweep.py opens the architecture (B4) and emits the labeled
corpus; surrogate.py is the dependency-free graph-regression QoR predictor that
makes DSE tractable; rules.py extracts the transferable design rules (B5).

Everything is pure standard-library Python so it runs on the remote box (or
locally) without numpy/torch. Coefficients in tech.py are analytical, not
silicon -- the model's fidelity bounds the trustworthiness of any rule.
"""

from .kernel_graph import KernelGraph, KernelNode, KernelEdge, egnn_kernel_graph
from .tech import TechConfig, DEFAULT_TECH
from .tier_model import Metrics, evaluate, LOGIC_TIER, MEMORY_TIER
from .partition import flat_2d, blind_3d, aware_3d, best_aware_partition, evaluate_arm

__all__ = [
    "KernelGraph",
    "KernelNode",
    "KernelEdge",
    "egnn_kernel_graph",
    "TechConfig",
    "DEFAULT_TECH",
    "Metrics",
    "evaluate",
    "LOGIC_TIER",
    "MEMORY_TIER",
    "flat_2d",
    "blind_3d",
    "aware_3d",
    "best_aware_partition",
    "evaluate_arm",
]
