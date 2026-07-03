# Phase 2 gate report

**Status:** IN PROGRESS (4 checklist items pending)

## Phase 2 crossover (measured scatter + full-path delivery)

**Verdict:** `PENDING_CSYNTH`

Crossover table uses analytic scatter target; run run_hls_scatter.tcl on the Vitis box and re-run phase2_gate.gate_report.

- Hardware scatter (fan-out=2): **3 cycles** = **0.01 µs** @ 300.0 MHz
- csynth source: `analytic (pending csynth)`

| baseline | µs/completion | vs engine+PCIe | vs engine+on-SoC |
|----------|---------------|----------------|------------------|
| LangGraph (deployed) | 1677.78 | 2207.6x | 15252.5x |
| asyncio + epoll (measured full-path) | 7.0 | 9.2x | 63.6x |
| asyncio + kernel-bypass (measured full-path) | 4.75 | 6.2x | 43.2x |

_Scan-class O(N) crossover remains in Phase 1 check 9; this table closes Claim 2 (constant factor + energy) against event-driven baselines._

## Checklist

| item | status | detail |
|------|--------|--------|
| HLS csynth scatter kernel (run_hls_scatter.tcl) | pending | No report under oe_scatter_proj/ |
| HLS cosim scatter (trust cycle count) | pending | Enable cosim in run_hls_scatter.tcl |
| LightningSim FIFO DSE (eval/dse_sweep.py) | pending | Requires fifo-advisor on Vitis box |
| Real OpenAI anchor at c=1000 | done | C:\Users\zjohn\Projects\gnn-hls-accel\orchestration_engine\characterization\out\gate\openai_action_heavy_c1000.json |
| Native oe_bench structural proof | pending | build.ps1 on Windows or g++ on Vitis box |

## Next commands (Vitis box)

```bash
source /tools/software/xilinx/setup_env.sh
cd gnn-hls-accel
bash orchestration_engine/run_phase2.sh
```

## Next commands (OpenAI / local)

```powershell
py -3 -m orchestration_engine.characterization.phase1_gate.closeout
```