# Live FIFO depth Pareto frontier demo (LightningSim V2 + FIFOAdvisor)

# FIFO Pareto Frontier — Live Demo

Multi-objective FIFO depth design space exploration on top of **LightningSim V2**
parallel evaluation. Sweeps hundreds or thousands of latency/BRAM tradeoff points
in seconds and animates the Pareto frontier forming in real time.

This fills the gap left by prior FIFO sizing work (hls4ml cosim profiling, Vitis
HLS RTL iteration, FIFOAdvisor minimum-stall heuristics): **the engineering
tradeoff is not "find the smallest depth that doesn't stall" — it's the full
Pareto set** of depth assignments where you cannot improve latency without
spending more BRAM, or cut BRAM without accepting more latency.

## Background

| Paper | Role |
|-------|------|
| **LightningSim** (FCCM 2023) | Trace-based cycle-accurate HLS simulator ~100× faster than RTL cosim |
| **LightningSim V2** (FCCM 2024) | Graph-compiled simulation; incremental FIFO-depth re-eval in <1 ms; trivially parallel DSE across CPU cores |
| **FIFOAdvisor** (ASP-DAC 2026) | Black-box dual-objective optimizer (latency + BRAM) built on LightningSim; extracts Pareto points from random/SA search |

V2 makes the inner loop fast enough to explore **thousands** of FIFO configurations
per design. This tool visualizes that exploration live: latency on Y, total FIFO
BRAM on X, dots filling in, the green frontier crystallizing.

**Hook for demos:** *"Same HLS design, ten different cost-performance points,
found in seconds — cosim could never explore this space."*

## Quick start (offline, no Vitis)

Requires Python 3.11+ and matplotlib:

```bash
pip install matplotlib numpy

# 2000-point sweep on a 24-FIFO synthetic design (~instant)
python -m fifo_pareto.live_demo --n-samples 2000 --batch-size 128

# Larger synthetic benchmark (~178 FIFOs, k15mmtree shape)
python -m fifo_pareto.live_demo --synthetic k15mmtree --n-samples 3000

# Save final frame
python -m fifo_pareto.live_demo --save pareto.png --export results.json
```

## With LightningSim (remote Vitis box)

**Vitis version:** synthesize the target kernel with **2021.1–2024.x** (site ARCHIVE),
not the same 2025.x toolchain used for orchestration scatter cosim. LightningSim
0.2.x trace capture and AXI models target that era; 2025.x may fail `trace.pkl`
generation or skew FIFO latency (see [LightningSim setup docs](https://lightningsim-doc.readthedocs.io/en/latest/tutorial/setup-local.html)).
This repo runs DSE on `gcn_stream_proj` (DATAFLOW GNN substrate) via
`orchestration_engine/run_phase2_lightningsim.sh`, which sources
`hls_env_lightningsim.sh` (ARCHIVE 2024.2 → 2023.1 → 2021.1).

Install [fifo-advisor](https://github.com/sharc-lab/fifo-advisor) (includes
LightningSim 0.2.6 via conda):

```bash
conda env create -f environment.yml   # from fifo-advisor repo
conda activate fifo-advisor
pip install --no-deps git+https://github.com/sharc-lab/fifo-advisor.git

# After Vitis HLS csynth + testbench on your design:
python -m fifo_pareto.live_demo \
  --solution-dir /path/to/hls_proj/solution1 \
  --n-samples 2000 \
  --batch-size 128
```

The first run builds/caches `trace.pkl` in the solution directory (one-time
LightningSim trace capture). Subsequent batches use V2's parallel
`compiled.dse()` path — the same fast evaluator FIFOAdvisor uses internally.

## Replay fifo-advisor JSON

```bash
fifo-advisor <solution_dir> --solver group-random --n-samples 2000 --output run.json
python -m fifo_pareto.live_demo --replay run.json --batch-size 64
```

## Architecture

```
fifo_pareto/
  pareto.py      Pareto extraction + BRAM18K model (FIFOAdvisor §III-B/C)
  synthetic.py   Offline stall model for laptop demos
  sweep.py       Streaming batch sweep (LSEnv wrapper or synthetic)
  live_demo.py   Animated matplotlib UI + CLI
```

**Evaluation loop** (matches FIFOAdvisor formulation):

```
minimize (f_lat(x), f_bram(x))
subject to: no deadlock, 2 ≤ x_i ≤ u_i
LightningSim_V2.dse(x) → (latency, BRAM) in <1 ms amortized
```

**Why grouped sampling:** Stream-HLS and GNN dataflow designs use FIFO arrays
(`hls::stream T data[N]`). Grouped random search (FIFOAdvisor §III-D) assigns
one depth per array — better frontier quality per sample.

## Integration with this repo

The GNN HLS accelerators in `src/gcn_layer_stream.*` and `hls4ml_gnn/` are
natural targets once synthesized with `#pragma HLS DATAFLOW` and profiled
FIFOs. Workflow:

1. Run Vitis HLS csynth on a streaming GNN kernel
2. Point `--solution-dir` at `solution1/`
3. Watch the latency/BRAM frontier for that kernel's FIFO topology

## References

```bibtex
@inproceedings{lightningsim,
  title={LightningSim: Fast and Accurate Trace-Based Simulation for High-Level Synthesis},
  author={Sarkar, Rishov and Hao, Callie},
  booktitle={FCCM}, year={2023}
}
@inproceedings{lightningsimv2,
  title={LightningSimV2: Faster and Scalable Simulation for HLS via Graph Compilation},
  author={Sarkar, Rishov and Paul, Rachel and Hao, Callie},
  booktitle={FCCM}, year={2024}
}
@inproceedings{fifoadvisor,
  title={{FIFOAdvisor}: Automated FIFO Sizing DSE for HLS Designs},
  author={Abi-Karam, Stefan and Sarkar, Rishov and Basalama, Suhail and Cong, Jason and Hao, Callie},
  booktitle={ASP-DAC}, year={2026}
}
```
