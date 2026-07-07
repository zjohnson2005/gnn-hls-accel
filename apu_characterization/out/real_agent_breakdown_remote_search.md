# Experiment 0R: real LangGraph agent CPU-time breakdown (openai, remote search deployment)

> **Windows footnote only — NOT quotable for headlines.** Data affected by 15.625 ms thread-time tick quantization. Re-run on Linux with test_resolution PASS for publishable numbers.

Generated: 2026-07-07T18:50:58.668338+00:00 from `real_agent_breakdown_remote_search.json`.
All numbers below are read from that artifact.

## Setup

- setup record: digest `be14904706711ea6`, task suite `a88a9e1058964219` (see EXPERIMENT_SETUP.md)
- cpu (from setup record): Intel(R) Core(TM) Ultra 5 325
- git commit: `d98b8d80538abf3f59fc00ca172491256478a65d` (dirty tree: yes)
- python: 3.14.0
- platform: Windows-11-10.0.26200-SP0
- cpu: Intel64 Family 6 Model 204 Stepping 3, GenuineIntel, logical cores: 8
- ram_gb: 15.6

### Protocol

- profile: `mixed`, seed: 0, sessions: 10, execution: threads/openai
- search locality: `remote`
- payload profile: `locality_ablation` (synthetic tool-result padding; see tool-locality ablation note)
- total CPU basis: sum(session process_time)
- mock LLM latency scale: 0.05 (scripted backend sleeps (wall only); openai backend ignores this)
- clocks: wall = perf_counter_ns; CPU = thread_time_ns per region; real-agent total CPU = process_time (all threads, including LangGraph tool executors)
- nesting: exclusive self-time accounting; an inner region pauses its parent
- timer overhead: 4062 ns per enter/exit pair
- batch wall time: 98.13 s

### What each category wraps in this harness

- `ORCH_SETUP`: REAL AGENT MODE: LangGraph first-step CPU residual (framework graph/session construction), the Phase 0 setup definition
- `ORCH_DISPATCH`: REAL AGENT MODE: LangGraph per-step CPU residual between stream events minus tagged tool CPU (completion handling, channel updates, handoff), the Phase 0 steady definition
- `SERIALIZATION`: json.dumps/loads of LLM responses and tool results, response parse
- `TOKENIZATION`: token counting of the full assembled prompt each turn plus the response body (tiktoken or len/4 fallback); models client-side context-window bookkeeping, so it scales with conversation length per turn
- `PROMPT_ASSEMBLY`: REAL AGENT MODE: inside the framework, not separable; included in the ORCH buckets
- `CONTEXT_MGMT`: REAL AGENT MODE: inside the framework (LangGraph state channels), not separable; included in the ORCH buckets
- `HTTP_CLIENT`: OpenAI backend: LangChain callback wraps each LLM call (request build, response parse; network wait costs ~zero thread CPU). Remote search: mock search round-trip wall (I/O wait) also in HTTP_CLIENT.
- `TOOL_COMPUTE`: Local tool bodies only (code_exec, retrieve, calculator). Search is remote: HTTP envelope + I/O wait, not TOOL_COMPUTE.
- `LOGGING`: REAL AGENT MODE: not separately instrumented; inside ORCH buckets
- `GC`: collector cycles via gc.callbacks (lower bound, excludes refcount frees)
- `RESIDUAL`: computed: total thread CPU minus sum of instrumented categories

## Accounting invariant

sum(category thread-CPU) + residual = total thread-CPU of the run:

- total thread CPU: 1140.62 ms
- instrumented: 1156.25 ms
- residual: 0.00 ms (0.0% of total)
- limit: 15%  ->  PASS

## Breakdown (thread CPU, exclusive per category — pooled across all sessions)

*Denominators: n=1 seed(s)=[0], search=remote, batch host CPU=1141 ms, batch wall=98.1 s, CPU% of wall≈1.21%, c=1*

| Category | CPU ms | Share of total | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|
| ORCH_DISPATCH | 531.250 | 46.6% | 3991.059 | 118 | 0 | 0 |
| HTTP_CLIENT | 312.500 | 27.4% | 95363.673 | 67 | 17651 | 335 |
| ORCH_SETUP | 93.750 | 8.2% | 153.365 | 20 | 0 | 0 |
| TOKENIZATION | 93.750 | 8.2% | 115.749 | 117 | 381193 | 0 |
| TOOL_COMPUTE | 78.125 | 6.8% | 268.190 | 33 | 1332 | 0 |
| GC | 46.875 | 4.1% | 46.875 | 82 | 0 | 0 |
| PROMPT_ASSEMBLY | 0.000 | 0.0% | 0.219 | 37 | 0 | 280610 |
| SERIALIZATION | 0.000 | 0.0% | 4.208 | 117 | 16324 | 364148 |
| RESIDUAL | 0.000 | 0.0% | n/a | n/a | n/a | n/a |

## Per-task breakdowns and hardware amenability

The headline table sums all sessions. Sections here are per task, which is the grouping the archetype analysis uses.

Amenability tiers (classification is a documented input assumption, refined later by the measured scorecard):

- `ORCH_SETUP` [direct]: graph-load/session-append kernel demonstrated in Phase 2
- `ORCH_DISPATCH` [direct]: scatter-on-completion kernel demonstrated in Phase 2
- `SERIALIZATION` [direct]: JSON parse/serialize accelerators are an established block class
- `TOKENIZATION` [direct]: BPE encode/count is fixed-function friendly, table-driven
- `PROMPT_ASSEMBLY` [partial]: template fill and concatenation map to copy engines; message-selection logic stays on host
- `CONTEXT_MGMT` [partial]: state copies map to DMA/copy engines; structure traversal stays on host
- `HTTP_CLIENT` [overlap]: NIC/DPU class devices already own HTTP/TLS envelope work
- `TOOL_COMPUTE` [none]: application compute, not serving-harness work; out of APU scope by definition
- `LOGGING` [partial]: format-and-ship maps to telemetry offload engines
- `GC` [none]: CPython runtime internals, not a separable block

strict = direct tiers; broad = direct + partial + overlap tiers. Base is the task's instrumented CPU; GC and RESIDUAL are process-global and excluded from per-task math.

### Summary

| Task | Instrumented CPU ms | Amenable strict | Amenable broad |
|---|---|---|---|
| CH-01 | 156.2 | 40.0% | 90.0% |
| CH-02 | 31.2 | 0.0% | 100.0% |
| LH-01 | 390.6 | 60.0% | 88.0% |
| LH-02 | 15.6 | 100.0% | 100.0% |
| RE-01 | 31.2 | 100.0% | 100.0% |
| RE-02 | 31.2 | 50.0% | 100.0% |
| RH-01 | 203.1 | 92.3% | 92.3% |
| RH-02 | 109.4 | 85.7% | 100.0% |
| SH-01 | 140.6 | 22.2% | 66.7% |
| SH-02 | 46.9 | 100.0% | 100.0% |

### Per-task LLM I/O wait vs host CPU

Each row is one session. **LLM I/O wait** = HTTP_CLIENT wall (blocked on OpenAI). **Host CPU** = session process_time. I/O % and CPU % both divide by session wall; they are different axes (wait vs compute), not additive category wall fractions.

| Task | Session wall s | LLM I/O wait s | Non-LLM wall s | Host CPU ms | I/O % of wall | CPU % of wall | Tool CPU ms | Harness CPU ms | Tools |
|---|---|---|---|---|---|---|---|---|---|
| CH-01 | 14.34 | 14.24 | 0.10 | 156.2 | 99.3% | 1.09% | 15.6 | 140.6 | calculator×2, code_exec×4 |
| CH-02 | 5.10 | 5.07 | 0.03 | 31.2 | 99.4% | 0.61% | 0.0 | 31.2 | calculator×1, code_exec×1, search×1 |
| LH-01 | 17.91 | 17.70 | 0.20 | 390.6 | 98.9% | 2.18% | 46.9 | 343.8 | retrieve×12 |
| LH-02 | 4.72 | 4.71 | 0.01 | 0.0 | 99.8% | 0.00% | 0.0 | 15.6 | none |
| RE-01 | 15.24 | 15.20 | 0.04 | 31.2 | 99.7% | 0.21% | 0.0 | 31.2 | calculator×2, code_exec×3 |
| RE-02 | 6.04 | 6.19 | 0.00 | 31.2 | 102.5% | 0.52% | 0.0 | 31.2 | search×2 |
| RH-01 | 8.09 | 7.99 | 0.10 | 203.1 | 98.8% | 2.51% | 15.6 | 187.5 | retrieve×5 |
| RH-02 | 8.02 | 7.98 | 0.04 | 109.4 | 99.5% | 1.36% | 0.0 | 109.4 | retrieve×3 |
| SH-01 | 8.78 | 9.32 | 0.00 | 140.6 | 106.2% | 1.60% | 0.0 | 140.6 | search×3 |
| SH-02 | 6.14 | 6.96 | 0.00 | 46.9 | 113.3% | 0.76% | 0.0 | 46.9 | search×4 |
| **Total** | 94.37 | 95.36 | -1.00 | 1140.6 | 101.1% | 1.21% | | | |

#### Per-task CPU category breakdown

**CH-01** — 156.2 ms host CPU, 14.34 s session wall — tools: calculator×2, code_exec×4

| Category | CPU ms | Share of task CPU |
|---|---|---|
| HTTP_CLIENT | 78.1 | 50.0% |
| ORCH_DISPATCH | 31.2 | 20.0% |
| ORCH_SETUP | 15.6 | 10.0% |
| TOKENIZATION | 15.6 | 10.0% |
| TOOL_COMPUTE | 15.6 | 10.0% |

**CH-02** — 31.2 ms host CPU, 5.10 s session wall — tools: calculator×1, code_exec×1, search×1

| Category | CPU ms | Share of task CPU |
|---|---|---|
| HTTP_CLIENT | 31.2 | 100.0% |

**LH-01** — 390.6 ms host CPU, 17.91 s session wall — tools: retrieve×12

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 187.5 | 48.0% |
| HTTP_CLIENT | 109.4 | 28.0% |
| TOOL_COMPUTE | 46.9 | 12.0% |
| TOKENIZATION | 31.2 | 8.0% |
| ORCH_SETUP | 15.6 | 4.0% |

**LH-02** — 0.0 ms host CPU, 4.72 s session wall — tools: none

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_SETUP | 15.6 | 100.0% |

**RE-01** — 31.2 ms host CPU, 15.24 s session wall — tools: calculator×2, code_exec×3

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_SETUP | 15.6 | 50.0% |
| ORCH_DISPATCH | 15.6 | 50.0% |

**RE-02** — 31.2 ms host CPU, 6.04 s session wall — tools: search×2

| Category | CPU ms | Share of task CPU |
|---|---|---|
| HTTP_CLIENT | 15.6 | 50.0% |
| ORCH_DISPATCH | 15.6 | 50.0% |

**RH-01** — 203.1 ms host CPU, 8.09 s session wall — tools: retrieve×5

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 140.6 | 69.2% |
| TOKENIZATION | 31.2 | 15.4% |
| ORCH_SETUP | 15.6 | 7.7% |
| TOOL_COMPUTE | 15.6 | 7.7% |

**RH-02** — 109.4 ms host CPU, 8.02 s session wall — tools: retrieve×3

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 93.8 | 85.7% |
| HTTP_CLIENT | 15.6 | 14.3% |

**SH-01** — 140.6 ms host CPU, 8.78 s session wall — tools: search×3

| Category | CPU ms | Share of task CPU |
|---|---|---|
| HTTP_CLIENT | 62.5 | 44.4% |
| GC | 46.9 | 33.3% |
| TOKENIZATION | 15.6 | 11.1% |
| ORCH_DISPATCH | 15.6 | 11.1% |

**SH-02** — 46.9 ms host CPU, 6.14 s session wall — tools: search×4

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 31.2 | 66.7% |
| ORCH_SETUP | 15.6 | 33.3% |


### Pooled vs equal-weight (different questions)

*Denominators: n=1 seed(s)=[0], search=remote, batch host CPU=1141 ms, batch wall=98.1 s, CPU% of wall≈1.21%, c=1. Comparison type: single-run sample unless replication_batch artifact.*

| Metric | Pooled (headline table) | Equal-weight task average |
|---|---|---|
| TOOL_COMPUTE CPU share | 6.8% of batch CPU | 3.0% |
| Answers | What consumed this batch's total host capacity | What a typical task of each type costs (one session per task here) |

Use **pooled** for capacity planning (dominated by heavy outlier sessions). Use **equal-weight per-archetype** rows below for archetype characterization. Do not treat the overall equal-weight amenability mean as a representative headline — it averages a bimodal distribution.

### Archetype amenability (primary equal-weight table)

| Archetype | Tasks | Mean CPU ms | Strict amenable | Broad amenable |
|---|---|---|---|---|
| CH (code_heavy) | CH-01, CH-02 | 93.8 | 20.0% | 95.0% |
| LH (long_horizon) | LH-01, LH-02 | 203.1 | 80.0% ‡ | 94.0% ‡ |
| RE (reasoning_heavy) | RE-01, RE-02 | 31.2 | 75.0% | 100.0% |
| RH (rag_heavy) | RH-01, RH-02 | 156.2 | 89.0% ‡ | 96.2% ‡ |
| SH (search_heavy) | SH-01, SH-02 | 93.8 | 61.1% | 83.3% |

‡ **Small-base caution:** strict/broad percentages are of mean instrumented CPU near the Windows thread-time tick floor (~15 ms). High amenability % on RH/LH reflects sessions that barely ran local work, not hardware-friendly archetypes. Do not quote without absolute CPU ms; prefer Linux re-run for tick resolution.

**CH blend:** the CH archetype row averages tasks that can land in opposite behavior clusters — report CH-01 and CH-02 individually alongside the CH row (see per-task sections).

### Deployment model and headline reconciliation

This run models **production-shaped search** (remote API + I/O wait). The baseline `real_agent_breakdown.json` used **local in-process regex search**.

**Corrected headline framing:** local-search runs looked TOOL-dominated because the mock search tool intentionally scans a 50 MB corpus on-host. Under remote search, TOOL_COMPUTE falls and orchestration/serialization/tokenization (APU-relevant harness work) become the dominant *on-host* categories — reconciling this breakdown with the Phase 0 concurrency experiment's orchestration-dominant picture.

| Metric | Local search (baseline) | Remote search (this run) |
|---|---|---|
| Batch host CPU | 6203.1 ms | 1140.6 ms |
| Pooled TOOL_COMPUTE share | 86.1% | 6.8% |
| Pooled ORCH share | 7.1% | 54.8% |
| Pooled harness APU share (ORCH+TOKEN+SERIAL) | 11.3% | 63.0% |
| Equal-weight TOOL_COMPUTE share | 32.6% | 3.0% |

Sessions that invoked local search (SH, and CH-02 when the model chose search) move from the CPU-heavy cluster to I/O-dominated wall time; remaining TOOL_COMPUTE is code_exec and local retrieve only.

### Behavioral buckets (realized workload, not task labels)

Buckets are assigned from realized tool calls and turn count, not from task archetype labels. Task-label tables are prompt-intent only.

CPU floor for detailed per-task amenability: 200.0 ms

| Bucket | Label | Tasks | Mean host CPU ms | Mean strict amenable |
|---|---|---|---|---|
| B0_io_only | no tool calls (LLM-only) | LH-02 | 0.0 | 100.0% |
| B1_search_only | search only (no local code/retrieve) | SH-01, SH-02, RE-02 | 72.9 | 57.4% |
| B2_mixed_tools | search plus code and/or retrieve | CH-02 | 31.2 | 0.0% |
| B3_retrieve_heavy | retrieve-heavy (≥5 calls) | RH-01, LH-01 | 296.9 | 76.2% |
| B3_retrieve_light | retrieve-light (<5 calls) | RH-02 | 109.4 | 85.7% |
| B4_code_light | code_exec light (<5 calls) | CH-01, RE-01 | 93.8 | 70.0% |

Task archetype labels (SH, RH, …) are prompt-intent only; use behavioral buckets for workload-ground-truth grouping.

### Accounting audit

- pass: **YES**
- publishable_ok: **NO**
- platform: `win32`
- Windows tick: 15.625 ms (footnote-only below 200 ms/session)
- warning: Host CPU values appear quantized to 15.625 ms Windows thread-time ticks; per-task shares below ~200 ms/session are not quotable. Re-run on Linux with test_resolution PASS before publishing.
- warning: SH-01: host CPU 140.6 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: SH-02: host CPU 46.9 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: CH-01: host CPU 156.2 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: CH-02: host CPU 31.2 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: RH-01: reconcile gap 109.4 ms is 54% of process CPU — check attribution
- warning: RH-02: host CPU 109.4 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: RE-01: host CPU 31.2 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: RE-02: host CPU 31.2 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: LH-01: reconcile gap 140.6 ms is 36% of process CPU — check attribution
- warning: RE-02: I/O % of wall is 102.5% (>100%) — HTTP_CLIENT wall includes remote-tool waits concurrent with session clock; not an additive partition (see wall integrity table)
- warning: SH-01: I/O % of wall is 106.2% (>100%) — HTTP_CLIENT wall includes remote-tool waits concurrent with session clock; not an additive partition (see wall integrity table)
- warning: SH-02: I/O % of wall is 113.3% (>100%) — HTTP_CLIENT wall includes remote-tool waits concurrent with session clock; not an additive partition (see wall integrity table)
- warning: Single-seed run (n=1); replication requires n≥5 seeds with medians and IQR before headline numbers are quotable

### Wall-time attribution integrity

CPU category shares partition instrumented CPU (exclusive nesting; invariant PASS). **Wall fractions are not a partition metric** in real-agent mode: TOOL_COMPUTE/GC timers run on LangGraph tool-pool threads while the stream thread's session clock is also advancing, so summing all category wall fractions can exceed 100%. ORCH stream steps now use perf_counter gaps minus tagged wall (not thread CPU).

† TOOL_COMPUTE/GC: report mean wall ms; wall/session is marked concurrent (same clock period as session wait, not additive).

| Task | Session wall s | All-category coverage | Partition coverage |
|---|---|---|---|
| CH-01 | 14.34 | 99.9% | 99.5% |
| CH-02 | 5.10 | 105.0% | 104.8% |
| LH-01 | 17.91 | 100.6% | 100.2% |
| LH-02 | 4.72 | 100.0% | 99.8% |
| RE-01 | 15.24 | 99.9% | 99.9% |
| RE-02 | 6.04 | 111.8% | 111.6% |
| RH-01 | 8.09 | 104.6% | 102.6% |
| RH-02 | 8.02 | 101.0% | 100.6% |
| SH-01 | 8.78 | 120.4% | 119.2% |
| SH-02 | 6.14 | 137.3% | 137.1% |

### Equal-weight category breakdown by archetype

Mean CPU share partitions instrumented CPU (~100% per task). Wall/session excludes concurrent tool-pool categories (†).

#### CH (code_heavy)

- tasks (2): CH-01, CH-02
- mean session wall: 9.72 s
- mean instrumented CPU: 93.8 ms
- mean amenable strict: 20.0%
- mean amenable broad: 95.0%
- partition wall fractions sum: 102.2% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)
- **Caveat:** CH-01 and CH-02 landed in opposite behavior clusters; see individual task sections below.

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| HTTP_CLIENT | overlap | 54.7 | 75.0% | 9654.7 | 99.4% |
| ORCH_DISPATCH | direct | 15.6 | 10.0% | 142.4 | 2.7% |
| ORCH_SETUP | direct | 7.8 | 5.0% | 10.1 | n/a |
| TOKENIZATION | direct | 7.8 | 5.0% | 11.6 | 0.1% |
| TOOL_COMPUTE | none | 7.8 | 5.0% | 18.4 | concurrent† |
| GC | none | 0.0 | 0.0% | 0.0 | concurrent† |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.5 | 0.0% |

#### LH (long_horizon)

- tasks (2): LH-01, LH-02
- mean session wall: 11.31 s
- mean instrumented CPU: 203.1 ms
- mean amenable strict: 80.0%
- mean amenable broad: 94.0%
- partition wall fractions sum: 100.0% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 93.8 | 24.0% | 91.9 | 0.5% |
| HTTP_CLIENT | overlap | 54.7 | 14.0% | 11206.7 | 99.3% |
| TOOL_COMPUTE | none | 23.4 | 6.0% | 33.5 | concurrent† |
| ORCH_SETUP | direct | 15.6 | 52.0% | 8.6 | n/a |
| TOKENIZATION | direct | 15.6 | 4.0% | 23.3 | 0.1% |
| GC | none | 0.0 | 0.0% | 0.0 | concurrent† |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.9 | 0.0% |

#### RE (reasoning_heavy)

- tasks (2): RE-01, RE-02
- mean session wall: 10.64 s
- mean instrumented CPU: 31.2 ms
- mean amenable strict: 75.0%
- mean amenable broad: 100.0%
- partition wall fractions sum: 105.7% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 15.6 | 50.0% | 277.6 | 4.5% |
| HTTP_CLIENT | overlap | 7.8 | 25.0% | 10696.6 | 101.1% |
| ORCH_SETUP | direct | 7.8 | 25.0% | 11.8 | n/a |
| GC | none | 0.0 | 0.0% | 0.0 | concurrent† |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.3 | 0.0% |
| TOKENIZATION | direct | 0.0 | 0.0% | 6.0 | 0.1% |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 1.6 | concurrent† |

#### RH (rag_heavy)

- tasks (2): RH-01, RH-02
- mean session wall: 8.05 s
- mean instrumented CPU: 156.2 ms
- mean amenable strict: 89.0%
- mean amenable broad: 96.2%
- partition wall fractions sum: 101.6% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 117.2 | 77.5% | 194.7 | 2.4% |
| TOKENIZATION | direct | 15.6 | 7.7% | 6.5 | 0.1% |
| HTTP_CLIENT | overlap | 7.8 | 7.1% | 7982.1 | 99.1% |
| ORCH_SETUP | direct | 7.8 | 3.8% | 12.4 | n/a |
| TOOL_COMPUTE | none | 7.8 | 3.8% | 80.6 | concurrent† |
| GC | none | 0.0 | 0.0% | 0.0 | concurrent† |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 0.0% |

#### SH (search_heavy)

- tasks (2): SH-01, SH-02
- mean session wall: 7.46 s
- mean instrumented CPU: 93.8 ms
- mean amenable strict: 61.1%
- mean amenable broad: 83.3%
- partition wall fractions sum: 128.2% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| HTTP_CLIENT | overlap | 31.2 | 22.2% | 8141.8 | 109.8% |
| GC | none | 23.4 | 16.7% | 23.4 | concurrent† |
| ORCH_DISPATCH | direct | 23.4 | 38.9% | 1288.9 | 18.2% |
| ORCH_SETUP | direct | 7.8 | 16.7% | 33.8 | n/a |
| TOKENIZATION | direct | 7.8 | 5.6% | 10.5 | 0.1% |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 0.0% |

### CH-01

- sessions: agent_2
- tool invocations: calculator×2, code_exec×4
- instrumented CPU: 156.2 ms
- hardware amenable: strict 40.0% (62.5 ms), broad 90.0% (140.6 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| HTTP_CLIENT | overlap | 78.1 | 50.0% | 14237.0 | 6 | 602 | 0 |
| ORCH_DISPATCH | direct | 31.2 | 20.0% | 20.1 | 17 | 0 | 0 |
| ORCH_SETUP | direct | 15.6 | 10.0% | 9.7 | 2 | 0 | 0 |
| TOKENIZATION | direct | 15.6 | 10.0% | 15.5 | 18 | 58900 | 0 |
| TOOL_COMPUTE | none | 15.6 | 10.0% | 35.4 | 6 | 469 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 6 | 0 | 45278 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.7 | 18 | 602 | 58195 |

### CH-02

- sessions: agent_3
- tool invocations: calculator×1, code_exec×1, search×1
- instrumented CPU: 31.2 ms
- hardware amenable: strict 0.0% (0.0 ms), broad 100.0% (31.2 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| HTTP_CLIENT | overlap | 31.2 | 100.0% | 5072.4 | 5 | 570 | 41 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 10.4 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 8827 |
| TOKENIZATION | direct | 0.0 | 0.0% | 7.7 | 7 | 17341 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.4 | 7 | 430 | 16864 |
| GC | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 1.5 | 2 | 98 | 0 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 264.7 | 7 | 0 | 0 |

### LH-01

- sessions: agent_8
- tool invocations: retrieve×12
- instrumented CPU: 390.6 ms
- hardware amenable: strict 60.0% (234.4 ms), broad 88.0% (343.8 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 187.5 | 48.0% | 183.9 | 37 | 0 | 0 |
| HTTP_CLIENT | overlap | 109.4 | 28.0% | 17701.6 | 13 | 2294 | 0 |
| TOOL_COMPUTE | none | 46.9 | 12.0% | 67.0 | 12 | 386 | 0 |
| TOKENIZATION | direct | 31.2 | 8.0% | 46.2 | 38 | 185925 | 0 |
| ORCH_SETUP | direct | 15.6 | 4.0% | 10.1 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.1 | 13 | 0 | 159548 |
| SERIALIZATION | direct | 0.0 | 0.0% | 1.7 | 38 | 2294 | 183431 |
| GC | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |

### LH-02

- sessions: agent_9
- tool invocations: none
- instrumented CPU: 15.6 ms
- hardware amenable: strict 100.0% (15.6 ms), broad 100.0% (15.6 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_SETUP | direct | 15.6 | 100.0% | 7.1 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 1 | 0 | 214 |
| TOKENIZATION | direct | 0.0 | 0.0% | 0.5 | 2 | 1852 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.0 | 2 | 1638 | 214 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 4711.8 | 1 | 1638 | 0 |

### RE-01

- sessions: agent_6
- tool invocations: calculator×2, code_exec×3
- instrumented CPU: 31.2 ms
- hardware amenable: strict 100.0% (31.2 ms), broad 100.0% (31.2 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_SETUP | direct | 15.6 | 50.0% | 10.9 | 2 | 0 | 0 |
| ORCH_DISPATCH | direct | 15.6 | 50.0% | 9.0 | 14 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 5 | 0 | 35100 |
| TOKENIZATION | direct | 0.0 | 0.0% | 9.1 | 15 | 47130 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.4 | 15 | 1183 | 45870 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 15199.4 | 5 | 1183 | 0 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 3.1 | 5 | 265 | 0 |
| GC | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |

### RE-02

- sessions: agent_7
- tool invocations: search×2
- instrumented CPU: 31.2 ms
- hardware amenable: strict 50.0% (15.6 ms), broad 100.0% (31.2 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| HTTP_CLIENT | overlap | 15.6 | 50.0% | 6193.7 | 8 | 2213 | 109 |
| ORCH_DISPATCH | direct | 15.6 | 50.0% | 546.1 | 5 | 0 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 12.7 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 4910 |
| TOKENIZATION | direct | 0.0 | 0.0% | 2.9 | 6 | 11177 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 6 | 1905 | 9241 |

### RH-01

- sessions: agent_4
- tool invocations: retrieve×5
- instrumented CPU: 203.1 ms
- hardware amenable: strict 92.3% (187.5 ms), broad 92.3% (187.5 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 140.6 | 69.2% | 306.4 | 12 | 0 | 0 |
| TOKENIZATION | direct | 31.2 | 15.4% | 7.7 | 9 | 21661 | 0 |
| ORCH_SETUP | direct | 15.6 | 7.7% | 13.2 | 2 | 0 | 0 |
| TOOL_COMPUTE | none | 15.6 | 7.7% | 142.7 | 5 | 59 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 10250 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.3 | 9 | 2047 | 19523 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 7985.4 | 2 | 2047 | 0 |
| GC | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |

### RH-02

- sessions: agent_5
- tool invocations: retrieve×3
- instrumented CPU: 109.4 ms
- hardware amenable: strict 85.7% (93.8 ms), broad 100.0% (109.4 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 93.8 | 85.7% | 82.9 | 8 | 0 | 0 |
| HTTP_CLIENT | overlap | 15.6 | 14.3% | 7978.7 | 2 | 2429 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 11.6 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 4774 |
| TOKENIZATION | direct | 0.0 | 0.0% | 5.3 | 7 | 11359 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 7 | 2429 | 8877 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 18.5 | 3 | 55 | 0 |

### SH-01

- sessions: agent_0
- tool invocations: search×3
- instrumented CPU: 140.6 ms
- hardware amenable: strict 22.2% (31.2 ms), broad 66.7% (93.8 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| HTTP_CLIENT | overlap | 62.5 | 44.4% | 9323.2 | 11 | 2791 | 82 |
| GC | none | 46.9 | 33.3% | 46.9 | 77 | 0 | 0 |
| TOKENIZATION | direct | 15.6 | 11.1% | 17.0 | 7 | 15015 | 0 |
| ORCH_DISPATCH | direct | 15.6 | 11.1% | 1121.8 | 8 | 0 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 55.0 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 6616 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 7 | 2411 | 12546 |

### SH-02

- sessions: agent_1
- tool invocations: search×4
- instrumented CPU: 46.9 ms
- hardware amenable: strict 100.0% (46.9 ms), broad 100.0% (46.9 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 31.2 | 66.7% | 1456.1 | 10 | 0 | 0 |
| ORCH_SETUP | direct | 15.6 | 33.3% | 12.7 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 5093 |
| TOKENIZATION | direct | 0.0 | 0.0% | 4.0 | 8 | 10833 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 8 | 1385 | 9387 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 6960.3 | 14 | 1884 | 103 |
| GC | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |

## Process user/system split

- user: 2.047 s, system: 1.344 s
- per-category kernel-time attribution is approximate; category timers are user-space, syscall-heavy regions surface partly as system time

## Per-session summary

| Session | Task | Turns | Tool calls | Graph nodes | Dispatches | Wall s | Thread CPU ms |
|---|---|---|---|---|---|---|---|
| agent_0 | SH-01 | 5 | search:3 | n/a | n/a | 8.78 | 140.62 |
| agent_1 | SH-02 | 6 | search:4 | n/a | n/a | 6.14 | 46.88 |
| agent_2 | CH-01 | 12 | calculator:2, code_exec:4 | n/a | n/a | 14.34 | 156.25 |
| agent_3 | CH-02 | 5 | calculator:1, code_exec:1, search:1 | n/a | n/a | 5.10 | 31.25 |
| agent_4 | RH-01 | 7 | retrieve:5 | n/a | n/a | 8.09 | 203.12 |
| agent_5 | RH-02 | 5 | retrieve:3 | n/a | n/a | 8.02 | 109.38 |
| agent_6 | RE-01 | 10 | calculator:2, code_exec:3 | n/a | n/a | 15.24 | 31.25 |
| agent_7 | RE-02 | 4 | search:2 | n/a | n/a | 6.04 | 31.25 |
| agent_8 | LH-01 | 25 | retrieve:12 | n/a | n/a | 17.91 | 390.62 |
| agent_9 | LH-02 | 1 | none | n/a | n/a | 4.72 | 0.00 |

## Tool usage (all sessions including sub-agents)

| Tool | Calls | Result bytes |
|---|---|---|
| calculator | 5 | 0 |
| code_exec | 8 | 0 |
| retrieve | 20 | 0 |
| search | 10 | 0 |

## Tasks executed

### SH-01 (search_heavy)

Goal: What causes different kinds of weather? Collect mentions of rain, storms, and temperature changes and summarize the patterns.

- turn 0: search <- rain storm
- turn 1: search <- temperature cold warm
- turn 2: search <- wind forecast
- turn 3: search <- snow season
- turn 4: search <- climate humidity
- turn 5: search <- cloud sun
- turn 6: calculator <- (72 - 32) * 5 / 9
- turn 7: search <- storm wind rain
- turn 8: search <- season climate
- turn 9: reasoning only

### SH-02 (search_heavy)

Goal: Put together a short overview of space topics: find what the corpus says about planets, the moon, eclipses, and telescopes.

- turn 0: search <- planet orbit
- turn 1: search <- moon eclipse
- turn 2: search <- solar eclipse
- turn 3: search <- telescope star
- turn 4: search <- rocket astronaut
- turn 5: retrieve <- which planets can be seen without a telescope
- turn 6: search <- mars earth
- turn 7: search <- gravity light
- turn 8: search <- galaxy star
- turn 9: search <- orbit gravity
- turn 10: reasoning only

### CH-01 (code_heavy)

Goal: What is the sum of all prime numbers below 20000? Verify with a second computation and sanity-check the magnitude.

- turn 0: code_exec <- limit = 20000 sieve = [True] * limit sieve[0] = sieve[1] = False for i in range(2, int(limit ** 0.5)
- turn 1: code_exec <- xs = [(i * 2654435761) % 100003 for i in range(30000)] xs.sort() result = xs[len(xs) // 2]
- turn 2: calculator <- 21171191 / 1000000
- turn 3: code_exec <- a, b = 0, 1 for _ in range(50000):     a, b = b, (a + b) % 1000000007 result = a
- turn 4: reasoning only

### CH-02 (code_heavy)

Goal: If I save 1000 dollars at 5 percent interest for 30 years, how much do I have? Also check a word-frequency count and a median.

- turn 0: code_exec <- balance = 1000.0 rate = 0.05 for year in range(30):     balance = balance * (1 + rate) result = int(
- turn 1: code_exec <- text = ("the quick brown fox jumps over the lazy dog and runs away " * 800).split() counts = {} for 
- turn 2: code_exec <- xs = [(i * 2654435761) % 100003 for i in range(30000)] xs.sort() result = xs[len(xs) // 2]
- turn 3: search <- bank interest save
- turn 4: calculator <- 1000 * 1.05 ** 30
- turn 5: reasoning only

### RH-01 (rag_heavy)

Goal: Answer five basic nature questions using retrieval: how plants grow, the water cycle, rivers and oceans, forests, and birds.

- turn 0: retrieve <- how do plants grow from soil and water
- turn 1: retrieve <- what is the water cycle rain river ocean
- turn 2: retrieve <- why do rivers flow into the ocean
- turn 3: retrieve <- what animals live in a forest
- turn 4: retrieve <- where do birds go in winter
- turn 5: search <- tree leaf forest
- turn 6: reasoning only

### RH-02 (rag_heavy)

Goal: Build a simple guide to home baking by retrieving passages about bread, ingredients, and oven technique.

- turn 0: retrieve <- how to bake bread with flour and butter
- turn 1: retrieve <- what temperature should the oven be for baking
- turn 2: retrieve <- how much sugar and salt goes in a recipe
- turn 3: calculator <- 350 / 2 + 25
- turn 4: retrieve <- difference between baking with butter and oil
- turn 5: retrieve <- how long should bread rest before cutting
- turn 6: retrieve <- simple dinner recipes with vegetables and cheese
- turn 7: reasoning only

### RE-01 (reasoning_heavy)

Goal: A train leaves at 9am going 80 km per hour and another leaves at 10am going 100 km per hour on the same route. Reason through when the second catches the first, and verify the arithmetic.

- turn 0: reasoning only
- turn 1: reasoning only
- turn 2: calculator <- 80 / (100 - 80)
- turn 3: reasoning only

### RE-02 (reasoning_heavy)

Goal: Is it better to sleep eight hours or exercise an extra hour? Reason through the trade-offs, checking one fact in the corpus.

- turn 0: reasoning only
- turn 1: search <- sleep exercise energy
- turn 2: reasoning only
- turn 3: reasoning only

### LH-01 (long_horizon)

Goal: Help me plan a vegetable garden for the whole year, month by month. One retrieval per month; the growing plan accumulates in context, so state copies and token counts grow within the session.

- turn 0: retrieve <- what vegetables grow in january winter
- turn 1: retrieve <- what to plant in february cold soil
- turn 2: retrieve <- what vegetables grow in early spring march
- turn 3: retrieve <- when to plant tomatoes in april
- turn 4: retrieve <- what to plant in may after last frost
- turn 5: retrieve <- which vegetables handle summer heat in june
- turn 6: retrieve <- watering schedule for july vegetable garden
- turn 7: retrieve <- what to harvest and replant in august
- turn 8: retrieve <- what vegetables grow in september fall
- turn 9: retrieve <- which crops survive october frost
- turn 10: retrieve <- preparing garden soil in november
- turn 11: retrieve <- what can grow in december indoors
- turn 12: reasoning only

### LH-02 (long_horizon)

Goal: Teach me basic cooking, one lesson at a time, and quiz me as we go. Alternates retrieval, quiz-composition reasoning, and a calculator check on a scaled recipe. Long and chatty; state accumulates every turn.

- turn 0: retrieve <- how to boil an egg step by step
- turn 1: reasoning only
- turn 2: calculator <- 2 * 3 / 4
- turn 3: retrieve <- what does simmer mean in cooking
- turn 4: reasoning only
- turn 5: calculator <- 1.5 * 2 / 3
- turn 6: retrieve <- how to chop an onion safely
- turn 7: reasoning only
- turn 8: calculator <- 3 * 1 / 2
- turn 9: retrieve <- how do I know when pasta is done
- turn 10: reasoning only
- turn 11: reasoning only


## Reproduce

```
python -m apu_characterization.experiments.real_agent_breakdown --backend openai --profile mixed --seed 0 --sessions 10 --llm-scale 0.05 --search-locality remote --payload-profile locality_ablation
```
