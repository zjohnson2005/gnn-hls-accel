# CPU attribution model (real LangGraph agent mode)

This document explains how host CPU is partitioned in `real_agent_breakdown`
and replication artifacts, and how to read ORCH headlines.

## Host CPU basis

- **Per session:** `process_time()` delta (all OS threads: main agent loop,
  LangGraph tool pool, httpx).
- **Per batch:** sum of session `process_cpu_ns` (10 sessions; default
  `workers=1` runs them **sequentially**).

Region timers use `thread_time()` on the thread entering each `@timed` region.
When tool work runs on other threads, category thread-time can exceed process
clock; `parallel_cpu_trim_ns` proportionally scales categories down (typically
&lt;1% of batch host CPU).

## ORCH: measured vs reconcile

LangGraph step CPU is not fully wrap-able. During streaming:

- **ORCH measured** (`orch_measured_cpu_ns`): per-step residual
  `(step_thread_cpu - step_tagged_cpu)` booked to `ORCH_SETUP` / `ORCH_DISPATCH`.

At session end:

- **Reconcile gap** = `process_cpu_ns - tagged_cpu_ns` before gap fill.
- That gap is added to `ORCH_DISPATCH` (convention: unattributed process CPU
  is orchestration-adjacent).
- **ORCH reconcile** (`orch_reconcile_cpu_ns`): portion of final session ORCH
  attributed to this gap (split proportionally if parallel trim applied).

**Headline rule:** quote `pooled_orch_measured_pct` and
`pooled_orch_reconcile_pct` separately. Total ORCH ≈ measured + reconcile.
In current replication, reconcile dominates (~90%+ of ORCH) because most
process CPU is not caught by main-thread region tags.

## Harness strict (not “harness APU + TOOL/HTTP”)

**Harness strict** = ORCH + TOKENIZATION + SERIALIZATION only.

- JSON key `pooled_harness_apu_pct` is legacy; definition is strict tier.
- **TOOL_COMPUTE** is application compute (amenability tier `none`).
- **HTTP_CLIENT** is overlap tier (NIC/DPU class); not in strict harness sum.

## Search locality (methods only)

Matched-pair ablation (`tool_locality_ablation.json`) compares local vs remote
**search** with identical call counts on **SH-01 and SH-02 only**. Other rows
in the comparison table are unmatched context. Local search is a control arm,
not a production workload characterization.

## Recommended follow-up

1. **py-spy** one heavy session (RH-02 / LH-01): stacks in reconcile gap.
2. **Retrieve locality ablation** (RH-01, LH-01) — same design as search.
3. **Git-clean re-stamp** after code freeze for strict reproducibility.

See `RUNBOOK.md` for experiment commands.
