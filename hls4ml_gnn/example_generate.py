"""End-to-end demo of the GNN generator (A6), torch-free.

Builds a 2-layer GCN model graph from plain specs, prints the IR, and emits a
synthesizable accelerator (generated_model.{h,cpp} + run_generated.tcl) under
./generated. Run from the repo root:

    python -m hls4ml_gnn.example_generate

With torch + torch_geometric installed you would instead call
`parse_pyg_model(model, ...)` on a live PyG module and feed the result to
`emit_accelerator` unchanged.
"""

from __future__ import annotations

import os

from .codegen import emit_accelerator
from .pyg_parser import parse_layer_specs


def main() -> None:
    specs = [
        {"name": "gcn0", "kind": "gcn", "in_dim": 16, "out_dim": 32,
         "aggregation": "sum", "normalize": True},
        {"name": "gcn1", "kind": "gcn", "in_dim": 32, "out_dim": 16,
         "aggregation": "sum", "normalize": True},
    ]
    graph = parse_layer_specs(specs, max_nodes=256, max_edges=4096,
                              precision_profile=0)
    print(graph.describe())
    print(f"total update MACs: {graph.total_update_macs()}")

    out_dir = os.path.join(os.path.dirname(__file__), "..", "generated")
    out_dir = os.path.abspath(out_dir)
    paths = emit_accelerator(graph, out_dir)
    print("emitted:")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
