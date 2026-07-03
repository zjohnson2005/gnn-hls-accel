# hls4ml_gnn — generic GNN front-end + message-passing backend (Phase A / A6)

This package is the Phase A generator: **PyG model in → HLS accelerator out**.
It fills the gap the hls4ml 2025 platform paper documents (no PyTorch Geometric
support; generic GNN support still in development) by adding the two pieces
hls4ml lacks for message passing.

## Pipeline

```
PyG MessagePassing model
      │  pyg_parser.parse_pyg_model        (front-end: torch -> IR)
      ▼
GNNModelGraph  (ir.py)                      (ModelGraph-style IR)
      │  codegen.emit_accelerator          (backend: IR -> HLS C++)
      ▼
generated_model.{h,cpp}  +  run_generated.tcl
      │  vitis_hls -f run_generated.tcl
      ▼
RTL / QoR report  ──►  feeds Phase B cost model
```

- `ir.py` — `GNNModelGraph` / `GNNLayer` / `LinearSpec` / `Aggregation`. The
  IR keeps the aggregate/update split explicit; `seam_payload_bits()` reports
  the bandwidth crossing that seam (the Phase B tier cut).
- `pyg_parser.py` — lowers `GCNConv` / `GINConv` / `SAGEConv` into the IR.
  `parse_layer_specs` is a torch-free path for tests and the Phase B sweep.
- `codegen.py` — emits C++ that instantiates the `src/mp_template.h`
  primitives (`mp_linear`, `mp_aggregate`) plus a Vitis project.
- `example_generate.py` — runnable demo (no torch needed).

## Quick start (torch-free)

```bash
cd gnn-hls-accel
python -m hls4ml_gnn.example_generate     # writes ./generated/*
# then on the Vitis box:
cd generated && rm -rf gen_proj && vitis_hls -f run_generated.tcl
```

## Where this attaches inside upstream hls4ml

The package is structured to mirror hls4ml seams so it can be lifted in with
minimal change:

1. **Front-end (converters).** Register a PyG reader alongside the existing
   PyTorch parser in `hls4ml/converters/` (e.g. `pytorch_to_hls` /
   `convert_from_pytorch_model`). `pyg_parser._PYG_LAYER_MAP` is the layer
   handler table; in hls4ml this is the `@pytorch_handler(...)` registry.
2. **IR (ModelGraph).** `GNNModelGraph`/`GNNLayer` correspond to hls4ml's
   `ModelGraph`/`Layer` in `hls4ml/model/graph.py`. Upstreaming means adding
   message-passing layer classes (`GNNAggregate`, `GNNCombine`) to
   `hls4ml/model/layers.py` with their `Attribute`s (aggregation, normalize,
   feature dims, edge bounds).
3. **Backend templates.** `codegen.py` is the analogue of a backend pass in
   `hls4ml/backends/<backend>/passes/`. The C++ it emits calls into the
   message-passing template header (`src/mp_template.h`), which would ship in
   `hls4ml/templates/` as `nnet_gnn.h` next to `nnet_dense.h`.
4. **Config.** `precision_profile` maps to hls4ml's per-layer `Precision`
   config; `gnn_config.h` is the generated `defines.h` precision block.

## Scope notes

- Auto-chained codegen covers GCN and GraphSAGE (single-linear update). GIN and
  EGNN ship as dedicated hand-written tops (`src/mp_layers.cpp`,
  `src/egnn_layer.cpp`) because their multi-layer MLPs are clearer hand-written;
  the generator references those rather than re-emitting them.
- This is "Level 1" tooling per the roadmap: Vitis HLS stays an unmodified
  black-box backend; all generation logic lives in this layer around it.
