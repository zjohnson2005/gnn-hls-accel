"""PyTorch front-end module for the hls4ml GNN extension.

`GraphMP` is the layer a user puts in their PyTorch model. It subclasses
`hls4ml.utils.torch.HLS4MLModule` so hls4ml's `CustomFXTracer` treats it as a
*leaf* during symbolic tracing -- the converter then dispatches it to our
registered handler instead of trying to trace the message-passing internals
(which torch.fx cannot follow for real PyG ops).

Fixed-graph assumption: the adjacency is a registered buffer, so the layer is a
single-input / single-output node and flows through hls4ml's io_parallel path
like any other layer. The forward() here is the bit-accurate float reference the
generated HLS is checked against; it mirrors nnet_graph.h exactly.
"""

from __future__ import annotations

import torch

import hls4ml.utils.torch


_VALID_AGG = ("sum", "mean", "max")


class GraphMP(hls4ml.utils.torch.HLS4MLModule):
    """Fixed-graph message-passing layer: combine (linear) then aggregate.

    Args:
        in_features:  input features per node (F_in)
        out_features: output features per node (F_out)
        adj:          [N, N] adjacency (0 = no edge). Values are used directly as
                      edge coefficients when ``normalize=False``.
        aggregation:  "sum" | "mean" | "max"
        normalize:    symmetric GCN coefficients c_ij = d_i^-0.5 d_j^-0.5
        bias:         include a per-output bias
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        adj: torch.Tensor,
        aggregation: str = "sum",
        normalize: bool = False,
        bias: bool = True,
    ):
        super().__init__()
        if aggregation not in _VALID_AGG:
            raise ValueError(f"aggregation must be one of {_VALID_AGG}, got {aggregation!r}")
        adj = torch.as_tensor(adj, dtype=torch.float32)
        if adj.dim() != 2 or adj.shape[0] != adj.shape[1]:
            raise ValueError(f"adj must be square [N, N], got {tuple(adj.shape)}")

        self.in_features = int(in_features)
        self.out_features = int(out_features)
        self.n_node = int(adj.shape[0])
        self.aggregation = aggregation
        self.normalize = bool(normalize)

        self.weight = torch.nn.Parameter(torch.empty(out_features, in_features))
        torch.nn.init.kaiming_uniform_(self.weight, a=5 ** 0.5)
        if bias:
            self.bias = torch.nn.Parameter(torch.zeros(out_features))
        else:
            self.register_parameter("bias", None)
        self.register_buffer("adj", adj)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [..., N, F_in]  ->  y: [..., N, F_out]
        # bias is applied once per node, after aggregation (PyG convention)
        comb = x @ self.weight.t()

        A = self.adj
        mask = (A != 0).to(comb.dtype)

        if self.aggregation == "max":
            # masked elementwise max over neighbors
            neg = torch.finfo(comb.dtype).min
            # [N, N, 1] mask * comb[N, F] broadcast -> per-target max
            contrib = torch.where(
                mask.unsqueeze(-1) > 0,
                comb.unsqueeze(-3).expand(*comb.shape[:-2], self.n_node, self.n_node, self.out_features),
                torch.full_like(comb[..., :1, :].expand(*comb.shape[:-2], self.n_node, self.n_node, self.out_features), neg),
            )
            y = contrib.max(dim=-2).values
        else:
            if self.normalize:
                deg = mask.sum(-1)
                dinv = torch.where(deg > 0, deg.pow(-0.5), torch.zeros_like(deg))
                coeff = dinv.unsqueeze(-1) * mask * dinv.unsqueeze(-2)
            else:
                coeff = A

            y = coeff @ comb
            if self.aggregation == "mean":
                deg = mask.sum(-1, keepdim=True).clamp(min=1)
                y = y / deg

        if self.bias is not None:
            y = y + self.bias
        return y


class GraphMPDynamic(hls4ml.utils.torch.HLS4MLModule):
    """Dynamic-graph message passing: connectivity is a runtime ``edge_index``.

    This is the real GNN interface -- the graph is an input, not baked in. The
    same accelerator handles any graph up to ``(n_node, max_edges)``. Pad unused
    edge slots with an out-of-range index (>= n_node); they are skipped.

    Args:
        in_features:  input features per node (F_in)
        out_features: output features per node (F_out)
        n_node:       max number of nodes (compile-time bound)
        max_edges:    max number of edges (compile-time bound)
        aggregation:  "sum" | "mean" | "max"
        normalize:    symmetric GCN coefficients d_s^-0.5 d_d^-0.5
        bias:         include a per-output bias

    forward(x, edge_index):
        x          : [N, F_in] node features
        edge_index : [2, E] COO (row 0 = source, row 1 = target), PyG convention
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        n_node: int,
        max_edges: int,
        aggregation: str = "sum",
        normalize: bool = False,
        bias: bool = True,
    ):
        super().__init__()
        if aggregation not in _VALID_AGG:
            raise ValueError(f"aggregation must be one of {_VALID_AGG}, got {aggregation!r}")
        self.in_features = int(in_features)
        self.out_features = int(out_features)
        self.n_node = int(n_node)
        self.n_edge = int(max_edges)
        self.aggregation = aggregation
        self.normalize = bool(normalize)

        self.weight = torch.nn.Parameter(torch.empty(out_features, in_features))
        torch.nn.init.kaiming_uniform_(self.weight, a=5 ** 0.5)
        if bias:
            self.bias = torch.nn.Parameter(torch.zeros(out_features))
        else:
            self.register_parameter("bias", None)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        N = self.n_node
        # bias is applied once per node, after aggregation (PyG convention)
        comb = x @ self.weight.t()

        src = edge_index[0].long()
        dst = edge_index[1].long()
        valid = (src >= 0) & (src < N) & (dst >= 0) & (dst < N)
        src, dst = src[valid], dst[valid]

        deg = torch.zeros(N, dtype=comb.dtype, device=comb.device)
        deg.index_add_(0, dst, torch.ones_like(dst, dtype=comb.dtype))

        if self.aggregation == "max":
            out = torch.full((N, self.out_features), torch.finfo(comb.dtype).min, dtype=comb.dtype, device=comb.device)
            idx = dst.unsqueeze(-1).expand(-1, self.out_features)
            out.scatter_reduce_(0, idx, comb[src], reduce="amax", include_self=True)
            out[deg == 0] = 0.0
        else:
            if self.normalize:
                dinv = torch.where(deg > 0, deg.pow(-0.5), torch.zeros_like(deg))
                coeff = (dinv[src] * dinv[dst]).unsqueeze(-1)
            else:
                coeff = torch.ones(src.shape[0], 1, dtype=comb.dtype, device=comb.device)

            out = torch.zeros(N, self.out_features, dtype=comb.dtype, device=comb.device)
            out.index_add_(0, dst, coeff * comb[src])
            if self.aggregation == "mean":
                out = out / deg.clamp(min=1).unsqueeze(-1)

        if self.bias is not None:
            out = out + self.bias
        return out


class GraphSAGEDynamic(hls4ml.utils.torch.HLS4MLModule):
    """Dynamic-graph GraphSAGE layer (PyG ``SAGEConv`` semantics).

        out_i = AGG_{j in N(i)}(x_j W_l) + x_i W_r + b

    Two weights: ``weight`` (W_l, neighbor / lin_l) and ``root_weight``
    (W_r, self / lin_r). Default aggregation is mean. No symmetric
    normalization and no self-loops (the self term is the explicit root
    weight, unlike GCN). ``edge_index`` is the runtime COO input.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        n_node: int,
        max_edges: int,
        aggregation: str = "mean",
        bias: bool = True,
    ):
        super().__init__()
        if aggregation not in ("sum", "mean"):
            raise ValueError(f"GraphSAGE aggregation must be sum|mean, got {aggregation!r}")
        self.in_features = int(in_features)
        self.out_features = int(out_features)
        self.n_node = int(n_node)
        self.n_edge = int(max_edges)
        self.aggregation = aggregation
        self.normalize = False  # symmetric-norm flag unused; kept for template parity

        self.weight = torch.nn.Parameter(torch.empty(out_features, in_features))
        self.root_weight = torch.nn.Parameter(torch.empty(out_features, in_features))
        torch.nn.init.kaiming_uniform_(self.weight, a=5 ** 0.5)
        torch.nn.init.kaiming_uniform_(self.root_weight, a=5 ** 0.5)
        if bias:
            self.bias = torch.nn.Parameter(torch.zeros(out_features))
        else:
            self.register_parameter("bias", None)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        N = self.n_node
        comb = x @ self.weight.t()       # neighbor transform (lin_l)
        root = x @ self.root_weight.t()  # self transform (lin_r)

        src = edge_index[0].long()
        dst = edge_index[1].long()
        valid = (src >= 0) & (src < N) & (dst >= 0) & (dst < N)
        src, dst = src[valid], dst[valid]

        deg = torch.zeros(N, dtype=comb.dtype, device=comb.device)
        deg.index_add_(0, dst, torch.ones_like(dst, dtype=comb.dtype))

        out = torch.zeros(N, self.out_features, dtype=comb.dtype, device=comb.device)
        out.index_add_(0, dst, comb[src])
        if self.aggregation == "mean":
            out = out / deg.clamp(min=1).unsqueeze(-1)

        out = out + root
        if self.bias is not None:
            out = out + self.bias
        return out


class GINAggregateDynamic(hls4ml.utils.torch.HLS4MLModule):
    """GINConv aggregation (no weights): ``agg_i = (1+eps) x_i + sum_j x_j``.

    This is the only graph-specific part of GINConv; the learnable MLP that
    follows is left as standard ``nn.Linear``/activation layers so hls4ml
    lowers it with its native Dense support. Feature width is preserved
    (``in_features == out_features``).
    """

    def __init__(
        self,
        in_features: int,
        n_node: int,
        max_edges: int,
        eps: float = 0.0,
    ):
        super().__init__()
        self.in_features = int(in_features)
        self.out_features = int(in_features)
        self.n_node = int(n_node)
        self.n_edge = int(max_edges)
        self.aggregation = "sum"
        self.eps = float(eps)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        N = self.n_node
        src = edge_index[0].long()
        dst = edge_index[1].long()
        valid = (src >= 0) & (src < N) & (dst >= 0) & (dst < N)
        src, dst = src[valid], dst[valid]

        out = (1.0 + self.eps) * x
        out = out.index_add(0, dst, x[src])
        return out


class GINConvDynamic(hls4ml.utils.torch.HLS4MLModule):
    """Full GINConv (PyG) with a 2-layer ReLU MLP, self-contained for HLS:

        agg_i = (1+eps) x_i + sum_{j in N(i)} x_j
        out_i = W2 @ relu(W1 @ agg_i + b1) + b2

    Weights mirror an ``nn.Sequential(Linear(in,hidden), ReLU,
    Linear(hidden,out))`` MLP -- the overwhelmingly common GINConv head.
    """

    def __init__(
        self,
        in_features: int,
        hidden_features: int,
        out_features: int,
        n_node: int,
        max_edges: int,
        eps: float = 0.0,
    ):
        super().__init__()
        self.in_features = int(in_features)
        self.hidden_features = int(hidden_features)
        self.out_features = int(out_features)
        self.n_node = int(n_node)
        self.n_edge = int(max_edges)
        self.aggregation = "sum"
        self.eps = float(eps)

        self.weight1 = torch.nn.Parameter(torch.empty(hidden_features, in_features))
        self.bias1 = torch.nn.Parameter(torch.zeros(hidden_features))
        self.weight2 = torch.nn.Parameter(torch.empty(out_features, hidden_features))
        self.bias2 = torch.nn.Parameter(torch.zeros(out_features))
        torch.nn.init.kaiming_uniform_(self.weight1, a=5 ** 0.5)
        torch.nn.init.kaiming_uniform_(self.weight2, a=5 ** 0.5)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        N = self.n_node
        src = edge_index[0].long()
        dst = edge_index[1].long()
        valid = (src >= 0) & (src < N) & (dst >= 0) & (dst < N)
        src, dst = src[valid], dst[valid]

        agg = (1.0 + self.eps) * x
        agg = agg.index_add(0, dst, x[src])

        h = torch.relu(agg @ self.weight1.t() + self.bias1)
        out = h @ self.weight2.t() + self.bias2
        return out


class GATConvDynamic(hls4ml.utils.torch.HLS4MLModule):
    """Single-head GAT (PyG ``GATConv``, heads=1) on a dynamic graph.

        h_i      = x_i W
        e_ij     = LeakyReLU(a_src . h_src + a_dst . h_dst)
        alpha_ij = softmax_{j in N(i)}(e_ij)
        out_i    = sum_j alpha_ij h_j + b

    GAT adds self-loops by default, so feed a self-loop-augmented edge_index
    (``prepare_edge_index(add_self_loops=True)``).
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        n_node: int,
        max_edges: int,
        negative_slope: float = 0.2,
        bias: bool = True,
    ):
        super().__init__()
        self.in_features = int(in_features)
        self.out_features = int(out_features)
        self.n_node = int(n_node)
        self.n_edge = int(max_edges)
        self.negative_slope = float(negative_slope)
        self.aggregation = "sum"

        self.weight = torch.nn.Parameter(torch.empty(out_features, in_features))
        self.att_src = torch.nn.Parameter(torch.empty(out_features))
        self.att_dst = torch.nn.Parameter(torch.empty(out_features))
        torch.nn.init.kaiming_uniform_(self.weight, a=5 ** 0.5)
        torch.nn.init.normal_(self.att_src, std=0.1)
        torch.nn.init.normal_(self.att_dst, std=0.1)
        if bias:
            self.bias = torch.nn.Parameter(torch.zeros(out_features))
        else:
            self.register_parameter("bias", None)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        N = self.n_node
        h = x @ self.weight.t()                 # [N, out]
        asrc = h @ self.att_src                 # [N]
        adst = h @ self.att_dst                 # [N]

        src = edge_index[0].long()
        dst = edge_index[1].long()
        valid = (src >= 0) & (src < N) & (dst >= 0) & (dst < N)
        src, dst = src[valid], dst[valid]

        z = asrc[src] + adst[dst]
        e = torch.where(z > 0, z, self.negative_slope * z)  # LeakyReLU

        emax = torch.full((N,), float("-inf"), dtype=h.dtype, device=h.device)
        emax = emax.scatter_reduce(0, dst, e, reduce="amax", include_self=True)
        ex = torch.exp(e - emax[dst])
        denom = torch.zeros(N, dtype=h.dtype, device=h.device).index_add(0, dst, ex)
        alpha = ex / denom[dst].clamp(min=1e-30)

        out = torch.zeros(N, self.out_features, dtype=h.dtype, device=h.device)
        out = out.index_add(0, dst, alpha.unsqueeze(-1) * h[src])
        if self.bias is not None:
            out = out + self.bias
        return out


class EGNNDynamic(hls4ml.utils.torch.HLS4MLModule):
    """E(n)-equivariant GNN layer (Satorras et al. 2021) on a dynamic graph.

    Inputs ``(h, x, edge_index)``; output is the concatenation ``[h' | x']`` of
    shape ``[N, n_h + n_coord]``. Coordinates enter only through the invariant
    squared distance and move along relative vectors, so the layer is
    E(n)-equivariant: rotating/translating ``x`` rotates/translates ``x'`` and
    leaves ``h'`` unchanged.

        m_e  = phi_e([h_d, h_s, ||x_d-x_s||^2])
        m_i  = sum_e m_e ;  dx_i = sum_e (x_i - x_s) * phi_x(m_e)
        h_i' = h_i + phi_h([h_i, m_i]) ;  x_i' = x_i + dx_i
    """

    def __init__(
        self,
        n_h: int,
        n_coord: int,
        n_node: int,
        max_edges: int,
        msg_dim: int = 8,
        hidden_dim: int = 16,
    ):
        super().__init__()
        self.n_h = int(n_h)
        self.n_coord = int(n_coord)
        self.n_msg = int(msg_dim)
        self.n_hidden = int(hidden_dim)
        self.n_node = int(n_node)
        self.n_edge = int(max_edges)
        self.in_features = int(n_h)
        self.out_features = int(n_h + n_coord)

        e_in = 2 * self.n_h + 1
        h_in = self.n_h + self.n_msg
        self.phi_e = torch.nn.Sequential(
            torch.nn.Linear(e_in, self.n_hidden), torch.nn.ReLU(),
            torch.nn.Linear(self.n_hidden, self.n_msg),
        )
        self.phi_x = torch.nn.Linear(self.n_msg, 1)
        self.phi_h = torch.nn.Sequential(
            torch.nn.Linear(h_in, self.n_hidden), torch.nn.ReLU(),
            torch.nn.Linear(self.n_hidden, self.n_h),
        )

    def forward(self, h: torch.Tensor, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        N = self.n_node
        src = edge_index[0].long()
        dst = edge_index[1].long()
        valid = (src >= 0) & (src < N) & (dst >= 0) & (dst < N)
        src, dst = src[valid], dst[valid]

        rel = x[dst] - x[src]                               # [Ev, C]
        dist2 = (rel * rel).sum(-1, keepdim=True)           # [Ev, 1]
        e_in = torch.cat([h[dst], h[src], dist2], dim=-1)   # [Ev, 2H+1]
        m_e = self.phi_e(e_in)                              # [Ev, M]
        wcoef = self.phi_x(m_e)                             # [Ev, 1]

        m_node = torch.zeros(N, self.n_msg, dtype=h.dtype, device=h.device).index_add(0, dst, m_e)
        dx = torch.zeros(N, self.n_coord, dtype=x.dtype, device=x.device).index_add(0, dst, rel * wcoef)

        h_out = h + self.phi_h(torch.cat([h, m_node], dim=-1))
        x_out = x + dx
        return torch.cat([h_out, x_out], dim=-1)            # [N, H+C]
