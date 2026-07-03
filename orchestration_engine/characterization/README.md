# Phase 0/1 — CPU-side latency disaggregation

**Goal:** A precise, publishable answer to *how much of agentic latency is genuinely
coordination, as opposed to waiting* — independent of whether the HLS engine works.

This is the **floor result**: useful and citable even if DSE fails.

## Methodology

### Buckets

| Bucket | In GT 50–90%? | Accelerable? |
|--------|---------------|--------------|
| `gpu_inference` | No (separate) | GPU |
| `cpu_io_wait` | Yes | **No** — blocked on external systems |
| `cpu_parse` | Yes | Yes (DPU-class) |
| `cpu_tokenize` | Yes | Yes (small) |
| **`cpu_orchestration`** | Yes | **Yes — thesis target** |
| `cpu_state` | Yes | Partly (KV-adjacent) |

### Key metrics

1. **CPU tool / E2E** — reproduces GT/Intel headline (50–90% in action-heavy mixes)
2. **I/O wait / CPU tool** — unaccelerable floor inside the bucket
3. **Orchestration / (CPU tool − I/O)** — coordination as share of hardware-amenable CPU
4. **Aggregate orchestration at concurrency N** — datacenter-relevant CPU cycles

### Success criterion (Phase 1)

Three layers:

1. **Trace calibration** — real OpenAI ladder (parallel `--fast`, wall_residual):
   orchestration incl. per-session setup is 33–50% of accelerable CPU;
   steady-state dispatch alone is 12–25% at ~250–850 µs/decision. Mock is
   recalibrated from these traces (`phase1_gate.recalibrate`).
2. **Structural proof** — `check9`: hardware scatter beats optimized O(N)
   software scan above a `(live_nodes, fan-out)` crossover; includes an honest
   event-driven O(1) baseline (constant-factor + energy case).
3. **Measured dispatch constants** — `check11` (`phase1_gate.dispatch_stress`,
   local, no API): real LangGraph ~1.7 ms/decision flat with live_n;
   asyncio event-driven ~2 µs; sharded x4 event loops ~2 µs (throughput
   fix, not per-decision fix); scan-class scheduler grows ~60x to N=1000.
   Also emits the full-path table (completion delivery + dispatch): the
   engine's dispatch-only gap vs ideal asyncio collapses to ~4–7x at PCIe
   attach; on-SoC integration recovers it. Dynamic-graph append/capacity/
   energy design model: `../docs/dynamic_graph_cost_model.md`.

## Pre-HLS gate (primary + calibration)

```powershell
py -3 -m orchestration_engine.characterization.phase1_gate.gate_report --skip-openai

# Real API anchors at c=100 and c=500 (regime discriminator)
py -3 -m orchestration_engine.characterization.phase1_gate.openai_scaling_sweep --levels 100,500 --fast --force

# Required before paper headline: same methodology at every concurrency
py -3 -m orchestration_engine.characterization.phase1_gate.openai_scaling_sweep --full-ladder --fast --force

# Error bars (recommended: 10 repeats for c=1, 3 for c>=100)
py -3 -m orchestration_engine.characterization.phase1_gate.openai_scaling_sweep --levels 1 --fast --force --repeats 10

# Local dispatch stress (no API) — measured O(live) evidence, feeds check 11
py -3 -m orchestration_engine.characterization.phase1_gate.dispatch_stress

# Recalibrate mock timing from the real ladder (then re-run gate_report)
py -3 -m orchestration_engine.characterization.phase1_gate.recalibrate
```

See `out/gate/gate_report.md` — **section 9** = structural proof; **section 10** = headline regime (plateau vs inflection).

## Run

```bash
# All three presets (action-heavy, balanced, reasoning-heavy), concurrency=1
python -m orchestration_engine.characterization.run

# Datacenter scaling study (orchestration share vs concurrency)
python -m orchestration_engine.characterization.run --scaling --preset action_heavy

# LangGraph ReAct agent (Phase 1 traces)

Instrumented LangGraph ReAct loop that exports JSON traces for the disaggregation pipeline.

## Install

```powershell
py -3 -m pip install -r orchestration_engine/characterization/requirements-langgraph.txt
```

## Run

```powershell
# Full Phase 1 study (calibrate + action/reasoning × c=1,100,500)
py -3 -m orchestration_engine.characterization.langgraph_react.study

# OpenAI wall-clock (requires OPENAI_API_KEY)
py -3 -m orchestration_engine.characterization.langgraph_react.study

# Calibrate only (wall-clock mock, writes out/calibration_{preset}.json)
py -3 -m orchestration_engine.characterization.langgraph_react.run --calibrate --preset action_heavy

# Single calibrated mock run
py -3 -m orchestration_engine.characterization.langgraph_react.run `
  --preset action_heavy --concurrency 500 --calibrated --analyze
```

## Backends

| Backend | Use |
|---------|-----|
| `mock` (default) | Offline ReAct loop with simulated GPU/tool latencies; structure matches real LangGraph |
| `openai` | Real API calls — set `OPENAI_API_KEY`; wall-clock spans (LLM = external wait) |

## Span → bucket mapping

| Component | Bucket |
|-----------|--------|
| LangGraph chain routing | `cpu_orchestration` |
| Mock LLM prefill/decode | `gpu_inference` |
| Tool sandbox/API/search sleep | `cpu_io_wait` |
| JSON parse/format | `cpu_parse` |
| Prompt tokenize | `cpu_tokenize` |
| Message/state append | `cpu_state` |

## Presets

- `action_heavy` — long tool I/O, shorter decode (GT action-heavy axis)
- `reasoning_heavy` — long decode, short tools
- `balanced`

```

Outputs land in `characterization/out/`:
- `disaggregation_report.json` — machine-readable
- `*_summary.md` — publishable prose per workload

## Instrument real agents

Use the profiler hooks in `trace_io.instrument_hook_example()`:

```python
from orchestration_engine.characterization.profiler import Profiler
from orchestration_engine.characterization.taxonomy import Bucket

prof = Profiler(name="langgraph_session")
with prof.span("tool_search", Bucket.CPU_IO_WAIT):
    ...
with prof.span("scheduler_dispatch", Bucket.CPU_ORCHESTRATION):
    ...
```

Export with `save_trace(profile, Path("my_trace.json"))` and analyze with `--trace`.

## Synthetic vs measured

| Source | Role |
|--------|------|
| `react_sim.py` presets | Hypothesis generation, scaling trends |
| Instrumented traces | **Publishable numbers** — replace synthetics before submission |
| GT/Intel Nov 2025 | External anchor for 50–90% headline |

**Before citing numbers in a paper:** calibrate `TimingModel` against at least one
real instrumented run, or report measured traces only.

## Next gate (Phase 2)

If **check9 structural proof** shows hardware scatter beats optimized software
scan at target `(live_nodes, fan-out)` → implement HLS engine + LightningSim DSE
to match the analytical crossover. Trace percentages (checks 1–7) support workload
scope but do not alone justify silicon.
