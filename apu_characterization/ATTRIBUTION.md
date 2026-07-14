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
2. **Instrumentation v2** (`--instr-version 2`): thread hooks + RESIDUAL_UNATTRIBUTED gate.
3. **Retrieve locality ablation** (RH-01, LH-01) — same design as search.
4. **Git-clean re-stamp** after code freeze for strict reproducibility.

See `METHODOLOGY.md` and `out/reconcile_bug_checks.md` for the reconcile diagnosis path.

## MCP-01 message attribution

MCP-01 uses an isolated taxonomy under `mcp_tax/taxonomy.py`; it does not add
message categories to the agent `Category` enum. Client and server endpoints
each conserve process CPU independently.

- `MSG_SERIAL`: JSON-RPC encode/decode and parse.
- `MSG_VALIDATE`: JSON Schema validation only; never folded into serialization.
- `MSG_FRAME`: stdio/HTTP/SSE framing.
- `MSG_TRANSPORT_CPU`: syscall/TLS CPU only, never blocking wall.
- `MSG_DISPATCH`: server method lookup and client completion routing.
- `SESSION_SETUP`: cold connection/capability/catalog setup, reported separately.
- `RESIDUAL`: process CPU not booked above; G1-gated.

Transport-blocked, runqueue, synthetic-tool-delay, and unattributed wait live
on a separate wall ledger. Client+server CPU may be summed as derived protocol
tax, but that sum is not a cross-process wall conservation equation.

## v2 attribution (RESIDUAL_UNATTRIBUTED)

Under `--instr-version 2`, session-end gap is booked to `RESIDUAL_UNATTRIBUTED`, not
`ORCH_DISPATCH`. Publishable v2 replication requires every session below 15% residual.
Headline tiers: `harness_strict`, `harness_broad`, explicit CLIENT_* / FRAMEWORK / THREADPOOL.

### Epistemic provenance tiers (required for quoting)

Every category total has a **provenance** column:

| Tier | Meaning | Quote for harness headlines? |
|------|---------|------------------------------|
| **measured** | Direct `@timed` regions or thread-identity CPU (instr v3) | **Yes** |
| **step_inferred** | Process-time gap during a LangGraph step assigned by node type (instr v2 fix #1) | **No** — corroborating only; needs mock calibration |
| **residual** | Session-end gap after all booking | **No** — must stay &lt; 15% |

**Regression to name:** step-inferred booking can drive category totals (e.g. CLIENT_HTTP)
while driving **residual provenance** near zero. The old RESIDUAL &lt; 15% gate becomes
vacuous unless it checks **residual provenance**, not step-inferred mass.

**Concurrency:** step-inferred attribution is valid only for `workers=1` sequential runs
(one session owns the process clock). It **cannot** survive the concurrency sweep.
Use **`--instr-version 3`** (thread-identity via psutil per-thread CPU) before c&gt;1.

Validation (run regardless of mechanism):

1. `python -m apu_characterization.experiments.step_infer_calibration` — mock backend;
   false CLIENT_HTTP step-inferred rate must be ≤ 5%.
2. py-spy stack-walk cross-check — timer vs profiler within 10 pp per major category.
3. `tests/test_attribution_provenance.py` — synthetic HTTP worker discriminator.

See `provenance.py`, `thread_identity.py`, `out/step_infer_calibration.json`.
