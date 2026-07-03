"""Adapter: lower a real ``torch_geometric`` layer into our hls4ml GNN layer.

Why an adapter instead of feeding ``GCNConv`` straight into hls4ml?
Two limitations live inside hls4ml itself (consistent with the hls4ml paper
noting PyG support is "in development"):

  1. hls4ml's PyTorch parser special-cases any class whose name contains
     ``"Conv"`` and assumes it is a spatial convolution (it reads
     ``padding_mode`` / ``groups``). ``GCNConv`` matches that substring and
     crashes before any custom handler runs.
  2. ``torch_geometric.nn.MessagePassing.propagate()`` is not cleanly
     FX-traceable, so the symbolic tracer cannot follow the message-passing
     internals.

So the robust, faithful path is to take a *trained* PyG layer and lower its
math + weights into our ``GraphMPDynamic`` (a name without ``"Conv"`` and an
``HLS4MLModule`` leaf that hls4ml traces and synthesizes). We then prove the
lowered module matches the original PyG layer numerically before synthesis.

GCNConv semantics reproduced here:
    out_i = sum_{j in N(i) U {i}} (d_i d_j)^-1/2 * (x_j W) + b
where the self-loops and symmetric normalization are exactly PyG's
``gcn_norm`` (``improved=False``). The self-loop augmentation of ``edge_index``
is graph preprocessing (host side) -- use :func:`prepare_edge_index`.
"""

from __future__ import annotations

import torch

from .torch_modules import GraphMPDynamic, GraphSAGEDynamic, GINConvDynamic, GATConvDynamic


def _aggr_to_str(aggr) -> str:
    # PyG stores aggr as a string ("add"/"mean"/"max") or an Aggregation module.
    name = str(aggr).lower()
    if name in ("add", "sum", "sumaggregation"):
        return "sum"
    if name in ("mean", "meanaggregation"):
        return "mean"
    if name in ("max", "maxaggregation"):
        return "max"
    raise ValueError(f"unsupported PyG aggregation {aggr!r}; expected add/mean/max")


def from_gcnconv(conv, n_node: int, max_edges: int) -> GraphMPDynamic:
    """Build a ``GraphMPDynamic`` equivalent to a ``torch_geometric.nn.GCNConv``.

    Args:
        conv:       a (trained) ``torch_geometric.nn.GCNConv`` instance
        n_node:     compile-time max node count for the accelerator
        max_edges:  compile-time max edge count, INCLUDING self-loops if the
                    GCNConv adds them (see :func:`prepare_edge_index`)

    Returns:
        a ``GraphMPDynamic`` whose ``forward(x, edge_index)`` matches
        ``conv(x, edge_index_raw)`` when ``edge_index`` has been prepared with
        :func:`prepare_edge_index`.
    """
    if conv.__class__.__name__ != "GCNConv":
        raise TypeError(f"from_gcnconv expects a GCNConv, got {conv.__class__.__name__}")
    if getattr(conv, "improved", False):
        raise NotImplementedError("GCNConv(improved=True) is not supported (self-loop weight=2)")

    lin = conv.lin  # torch_geometric.nn.dense.linear.Linear, weight [out, in]
    out_features, in_features = lin.weight.shape
    has_bias = getattr(conv, "bias", None) is not None
    normalize = bool(getattr(conv, "normalize", True))
    aggregation = _aggr_to_str(getattr(conv, "aggr", "add"))

    module = GraphMPDynamic(
        in_features=int(in_features),
        out_features=int(out_features),
        n_node=int(n_node),
        max_edges=int(max_edges),
        aggregation=aggregation,
        normalize=normalize,
        bias=has_bias,
    )
    with torch.no_grad():
        module.weight.copy_(lin.weight.detach())
        if has_bias:
            module.bias.copy_(conv.bias.detach())
    module.eval()
    return module


def from_sageconv(conv, n_node: int, max_edges: int) -> GraphSAGEDynamic:
    """Build a ``GraphSAGEDynamic`` equivalent to a ``torch_geometric.nn.SAGEConv``.

    SAGEConv: out_i = lin_l(AGG_{j in N(i)} x_j) + lin_r(x_i), with bias in
    lin_l. We map lin_l -> ``weight`` (neighbor), lin_r -> ``root_weight``
    (self), and lin_l.bias -> ``bias``. Unlike GCN there are NO self-loops, so
    feed the raw ``edge_index`` (use ``prepare_edge_index(add_self_loops=False)``
    just for padding).
    """
    if conv.__class__.__name__ != "SAGEConv":
        raise TypeError(f"from_sageconv expects a SAGEConv, got {conv.__class__.__name__}")
    if getattr(conv, "project", False):
        raise NotImplementedError("SAGEConv(project=True) pre-projection is not supported")
    if getattr(conv, "normalize", False):
        raise NotImplementedError("SAGEConv(normalize=True) L2 output norm is not supported")

    aggregation = _aggr_to_str(getattr(conv, "aggr", "mean"))
    if aggregation not in ("sum", "mean"):
        raise NotImplementedError(f"GraphSAGE HLS kernel supports sum|mean, not {aggregation!r}")

    lin_l = conv.lin_l
    out_features, in_features = lin_l.weight.shape
    has_bias = getattr(lin_l, "bias", None) is not None
    lin_r = getattr(conv, "lin_r", None)

    module = GraphSAGEDynamic(
        in_features=int(in_features),
        out_features=int(out_features),
        n_node=int(n_node),
        max_edges=int(max_edges),
        aggregation=aggregation,
        bias=has_bias,
    )
    with torch.no_grad():
        module.weight.copy_(lin_l.weight.detach())
        if lin_r is not None:
            module.root_weight.copy_(lin_r.weight.detach())
        else:
            module.root_weight.zero_()  # root_weight=False -> no self term
        if has_bias:
            module.bias.copy_(lin_l.bias.detach())
    module.eval()
    return module


def from_ginconv(conv, n_node: int, max_edges: int) -> GINConvDynamic:
    """Build a ``GINConvDynamic`` equivalent to a ``torch_geometric.nn.GINConv``.

    GINConv: out = MLP((1+eps) x_i + sum_{j in N(i)} x_j). We support the common
    MLP head ``Linear -> ReLU -> Linear`` (2 Linear layers), copy its weights,
    and bake ``eps`` into the kernel. No self-loops (the self term is explicit).
    """
    if conv.__class__.__name__ != "GINConv":
        raise TypeError(f"from_ginconv expects a GINConv, got {conv.__class__.__name__}")
    aggregation = _aggr_to_str(getattr(conv, "aggr", "add"))
    if aggregation != "sum":
        raise NotImplementedError(f"GIN HLS kernel supports add/sum aggregation, not {aggregation!r}")

    eps = float(conv.eps)
    linears = [m for m in conv.nn.modules() if isinstance(m, torch.nn.Linear)]
    if len(linears) != 2:
        raise NotImplementedError(
            f"from_ginconv supports a 2-layer (Linear-ReLU-Linear) MLP head; found {len(linears)} Linear layers"
        )
    lin1, lin2 = linears
    in_features = lin1.in_features
    hidden = lin1.out_features
    out_features = lin2.out_features
    if lin2.in_features != hidden:
        raise ValueError("GINConv MLP layer dims do not chain (hidden size mismatch)")

    module = GINConvDynamic(
        in_features=int(in_features),
        hidden_features=int(hidden),
        out_features=int(out_features),
        n_node=int(n_node),
        max_edges=int(max_edges),
        eps=eps,
    )
    with torch.no_grad():
        module.weight1.copy_(lin1.weight.detach())
        module.bias1.copy_(lin1.bias.detach() if lin1.bias is not None else torch.zeros(hidden))
        module.weight2.copy_(lin2.weight.detach())
        module.bias2.copy_(lin2.bias.detach() if lin2.bias is not None else torch.zeros(out_features))
    module.eval()
    return module


def from_gatconv(conv, n_node: int, max_edges: int) -> GATConvDynamic:
    """Build a ``GATConvDynamic`` equivalent to a single-head ``GATConv``.

    Extracts the linear (``lin_src``), the two attention vectors
    (``att_src``/``att_dst``), the bias, and the LeakyReLU slope. Only
    ``heads=1`` is supported. GAT adds self-loops, so feed
    ``prepare_edge_index(add_self_loops=True)``.
    """
    if conv.__class__.__name__ != "GATConv":
        raise TypeError(f"from_gatconv expects a GATConv, got {conv.__class__.__name__}")
    if int(getattr(conv, "heads", 1)) != 1:
        raise NotImplementedError("from_gatconv supports single-head GAT (heads=1) only")

    lin = getattr(conv, "lin_src", None)
    if lin is None:
        lin = getattr(conv, "lin", None)
    if lin is None:
        raise ValueError("could not locate GATConv linear (lin_src/lin)")

    out_features, in_features = lin.weight.shape
    slope = float(getattr(conv, "negative_slope", 0.2))
    has_bias = getattr(conv, "bias", None) is not None

    module = GATConvDynamic(
        in_features=int(in_features),
        out_features=int(out_features),
        n_node=int(n_node),
        max_edges=int(max_edges),
        negative_slope=slope,
        bias=has_bias,
    )
    with torch.no_grad():
        module.weight.copy_(lin.weight.detach())
        module.att_src.copy_(conv.att_src.detach().reshape(-1))
        module.att_dst.copy_(conv.att_dst.detach().reshape(-1))
        if has_bias:
            module.bias.copy_(conv.bias.detach().reshape(-1))
    module.eval()
    return module


def prepare_edge_index(
    edge_index: torch.Tensor,
    n_node: int,
    add_self_loops: bool = True,
    max_edges: int | None = None,
) -> torch.Tensor:
    """Reproduce GCNConv's edge preprocessing for the accelerator's edge port.

    GCNConv adds self-loops to every node internally before normalizing. Our
    kernel does NOT add self-loops, so we bake that step into the edge tensor
    the accelerator receives (this is the host-side graph prep an FPGA flow
    would do anyway). Optionally pad to ``max_edges`` with out-of-range indices
    (``n_node``), which the kernel skips.

    Returns an int64 ``[2, E']`` tensor.
    """
    ei = edge_index.long()
    if add_self_loops:
        loops = torch.arange(n_node, dtype=ei.dtype, device=ei.device)
        loops = torch.stack([loops, loops], dim=0)
        ei = torch.cat([ei, loops], dim=1)
    if max_edges is not None:
        e = ei.shape[1]
        if e > max_edges:
            raise ValueError(f"edge count {e} exceeds max_edges {max_edges}")
        if e < max_edges:
            pad = torch.full((2, max_edges - e), n_node, dtype=ei.dtype, device=ei.device)
            ei = torch.cat([ei, pad], dim=1)
    return ei
