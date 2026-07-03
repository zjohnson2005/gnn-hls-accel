# Phase 2 gate report

**Status:** IN PROGRESS (3 checklist items pending)

## Phase 2 crossover (measured scatter + full-path delivery)

**Verdict:** `FULL_PATH_ADVANTAGE`

Cosim latency 17 cycles (0.0409 us one-shot) + PCIe delivery -> ~3.9x vs kernel-bypass (re-run cosim x4 for II).

- Hardware scatter (fan-out=2): **17 cycles** = **0.0409 us** @ 415.6 MHz (cosim one-shot latency)
- Cosim one-shot latency: **17 cycles** (ap_start/ap_done)
- csynth source: `oe_scatter_proj/sol1/syn/report/oe_hls_scatter_kernel_csynth.rpt`
- cosim source: `oe_scatter_proj/sol1/sim/report/oe_hls_scatter_kernel_cosim.rpt`

| baseline | us/completion | vs engine+PCIe | vs engine+on-SoC |
|----------|---------------|----------------|------------------|
| LangGraph (deployed) | 1334.83 | 1687.7x | 9473.6x |
| asyncio + epoll (measured full-path) | 5.37 | 6.8x | 38.1x |
| asyncio + kernel-bypass (measured full-path) | 3.12 | 3.9x | 22.1x |

_Delivery constants (mid-range): sw_epoll 3.5 us (Linux epoll wakeup path, see epoll_wakeup_bench.py); sw_kernel_bypass 1.25 us (DPDK/eRPC class); hw_pcie 0.75 us (PCIe Gen4 posted write); hw_cxl 0.45 us; hw_on_soc 0.10 us (AXI)._

_Scan-class O(N) crossover remains in Phase 1 check 9; this table closes Claim 2 (constant factor + energy) against event-driven baselines._

## Checklist

| item | status | detail |
|------|--------|--------|
| HLS csynth scatter kernel (run_hls_scatter.tcl) | done | oe_scatter_proj/sol1/syn/report/oe_hls_scatter_kernel_csynth.rpt |
| HLS cosim scatter (trust cycle count) | done | oe_scatter_proj/sol1/sim/report/oe_hls_scatter_kernel_cosim.rpt (17 cycles) |
| Streaming scatter cosim (steady-state cycles/completion) | pending | Run run_phase2_scatter_stream.sh on Vitis box |
| LightningSim FIFO DSE (eval/dse_sweep.py) | pending | Requires fifo-advisor on Vitis box |
| Real OpenAI anchor at c=1000 | done | C:\Users\zjohn\Projects\gnn-hls-accel\orchestration_engine\characterization\out\gate\openai_action_heavy_c1000.json |
| Native oe_bench structural proof | pending | build.ps1 on Windows or g++ on Vitis box |