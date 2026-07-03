# Phase 2 gate report

**Status:** IN PROGRESS (3 checklist items pending)

## Phase 2 crossover (measured scatter + full-path delivery)

**Verdict:** `FULL_PATH_ADVANTAGE`

Cosim II 24 cycles (0.1140 us steady-state) + PCIe delivery -> ~3.6x vs kernel-bypass (one-shot latency 13 cycles).

- Hardware scatter (fan-out=2): **24 cycles** = **0.114 us** @ 210.5 MHz (cosim II (steady-state))
- Cosim one-shot latency: **13 cycles** (ap_start/ap_done)
- Cosim measured II: **24 cycles** (multi-transaction steady-state)
- csynth source: `oe_scatter_proj/sol1/syn/report/oe_hls_scatter_kernel_csynth.rpt`
- cosim source: `oe_scatter_cosim_proj/sol1/sim/report/oe_hls_scatter_kernel_cosim.rpt`

| baseline | us/completion | vs engine+PCIe | vs engine+on-SoC |
|----------|---------------|----------------|------------------|
| LangGraph (deployed) | 1334.83 | 1544.9x | 6237.5x |
| asyncio + epoll (measured full-path) | 5.37 | 6.2x | 25.1x |
| asyncio + kernel-bypass (measured full-path) | 3.12 | 3.6x | 14.6x |

_Delivery constants (mid-range): sw_epoll 3.5 us (Linux epoll wakeup path, see epoll_wakeup_bench.py); sw_kernel_bypass 1.25 us (DPDK/eRPC class); hw_pcie 0.75 us (PCIe Gen4 posted write); hw_cxl 0.45 us; hw_on_soc 0.10 us (AXI)._

_Scan-class O(N) crossover remains in Phase 1 check 9; this table closes Claim 2 (constant factor + energy) against event-driven baselines._

## Checklist

| item | status | detail |
|------|--------|--------|
| HLS csynth scatter kernel (run_hls_scatter.tcl) | done | oe_scatter_proj/sol1/syn/report/oe_hls_scatter_kernel_csynth.rpt |
| HLS cosim scatter (trust cycle count) | done | oe_scatter_cosim_proj/sol1/sim/report/oe_hls_scatter_kernel_cosim.rpt (13 cycles) |
| Streaming scatter cosim (steady-state cycles/completion) | pending | Run run_phase2_scatter_stream.sh on Vitis box |
| LightningSim FIFO DSE (eval/dse_sweep.py) | pending | Requires fifo-advisor on Vitis box |
| Real OpenAI anchor at c=1000 | done | C:\Users\zjohn\Projects\gnn-hls-accel\orchestration_engine\characterization\out\gate\openai_action_heavy_c1000.json |
| Native oe_bench structural proof | pending | build.ps1 on Windows or g++ on Vitis box |