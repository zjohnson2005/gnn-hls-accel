"""End-to-end demo: a GNN through hls4ml via the hls4ml_gnn extension.

Run on the server (venv active + Vitis on PATH):

    python run_hls4ml_gnn.py

It builds a 1-layer fixed-graph GNN in PyTorch, registers our extension into
hls4ml, then runs the *standard* hls4ml flow:
    config_from_pytorch_model -> convert_from_pytorch_model -> compile/predict -> build

Success = hls4ml csim output matches the PyTorch reference, then Vitis HLS
csynth completes and prints a report.
"""

import numpy as np
import torch

import hls4ml
import hls4ml_gnn
from hls4ml_gnn.torch_modules import GraphMP

BACKEND = "Vitis"
PART = "xczu3eg-sbva484-1-e"
N, F_IN, F_OUT = 6, 4, 8


def ring_adj(n):
    """Ring graph with self-loops (each node connects to itself + 2 neighbors)."""
    a = np.eye(n, dtype=np.float32)
    for i in range(n):
        a[i, (i - 1) % n] = 1.0
        a[i, (i + 1) % n] = 1.0
    return a


class GNN(torch.nn.Module):
    def __init__(self, adj):
        super().__init__()
        self.gc = GraphMP(F_IN, F_OUT, adj, aggregation="mean", normalize=False)

    def forward(self, x):
        return self.gc(x)


def main():
    torch.manual_seed(0)
    adj = ring_adj(N)
    model = GNN(adj).eval()

    # 1. Drop the GNN layer into hls4ml.
    hls4ml_gnn.register()

    # 2. Standard hls4ml flow.
    cfg = hls4ml.utils.config_from_pytorch_model(
        model,
        (N, F_IN),
        default_precision="ap_fixed<16,6>",
        granularity="name",
        backend=BACKEND,
        channels_last_conversion="off",
        transpose_outputs=False,
    )
    hmodel = hls4ml.converters.convert_from_pytorch_model(
        model,
        output_dir="hls4ml_gnn_prj",
        backend=BACKEND,
        part=PART,
        io_type="io_parallel",
        hls_config=cfg,
    )

    # 3. C-sim vs PyTorch reference.
    hmodel.compile()
    x = torch.randn(N, F_IN)
    ref = model(x).detach().numpy().reshape(N, F_OUT)
    hres = np.asarray(hmodel.predict(x.numpy().reshape(1, N, F_IN))).reshape(N, F_OUT)

    err = np.max(np.abs(ref - hres))
    print("max |torch - hls4ml| =", err)
    print("PyTorch[0]:", np.round(ref[0], 4))
    print("hls4ml [0]:", np.round(hres[0], 4))

    # 4. Synthesize with Vitis HLS.
    hmodel.build(csim=False, synth=True, cosim=False, export=False)
    print(hls4ml.report.read_vivado_report("hls4ml_gnn_prj"))


if __name__ == "__main__":
    main()
