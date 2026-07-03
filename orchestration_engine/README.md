# Agent Orchestration Engine (APU core)

Custom hardware orchestration engine for agentic AI: a dynamic dataflow-graph
accelerator beside a RISC-V host. This directory is the **primary thesis track**
(pivot from GNN HLS); the GNN work in `src/` and `hls4ml_gnn/` supplies the
CSR / scatter substrate, not the product goal.

## Claim (two-part, scoped)

**Claim 1 — complexity class (measured):** scan-class schedulers grow
O(live_nodes) per coordination decision (measured 59x from N=10 to N=1000,
gate check 11); the engine's scatter-on-completion is O(fan-out). This claim
applies **only** against scan-class software, never event-driven baselines.

**Claim 2 — constant factor + energy (csynth + cosim measured):** event-driven
software is also O(fan-out) but carries measured constants — ~2 µs/decision
(ideal asyncio), ~1.7 ms/decision (deployed LangGraph, 850x worse than the
ideal, itself a finding) — vs cosim-measured scatter (**17 cycles one-shot,
0.041 µs @ 415.6 MHz csynth Fmax**; multi-transaction cosim for II pending).
Full-path accounting (completion delivery + dispatch) shows PCIe-attached
near parity with kernel-bypass software (~3.9x); the win there is
throughput/energy/offload, and on-SoC integration keeps the latency win
(check 11 full-path table).

The thesis is provable via the structural crossover (check 9) plus measured
dispatch constants (check 11) — not via E2E percentage of remote-LLM runs.
LangGraph/OpenAI traces **calibrate** workload realism (mock trace-anchored:
within 4–8 pp of real at c=100/500); `cpu_baseline` vs `engine_sim` plus
LightningSim **prove** the mechanism. Dynamic-graph capacity/append/energy
design model: `docs/dynamic_graph_cost_model.md`.

Real-trace split (check 10): coordination including per-session graph setup is
**33–50%** of accelerable CPU; steady-state dispatch alone is **12–25%**.
Setup maps to the engine's dynamic graph-load path, steady-state to
scatter-on-completion — both are hardware targets.

Target scope: **tool-heavy, bounded-fan-out** agent graphs on datacenter
orchestrator hosts at high concurrency. Must beat **optimized** software
(event-driven O(1) baseline measured at ~2 µs/decision), not naive LangGraph.

## Layout

| Path | Purpose |
|------|---------|
| `docs/` | Positioning, microarchitecture, Phase 0 disaggregation |
| `include/` | Shared CSR graph + types (software reference) |
| `software/` | Cycle simulator, CPU baseline, synthetic workloads |
| `hls/` | Synthesizable kernel scaffold (scatter + completion path) |
| `tb/` | Software + HLS testbenches |
| `eval/` | LightningSim DSE wrapper (remote Vitis box) |
| `run_hls.tcl` | C-sim → C-synth entry point |

## Microarchitecture (target)

```
Ready queue → Dispatch → [external tasks] → Completion intake → Scatter
                     ↑___________________________________|
```

On-chip state: CSR graph store, per-node readiness counters, MSHR-style
outstanding-wait table. No global scan — completion cost is O(out-degree).

**v1 scaffold status**

| Feature | Software sim | HLS kernel |
|---------|--------------|------------|
| CSR scatter on completion | yes | yes (scatter step) |
| MSHR outstanding waits | yes | stub (host-side) |
| Dynamic append / prune | yes | planned |
| Partial firing (any-of / threshold) | yes | yes |
| Coordination-first-class nodes | yes | partial |
| Speculation + rollback | simplified | planned |
| LightningSim DSE | eval skeleton | after csynth |

## Run locally (Windows / no Vitis)

Requires a C++17 compiler (`g++` or `cl`):

```powershell
cd orchestration_engine
.\build.ps1
.\build\oe_sim_tb.exe
.\build\oe_bench.exe 4 2 42
```

Or manually:

```powershell
g++ -std=c++17 -I include -I software -o oe_sim_tb.exe `
  software/engine_sim.cpp software/cpu_baseline.cpp software/workload_gen.cpp `
  tb/oe_sim_tb.cpp
```

## Run HLS + LightningSim (remote Vitis box)

```bash
source /tools/software/xilinx/setup_env.sh
cd gnn-hls-accel

# Full Phase 2 pipeline (scatter csynth → engine csynth → oe_bench → DSE → gate):
bash orchestration_engine/run_phase2.sh

# Or step-by-step:
rm -rf oe_scatter_proj && vitis_hls -f orchestration_engine/run_hls_scatter.tcl
rm -rf oe_proj && vitis_hls -f orchestration_engine/run_hls.tcl

# Streaming scatter (steady-state cycles/completion; 8 completions/invocation,
# compact ready-event output instead of an O(N) flag scan):
bash orchestration_engine/run_phase2_scatter_stream.sh

# After csynth produces solution1/:
python3 -m orchestration_engine.eval.dse_sweep \
  --solution-dir oe_proj/sol1 \
  --n-samples 500 \
  --output orchestration_engine/characterization/out/phase2/dse_report.json

python3 -m orchestration_engine.phase2_gate.gate_report
```

Phase 1 → Phase 2 handoff (local):

```powershell
py -3 -m orchestration_engine.characterization.phase1_gate.closeout
```

See `eval/README` inline docstring and `fifo_pareto/` for the LightningSim
toolchain setup (fifo-advisor conda env).

## Phased plan (from research brief)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | One-page 50–90% disaggregation | `docs/phase0_disaggregation.md` + `characterization/` |
| 1 | Profile agent traces; publishable coordination slice | **framework ready** — needs real instrumented runs |
| 2 | HLS baseline + proposed engine + LightningSim DSE | **in progress** — scatter csynth+cosim done; II + graph-load next |
| 3 | RISC-V host integration + crossover analysis | not started |

### Phase 0/1 (start here)

```bash
py -3 -m orchestration_engine.characterization.run
py -3 -m orchestration_engine.characterization.run --scaling --preset action_heavy

# Pre-HLS gate (structural proof + trace calibration)
py -3 -m orchestration_engine.characterization.phase1_gate.gate_report --skip-openai

# Refresh OpenAI anchors (wall-clock residual orchestration)
py -3 -m orchestration_engine.characterization.phase1_gate.gate_report --openai-only --force-openai --openai-levels 1,10,20

# Measured delivery constant (Linux: local epoll bench; Windows: literature stub)
py -3 -m orchestration_engine.characterization.epoll_wakeup_bench

# Sync check 11 hw scatter numbers after pulling csynth/cosim JSON from Vitis box
py -3 -m orchestration_engine.characterization.phase1_gate.dispatch_stress --refresh-hw
py -3 -m orchestration_engine.phase2_gate.gate_report
```

Outputs: `characterization/out/gate/gate_report.md` (check **9** = primary thesis evidence).

## Honest caveats

- Per-task scheduling overhead may be negligible when external tasks take seconds;
  the hardware case is **aggregate throughput / energy at datacenter scale**.
- Core mechanism is Picos lineage — lead with regime + dynamic graph + method.
- Dynamic graph in hardware is the hardest piece and least scaffolded in HLS.

## References

See `docs/positioning.md` and Appendix B of the research brief (GT/Intel 2025,
LightningSim V2, Picos, Halo, Agent.xpu, Helium, Graph Harness).
