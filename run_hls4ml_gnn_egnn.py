"""End-to-end demo: an E(n)-equivariant GNN (EGNN) through hls4ml.

EGNN (Satorras et al. 2021) is the equivariant / point-cloud workload at the
center of the project's positioning. It has three inputs -- node features ``h``,
coordinates ``x``, and a runtime ``edge_index`` -- and produces the concatenated
update ``[h' | x']``. Coordinates enter only through the invariant squared
distance and move along relative vectors, so the layer is E(n)-equivariant.

This script:
  1. matches the hls4ml fixed-point output against the PyTorch reference, and
  2. checks equivariance: rotating the input coordinates rotates ``x'`` and
     leaves ``h'`` unchanged (verified on the float reference).

There is no EGNN in torch_geometric core, so this is our own equivariant layer
dropped into hls4ml via the extension API.

Run on the server (venv active + Vitis on PATH):

    python run_hls4ml_gnn_egnn.py
"""

import numpy as np
import torch

import hls4ml
import hls4ml_gnn
from hls4ml_gnn.torch_modules import EGNNDynamic

BACKEND = "Vitis"
PART = "xczu3eg-sbva484-1-e"
N, H, COORD, M, HID = 6, 8, 3, 8, 16
E = 2 * N  # ring, no self-loops


def ring_edge_index(n):
    src, dst = [], []
    for i in range(n):
        for j in ((i - 1) % n, (i + 1) % n):
            src.append(j)
            dst.append(i)
    return np.array([src, dst], dtype=np.int64)


def rotation_3d(seed=1):
    g = torch.Generator().manual_seed(seed)
    a = torch.randn(3, 3, generator=g)
    q, _ = torch.linalg.qr(a)
    if torch.det(q) < 0:
        q[:, 0] = -q[:, 0]
    return q


class Net(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.egnn = EGNNDynamic(H, COORD, n_node=N, max_edges=E, msg_dim=M, hidden_dim=HID)

    def forward(self, h, x, edge_index):
        return self.egnn(h, x, edge_index)


def main():
    torch.manual_seed(0)
    model = Net().eval()
    ei = ring_edge_index(N)
    assert ei.shape[1] == E

    h = torch.randn(N, H)
    x = torch.randn(N, COORD)
    eit = torch.tensor(ei)

    # --- equivariance check on the float reference ---
    out = model(h, x, eit).detach()
    h_out, x_out = out[:, :H], out[:, H:]
    R = rotation_3d()
    t = torch.randn(COORD)
    out_rt = model(h, x @ R.t() + t, eit).detach()
    h_rt, x_rt = out_rt[:, :H], out_rt[:, H:]
    h_equiv_err = float((h_rt - h_out).abs().max())
    x_equiv_err = float((x_rt - (x_out @ R.t() + t)).abs().max())
    print("equivariance: max|h' diff| =", h_equiv_err, " max|x' - (R x' + t)| =", x_equiv_err)
    assert h_equiv_err < 1e-4 and x_equiv_err < 1e-4, "EGNN layer is not equivariant -- check math"

    # --- hls4ml flow ---
    hls4ml_gnn.register()
    cfg = hls4ml.utils.config_from_pytorch_model(
        model,
        [(N, H), (N, COORD), (2, E)],
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
        output_dir="hls4ml_gnn_egnn_prj",
        backend=BACKEND,
        part=PART,
        io_type="io_parallel",
        hls_config=cfg,
    )

    hmodel.compile()
    ref = out.numpy().reshape(N, H + COORD)
    hres = np.asarray(
        hmodel.predict([
            h.numpy().reshape(1, N, H),
            x.numpy().reshape(1, N, COORD),
            ei.reshape(1, 2, E).astype(np.float32),
        ])
    ).reshape(N, H + COORD)

    err = float(np.max(np.abs(ref - hres)))
    print("max |torch - hls4ml| =", err)
    print("torch [h'|x'][0]:", np.round(ref[0], 4))
    print("hls4ml[h'|x'][0]:", np.round(hres[0], 4))

    hmodel.build(csim=True, synth=True, cosim=True, export=True)
    print(hls4ml.report.read_vivado_report("hls4ml_gnn_egnn_prj"))


if __name__ == "__main__":
    main()
