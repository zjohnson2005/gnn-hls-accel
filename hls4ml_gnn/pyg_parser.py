"""PyTorch Geometric front-end for the GNN generator (A6).

Reads a `torch_geometric.nn.MessagePassing` model and lowers each recognized
convolution into a `GNNLayer` in our ModelGraph-style IR. This is the piece
hls4ml is missing today (its 2025 platform paper notes no PyG support and only
in-development generic GNN support); the mapping below is exactly what would be
registered in `hls4ml/converters/pytorch/` once lifted upstream.

torch / torch_geometric are imported lazily so the rest of the package (IR,
codegen) works without a DL stack. `parse_layer_specs` provides a torch-free
path that builds the same IR from plain dicts, which is what the unit-style
checks and the Phase B sweep use.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .ir import Aggregation, GNNLayer, GNNModelGraph, LinearSpec


# Map a PyG conv class name -> (kind, normalize, default aggregation).
_PYG_LAYER_MAP = {
    "GCNConv": ("gcn", True, Aggregation.SUM),
    "GINConv": ("gin", False, Aggregation.SUM),
    "SAGEConv": ("sage", False, Aggregation.MEAN),
}

_AGGR_MAP = {
    "add": Aggregation.SUM,
    "sum": Aggregation.SUM,
    "mean": Aggregation.MEAN,
    "max": Aggregation.MAX,
}


def parse_layer_specs(
    specs: List[Dict[str, Any]],
    max_nodes: int,
    max_edges: int,
    precision_profile: int = 0,
) -> GNNModelGraph:
    """Build a GNNModelGraph from plain dicts (no torch required).

    Each spec dict: {name, kind, in_dim, out_dim, aggregation, normalize,
                     [hidden, coord_dim, message_dim, activation]}
    """
    layers: List[GNNLayer] = []
    for i, s in enumerate(specs):
        kind = s["kind"]
        in_dim = int(s["in_dim"])
        out_dim = int(s["out_dim"])
        aggr = s.get("aggregation", "sum")
        aggr = aggr if isinstance(aggr, Aggregation) else _AGGR_MAP[aggr]
        normalize = bool(s.get("normalize", kind == "gcn"))

        update = _build_update(kind, s)
        layers.append(
            GNNLayer(
                name=s.get("name", f"{kind}{i}"),
                kind=kind,
                in_dim=in_dim,
                out_dim=out_dim,
                aggregation=aggr,
                normalize=normalize,
                update=update,
                coord_dim=int(s.get("coord_dim", 0)),
                message_dim=int(s.get("message_dim", 0)),
            )
        )
    return GNNModelGraph(
        layers=layers,
        max_nodes=max_nodes,
        max_edges=max_edges,
        precision_profile=precision_profile,
    )


def _build_update(kind: str, s: Dict[str, Any]) -> List[LinearSpec]:
    in_dim, out_dim = int(s["in_dim"]), int(s["out_dim"])
    if kind in ("gcn", "sage"):
        return [LinearSpec(in_dim, out_dim, has_bias=True, activation=None)]
    if kind == "gin":
        hid = int(s.get("hidden", out_dim))
        return [
            LinearSpec(in_dim, hid, has_bias=True, activation="relu"),
            LinearSpec(hid, out_dim, has_bias=True, activation=None),
        ]
    if kind == "egnn":
        hid = int(s.get("hidden", out_dim))
        m = int(s.get("message_dim", out_dim))
        return [
            LinearSpec(2 * in_dim + 1, hid, activation="relu"),  # phi_e.1
            LinearSpec(hid, m, activation=None),                 # phi_e.2
            LinearSpec(in_dim + m, hid, activation="relu"),      # phi_h.1
            LinearSpec(hid, out_dim, activation=None),           # phi_h.2
        ]
    raise ValueError(f"unknown layer kind: {kind}")


def parse_pyg_model(
    model: "Any",
    max_nodes: int,
    max_edges: int,
    precision_profile: int = 0,
) -> GNNModelGraph:
    """Lower a live PyG model into the IR. Imports torch lazily."""
    try:
        import torch  # noqa: F401
        from torch_geometric.nn import MessagePassing
    except Exception as exc:  # pragma: no cover - depends on user env
        raise ImportError(
            "parse_pyg_model needs torch + torch_geometric installed. "
            "Use parse_layer_specs for a torch-free path."
        ) from exc

    specs: List[Dict[str, Any]] = []
    idx = 0
    for module in model.modules():
        cls = type(module).__name__
        if cls in _PYG_LAYER_MAP:
            kind, normalize, default_aggr = _PYG_LAYER_MAP[cls]
            aggr = getattr(module, "aggr", None) or default_aggr.value
            in_dim, out_dim = _infer_dims(module)
            specs.append(
                {
                    "name": f"{kind}{idx}",
                    "kind": kind,
                    "in_dim": in_dim,
                    "out_dim": out_dim,
                    "aggregation": aggr,
                    "normalize": normalize,
                }
            )
            idx += 1
    if not specs:
        raise ValueError(
            "No supported MessagePassing layers found "
            "(GCNConv / GINConv / SAGEConv)."
        )
    return parse_layer_specs(specs, max_nodes, max_edges, precision_profile)


def _infer_dims(module: "Any"):
    """Best-effort (in_dim, out_dim) extraction from a PyG conv module."""
    for attr in ("in_channels", "in_features"):
        in_dim = getattr(module, attr, None)
        if in_dim is not None:
            break
    else:
        in_dim = None
    for attr in ("out_channels", "out_features"):
        out_dim = getattr(module, attr, None)
        if out_dim is not None:
            break
    else:
        out_dim = None
    if in_dim is None or out_dim is None:
        raise ValueError(f"could not infer dims from {type(module).__name__}")
    return int(in_dim), int(out_dim)
