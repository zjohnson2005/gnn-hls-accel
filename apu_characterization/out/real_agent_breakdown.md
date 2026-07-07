# Experiment 0R: real LangGraph agent CPU-time breakdown (openai, local search (baseline))

> **AUDIT FAILED — DO NOT CITE.** Accounting assertions failed. Fix violations before using any numbers from this artifact.

Generated: 2026-07-07T18:49:17.234689+00:00 from `real_agent_breakdown.json`.
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
- search locality: `local`
- total CPU basis: sum(session process_time)
- mock LLM latency scale: 0.05 (scripted backend sleeps (wall only); openai backend ignores this)
- clocks: wall = perf_counter_ns; CPU = thread_time_ns per region; real-agent total CPU = process_time (all threads, including LangGraph tool executors)
- nesting: exclusive self-time accounting; an inner region pauses its parent
- timer overhead: 4219 ns per enter/exit pair
- batch wall time: 148.92 s

### What each category wraps in this harness

- `ORCH_SETUP`: REAL AGENT MODE: LangGraph first-step CPU residual (framework graph/session construction), the Phase 0 setup definition
- `ORCH_DISPATCH`: REAL AGENT MODE: LangGraph per-step CPU residual between stream events minus tagged tool CPU (completion handling, channel updates, handoff), the Phase 0 steady definition
- `SERIALIZATION`: json.dumps/loads of LLM responses and tool results, response parse
- `TOKENIZATION`: token counting of the full assembled prompt each turn plus the response body (tiktoken or len/4 fallback); models client-side context-window bookkeeping, so it scales with conversation length per turn
- `PROMPT_ASSEMBLY`: REAL AGENT MODE: inside the framework, not separable; included in the ORCH buckets
- `CONTEXT_MGMT`: REAL AGENT MODE: inside the framework (LangGraph state channels), not separable; included in the ORCH buckets
- `HTTP_CLIENT`: OpenAI backend: LangChain callback wraps each LLM call (request build, response parse; network wait costs ~zero thread CPU). Scripted backend: not used.
- `TOOL_COMPUTE`: tool bodies: regex corpus scan, exec'd snippet, numpy cosine top-k, sympy eval
- `LOGGING`: REAL AGENT MODE: not separately instrumented; inside ORCH buckets
- `GC`: collector cycles via gc.callbacks (lower bound, excludes refcount frees)
- `RESIDUAL`: computed: total thread CPU minus sum of instrumented categories

## Accounting invariant

sum(category thread-CPU) + residual = total thread-CPU of the run:

- total thread CPU: 6203.12 ms
- instrumented: 6218.75 ms
- residual: 0.00 ms (0.0% of total)
- limit: 15%  ->  PASS

## Breakdown (thread CPU, exclusive per category — pooled across all sessions)

*Denominators: n=1 seed(s)=[0], search=local, batch host CPU=6203 ms, batch wall=148.9 s, CPU% of wall≈4.28%, c=1*

| Category | CPU ms | Share of total | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|
| TOOL_COMPUTE | 5343.750 | 86.1% | 5865.533 | 26 | 584 | 0 |
| ORCH_DISPATCH | 390.625 | 6.3% | 1129.572 | 69 | 0 | 0 |
| TOKENIZATION | 265.625 | 4.3% | 2823.447 | 68 | 2364535 | 0 |
| HTTP_CLIENT | 140.625 | 2.3% | 138802.298 | 21 | 16811 | 0 |
| ORCH_SETUP | 46.875 | 0.8% | 98.493 | 20 | 0 | 0 |
| GC | 31.250 | 0.5% | 31.250 | 81 | 0 | 0 |
| PROMPT_ASSEMBLY | 0.000 | 0.0% | 0.099 | 21 | 0 | 1266364 |
| SERIALIZATION | 0.000 | 0.0% | 5.294 | 68 | 16811 | 2347315 |
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
| CH-01 | 31.2 | 100.0% | 100.0% |
| CH-02 | 203.1 | 84.6% | 84.6% |
| LH-01 | 46.9 | 66.7% | 100.0% |
| LH-02 | 15.6 | 0.0% | 100.0% |
| RE-01 | 140.6 | 77.8% | 100.0% |
| RE-02 | 687.5 | 4.5% | 4.5% |
| RH-01 | 109.4 | 57.1% | 85.7% |
| RH-02 | 109.4 | 71.4% | 85.7% |
| SH-01 | 1625.0 | 6.7% | 8.7% |
| SH-02 | 3250.0 | 2.4% | 2.4% |

### Per-task LLM I/O wait vs host CPU

Each row is one session. **LLM I/O wait** = HTTP_CLIENT wall (blocked on OpenAI). **Host CPU** = session process_time. I/O % and CPU % both divide by session wall; they are different axes (wait vs compute), not additive category wall fractions.

| Task | Session wall s | LLM I/O wait s | Non-LLM wall s | Host CPU ms | I/O % of wall | CPU % of wall | Tool CPU ms | Harness CPU ms | Tools |
|---|---|---|---|---|---|---|---|---|---|
| CH-01 | 9.35 | 9.31 | 0.04 | 31.2 | 99.6% | 0.33% | 0.0 | 31.2 | calculator×1, code_exec×1 |
| CH-02 | 11.06 | 10.93 | 0.13 | 203.1 | 98.8% | 1.84% | 31.2 | 171.9 | calculator×1, retrieve×2 |
| LH-01 | 6.31 | 6.29 | 0.03 | 46.9 | 99.6% | 0.74% | 0.0 | 46.9 | retrieve×1 |
| LH-02 | 6.84 | 6.83 | 0.01 | 15.6 | 99.8% | 0.23% | 0.0 | 15.6 | none |
| RE-01 | 15.66 | 15.53 | 0.13 | 125.0 | 99.1% | 0.80% | 0.0 | 140.6 | calculator×2, code_exec×2 |
| RE-02 | 7.64 | 6.92 | 0.72 | 687.5 | 90.6% | 9.00% | 656.2 | 31.2 | search×1 |
| RH-01 | 22.10 | 22.03 | 0.07 | 109.4 | 99.7% | 0.49% | 15.6 | 93.8 | retrieve×5 |
| RH-02 | 29.09 | 29.03 | 0.06 | 109.4 | 99.8% | 0.38% | 15.6 | 93.8 | retrieve×3 |
| SH-01 | 22.12 | 20.50 | 1.62 | 1625.0 | 92.7% | 7.35% | 1453.1 | 171.9 | search×3 |
| SH-02 | 14.85 | 11.43 | 3.42 | 3250.0 | 77.0% | 21.88% | 3171.9 | 78.1 | search×4 |
| **Total** | 145.03 | 138.80 | 6.23 | 6203.1 | 95.7% | 4.28% | | | |

#### Per-task CPU category breakdown

**CH-01** — 31.2 ms host CPU, 9.35 s session wall — tools: calculator×1, code_exec×1

| Category | CPU ms | Share of task CPU |
|---|---|---|
| TOKENIZATION | 31.2 | 100.0% |

**CH-02** — 203.1 ms host CPU, 11.06 s session wall — tools: calculator×1, retrieve×2

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 171.9 | 84.6% |
| TOOL_COMPUTE | 31.2 | 15.4% |

**LH-01** — 46.9 ms host CPU, 6.31 s session wall — tools: retrieve×1

| Category | CPU ms | Share of task CPU |
|---|---|---|
| TOKENIZATION | 31.2 | 66.7% |
| HTTP_CLIENT | 15.6 | 33.3% |

**LH-02** — 15.6 ms host CPU, 6.84 s session wall — tools: none

| Category | CPU ms | Share of task CPU |
|---|---|---|
| HTTP_CLIENT | 15.6 | 100.0% |

**RE-01** — 125.0 ms host CPU, 15.66 s session wall — tools: calculator×2, code_exec×2

| Category | CPU ms | Share of task CPU |
|---|---|---|
| TOKENIZATION | 78.1 | 55.6% |
| HTTP_CLIENT | 31.2 | 22.2% |
| ORCH_SETUP | 15.6 | 11.1% |
| ORCH_DISPATCH | 15.6 | 11.1% |

**RE-02** — 687.5 ms host CPU, 7.64 s session wall — tools: search×1

| Category | CPU ms | Share of task CPU |
|---|---|---|
| TOOL_COMPUTE | 656.2 | 95.5% |
| ORCH_SETUP | 15.6 | 2.3% |
| ORCH_DISPATCH | 15.6 | 2.3% |

**RH-01** — 109.4 ms host CPU, 22.10 s session wall — tools: retrieve×5

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 46.9 | 42.9% |
| HTTP_CLIENT | 31.2 | 28.6% |
| TOKENIZATION | 15.6 | 14.3% |
| TOOL_COMPUTE | 15.6 | 14.3% |

**RH-02** — 109.4 ms host CPU, 29.09 s session wall — tools: retrieve×3

| Category | CPU ms | Share of task CPU |
|---|---|---|
| TOKENIZATION | 31.2 | 28.6% |
| ORCH_DISPATCH | 31.2 | 28.6% |
| ORCH_SETUP | 15.6 | 14.3% |
| HTTP_CLIENT | 15.6 | 14.3% |
| TOOL_COMPUTE | 15.6 | 14.3% |

**SH-01** — 1625.0 ms host CPU, 22.12 s session wall — tools: search×3

| Category | CPU ms | Share of task CPU |
|---|---|---|
| TOOL_COMPUTE | 1453.1 | 89.4% |
| ORCH_DISPATCH | 62.5 | 3.8% |
| TOKENIZATION | 46.9 | 2.9% |
| GC | 31.2 | 1.9% |
| HTTP_CLIENT | 31.2 | 1.9% |

**SH-02** — 3250.0 ms host CPU, 14.85 s session wall — tools: search×4

| Category | CPU ms | Share of task CPU |
|---|---|---|
| TOOL_COMPUTE | 3171.9 | 97.6% |
| ORCH_DISPATCH | 46.9 | 1.4% |
| TOKENIZATION | 31.2 | 1.0% |


### Pooled vs equal-weight (different questions)

*Denominators: n=1 seed(s)=[0], search=local, batch host CPU=6203 ms, batch wall=148.9 s, CPU% of wall≈4.28%, c=1. Comparison type: single-run sample unless replication_batch artifact.*

| Metric | Pooled (headline table) | Equal-weight task average |
|---|---|---|
| TOOL_COMPUTE CPU share | 86.1% of batch CPU | 32.6% |
| Answers | What consumed this batch's total host capacity | What a typical task of each type costs (one session per task here) |

Use **pooled** for capacity planning (dominated by heavy outlier sessions). Use **equal-weight per-archetype** rows below for archetype characterization. Do not treat the overall equal-weight amenability mean as a representative headline — it averages a bimodal distribution.

### Archetype amenability (primary equal-weight table)

| Archetype | Tasks | Mean CPU ms | Strict amenable | Broad amenable |
|---|---|---|---|---|
| CH (code_heavy) | CH-01, CH-02 | 117.2 | 92.3% | 92.3% |
| LH (long_horizon) | LH-01, LH-02 | 31.2 | 33.3% ‡ | 100.0% ‡ |
| RE (reasoning_heavy) | RE-01, RE-02 | 414.1 | 41.2% | 52.3% |
| RH (rag_heavy) | RH-01, RH-02 | 109.4 | 64.3% ‡ | 85.7% ‡ |
| SH (search_heavy) | SH-01, SH-02 | 2437.5 | 4.6% | 5.5% |

‡ **Small-base caution:** strict/broad percentages are of mean instrumented CPU near the Windows thread-time tick floor (~15 ms). High amenability % on RH/LH reflects sessions that barely ran local work, not hardware-friendly archetypes. Do not quote without absolute CPU ms; prefer Linux re-run for tick resolution.

**CH blend:** the CH archetype row averages tasks that can land in opposite behavior clusters — report CH-01 and CH-02 individually alongside the CH row (see per-task sections).

### Behavioral buckets (realized workload, not task labels)

Buckets are assigned from realized tool calls and turn count, not from task archetype labels. Task-label tables are prompt-intent only.

CPU floor for detailed per-task amenability: 200.0 ms

| Bucket | Label | Tasks | Mean host CPU ms | Mean strict amenable |
|---|---|---|---|---|
| B0_io_only | no tool calls (LLM-only) | LH-02 | 15.6 | 0.0% |
| B1_search_only | search only (no local code/retrieve) | SH-01, SH-02, RE-02 | 1854.2 | 4.6% |
| B3_retrieve_heavy | retrieve-heavy (≥5 calls) | RH-01 | 109.4 | 57.1% |
| B3_retrieve_light | retrieve-light (<5 calls) | CH-02, RH-02, LH-01 | 119.8 | 74.2% |
| B4_code_light | code_exec light (<5 calls) | CH-01, RE-01 | 78.1 | 88.9% |

Task archetype labels (SH, RH, …) are prompt-intent only; use behavioral buckets for workload-ground-truth grouping.

### Accounting audit

- pass: **NO**
- publishable_ok: **NO**
- platform: `win32`
- Windows tick: 15.625 ms (footnote-only below 200 ms/session)
- **VIOLATION:** RE-01: instrumented 140.6 ms > process CPU 125.0 ms — thread_time timers vs process_time host basis; diagnose before quoting shares
- warning: Host CPU values appear quantized to 15.625 ms Windows thread-time ticks; per-task shares below ~200 ms/session are not quotable. Re-run on Linux with test_resolution PASS before publishing.
- warning: CH-01: host CPU 31.2 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: CH-02: reconcile gap 156.2 ms is 77% of process CPU — check attribution
- warning: RH-01: host CPU 109.4 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: RH-02: host CPU 109.4 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: RE-01: host CPU 125.0 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: LH-01: host CPU 46.9 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: LH-02: host CPU 15.6 ms below Windows quotable floor (200 ms); per-task shares not publishable
- warning: Single-seed run (n=1); replication requires n≥5 seeds with medians and IQR before headline numbers are quotable

### Wall-time attribution integrity

CPU category shares partition instrumented CPU (exclusive nesting; invariant PASS). **Wall fractions are not a partition metric** in real-agent mode: TOOL_COMPUTE/GC timers run on LangGraph tool-pool threads while the stream thread's session clock is also advancing, so summing all category wall fractions can exceed 100%. ORCH stream steps now use perf_counter gaps minus tagged wall (not thread CPU).

† TOOL_COMPUTE/GC: report mean wall ms; wall/session is marked concurrent (same clock period as session wait, not additive).

| Task | Session wall s | All-category coverage | Partition coverage |
|---|---|---|---|
| CH-01 | 9.35 | 100.0% | 99.9% |
| CH-02 | 11.06 | 102.4% | 100.9% |
| LH-01 | 6.31 | 100.0% | 99.7% |
| LH-02 | 6.84 | 100.0% | 99.8% |
| RE-01 | 15.66 | 100.1% | 99.8% |
| RE-02 | 7.64 | 100.2% | 91.0% |
| RH-01 | 22.10 | 100.3% | 100.1% |
| RH-02 | 29.09 | 100.2% | 100.0% |
| SH-01 | 22.12 | 103.7% | 96.5% |
| SH-02 | 14.85 | 116.8% | 93.9% |

### Equal-weight category breakdown by archetype

Mean CPU share partitions instrumented CPU (~100% per task). Wall/session excludes concurrent tool-pool categories (†).

#### CH (code_heavy)

- tasks (2): CH-01, CH-02
- mean session wall: 10.21 s
- mean instrumented CPU: 117.2 ms
- mean amenable strict: 92.3%
- mean amenable broad: 92.3%
- partition wall fractions sum: 100.4% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)
- **Caveat:** CH-01 and CH-02 landed in opposite behavior clusters; see individual task sections below.

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 85.9 | 42.3% | 113.2 | 1.0% |
| TOKENIZATION | direct | 15.6 | 50.0% | 20.7 | 0.2% |
| TOOL_COMPUTE | none | 15.6 | 7.7% | 80.8 | concurrent† |
| GC | none | 0.0 | 0.0% | 0.0 | concurrent† |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 10121.1 | 99.2% |
| ORCH_SETUP | direct | 0.0 | 0.0% | 7.4 | n/a |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.4 | 0.0% |

#### LH (long_horizon)

- tasks (2): LH-01, LH-02
- mean session wall: 6.58 s
- mean instrumented CPU: 31.2 ms
- mean amenable strict: 33.3%
- mean amenable broad: 100.0%
- partition wall fractions sum: 99.8% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| HTTP_CLIENT | overlap | 15.6 | 66.7% | 6559.9 | 99.7% |
| TOKENIZATION | direct | 15.6 | 33.3% | 4.0 | 0.1% |
| GC | none | 0.0 | 0.0% | 0.0 | concurrent† |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 2.0 | 0.0% |
| ORCH_SETUP | direct | 0.0 | 0.0% | 8.7 | n/a |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.1 | 0.0% |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 3.2 | concurrent† |

#### RE (reasoning_heavy)

- tasks (2): RE-01, RE-02
- mean session wall: 11.65 s
- mean instrumented CPU: 414.1 ms
- mean amenable strict: 41.2%
- mean amenable broad: 52.3%
- partition wall fractions sum: 95.4% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 328.1 | 47.7% | 363.8 | concurrent† |
| TOKENIZATION | direct | 39.1 | 27.8% | 45.5 | 0.3% |
| HTTP_CLIENT | overlap | 15.6 | 11.1% | 11224.5 | 94.9% |
| ORCH_DISPATCH | direct | 15.6 | 6.7% | 21.1 | 0.2% |
| ORCH_SETUP | direct | 15.6 | 6.7% | 11.0 | n/a |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.9 | 0.0% |

#### RH (rag_heavy)

- tasks (2): RH-01, RH-02
- mean session wall: 25.59 s
- mean instrumented CPU: 109.4 ms
- mean amenable strict: 64.3%
- mean amenable broad: 85.7%
- partition wall fractions sum: 100.1% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 39.1 | 35.7% | 45.4 | 0.2% |
| HTTP_CLIENT | overlap | 23.4 | 21.4% | 25528.9 | 99.7% |
| TOKENIZATION | direct | 23.4 | 21.4% | 39.5 | 0.2% |
| TOOL_COMPUTE | none | 15.6 | 14.3% | 22.8 | concurrent† |
| ORCH_SETUP | direct | 7.8 | 7.1% | 8.8 | n/a |
| GC | none | 0.0 | 0.0% | 0.0 | concurrent† |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.8 | 0.0% |

#### SH (search_heavy)

- tasks (2): SH-01, SH-02
- mean session wall: 18.49 s
- mean instrumented CPU: 2437.5 ms
- mean amenable strict: 4.6%
- mean amenable broad: 5.5%
- partition wall fractions sum: 95.2% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 2312.5 | 93.5% | 2462.2 | concurrent† |
| ORCH_DISPATCH | direct | 54.7 | 2.6% | 383.1 | 2.5% |
| TOKENIZATION | direct | 39.1 | 1.9% | 1302.0 | 7.9% |
| GC | none | 15.6 | 1.0% | 15.6 | concurrent† |
| HTTP_CLIENT | overlap | 15.6 | 1.0% | 15966.8 | 84.8% |
| ORCH_SETUP | direct | 0.0 | 0.0% | 13.4 | n/a |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.5 | 0.0% |

### CH-01

- sessions: agent_2
- tool invocations: calculator×1, code_exec×1
- instrumented CPU: 31.2 ms
- hardware amenable: strict 100.0% (31.2 ms), broad 100.0% (31.2 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOKENIZATION | direct | 31.2 | 100.0% | 23.0 | 6 | 214740 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 9.3 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 107455 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.3 | 6 | 570 | 214137 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 9312.3 | 2 | 570 | 0 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 1.3 | 2 | 100 | 0 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 7.1 | 5 | 0 | 0 |

### CH-02

- sessions: agent_3
- tool invocations: calculator×1, retrieve×2
- instrumented CPU: 203.1 ms
- hardware amenable: strict 84.6% (171.9 ms), broad 84.6% (171.9 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 171.9 | 84.6% | 219.2 | 8 | 0 | 0 |
| TOOL_COMPUTE | none | 31.2 | 15.4% | 160.3 | 3 | 49 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 5.4 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 101346 |
| TOKENIZATION | direct | 0.0 | 0.0% | 18.5 | 7 | 202856 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.4 | 7 | 822 | 201989 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 10930.0 | 2 | 822 | 0 |
| GC | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |

### LH-01

- sessions: agent_8
- tool invocations: retrieve×1
- instrumented CPU: 46.9 ms
- hardware amenable: strict 66.7% (31.2 ms), broad 100.0% (46.9 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOKENIZATION | direct | 31.2 | 66.7% | 7.2 | 5 | 50284 | 0 |
| HTTP_CLIENT | overlap | 15.6 | 33.3% | 6287.2 | 2 | 1689 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 7.0 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 24571 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 5 | 1689 | 48577 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 6.3 | 1 | 34 | 0 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 4.0 | 3 | 0 | 0 |

### LH-02

- sessions: agent_9
- tool invocations: none
- instrumented CPU: 15.6 ms
- hardware amenable: strict 0.0% (0.0 ms), broad 100.0% (15.6 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| HTTP_CLIENT | overlap | 15.6 | 100.0% | 6832.6 | 1 | 1732 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 10.3 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 1 | 0 | 214 |
| TOKENIZATION | direct | 0.0 | 0.0% | 0.8 | 2 | 1946 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.1 | 2 | 1732 | 214 |
| GC | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |

### RE-01

- sessions: agent_6
- tool invocations: calculator×2, code_exec×2
- instrumented CPU: 140.6 ms
- hardware amenable: strict 77.8% (109.4 ms), broad 100.0% (140.6 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOKENIZATION | direct | 78.1 | 55.6% | 84.5 | 12 | 530911 | 0 |
| HTTP_CLIENT | overlap | 31.2 | 22.2% | 15526.7 | 4 | 1445 | 0 |
| ORCH_SETUP | direct | 15.6 | 11.1% | 14.0 | 2 | 0 | 0 |
| ORCH_DISPATCH | direct | 15.6 | 11.1% | 22.6 | 11 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 4 | 0 | 354513 |
| SERIALIZATION | direct | 0.0 | 0.0% | 1.5 | 12 | 1445 | 529405 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 31.6 | 4 | 187 | 0 |

### RE-02

- sessions: agent_7
- tool invocations: search×1
- instrumented CPU: 687.5 ms
- hardware amenable: strict 4.5% (31.2 ms), broad 4.5% (31.2 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 656.2 | 95.5% | 696.1 | 1 | 38 | 0 |
| ORCH_SETUP | direct | 15.6 | 2.3% | 7.9 | 2 | 0 | 0 |
| ORCH_DISPATCH | direct | 15.6 | 2.3% | 19.7 | 4 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 34282 |
| TOKENIZATION | direct | 0.0 | 0.0% | 6.4 | 5 | 69929 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 5 | 1780 | 68134 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 6922.2 | 2 | 1780 | 0 |

### RH-01

- sessions: agent_4
- tool invocations: retrieve×5
- instrumented CPU: 109.4 ms
- hardware amenable: strict 57.1% (62.5 ms), broad 85.7% (93.8 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 46.9 | 42.9% | 47.3 | 12 | 0 | 0 |
| HTTP_CLIENT | overlap | 31.2 | 28.6% | 22028.9 | 2 | 1972 | 0 |
| TOKENIZATION | direct | 15.6 | 14.3% | 48.7 | 9 | 539058 | 0 |
| TOOL_COMPUTE | none | 15.6 | 14.3% | 22.1 | 5 | 59 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 9.8 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 268986 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.8 | 9 | 1972 | 537008 |

### RH-02

- sessions: agent_5
- tool invocations: retrieve×3
- instrumented CPU: 109.4 ms
- hardware amenable: strict 71.4% (78.1 ms), broad 85.7% (93.8 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOKENIZATION | direct | 31.2 | 28.6% | 30.4 | 7 | 243208 | 0 |
| ORCH_DISPATCH | direct | 31.2 | 28.6% | 43.5 | 8 | 0 | 0 |
| ORCH_SETUP | direct | 15.6 | 14.3% | 7.9 | 2 | 0 | 0 |
| HTTP_CLIENT | overlap | 15.6 | 14.3% | 29028.9 | 2 | 2922 | 0 |
| TOOL_COMPUTE | none | 15.6 | 14.3% | 23.5 | 3 | 55 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 120452 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.7 | 7 | 2922 | 240240 |
| GC | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |

### SH-01

- sessions: agent_0
- tool invocations: search×3
- instrumented CPU: 1625.0 ms
- hardware amenable: strict 6.7% (109.4 ms), broad 8.7% (140.6 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 1453.1 | 89.4% | 1533.9 | 3 | 29 | 0 |
| ORCH_DISPATCH | direct | 62.5 | 3.8% | 56.6 | 8 | 0 | 0 |
| TOKENIZATION | direct | 46.9 | 2.9% | 794.6 | 7 | 311379 | 0 |
| GC | none | 31.2 | 1.9% | 31.2 | 77 | 0 | 0 |
| HTTP_CLIENT | overlap | 31.2 | 1.9% | 20503.7 | 2 | 1985 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 21.0 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 155011 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.5 | 7 | 1985 | 309349 |

### SH-02

- sessions: agent_1
- tool invocations: search×4
- instrumented CPU: 3250.0 ms
- hardware amenable: strict 2.4% (78.1 ms), broad 2.4% (78.1 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 3171.9 | 97.6% | 3390.4 | 4 | 33 | 0 |
| ORCH_DISPATCH | direct | 46.9 | 1.4% | 709.6 | 10 | 0 | 0 |
| TOKENIZATION | direct | 31.2 | 1.0% | 1809.4 | 8 | 200224 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 5.9 | 2 | 0 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 99534 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.4 | 8 | 1894 | 198262 |
| HTTP_CLIENT | overlap | 0.0 | 0.0% | 11429.9 | 2 | 1894 | 0 |
| GC | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |

## Process user/system split

- user: 6.641 s, system: 1.484 s
- per-category kernel-time attribution is approximate; category timers are user-space, syscall-heavy regions surface partly as system time

## Per-session summary

| Session | Task | Turns | Tool calls | Graph nodes | Dispatches | Wall s | Thread CPU ms |
|---|---|---|---|---|---|---|---|
| agent_0 | SH-01 | 5 | search:3 | n/a | n/a | 22.12 | 1625.00 |
| agent_1 | SH-02 | 6 | search:4 | n/a | n/a | 14.85 | 3250.00 |
| agent_2 | CH-01 | 4 | calculator:1, code_exec:1 | n/a | n/a | 9.35 | 31.25 |
| agent_3 | CH-02 | 5 | calculator:1, retrieve:2 | n/a | n/a | 11.06 | 203.12 |
| agent_4 | RH-01 | 7 | retrieve:5 | n/a | n/a | 22.10 | 109.38 |
| agent_5 | RH-02 | 5 | retrieve:3 | n/a | n/a | 29.09 | 109.38 |
| agent_6 | RE-01 | 8 | calculator:2, code_exec:2 | n/a | n/a | 15.66 | 125.00 |
| agent_7 | RE-02 | 3 | search:1 | n/a | n/a | 7.64 | 687.50 |
| agent_8 | LH-01 | 3 | retrieve:1 | n/a | n/a | 6.31 | 46.88 |
| agent_9 | LH-02 | 1 | none | n/a | n/a | 6.84 | 15.62 |

## Tool usage (all sessions including sub-agents)

| Tool | Calls | Result bytes |
|---|---|---|
| calculator | 4 | 0 |
| code_exec | 3 | 0 |
| retrieve | 11 | 0 |
| search | 8 | 0 |

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
python -m apu_characterization.experiments.real_agent_breakdown --backend openai --profile mixed --seed 0 --sessions 10 --llm-scale 0.05 --search-locality local
```
