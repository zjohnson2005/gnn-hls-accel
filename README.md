# GNN-on-HLS accelerator + Agent Orchestration Engine (APU core)

Baseline message-passing GNN accelerator in Vitis HLS, plus a **primary thesis
track** for custom hardware agent orchestration in `orchestration_engine/`.
single **GCN layer** (PyG `GCNConv` ordering) that doubles as:

- the concrete artifact to port into hls4ml's `ModelGraph` / multi-backend codegen (Phase A), and
- the tier-partitionable driver workload for the "HLS for 3D IC" case study (Phase B):
  the **aggregate** stage is memory-bound (gather from neighbors), the **combine** stage
  is compute-bound (dense MLP) — a clean cut for assigning stages to different dies/tiers.

## What it computes

One GCN propagation step with symmetric normalization:

```
Xt   = X * W + b                          # combine / linear transform
Y[i] = sum_{j in N(i)} c(i,j) * Xt[j]     # normalized neighbor aggregate
c(i,j) = 1/sqrt(deg_i) * 1/sqrt(deg_j)
```

Self-loops (`A + I`) are assumed already present in the CSR graph, so
`deg_i = row_ptr[i+1] - row_ptr[i]`.

## Layout

| File                | Purpose                                                        |
|---------------------|----------------------------------------------------------------|
| `src/gcn_layer.h`   | Compile-time sizes, `ap_fixed` datatypes, top-level prototype  |
| `src/gcn_layer.cpp` | Kernel: inv-sqrt-degree -> combine -> normalized aggregate     |
| `tb/gcn_tb.cpp`     | 6-node ring testbench, double-precision golden + tolerance     |
| `run_hls.tcl`       | C-sim -> C-synth -> cosim for `xczu3eg-sbva484-1-e` @ 3.33 ns   |

## Design choices (baseline)

- **Precision:** `ap_fixed<16,6>` datapath, `ap_fixed<32,12>` accumulators.
  Narrowing internal bitwidth is the primary Fmax lever and the first thing to chase next.
- **Graph bounds:** `MAX_NODES=256`, `MAX_EDGES=4096`, `F_IN=F_OUT=16`, all on-chip BRAM.
- **Normalization:** `1/sqrt(deg)` currently uses an `hls::sqrt` core for correctness —
  the obvious target for a Newton-Raphson reciprocal/rsqrt replacement.
- **Structure:** three sequential stages over BRAM arrays. The combine→aggregate
  boundary is a full-array dependency (gather is irregular), so it does not yet stream;
  converting to true `DATAFLOW`/`hls::stream` is a planned optimization.

## Build / run (on the Xilinx box)

The toolchain is not installed locally; run on the machine that has Vitis HLS.

```bash
# re-source every session (SSH sessions drop)
source /tools/software/xilinx/setup_env.sh
export PATH=/tools/software/xilinx/ARCHIVE/Vitis_HLS/2024.2/bin:$PATH

cd gnn-hls-accel
rm -rf gcn_proj          # always clear stale project before re-running
vitis_hls -f run_hls.tcl
```

Where to read results:

- **C-sim** console: `TEST PASSED` / `max abs error`.
- **C-synth** estimates: `gcn_proj/sol1/syn/report/gcn_layer_csynth.rpt` (II, est. Fmax, resources).
- **cosim** real cycles: `gcn_proj/sol1/sim/report/gcn_layer_cosim.rpt` — this is the
  number to quote for any speedup (`baseline_cosim / optimized_cosim`).

## Project map (Phase A generator + Phase B 3D co-design)

Phase A — generic GNN accelerator generation (the committed floor):

| Component | Files | Build |
|-----------|-------|-------|
| A1 baseline GCN | `src/gcn_layer.{h,cpp}`, `tb/gcn_tb.cpp` | `run_hls.tcl` |
| A2 precision + NR rsqrt | `src/gnn_config.h`, `src/hls_rsqrt.h` | `run_hls_sweep.tcl` |
| A3 DATAFLOW streaming seam | `src/gcn_layer_stream.{h,cpp}`, `tb/gcn_stream_tb.cpp` | `run_hls_stream.tcl` |
| A4 message-passing template | `src/mp_template.h`, `src/mp_layers.{h,cpp}` (GIN/SAGE), `tb/{gin,sage}_tb.cpp` | `run_hls_mp.tcl` |
| A5 EGNN workload | `src/egnn_layer.{h,cpp}`, `tb/egnn_tb.cpp` | `run_hls_egnn.tcl` |
| A6 hls4ml port | `hls4ml_gnn/` (IR, PyG parser, codegen) | `python -m hls4ml_gnn.example_generate` |
| A7 hls4ml Extension layers | `hls4ml_gnn/{nnet_graph.h,torch_modules.py,hls_layers.py,converters.py,templates.py,register.py}` | `python run_hls4ml_gnn.py` (fixed), `python run_hls4ml_gnn_dynamic.py` (dynamic) |
| A8 torch_geometric layers | `hls4ml_gnn/pyg_adapter.py` lowers real PyG `GCNConv`/`SAGEConv`/`GINConv`/`GATConv` | `pip install torch_geometric && python run_hls4ml_gnn_pyg.py` (GCN), `_sage.py`, `_gin.py`, `_gat.py` |
| A9 multi-layer + equivariant | stacked message passing + ReLU; EGNN (`EGNNDynamic`, h+x+edge_index → [h'\|x']) | `python run_hls4ml_gnn_multilayer.py`, `python run_hls4ml_gnn_egnn.py` |

Phase B — HLS-level 3D-IC co-design (the ambitious ceiling), all pure-Python:

| Rung | Entry point |
|------|-------------|
| B1–B3 fixed-EGNN arms + metrics | `python -m cost_model_3d.experiment` |
| B4 architecture sweep + corpus | `python -m cost_model_3d.sweep` |
| B4 QoR surrogate | `python -m cost_model_3d.surrogate` |
| B5 design-rule extraction | `python -m cost_model_3d.rules` |

See `cost_model_3d/README.md` for the cost-model details and `docs/research_positioning.md`
for the prior-art "how we differ" analysis.

**FIFO Pareto demo:** `fifo_pareto/` — live latency/BRAM frontier animation on top of
LightningSim V2 (see `fifo_pareto/README.md`).

## Agent orchestration engine (thesis pivot)

Custom hardware orchestration for agentic AI — dynamic CSR dependency graph,
MSHR-style outstanding waits, scatter-on-completion, evaluated via HLS +
LightningSim. See **`orchestration_engine/README.md`**.

**Start here (Phase 0/1 — publishable floor):**

```powershell
py -3 -m pip install -r orchestration_engine/characterization/requirements-langgraph.txt

py -3 -m orchestration_engine.characterization.langgraph_react.run --preset action_heavy --concurrency 1 --analyze
py -3 -m orchestration_engine.characterization.langgraph_react.run --preset action_heavy --concurrency 100 --analyze

py -3 -m orchestration_engine.characterization.run --trace orchestration_engine/characterization/out/langgraph_c100.json
```

## Status / next steps

Code for every rung is in the repo. The remaining work is **verification on the
remote Vitis box** (no Vitis locally):

1. A1: run `run_hls.tcl`, confirm `TEST PASSED`, capture reference cosim cycles + csynth.
2. A2: run `run_hls_sweep.tcl`, compare accuracy/II/Fmax across precision + rsqrt arms.
3. A3: run `run_hls_stream.tcl`, quote cosim delta vs the A1 baseline.
4. A4/A5: run `run_hls_mp.tcl` and `run_hls_egnn.tcl`, confirm csim + capture per-kernel csynth.
5. Feed per-kernel csynth/activity numbers into `cost_model_3d/kernel_graph.py` to
   replace the analytical defaults, then re-run the Phase B experiment/sweep/rules.
