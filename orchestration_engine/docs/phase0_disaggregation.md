# Phase 0 — Disaggregating the 50–90% CPU bucket

One-page pitch artifact. External anchor: Georgia Tech + Intel (Nov 2025).
**Measured numbers:** run `python -m orchestration_engine.characterization.run`.

## Headline

CPU-side tool processing is **50–90%** of end-to-end agentic latency (action-heavy
mixes). That figure is real but **not one problem**. Most of it is I/O wait —
blocked on someone else's system — not coordination.

## The question we answer

> How much of agentic latency is **genuinely coordination**, as opposed to **waiting**?

Three sub-questions:

1. What fraction of E2E is CPU tool phase? (GT/Intel replication)
2. Inside CPU tool phase, what fraction is I/O wait? (unaccelerable floor)
3. Inside the remainder, what fraction is orchestration? (thesis target)

## Five-way split

| Slice | Accelerable? | Typical share *of CPU tool* | Remedy |
|-------|--------------|----------------------------|--------|
| **I/O wait** | No | **~95–99%** (action-heavy) | Overlap only |
| Parse / format | Yes | ~0.1–2% | DPU / parser IP |
| Tokenize | Yes | <0.1% | Tokenizer IP |
| **Orchestration** | **Yes** | **~0.02–0.2%** of CPU tool at c=1; **~12–36% of accelerable CPU at c=100–1000** | **This project** |
| State / KV | Partly | ~0.1–3% | KV manager |

*Trace status: real OpenAI ladder measured (parallel `--fast`, wall_residual) — see below.*

## Measured findings (real OpenAI ladder, gpt-4o-mini, consistent methodology)

| Concurrency | Orch / accel CPU (incl. setup) | Steady-state dispatch only | Steady µs/decision | Setup ms/agent |
|-------------|-------------------------------|----------------------------|--------------------|----------------|
| 10 | 33.5% | 12.4% | 362 | 1.85 |
| 20 | 37.1% | 16.1% | 488 | 2.03 |
| 100 | 33.3% | 13.6% | 403 | 1.74 |
| 500 | 50.2% | 25.1% | 855 | 3.44 |

**Setup vs steady:** each agent's first orchestration step is LangGraph
session/graph initialization (1.7–3.4 ms); later steps are dispatch decisions
(~250–850 µs). Setup maps to the engine's dynamic graph-load path, steady-state
to scatter-on-completion — both are coordination and both are hardware targets.

**Dispatch constants (local stress, no API, gate check 11):** LangGraph
~1.7 ms/decision flat with live_n up to 1000; ideal event-driven asyncio ~2 µs;
scan-class scheduler grows 59x from N=10 to N=1000. Engine scatter measured
(csynth Jul 2026): **404.4 MHz Fmax**, streaming cosim **16.2 cycles/completion
steady-state** (0.040 µs); one-shot host-triggered 59 cycles (0.146 µs,
dominated by ap_ctrl/AXI-lite handshake); inner loop **3 cycles** for
fan-out=2.

## Synthetic findings (superseded — kept for history)

**Single agent (action-heavy):**

| Metric | Value |
|--------|-------|
| CPU tool / E2E | ~62% (GT-range) |
| I/O wait / CPU tool | ~99.7% |
| Orchestration / (CPU tool − I/O) | ~4% |
| Orchestration / E2E | ~0% (per-task — expected) |

**Interpretation:** Per single request, coordination is **not** the bottleneck;
I/O wait dominates. This is the honest per-task floor.

**Datacenter concurrency (action-heavy, aggregate CPU cycles):**

| Concurrency | Orch / accelerable CPU | Orch / normalized E2E |
|-------------|------------------------|------------------------|
| 1 | ~4% | ~0% |
| 100 | ~12% | ~2% |
| 500 | ~31% | ~24% |
| 1000 | ~36% | ~46% |

**Interpretation:** Coordination is a rounding error **per task** but becomes a
**sizeable slice of aggregate accelerable CPU** as concurrent agents scale.
Scan-class coordinators pay O(live tasks) per decision (claim 1); event-driven
coordinators avoid the scan but keep µs–ms constants (claim 2). This is the
datacenter case for silicon.

Run: `python -m orchestration_engine.characterization.run --scaling --preset action_heavy`

## Hypothesis for silicon (unchanged)

Custom orchestration hardware pays when:

1. Aggregate coordination CPU cycles saturate cores at datacenter concurrency.
2. The win is throughput / energy, not single-request latency.
3. Dynamic graphs stay expensive in software at scale.

**Negative result is publishable:** if instrumented traces show orchestration
 stays <5% of accelerable CPU even at 1000 agents, software suffices.

## Instrumentation next step

Synthetic presets generate hypotheses. **Publishable numbers require real traces:**

```bash
python -m orchestration_engine.characterization.run --trace my_instrumented_run.json
```

See `characterization/README.md` for profiler hooks.

## Two redundancies (do not conflate)

| Redundancy | Domain | Fix |
|------------|--------|-----|
| Re-prefill after KV eviction | GPU | KV-cache manager |
| Overlapping tool / speculative branches | CPU | Orchestration engine |

## Phase 2 gate (DSE) — **PASSED on real traces**

Condition was: orchestration ≥10–15% of accelerable CPU at target concurrency.
Measured: **12–25% steady-state** (33–50% including session setup) at c=10–500.

Remaining before paper: repeats for error bars (`--repeats`), native `oe_bench`,
multi-transaction cosim for steady-state II, LightningSim DSE, and measured
epoll delivery (`epoll_wakeup_bench.py`) to tighten full-path constants.
