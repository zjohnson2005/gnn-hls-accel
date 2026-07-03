"""End-to-end demo: a real ``torch_geometric`` GCNConv through hls4ml.

A genuine PyG ``GCNConv`` cannot be fed straight into hls4ml (its name contains
"Conv", which trips hls4ml's spatial-conv assumptions, and ``propagate()`` is
not FX-traceable). The faithful, robust path is to *lower* a trained GCNConv
into our hls4ml-native ``GraphMPDynamic`` layer with ``hls4ml_gnn.from_gcnconv``,
prove it matches the PyG layer numerically, then run that through hls4ml.

GCNConv(normalize=True, add_self_loops=True) computes
    out_i = sum_{j in N(i) U {i}} (d_i d_j)^-1/2 (x_j W) + b
The self-loop augmentation is host-side graph prep (``prepare_edge_index``).

Run on the server (venv active + Vitis on PATH):

    pip install torch_geometric        # one-time, CPU is fine for GCNConv
    python run_hls4ml_gnn_pyg.py
"""

import numpy as np
import torch
from torch_geometric.nn import GCNConv

import hls4ml
import hls4ml_gnn
from hls4ml_gnn import from_gcnconv, prepare_edge_index

BACKEND = "Vitis"
PART = "xczu3eg-sbva484-1-e"
N, F_IN, F_OUT = 6, 4, 8
# ring (2 directed edges/node) + GCNConv self-loops (N) => 3N edges
E = 3 * N


def ring_edge_index(n):
    """Raw COO ring edges [2, 2n] (no self-loops; GCNConv adds those)."""
    src, dst = [], []
    for i in range(n):
        for j in ((i - 1) % n, (i + 1) % n):
            src.append(j)
            dst.append(i)  # message j -> i
    return torch.tensor([src, dst], dtype=torch.long)


class PyGNet(torch.nn.Module):
    """The reference model: a stock torch_geometric GCNConv."""

    def __init__(self):
        super().__init__()
        self.conv = GCNConv(F_IN, F_OUT, normalize=True, add_self_loops=True, bias=True)

    def forward(self, x, edge_index):
        return self.conv(x, edge_index)


def main():
    torch.manual_seed(0)

    # 1. A real, trained PyG GCNConv (random init stands in for trained weights).
    pyg = PyGNet().eval()
    x = torch.randn(N, F_IN)
    ei_raw = ring_edge_index(N)  # [2, 2N], no self-loops
    pyg_out = pyg(x, ei_raw).detach().numpy().reshape(N, F_OUT)

    # 2. Lower GCNConv -> our hls4ml-native GraphMPDynamic and reproduce its
    #    edge preprocessing (self-loops). This is the "torch_geometric layer".
    ei = prepare_edge_index(ei_raw, n_node=N, add_self_loops=True, max_edges=E)
    assert ei.shape[1] == E, f"E mismatch: {ei.shape[1]} vs {E}"
    gmp = from_gcnconv(pyg.conv, n_node=N, max_edges=E)

    # 2a. Sanity: lowered torch module must match PyG GCNConv.
    adapter_out = gmp(x, ei).detach().numpy().reshape(N, F_OUT)
    adapter_err = float(np.max(np.abs(pyg_out - adapter_out)))
    print("max |GCNConv - adapter(torch)| =", adapter_err)
    assert adapter_err < 1e-4, "adapter does not match GCNConv in float -- check semantics"

    class Wrapped(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.gc = m

        def forward(self, x, edge_index):
            return self.gc(x, edge_index)

    model = Wrapped(gmp).eval()

    # 3. Drop the GNN extension into hls4ml and run the standard flow.
    hls4ml_gnn.register()
    cfg = hls4ml.utils.config_from_pytorch_model(
        model,
        [(N, F_IN), (2, E)],
        default_precision="ap_fixed<12,4>",
        granularity="name",
        backend=BACKEND,
        channels_last_conversion="off",
        transpose_outputs=False,
    )
    for lname, lcfg in cfg.get("LayerName", {}).items():
        if "edge_index" in lname:
            lcfg.setdefault("Precision", {})
            lcfg["Precision"]["result"] = "ap_uint<8>"

    hmodel = hls4ml.converters.convert_from_pytorch_model(
        model,
        output_dir="hls4ml_gnn_pyg_prj",
        backend=BACKEND,
        part=PART,
        io_type="io_parallel",
        hls_config=cfg,
    )

    # 4. C-sim vs the ORIGINAL PyG GCNConv.
    hmodel.compile()
    ei_np = ei.numpy().astype(np.float32).reshape(1, 2, E)
    hres = np.asarray(
        hmodel.predict([x.numpy().reshape(1, N, F_IN), ei_np])
    ).reshape(N, F_OUT)

    err = float(np.max(np.abs(pyg_out - hres)))
    print("max |GCNConv - hls4ml|        =", err)
    print("GCNConv[0]:", np.round(pyg_out[0], 4))
    print("hls4ml [0]:", np.round(hres[0], 4))

    # 5. Full Vitis HLS flow: C-sim + synthesis + C/RTL co-sim + IP export.
    hmodel.build(csim=True, synth=True, cosim=True, export=True)
    print(hls4ml.report.read_vivado_report("hls4ml_gnn_pyg_prj"))


if __name__ == "__main__":
    main()
