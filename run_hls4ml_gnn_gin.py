"""End-to-end demo: a real ``torch_geometric`` GINConv through hls4ml.

GINConv: out = MLP((1+eps) x_i + sum_{j in N(i)} x_j). We lower it into the
self-contained ``GINConvDynamic`` (aggregation + 2-layer ReLU MLP in one HLS
kernel), prove it matches the real PyG layer in float, then synthesize.

Run on the server (venv active + Vitis on PATH):

    pip install torch_geometric
    python run_hls4ml_gnn_gin.py
"""

import numpy as np
import torch
from torch_geometric.nn import GINConv

import hls4ml
import hls4ml_gnn
from hls4ml_gnn import from_ginconv, prepare_edge_index

BACKEND = "Vitis"
PART = "xczu3eg-sbva484-1-e"
N, F_IN, H, F_OUT = 6, 4, 8, 4
E = 2 * N  # ring, no self-loops (GIN adds the self term explicitly)


def ring_edge_index(n):
    src, dst = [], []
    for i in range(n):
        for j in ((i - 1) % n, (i + 1) % n):
            src.append(j)
            dst.append(i)
    return torch.tensor([src, dst], dtype=torch.long)


class PyGNet(torch.nn.Module):
    def __init__(self):
        super().__init__()
        mlp = torch.nn.Sequential(
            torch.nn.Linear(F_IN, H), torch.nn.ReLU(), torch.nn.Linear(H, F_OUT)
        )
        self.conv = GINConv(mlp, eps=0.3, train_eps=False)

    def forward(self, x, edge_index):
        return self.conv(x, edge_index)


def main():
    torch.manual_seed(0)

    pyg = PyGNet().eval()
    x = torch.randn(N, F_IN)
    ei_raw = ring_edge_index(N)
    pyg_out = pyg(x, ei_raw).detach().numpy().reshape(N, F_OUT)

    ei = prepare_edge_index(ei_raw, n_node=N, add_self_loops=False, max_edges=E)
    assert ei.shape[1] == E, f"E mismatch: {ei.shape[1]} vs {E}"
    gin = from_ginconv(pyg.conv, n_node=N, max_edges=E)

    adapter_out = gin(x, ei).detach().numpy().reshape(N, F_OUT)
    adapter_err = float(np.max(np.abs(pyg_out - adapter_out)))
    print("max |GINConv - adapter(torch)| =", adapter_err)
    assert adapter_err < 1e-4, "adapter does not match GINConv in float -- check semantics"

    class Wrapped(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.gc = m

        def forward(self, x, edge_index):
            return self.gc(x, edge_index)

    model = Wrapped(gin).eval()

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
        output_dir="hls4ml_gnn_gin_prj",
        backend=BACKEND,
        part=PART,
        io_type="io_parallel",
        hls_config=cfg,
    )

    hmodel.compile()
    ei_np = ei.numpy().astype(np.float32).reshape(1, 2, E)
    hres = np.asarray(hmodel.predict([x.numpy().reshape(1, N, F_IN), ei_np])).reshape(N, F_OUT)

    err = float(np.max(np.abs(pyg_out - hres)))
    print("max |GINConv - hls4ml|        =", err)
    print("GINConv[0]:", np.round(pyg_out[0], 4))
    print("hls4ml [0]:", np.round(hres[0], 4))

    hmodel.build(csim=True, synth=True, cosim=True, export=True)
    print(hls4ml.report.read_vivado_report("hls4ml_gnn_gin_prj"))


if __name__ == "__main__":
    main()
