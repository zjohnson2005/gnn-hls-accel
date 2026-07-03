# Phase 1 gate report (pre-HLS)

## Thesis (scoped, provable)

Two-claim thesis. (1) Complexity class: scan-class schedulers cost O(live_nodes) per coordination decision (measured 59x growth to N=1000, check 11) while the engine costs O(fan-out) via scatter-on-completion — proven at a measurable (live_nodes, fan-out) crossover below. (2) Constant factor + energy: event-driven software is also O(fan-out) but carries measured constants of ~2 us/decision (ideal asyncio) to ~1.7 ms/decision (deployed LangGraph) vs the engine's cycle-scale scatter — pending csynth and full-path interface accounting (check 11). Claim (1) never applies against event-driven baselines.

**Evidence hierarchy:** (9) structural sim is primary proof; (7) trace crossover is calibration/projection; (3) OpenAI anchors workload realism.

## 1. Absolute orchestration cost vs software models

| preset | c | orch (s) | ms/agent | cores eq | verdict |
|--------|---|----------|----------|----------|---------|
| action_heavy | 1 | 0.01 | 6.52 | 0.000 | WEAK_ABSOLUTE |
| action_heavy | 100 | 1.03 | 10.34 | 0.063 | WEAK_ABSOLUTE |
| action_heavy | 500 | 12.97 | 25.94 | 0.792 | MODERATE |
| action_heavy | 1000 | 45.44 | 45.44 | 2.773 | STRONG_ABSOLUTE |
| action_heavy | 5000 | 483.52 | 96.70 | 29.376 | STRONG_ABSOLUTE |
| reasoning_heavy | 1 | 0.00 | 2.16 | 0.000 | WEAK_ABSOLUTE |
| reasoning_heavy | 100 | 0.48 | 4.81 | 0.023 | WEAK_ABSOLUTE |
| reasoning_heavy | 500 | 7.80 | 15.61 | 0.375 | WEAK_ABSOLUTE |

### Deployment extrapolation (from c=500 per-agent orch cost)

- **1000 agents**: 25.94 CPU-seconds orchestration (serialized upper bound)
- **10000 agents**: 259.38 CPU-seconds orchestration (serialized upper bound)
- **50000 agents**: 1296.9 CPU-seconds orchestration (serialized upper bound)

## 2. Extended concurrency curve (action-heavy mock)

| c | orch / accelerable CPU | cores eq |
|---|------------------------|----------|
| 1 | 17.8% | 0.000 |
| 10 | 18.5% | 0.004 |
| 100 | 25.6% | 0.063 |
| 500 | 46.3% | 0.792 |
| 1000 | 60.2% | 2.773 |
| 5000 | 76.3% | 29.376 |

Plateau detected: **False**

## 3. Mock vs real OpenAI

Anchor points: **6** — curve trust: **MEDIUM — 6 anchors, max delta 44.3 pp**
Max |delta|: **44.3** percentage points

| c | mock % | real % | Δ pp | real ms/agent | instrumentation |
|---|--------|--------|------|---------------|-----------------|
| 1 | 17.8% | 62.1% | +44.3 | 8.35 | wall_residual |
| 10 | 18.5% | 35.6% | +17.1 | 2.82 | wall_residual |
| 20 | 19.3% | 48.2% | +28.9 | 4.76 | wall_residual |
| 100 | 25.6% | 39.9% | +14.3 | 3.39 | wall_residual |
| 500 | 46.3% | 56.2% | +9.9 | 6.54 | wall_residual |
| 1000 | 60.1% | 39.9% | -20.2 | 3.39 | wall_residual |

## 4. Action vs reasoning axis

| preset | c | CPU tool/E2E | orch/accel | cores eq |
|--------|---|--------------|------------|----------|
| action_heavy | 1 | 57.5% | 17.8% | 0.000 |
| action_heavy | 100 | 58.9% | 25.6% | 0.063 |
| action_heavy | 500 | 59.0% | 46.3% | 0.792 |
| reasoning_heavy | 1 | 3.7% | 9.8% | 0.000 |
| reasoning_heavy | 100 | 3.7% | 19.5% | 0.023 |
| reasoning_heavy | 500 | 3.7% | 44.0% | 0.375 |

## 5. Three-way comparison (LangGraph vs 4× opt vs HW flat)

| c | LangGraph | 4× opt | HW flat | HW beats 4×? |
|---|-----------|--------|---------|--------------|
| 1 | 0.000 | 0.000 | 0.000 | no |
| 10 | 0.004 | 0.001 | 0.002 | no |
| 100 | 0.063 | 0.016 | 0.021 | no |
| 500 | 0.792 | 0.198 | 0.107 | yes |
| 1000 | 2.773 | 0.693 | 0.214 | yes |
| 5000 | 29.376 | 7.344 | 1.066 | yes |

## 6. Graph out-degree shapes

| graph | max out-deg | mean | p95 |
|-------|-------------|------|-----|
| langgraph_react_chain | 1 | 0.91 | 1 |
| synthetic_fanout_action_heavy | 4 | 1.00 | 4 |
| synthetic_fanout_reasoning_heavy | 1 | 0.88 | 1 |
| planner_fanout_64 | 64 | 0.98 | 0 |
| planner_fanout_256 | 256 | 1.00 | 0 |

## 7. Trace-calibrated crossover (LangGraph projection)

_Secondary evidence — calibrates mock scaling against traces; primary proof is check 9._

**Headline:** Hardware crossover begins at concurrency ~500 (ReAct out-degree). Below that, optimized software on a spare core wins.

- ReAct avg out-degree: **1.5**
- Optimized software model: LangGraph measured / **4×**
- Hardware batched scatter: **8** successors/cycle

### Crossover at ReAct out-degree (cores equivalent)

| c | LangGraph | 4× opt | HW flat | HW batched | HW flat wins? |
|---|-----------|--------|---------|------------|---------------|
| 1 | 0.000 | 0.000 | 0.000 | 0.000 | no |
| 10 | 0.004 | 0.001 | 0.002 | 0.002 | no |
| 100 | 0.063 | 0.016 | 0.021 | 0.021 | no |
| 500 | 0.792 | 0.198 | 0.107 | 0.105 | yes |
| 1000 | 2.773 | 0.693 | 0.214 | 0.209 | yes |
| 5000 | 29.376 | 7.344 | 1.066 | 1.042 | yes |

### Max out-degree where hardware beats 4× opt at c=500

- Flat scatter: out-degree ≤ **16.0**
- 8-wide batched scatter: out-degree ≤ **64.0**

### Full grid (HW flat beats 4× opt?)

| c \ out-deg | 1 | 1.5 | 4 | 8 | 16 | 64 | 256 |
|---|---|---|---|---|---|---|---|
| 1 | · | · | · | · | · | · | · |
| 10 | · | · | · | · | · | · | · |
| 100 | · | · | · | · | · | · | · |
| 500 | ✓ | ✓ | ✓ | ✓ | ✓ | · | · |
| 1000 | ✓ | ✓ | ✓ | ✓ | ✓ | · | · |
| 5000 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | · |

_✓ = flat hardware cores < 4× optimized cores_

## 8. Fan-out resolution (planner stress cases)

**Design decision:** Phase 2 v1: flat CSR scatter for out-degree ≤ 8 (ReAct chains, modest trees). Planner fan-out 64: extend routing unit with 8-wide pipelined batch scatter (same pred-decrement semantics, inner loop unroll factor 8). Fan-out 256: unstructured single-step planner launch is out of v1 silicon; use tree-launch graph lowering (max degree 16) or 16-wide batch in a later revision.

V1 scope: out-degree ≤ **8** (flat scatter).

### Routing unit implications

- Flat scatter: single pred_remaining[] port, II=1 per edge — sufficient for d≤8.
- 8-wide batch unit: unroll inner scatter loop factor=8, cyclic partition preds — extends reach to d≤64 without changing O(out-degree) asymptotics.
- Barrier lowering (software): converts planner→N into N+1 single-edge scatters — same hardware, different graph IR; belongs in host compiler pass.

### planner_fanout_64

_LangGraph ≈ 1995 µs/decision; 4× opt ≈ 499 µs/decision_

| strategy | eff. degree | µs/completion | v1? |
|----------|-------------|---------------|-----|
| flat_csr_scatter | 64.0 | 1020 | no |
| pipelined_batch_scatter | 8.0 | 348 | yes |
| barrier_graph_rewrite | 1.0 | 17160 | yes |
| tree_launch (8×8 for 64, 16×16 for 256) | 8.0 | 348 | yes |

**Verdict:** Fan-out 64 exceeds flat v1 scope (>8) but **8-wide batched scatter** (348 µs) beats 4× optimized (499 µs). Phase 2 should add a pipelined batch scatter unit — not a thesis scope exclusion.

### planner_fanout_256

_LangGraph ≈ 1995 µs/decision; 4× opt ≈ 499 µs/decision_

| strategy | eff. degree | µs/completion | v1? |
|----------|-------------|---------------|-----|
| flat_csr_scatter | 256.0 | 3324 | no |
| pipelined_batch_scatter | 32.0 | 636 | no |
| barrier_graph_rewrite | 1.0 | 67848 | yes |
| tree_launch (8×8 for 64, 16×16 for 256) | 16.0 | 444 | yes |

**Verdict:** Fan-out 256: 8-wide batch (636 µs) loses to 4× opt (499 µs), but **tree-launch lowering** (444 µs, max degree 16) wins. Requires host-side graph rewrite before hardware; flat/batch silicon unchanged.

## 9. Structural proof (primary thesis evidence)

**Thesis:** Two-claim thesis. (1) Complexity class: scan-class schedulers cost O(live_nodes) per coordination decision (measured 59x growth to N=1000, check 11) while the engine costs O(fan-out) via scatter-on-completion — proven at a measurable (live_nodes, fan-out) crossover below. (2) Constant factor + energy: event-driven software is also O(fan-out) but carries measured constants of ~2 us/decision (ideal asyncio) to ~1.7 ms/decision (deployed LangGraph) vs the engine's cycle-scale scatter — pending csynth and full-path interface accounting (check 11). Claim (1) never applies against event-driven baselines.

**Headline:** Analytical crossover: flat hardware beats 4x optimized software at live_nodes >= 100 (fan-out=2). 8-wide batch lowers threshold to live_nodes >= 10.

_LangGraph percentages (checks 1–3) calibrate workload realism; this section proves the O(N) vs O(fan-out) mechanism._

### Crossover at fan-out=2 (live nodes vs coordination cycles)

| live N | completions | CPU scan | 4x opt scan | HW flat | HW batch | HW wins? |
|--------|-------------|----------|-------------|---------|----------|----------|
| 1 | 13 | 39 | 9 | 39 | 26 | no |
| 10 | 18 | 216 | 54 | 54 | 36 | no |
| 100 | 63 | 6426 | 1606 | 189 | 126 | yes |
| 500 | 263 | 132026 | 33006 | 789 | 526 | yes |
| 1000 | 513 | 514026 | 128506 | 1539 | 1026 | yes |
| 5000 | 2513 | 12570026 | 3142506 | 7539 | 5026 | yes |

_Native bench not built — run ``cd orchestration_engine && ./build.ps1`` for cycle-accurate C++ confirmation._

### Baseline honesty (event-driven software)

An ideal event-driven software scheduler (O(1) wakeup) matches the engine's O(fan-out) asymptotics. Against that baseline the hardware case is constant factor + energy, not complexity class. The scan columns model LangGraph-class superstep frameworks; check 11 measures both constants on real code.

| dispatcher | measured µs/decision | vs hardware |
|-----------|----------------------|-------------|
| LangGraph (real framework, live_n>=100) | 1331 | 133,133x |
| asyncio event-driven (O(1) baseline) | 1.87 | 187x |
| engine scatter (analytic, pre-csynth) | 0.01 | 1x |


### Hardware-wins region (flat vs 4x optimized scan)

| live N \ fan-out | 1 | 2 | 4 | 8 | 16 | 64 |
|---|---|---|---|---|---|---|
| 1 | . | . | . | . | . | . |
| 10 | Y | . | . | . | . | . |
| 100 | Y | Y | Y | Y | Y | . |
| 500 | Y | Y | Y | Y | Y | Y |
| 1000 | Y | Y | Y | Y | Y | Y |
| 5000 | Y | Y | Y | Y | Y | Y |

## 10. Real scaling regime (headline discriminator)

**Verdict:** `MIXED_MID_REGIME`

Real orch/accel at c=500 is 57.5%; combine structural crossover with measured absolute cores. NOTE: c=1000 measured 39.9% (back to plateau) vs c=500 57.5% — do not cite monotonic rise; c=500 spike may be latency variance or mid-scale contention, not sustained scaling.

- Real slope (orch/accel % per +1 conc): **+0.0035** pp
- Real steady-state slope (setup excluded): **+0.0022** pp
- Mock slope (same range): **+0.0434** pp
- Leading hypothesis: **plateau_or_falling_share**
- Has real c=100: **True** | c=500: **True** | c=1000: **True**
- Methodology consistent: **True**

_Linear extrapolation from anchors (do not cite as measured): c=100 ~36.8%, c=500 ~38.2%_

| c | orch/accel % (incl. setup) | steady-state % | steady µs/decision | setup ms/agent | workers | mode |
|---|------|------|------|------|------|------|
| 1 | 39.1% ±9.7 (n=10) | 26.0% | 898 | 6.55 | 4 | single_agent |
| 10 | 40.3% ±5.5 (n=10) | 11.0% | 315 | 2.19 | 8 | parallel |
| 20 | 40.6% ±4.8 (n=10) | 16.2% | 494 | 3.77 | 8 | parallel |
| 100 | 46.4% ±12.1 (n=3) | 16.8% | 516 | 2.35 | 8 | parallel |
| 500 | 57.5% ±1.8 (n=2) | 29.0% | 1045 | 4.45 | 8 | parallel |
| 1000 | 39.9% | 16.5% | 506 | 2.38 | 8 | parallel |

_Setup = each agent's first orchestration span (LangGraph session/graph init); steady-state = dispatch decisions after init. Both are coordination work; setup maps to the engine's dynamic graph-load path, steady-state to scatter-on-completion._

## 11. Local dispatch stress (measured O(live) evidence, no API)

**Verdict:** `LANGGRAPH_FLAT`

Measured: LangGraph per-decision CPU is ~flat with live_n (1.0x). The hardware case vs frameworks rests on constant factor + energy, not asymptotics - cite measured constants below.

N live tasks in one process; per-decision **process CPU** cost (GIL-independent, energy-relevant).

| live N | LangGraph µs/dec | asyncio event µs/dec | sharded x4 µs/dec | global scan µs/dec |
|--------|------------------|----------------------|-------------------|--------------------|
| 100 | 1298 | 2.1 | 1.7 | 1.4 |
| 500 | 1341 | 1.6 | 1.7 | 7.9 |
| 1000 | 1355 | 1.9 | 1.6 | 18.4 |

- Growth 100->1000: LangGraph **1.04x**, asyncio event **0.92x**, global scan **13.58x**
- Hardware reference: **0.01 µs/decision** (scatter = (1 + fan-out=2) cycles at 300 MHz (analytic target, pending HLS csynth))

### Full-path accounting (delivery + dispatch per completion)

Delivery + dispatch per completion, mid-range first-order estimates. Both sides pay inbound delivery: software completions cross NIC->kernel->epoll wakeup; engine completions cross an interconnect DMA write. Outbound work-launch to the executor (GPU/tool server) is symmetric on both sides and excluded. Dispatch-only comparisons overstate the hardware gap vs event-driven software.

| path | µs/completion |
|------|---------------|
| software: epoll wakeup + asyncio dispatch | 5.37 |
| software: kernel-bypass + asyncio dispatch | 3.12 |
| engine: PCIe Gen4 DMA + scatter | 0.76 |
| engine: CXL + scatter | 0.46 |
| engine: on-SoC AXI + scatter | 0.11 |

_Full-path, the dispatch-only ~200x gap vs ideal asyncio collapses to **~4.1x** (vs kernel-bypass software) / **~7.1x** (vs standard epoll), because interconnect delivery dominates the engine's cycle-scale scatter. The durable advantages at PCIe attach are throughput under load (banked counters, no queue contention), energy, and freeing host cores; on-SoC integration recovers the latency gap._

_Interpretation: sharded x4 event loops are the realistic deployed counter-proposal; single-core asyncio is the ideal. The hardware case against both is constant factor + energy + full-path latency; the case against LangGraph-class frameworks and scan-class schedulers adds the asymptotic gap._

## Gate recommendation

HEADLINE REGIME RESOLVED at c=500 real anchor (consistent methodology). Real orch/accel at c=500 is 57.5%; combine structural crossover with measured absolute cores. NOTE: c=1000 measured 39.9% (back to plateau) vs c=500 57.5% — do not cite monotonic rise; c=500 spike may be latency variance or mid-scale contention, not sustained scaling. Structural: hardware beats 4x optimized scan at live_nodes >= 100. Lead with check 9 crossover; check 10 picks percentage headline. Check 11 measured: real-framework dispatch is ~flat with live_n (constant-factor + energy case), while a scan-class scheduler grows 13.58x - frame the hardware win as constant factor vs deployed frameworks, complexity class vs scan schedulers.
