"""End-to-end demo: a MULTI-LAYER dynamic-graph GNN through hls4ml.

Proves layer composition works through the hls4ml extension: two
``GraphMPDynamic`` message-passing layers with a ReLU in between, both sharing
the same runtime ``edge_index`` input port. This is the shape of a real GNN
(stacked message passing + nonlinearity), not a single layer.

    x ->[GraphMP 4->8]-> ReLU ->[GraphMP 8->4]-> out
         \____________ edge_index ____________/

The ReLU is hls4ml's native layer; only the message-passing layers come from
our extension -- so this also exercises mixing custom + built-in layers.

Run on the server (venv active + Vitis on PATH):

    python run_hls4ml_gnn_multilayer.py
"""

import numpy as np
import torch

import hls4ml
import hls4ml_gnn
from hls4ml_gnn.torch_modules import GraphMPDynamic

BACKEND = "Vitis"
PART = "xczu3eg-sbva484-1-e"
N, F_IN, F_HID, F_OUT, E = 6, 4, 8, 4, 18


def ring_edge_index(n):
    """COO edge_index [2, E] for a ring with self-loops (PyG convention)."""
    src, dst = [], []
    for i in range(n):
        for j in (i, (i - 1) % n, (i + 1) % n):
            src.append(j)
            dst.append(i)  # message j -> i
    return np.array([src, dst], dtype=np.int64)


class GNN(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.gc1 = GraphMPDynamic(F_IN, F_HID, n_node=N, max_edges=E, aggregation="mean", normalize=False)
        self.gc2 = GraphMPDynamic(F_HID, F_OUT, n_node=N, max_edges=E, aggregation="mean", normalize=False)

    def forward(self, x, edge_index):
        h = self.gc1(x, edge_index)
        h = torch.relu(h)
        h = self.gc2(h, edge_index)
        return h


def main():
    torch.manual_seed(0)
    model = GNN().eval()
    ei = ring_edge_index(N)
    assert ei.shape[1] == E, f"E mismatch: {ei.shape[1]} vs {E}"

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
        output_dir="hls4ml_gnn_ml_prj",
        backend=BACKEND,
        part=PART,
        io_type="io_parallel",
        hls_config=cfg,
    )

    hmodel.compile()
    x = torch.randn(N, F_IN)
    eit = torch.tensor(ei)
    ref = model(x, eit).detach().numpy().reshape(N, F_OUT)
    hres = np.asarray(
        hmodel.predict([x.numpy().reshape(1, N, F_IN), ei.reshape(1, 2, E).astype(np.float32)])
    ).reshape(N, F_OUT)

    err = np.max(np.abs(ref - hres))
    print("max |torch - hls4ml| =", err)
    print("PyTorch[0]:", np.round(ref[0], 4))
    print("hls4ml [0]:", np.round(hres[0], 4))

    hmodel.build(csim=True, synth=True, cosim=True, export=True)
    print(hls4ml.report.read_vivado_report("hls4ml_gnn_ml_prj"))


if __name__ == "__main__":
    main()
