"""ModelGraph-style IR for GNN accelerators (A6).

This mirrors hls4ml's `ModelGraph` / `Layer` abstraction at the granularity the
message-passing backend needs. Each `GNNLayer` is one propagation step and
carries the three pieces of information the generator and the Phase B cost
model both consume:

  * the update (combine) MLP shape   -> compute-bound work (k_mlp / combine)
  * the aggregation semantics        -> memory-bound work  (k_magg / aggregate)
  * the precision profile            -> bitwidth knob (gnn_config.h)

The aggregate/update split is explicit in the IR because it *is* the Phase B
tier seam: `GNNLayer.seam_payload_bits()` reports the bandwidth that crosses
that seam, which is what a 3D partitioner cuts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Aggregation(Enum):
    SUM = "sum"
    MEAN = "mean"
    MAX = "max"

    def to_cpp_enum(self) -> str:
        return {"sum": "AGG_SUM", "mean": "AGG_MEAN", "max": "AGG_MAX"}[self.value]


@dataclass
class LinearSpec:
    """A dense transform y = W^T x + b used inside combine/update MLPs."""

    in_dim: int
    out_dim: int
    has_bias: bool = True
    activation: Optional[str] = None  # None | "relu"

    @property
    def macs(self) -> int:
        return self.in_dim * self.out_dim


@dataclass
class GNNLayer:
    """One message-passing layer in the IR."""

    name: str
    kind: str                       # "gcn" | "gin" | "sage" | "egnn"
    in_dim: int
    out_dim: int
    aggregation: Aggregation
    normalize: bool                 # symmetric GCN normalization
    update: List[LinearSpec] = field(default_factory=list)
    # EGNN-specific extras (ignored by the simpler kinds)
    coord_dim: int = 0
    message_dim: int = 0

    def seam_payload_bits(self, data_bits: int) -> int:
        """Bits crossing the aggregate<->combine seam, per inference.

        For the common case this is the transformed-feature matrix streamed
        across the seam: out_dim features per node. The caller multiplies by
        node count to get total inter-tier traffic.
        """
        feat = self.message_dim if self.kind == "egnn" else self.out_dim
        return feat * data_bits

    @property
    def update_macs(self) -> int:
        return sum(spec.macs for spec in self.update)


@dataclass
class GNNModelGraph:
    """Ordered list of GNN layers plus global problem bounds."""

    layers: List[GNNLayer]
    max_nodes: int
    max_edges: int
    precision_profile: int = 0      # selects gnn_config.h profile

    def total_update_macs(self) -> int:
        return sum(layer.update_macs for layer in self.layers)

    def describe(self) -> str:
        lines = [
            f"GNNModelGraph: {len(self.layers)} layer(s), "
            f"max_nodes={self.max_nodes}, max_edges={self.max_edges}, "
            f"profile={self.precision_profile}"
        ]
        for ly in self.layers:
            lines.append(
                f"  - {ly.name} [{ly.kind}] {ly.in_dim}->{ly.out_dim} "
                f"aggr={ly.aggregation.value} norm={ly.normalize} "
                f"update_macs={ly.update_macs}"
            )
        return "\n".join(lines)
