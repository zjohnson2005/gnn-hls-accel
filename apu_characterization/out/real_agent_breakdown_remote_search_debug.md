# Experiment 0R: real LangGraph agent CPU-time breakdown (scripted, remote search deployment)

> **DEBUG ONLY — NOT VALID EXPERIMENTAL DATA.** This artifact used a mock or scripted decision path (no live OpenAI agent). Use only to verify instrumentation and invariants. Do not cite in papers, slides, or findings. Publishable results require `real_agent_breakdown --backend openai`.

Generated: 2026-07-07T17:44:12.785851+00:00 from `real_agent_breakdown_remote_search_debug.json`.
All numbers below are read from that artifact.

## Setup

- setup record: digest `fe9707b03e17a5b7`, task suite `a88a9e1058964219` (see EXPERIMENT_SETUP.md)
- cpu (from setup record): Intel(R) Core(TM) Ultra 5 325
- git commit: `unknown` (dirty tree: unknown)
- python: 3.14.0
- platform: Windows-11-10.0.26200-SP0
- cpu: Intel64 Family 6 Model 204 Stepping 3, GenuineIntel, logical cores: 8
- ram_gb: 15.6

### Protocol

- profile: `mixed`, seed: 0, sessions: 10, execution: threads/scripted
- search locality: `remote`
- payload profile: `locality_ablation` (synthetic tool-result padding; see tool-locality ablation note)
- total CPU basis: sum(session process_time)
- mock LLM latency scale: 0.05 (scripted backend sleeps (wall only); openai backend ignores this)
- clocks: wall = perf_counter_ns; CPU = thread_time_ns per region; real-agent total CPU = process_time (all threads, including LangGraph tool executors)
- nesting: exclusive self-time accounting; an inner region pauses its parent
- timer overhead: 4219 ns per enter/exit pair
- batch wall time: 6.26 s

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

- total thread CPU: 5031.25 ms
- instrumented: 5031.25 ms
- residual: 0.00 ms (0.0% of total)
- limit: 15%  ->  PASS

## Breakdown (thread CPU, exclusive per category — pooled across all sessions)

| Category | CPU ms | Share of total | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|
| ORCH_DISPATCH | 4656.250 | 92.5% | 17357.716 | 196 | 0 | 0 |
| TOKENIZATION | 140.625 | 2.8% | 100.360 | 134 | 240654 | 0 |
| ORCH_SETUP | 109.375 | 2.2% | 2160.474 | 20 | 0 | 0 |
| TOOL_COMPUTE | 78.125 | 1.6% | 239.593 | 42 | 1956 | 0 |
| GC | 31.250 | 0.6% | 31.250 | 7 | 0 | 0 |
| HTTP_CLIENT | 15.625 | 0.3% | 6925.191 | 60 | 2651 | 668 |
| SERIALIZATION | 0.000 | 0.0% | 1.569 | 62 | 0 | 149383 |
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
| CH-01 | 531.2 | 91.2% | 91.2% |
| CH-02 | 562.5 | 97.2% | 97.2% |
| LH-01 | 562.5 | 97.2% | 97.2% |
| LH-02 | 500.0 | 96.9% | 96.9% |
| RE-01 | 234.4 | 100.0% | 100.0% |
| RE-02 | 265.6 | 100.0% | 100.0% |
| RH-01 | 562.5 | 97.2% | 97.2% |
| RH-02 | 515.6 | 100.0% | 100.0% |
| SH-01 | 656.2 | 100.0% | 100.0% |
| SH-02 | 640.6 | 97.6% | 100.0% |

### Per-task LLM I/O wait vs host CPU

Each row is one session. **LLM I/O wait** = HTTP_CLIENT wall (blocked on OpenAI). **Host CPU** = session process_time. I/O % and CPU % both divide by session wall; they are different axes (wait vs compute), not additive category wall fractions.

| Task | Session wall s | LLM I/O wait s | Non-LLM wall s | Host CPU ms | I/O % of wall | CPU % of wall | Tool CPU ms | Harness CPU ms | Tools |
|---|---|---|---|---|---|---|---|---|---|
| CH-01 | 0.94 | 0.00 | 0.94 | 531.2 | 0.0% | 56.40% | 15.6 | 515.6 | calculator×1, code_exec×3 |
| CH-02 | 0.99 | 0.37 | 0.62 | 562.5 | 37.4% | 56.79% | 15.6 | 546.9 | calculator×1, code_exec×3, search×1 |
| LH-01 | 1.41 | 0.00 | 1.41 | 562.5 | 0.0% | 39.97% | 15.6 | 546.9 | retrieve×12 |
| LH-02 | 0.84 | 0.00 | 0.84 | 500.0 | 0.0% | 59.38% | 15.6 | 484.4 | calculator×3, retrieve×4 |
| RE-01 | 0.27 | 0.00 | 0.27 | 234.4 | 0.0% | 85.51% | 0.0 | 234.4 | calculator×1 |
| RE-02 | 0.38 | 0.18 | 0.20 | 265.6 | 47.2% | 70.82% | 0.0 | 265.6 | search×1 |
| RH-01 | 1.10 | 0.27 | 0.83 | 562.5 | 24.4% | 51.05% | 15.6 | 546.9 | retrieve×5, search×1 |
| RH-02 | 0.89 | 0.00 | 0.89 | 515.6 | 0.0% | 57.83% | 0.0 | 515.6 | calculator×1, retrieve×6 |
| SH-01 | 4.05 | 2.71 | 1.35 | 656.2 | 66.8% | 16.19% | 0.0 | 656.2 | calculator×1, search×8 |
| SH-02 | 4.83 | 3.40 | 1.43 | 640.6 | 70.4% | 13.27% | 0.0 | 640.6 | retrieve×1, search×9 |
| **Total** | 15.71 | 6.93 | 8.78 | 5031.2 | 44.1% | 32.03% | | | |

#### Per-task CPU category breakdown

**CH-01** — 531.2 ms host CPU:

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 406.2 | 76.5% |
| ORCH_SETUP | 46.9 | 8.8% |
| GC | 31.2 | 5.9% |
| TOKENIZATION | 31.2 | 5.9% |
| TOOL_COMPUTE | 15.6 | 2.9% |

**CH-02** — 562.5 ms host CPU:

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 515.6 | 91.7% |
| ORCH_SETUP | 15.6 | 2.8% |
| TOKENIZATION | 15.6 | 2.8% |
| TOOL_COMPUTE | 15.6 | 2.8% |

**LH-01** — 562.5 ms host CPU:

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 500.0 | 88.9% |
| TOKENIZATION | 46.9 | 8.3% |
| TOOL_COMPUTE | 15.6 | 2.8% |

**LH-02** — 500.0 ms host CPU:

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 468.8 | 93.8% |
| TOKENIZATION | 15.6 | 3.1% |
| TOOL_COMPUTE | 15.6 | 3.1% |

**RE-01** — 234.4 ms host CPU:

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 234.4 | 100.0% |

**RE-02** — 265.6 ms host CPU:

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 250.0 | 94.1% |
| ORCH_SETUP | 15.6 | 5.9% |

**RH-01** — 562.5 ms host CPU:

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 546.9 | 97.2% |
| TOOL_COMPUTE | 15.6 | 2.8% |

**RH-02** — 515.6 ms host CPU:

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 484.4 | 93.9% |
| ORCH_SETUP | 15.6 | 3.0% |
| TOKENIZATION | 15.6 | 3.0% |

**SH-01** — 656.2 ms host CPU:

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 656.2 | 100.0% |

**SH-02** — 640.6 ms host CPU:

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 593.8 | 92.7% |
| ORCH_SETUP | 15.6 | 2.4% |
| TOKENIZATION | 15.6 | 2.4% |
| HTTP_CLIENT | 15.6 | 2.4% |


### Pooled vs equal-weight (different questions)

| Metric | Pooled (headline table) | Equal-weight task average |
|---|---|---|
| TOOL_COMPUTE CPU share | 1.6% of batch CPU | 1.4% |
| Answers | What consumed this batch's total host capacity | What a typical task of each type costs (one session per task here) |

Use **pooled** for capacity planning (dominated by heavy outlier sessions). Use **equal-weight per-archetype** rows below for archetype characterization. Do not treat the overall equal-weight amenability mean as a representative headline — it averages a bimodal distribution.

### Archetype amenability (primary equal-weight table)

| Archetype | Tasks | Mean CPU ms | Strict amenable | Broad amenable |
|---|---|---|---|---|
| CH (code_heavy) | CH-01, CH-02 | 546.9 | 94.2% | 94.2% |
| LH (long_horizon) | LH-01, LH-02 | 531.2 | 97.0% ‡ | 97.0% ‡ |
| RE (reasoning_heavy) | RE-01, RE-02 | 250.0 | 100.0% | 100.0% |
| RH (rag_heavy) | RH-01, RH-02 | 539.1 | 98.6% ‡ | 98.6% ‡ |
| SH (search_heavy) | SH-01, SH-02 | 648.4 | 98.8% | 100.0% |

‡ **Small-base caution:** strict/broad percentages are of mean instrumented CPU near the Windows thread-time tick floor (~15 ms). High amenability % on RH/LH reflects sessions that barely ran local work, not hardware-friendly archetypes. Do not quote without absolute CPU ms; prefer Linux re-run for tick resolution.

**CH blend:** the CH archetype row averages tasks that can land in opposite behavior clusters — report CH-01 and CH-02 individually alongside the CH row (see per-task sections).

### Deployment model and headline reconciliation

This run models **production-shaped search** (remote API + I/O wait). The baseline `real_agent_breakdown.json` used **local in-process regex search**.

**Corrected headline framing:** local-search runs looked TOOL-dominated because the mock search tool intentionally scans a 50 MB corpus on-host. Under remote search, TOOL_COMPUTE falls and orchestration/serialization/tokenization (APU-relevant harness work) become the dominant *on-host* categories — reconciling this breakdown with the Phase 0 concurrency experiment's orchestration-dominant picture.

| Metric | Local search (baseline) | Remote search (this run) |
|---|---|---|
| Batch host CPU | 9093.8 ms | 5031.2 ms |
| Pooled TOOL_COMPUTE share | 90.9% | 1.6% |
| Pooled ORCH share | 6.2% | 94.7% |
| Pooled harness APU share (ORCH+TOKEN+SERIAL) | 8.1% | 97.5% |
| Equal-weight TOOL_COMPUTE share | 32.0% | 1.4% |

Sessions that invoked local search (SH, and CH-02 when the model chose search) move from the CPU-heavy cluster to I/O-dominated wall time; remaining TOOL_COMPUTE is code_exec and local retrieve only.

### Wall-time attribution integrity

CPU category shares partition instrumented CPU (exclusive nesting; invariant PASS). **Wall fractions are not a partition metric** in real-agent mode: TOOL_COMPUTE/GC timers run on LangGraph tool-pool threads while the stream thread's session clock is also advancing, so summing all category wall fractions can exceed 100%. ORCH stream steps now use perf_counter gaps minus tagged wall (not thread CPU).

† TOOL_COMPUTE/GC: report mean wall ms; wall/session is marked concurrent (same clock period as session wait, not additive).

| Task | Session wall s | All-category coverage | Partition coverage |
|---|---|---|---|
| CH-01 | 0.94 | 140.9% | 84.1% |
| CH-02 | 0.99 | 187.2% | 170.1% |
| LH-01 | 1.41 | 125.3% | 113.7% |
| LH-02 | 0.84 | 149.8% | 129.2% |
| RE-01 | 0.27 | 183.9% | 115.4% |
| RE-02 | 0.38 | 213.0% | 168.7% |
| RH-01 | 1.10 | 167.9% | 149.7% |
| RH-02 | 0.89 | 150.0% | 119.0% |
| SH-01 | 4.05 | 181.6% | 175.0% |
| SH-02 | 4.83 | 181.3% | 175.3% |

### Equal-weight category breakdown by archetype

Mean CPU share partitions instrumented CPU (~100% per task). Wall/session excludes concurrent tool-pool categories (†).

#### CH (code_heavy)

- tasks (2): CH-01, CH-02
- mean session wall: 0.97 s
- mean instrumented CPU: 546.9 ms
- mean amenable strict: 94.2%
- mean amenable broad: 94.2%
- partition wall fractions sum: 127.1% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)
- **Caveat:** CH-01 and CH-02 landed in opposite behavior clusters; see individual task sections below.

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 460.9 | 84.1% | 1046.8 | 107.7% |
| ORCH_SETUP | direct | 31.2 | 5.8% | 321.0 | n/a |
| TOKENIZATION | direct | 23.4 | 4.3% | 6.0 | 0.6% |
| GC | none | 15.6 | 2.9% | 15.6 | concurrent† |
| TOOL_COMPUTE | none | 15.6 | 2.9% | 15.4 | concurrent† |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 185.4 | 18.7% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.1 | 0.0% |

#### LH (long_horizon)

- tasks (2): LH-01, LH-02
- mean session wall: 1.12 s
- mean instrumented CPU: 531.2 ms
- mean amenable strict: 97.0%
- mean amenable broad: 97.0%
- partition wall fractions sum: 121.5% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 484.4 | 91.3% | 1320.6 | 119.4% |
| TOKENIZATION | direct | 31.2 | 5.7% | 23.4 | 2.0% |
| TOOL_COMPUTE | none | 15.6 | 3.0% | 59.9 | concurrent† |
| GC | none | 0.0 | 0.0% | 0.0 | concurrent† |
| ORCH_SETUP | direct | 0.0 | 0.0% | 108.4 | n/a |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.3 | 0.0% |

#### RE (reasoning_heavy)

- tasks (2): RE-01, RE-02
- mean session wall: 0.32 s
- mean instrumented CPU: 250.0 ms
- mean amenable strict: 100.0%
- mean amenable broad: 100.0%
- partition wall fractions sum: 142.0% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 242.2 | 97.1% | 382.3 | 117.2% |
| ORCH_SETUP | direct | 7.8 | 2.9% | 176.7 | n/a |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 88.5 | 23.6% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.0 | 0.0% |
| TOKENIZATION | direct | 0.0 | 0.0% | 3.6 | 1.3% |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 0.4 | concurrent† |

#### RH (rag_heavy)

- tasks (2): RH-01, RH-02
- mean session wall: 1.00 s
- mean instrumented CPU: 539.1 ms
- mean amenable strict: 98.6%
- mean amenable broad: 98.6%
- partition wall fractions sum: 134.4% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 515.6 | 95.6% | 1215.3 | 121.6% |
| ORCH_SETUP | direct | 7.8 | 1.5% | 198.0 | n/a |
| TOKENIZATION | direct | 7.8 | 1.5% | 5.7 | 0.6% |
| TOOL_COMPUTE | none | 7.8 | 1.4% | 40.3 | concurrent† |
| GC | none | 0.0 | 0.0% | 0.0 | concurrent† |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 134.2 | 12.2% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 0.0% |

#### SH (search_heavy)

- tasks (2): SH-01, SH-02
- mean session wall: 4.44 s
- mean instrumented CPU: 648.4 ms
- mean amenable strict: 98.8%
- mean amenable broad: 100.0%
- partition wall fractions sum: 175.1% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 625.0 | 96.3% | 4713.7 | 106.3% |
| HTTP_CLIENT | overlap | 7.8 | 1.2% | 3054.4 | 68.6% |
| ORCH_SETUP | direct | 7.8 | 1.2% | 276.1 | n/a |
| TOKENIZATION | direct | 7.8 | 1.2% | 11.5 | 0.3% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 0.0% |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 3.8 | concurrent† |

### CH-01

- sessions: agent_2
- instrumented CPU: 531.2 ms
- hardware amenable: strict 91.2% (484.4 ms), broad 91.2% (484.4 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 406.2 | 76.5% | 784.2 | 13 | 0 | 0 |
| ORCH_SETUP | direct | 46.9 | 8.8% | 482.9 | 2 | 0 | 0 |
| GC | none | 31.2 | 5.9% | 31.2 | 1 | 0 | 0 |
| TOKENIZATION | direct | 31.2 | 5.9% | 7.7 | 9 | 15833 | 0 |
| TOOL_COMPUTE | none | 15.6 | 2.9% | 20.8 | 4 | 437 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.1 | 4 | 0 | 9768 |

### CH-02

- sessions: agent_3
- instrumented CPU: 562.5 ms
- hardware amenable: strict 97.2% (546.9 ms), broad 97.2% (546.9 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 515.6 | 91.7% | 1309.5 | 16 | 0 | 0 |
| ORCH_SETUP | direct | 15.6 | 2.8% | 159.1 | 2 | 0 | 0 |
| TOKENIZATION | direct | 15.6 | 2.8% | 4.3 | 11 | 16377 | 0 |
| TOOL_COMPUTE | none | 15.6 | 2.8% | 9.9 | 4 | 410 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.1 | 5 | 0 | 9683 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 370.9 | 3 | 138 | 39 |

### LH-01

- sessions: agent_8
- instrumented CPU: 562.5 ms
- hardware amenable: strict 97.2% (546.9 ms), broad 97.2% (546.9 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 500.0 | 88.9% | 1568.4 | 37 | 0 | 0 |
| TOKENIZATION | direct | 46.9 | 8.3% | 31.9 | 25 | 50911 | 0 |
| TOOL_COMPUTE | none | 15.6 | 2.8% | 91.4 | 12 | 443 | 0 |
| GC | none | 0.0 | 0.0% | 0.0 | 2 | 0 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 71.4 | 2 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.4 | 12 | 0 | 31861 |

### LH-02

- sessions: agent_9
- instrumented CPU: 500.0 ms
- hardware amenable: strict 96.9% (484.4 ms), broad 96.9% (484.4 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 468.8 | 93.8% | 1072.9 | 22 | 0 | 0 |
| TOKENIZATION | direct | 15.6 | 3.1% | 14.9 | 15 | 21675 | 0 |
| TOOL_COMPUTE | none | 15.6 | 3.1% | 28.4 | 7 | 151 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 145.4 | 2 | 0 | 0 |
| GC | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.1 | 7 | 0 | 9574 |

### RE-01

- sessions: agent_6
- instrumented CPU: 234.4 ms
- hardware amenable: strict 100.0% (234.4 ms), broad 100.0% (234.4 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 234.4 | 100.0% | 309.9 | 4 | 0 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 186.9 | 2 | 0 | 0 |
| TOKENIZATION | direct | 0.0 | 0.0% | 6.4 | 3 | 5350 | 0 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 0.9 | 1 | 15 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.0 | 1 | 0 | 3302 |

### RE-02

- sessions: agent_7
- instrumented CPU: 265.6 ms
- hardware amenable: strict 100.0% (265.6 ms), broad 100.0% (265.6 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 250.0 | 94.1% | 454.8 | 4 | 0 | 0 |
| ORCH_SETUP | direct | 15.6 | 5.9% | 166.5 | 2 | 0 | 0 |
| TOKENIZATION | direct | 0.0 | 0.0% | 0.8 | 3 | 2793 | 0 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 177.0 | 3 | 141 | 42 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.0 | 1 | 0 | 617 |

### RH-01

- sessions: agent_4
- instrumented CPU: 562.5 ms
- hardware amenable: strict 97.2% (546.9 ms), broad 97.2% (546.9 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 546.9 | 97.2% | 1375.0 | 19 | 0 | 0 |
| TOOL_COMPUTE | none | 15.6 | 2.8% | 35.8 | 5 | 167 | 0 |
| GC | none | 0.0 | 0.0% | 0.0 | 2 | 0 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 164.5 | 2 | 0 | 0 |
| TOKENIZATION | direct | 0.0 | 0.0% | 6.5 | 13 | 23265 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 6 | 0 | 15512 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 268.5 | 3 | 134 | 37 |

### RH-02

- sessions: agent_5
- instrumented CPU: 515.6 ms
- hardware amenable: strict 100.0% (515.6 ms), broad 100.0% (515.6 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 484.4 | 93.9% | 1055.7 | 22 | 0 | 0 |
| ORCH_SETUP | direct | 15.6 | 3.0% | 231.5 | 2 | 0 | 0 |
| TOKENIZATION | direct | 15.6 | 3.0% | 5.0 | 15 | 25618 | 0 |
| GC | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 44.8 | 7 | 271 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 7 | 0 | 15494 |

### SH-01

- sessions: agent_0
- instrumented CPU: 656.2 ms
- hardware amenable: strict 100.0% (656.2 ms), broad 100.0% (656.2 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 656.2 | 100.0% | 4376.2 | 28 | 0 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 269.0 | 2 | 0 | 0 |
| TOKENIZATION | direct | 0.0 | 0.0% | 10.5 | 19 | 36114 | 0 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 2706.8 | 24 | 1059 | 265 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 9 | 0 | 24513 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 0.9 | 1 | 17 | 0 |

### SH-02

- sessions: agent_1
- instrumented CPU: 640.6 ms
- hardware amenable: strict 97.6% (625.0 ms), broad 100.0% (640.6 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 593.8 | 92.7% | 5051.2 | 31 | 0 | 0 |
| ORCH_SETUP | direct | 15.6 | 2.4% | 283.2 | 2 | 0 | 0 |
| TOKENIZATION | direct | 15.6 | 2.4% | 12.4 | 21 | 42718 | 0 |
| HTTP_CLIENT | overlap | 15.6 | 2.4% | 3402.1 | 27 | 1179 | 285 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.3 | 10 | 0 | 29059 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 6.6 | 1 | 45 | 0 |

## Process user/system split

- user: 0.422 s, system: 0.344 s
- per-category kernel-time attribution is approximate; category timers are user-space, syscall-heavy regions surface partly as system time

## Per-session summary

| Session | Task | Turns | Tool calls | Graph nodes | Dispatches | Wall s | Thread CPU ms |
|---|---|---|---|---|---|---|---|
| agent_0 | SH-01 | 19 | calculator:1, search:8 | n/a | n/a | 4.05 | 656.25 |
| agent_1 | SH-02 | 21 | retrieve:1, search:9 | n/a | n/a | 4.83 | 640.62 |
| agent_2 | CH-01 | 9 | calculator:1, code_exec:3 | n/a | n/a | 0.94 | 531.25 |
| agent_3 | CH-02 | 11 | calculator:1, code_exec:3, search:1 | n/a | n/a | 0.99 | 562.50 |
| agent_4 | RH-01 | 13 | retrieve:5, search:1 | n/a | n/a | 1.10 | 562.50 |
| agent_5 | RH-02 | 15 | calculator:1, retrieve:6 | n/a | n/a | 0.89 | 515.62 |
| agent_6 | RE-01 | 3 | calculator:1 | n/a | n/a | 0.27 | 234.38 |
| agent_7 | RE-02 | 3 | search:1 | n/a | n/a | 0.38 | 265.62 |
| agent_8 | LH-01 | 25 | retrieve:12 | n/a | n/a | 1.41 | 562.50 |
| agent_9 | LH-02 | 15 | calculator:3, retrieve:4 | n/a | n/a | 0.84 | 500.00 |

## Tool usage (all sessions including sub-agents)

| Tool | Calls | Result bytes |
|---|---|---|
| calculator | 8 | 0 |
| code_exec | 6 | 0 |
| retrieve | 28 | 0 |
| search | 20 | 0 |

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
python -m apu_characterization.experiments.real_agent_breakdown --backend scripted --profile mixed --seed 0 --sessions 10 --llm-scale 0.05 --search-locality remote --payload-profile locality_ablation
```
