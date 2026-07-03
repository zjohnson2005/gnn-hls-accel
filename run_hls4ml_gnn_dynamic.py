"""End-to-end demo: a DYNAMIC-graph GNN through hls4ml via hls4ml_gnn.

This is the real bar: the graph connectivity (`edge_index`, PyG COO convention)
is a *runtime input* to the accelerator, not baked in. The same compiled design
handles any graph up to (N, max_edges).

Run on the server (venv active + Vitis on PATH):

    python run_hls4ml_gnn_dynamic.py

Flow is the standard hls4ml one, just with two inputs:
    config_from_pytorch_model([(N,F_in),(2,E)]) -> convert -> compile/predict -> build
"""

import numpy as np
import torch

import hls4ml
import hls4ml_gnn
from hls4ml_gnn.torch_modules import GraphMPDynamic

BACKEND = "Vitis"
PART = "xczu3eg-sbva484-1-e"
N, F_IN, F_OUT, E = 6, 4, 8, 18


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
        self.gc = GraphMPDynamic(F_IN, F_OUT, n_node=N, max_edges=E, aggregation="mean", normalize=False)

    def forward(self, x, edge_index):
        return self.gc(x, edge_index)


def main():
    torch.manual_seed(0)
    model = GNN().eval()
    ei = ring_edge_index(N)  # [2, E]
    assert ei.shape[1] == E, f"E mismatch: {ei.shape[1]} vs {E}"

    # 1. Drop the dynamic GNN layer into hls4ml.
    hls4ml_gnn.register()

    # 2. Standard hls4ml flow with two inputs (features + edge_index).
    cfg = hls4ml.utils.config_from_pytorch_model(
        model,
        [(N, F_IN), (2, E)],
        default_precision="ap_fixed<12,4>",
        granularity="name",
        backend=BACKEND,
        channels_last_conversion="off",
        transpose_outputs=False,
    )
    # edge_index carries integer node ids -> give that input an unsigned-int type.
    # (The input layer is named after the forward() arg: 'edge_index'.)
    for lname, lcfg in cfg.get("LayerName", {}).items():
        if "edge_index" in lname:
            lcfg.setdefault("Precision", {})
            lcfg["Precision"]["result"] = "ap_uint<8>"

    hmodel = hls4ml.converters.convert_from_pytorch_model(
        model,
        output_dir="hls4ml_gnn_dyn_prj",
        backend=BACKEND,
        part=PART,
        io_type="io_parallel",
        hls_config=cfg,
    )

    # 3. C-sim vs PyTorch reference.
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

    # 4. Synthesize with Vitis HLS.
    hmodel.build(csim=False, synth=True, cosim=False, export=False)
    print(hls4ml.report.read_vivado_report("hls4ml_gnn_dyn_prj"))


if __name__ == "__main__":
    main()
