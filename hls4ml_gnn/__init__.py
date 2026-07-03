"""hls4ml_gnn -- generic GNN front-end + message-passing backend for hls4ml (A6).

This package is the Phase A "generator": it reads a PyTorch Geometric
MessagePassing model, lowers it into a ModelGraph-style IR (`ir.py`), and emits
synthesizable HLS C++ that instantiates the message-passing templates in
`src/mp_template.h` (`codegen.py`).

It is deliberately structured to mirror the seams of upstream hls4ml so the
logic can be lifted into the real project with minimal change -- see README.md
for the exact attach points (converters / ModelGraph / backend templates).

Nothing here imports torch / torch_geometric at module load; the PyG parser
imports them lazily so the IR and codegen are usable (and testable) without a
deep-learning stack installed.
"""

from .ir import (
    Aggregation,
    GNNLayer,
    GNNModelGraph,
    LinearSpec,
)
from .codegen import emit_accelerator
from .pyg_parser import parse_pyg_model, parse_layer_specs


def register(backends=("Vivado", "Vitis")):
    """Drop the GNN extension into hls4ml. See hls4ml_gnn.register.register."""
    from .register import register as _register

    return _register(backends=backends)


def GraphMP(*args, **kwargs):
    """Construct the PyTorch GraphMP module (lazy import of torch/hls4ml)."""
    from .torch_modules import GraphMP as _GraphMP

    return _GraphMP(*args, **kwargs)


def GraphMPDynamic(*args, **kwargs):
    """Construct the dynamic-graph PyTorch GraphMP module (edge_index input)."""
    from .torch_modules import GraphMPDynamic as _GraphMPDynamic

    return _GraphMPDynamic(*args, **kwargs)


def GraphSAGEDynamic(*args, **kwargs):
    """Construct the dynamic-graph GraphSAGE module (neighbor + root weights)."""
    from .torch_modules import GraphSAGEDynamic as _GraphSAGEDynamic

    return _GraphSAGEDynamic(*args, **kwargs)


def from_gcnconv(*args, **kwargs):
    """Lower a torch_geometric GCNConv into a GraphMPDynamic (lazy import)."""
    from .pyg_adapter import from_gcnconv as _from_gcnconv

    return _from_gcnconv(*args, **kwargs)


def GINConvDynamic(*args, **kwargs):
    """Construct the dynamic-graph GINConv module (agg + 2-layer ReLU MLP)."""
    from .torch_modules import GINConvDynamic as _GINConvDynamic

    return _GINConvDynamic(*args, **kwargs)


def from_sageconv(*args, **kwargs):
    """Lower a torch_geometric SAGEConv into a GraphSAGEDynamic (lazy import)."""
    from .pyg_adapter import from_sageconv as _from_sageconv

    return _from_sageconv(*args, **kwargs)


def GATConvDynamic(*args, **kwargs):
    """Construct the single-head GAT attention module (dynamic graph)."""
    from .torch_modules import GATConvDynamic as _GATConvDynamic

    return _GATConvDynamic(*args, **kwargs)


def EGNNDynamic(*args, **kwargs):
    """Construct the E(n)-equivariant GNN module (h, x, edge_index inputs)."""
    from .torch_modules import EGNNDynamic as _EGNNDynamic

    return _EGNNDynamic(*args, **kwargs)


def from_ginconv(*args, **kwargs):
    """Lower a torch_geometric GINConv into a GINConvDynamic (lazy import)."""
    from .pyg_adapter import from_ginconv as _from_ginconv

    return _from_ginconv(*args, **kwargs)


def from_gatconv(*args, **kwargs):
    """Lower a single-head torch_geometric GATConv into a GATConvDynamic."""
    from .pyg_adapter import from_gatconv as _from_gatconv

    return _from_gatconv(*args, **kwargs)


def prepare_edge_index(*args, **kwargs):
    """Reproduce GCNConv edge preprocessing (self-loops + padding) for the port."""
    from .pyg_adapter import prepare_edge_index as _prepare_edge_index

    return _prepare_edge_index(*args, **kwargs)


__all__ = [
    # standalone look-alike generator (no hls4ml dependency)
    "Aggregation",
    "GNNLayer",
    "GNNModelGraph",
    "LinearSpec",
    "emit_accelerator",
    "parse_pyg_model",
    "parse_layer_specs",
    # real hls4ml extension
    "register",
    "GraphMP",
    "GraphMPDynamic",
    "GraphSAGEDynamic",
    "GINConvDynamic",
    "GATConvDynamic",
    "EGNNDynamic",
    "from_gcnconv",
    "from_sageconv",
    "from_ginconv",
    "from_gatconv",
    "prepare_edge_index",
]
