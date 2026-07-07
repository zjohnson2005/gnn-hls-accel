# Experiment 0: single-agent CPU-time breakdown

> **DEBUG ONLY — NOT VALID EXPERIMENTAL DATA.** This artifact used a mock or scripted decision path (no live OpenAI agent). Use only to verify instrumentation and invariants. Do not cite in papers, slides, or findings. Publishable results require `real_agent_breakdown --backend openai`.

Generated: 2026-07-07T16:39:15.072740+00:00 from `single_agent_breakdown_debug.json`.
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

- profile: `mixed`, seed: 0, sessions: 10, execution: asyncio
- total CPU basis: worker thread_time_ns sum
- mock LLM latency scale: 0.05 (mock LLM latency is asyncio sleep (I/O wait, zero thread CPU); scaling it changes wall time only, never CPU shares)
- clocks: wall = perf_counter_ns; CPU = thread_time_ns per region; real-agent total CPU = process_time (all threads, including LangGraph tool executors)
- nesting: exclusive self-time accounting; an inner region pauses its parent
- timer overhead: 4141 ns per enter/exit pair
- batch wall time: 5.83 s

### What each category wraps in this harness

- `ORCH_SETUP`: OrchEngine.setup_session: task-graph node/edge construction per session
- `ORCH_DISPATCH`: OrchEngine.dispatch_ready + complete_node: readiness scan, scatter, handoff
- `SERIALIZATION`: json.dumps/loads of LLM responses and tool results, response parse
- `TOKENIZATION`: token counting of the full assembled prompt each turn plus the response body (tiktoken or len/4 fallback); models client-side context-window bookkeeping, so it scales with conversation length per turn
- `PROMPT_ASSEMBLY`: message-list build + prompt text construction each turn
- `CONTEXT_MGMT`: deepcopy of session state, history append, artifact tracking
- `HTTP_CLIENT`: mock API envelopes: request build + response parse around the I/O-wait sleep (AH tasks); real HTTP session handling in live mode
- `TOOL_COMPUTE`: tool bodies: regex corpus scan, exec'd snippet, numpy cosine top-k, sympy eval
- `LOGGING`: logger formatting calls in the agent loop
- `GC`: collector cycles via gc.callbacks (lower bound, excludes refcount frees)
- `RESIDUAL`: computed: total thread CPU minus sum of instrumented categories

## Accounting invariant

sum(category thread-CPU) + residual = total thread-CPU of the run:

- total thread CPU: 3250.00 ms
- instrumented: 2843.75 ms
- residual: 406.25 ms (12.5% of total)
- limit: 15%  ->  PASS

## Breakdown (thread CPU, exclusive per category — pooled across all sessions)

| Category | CPU ms | Share of total | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|
| TOKENIZATION | 1406.250 | 43.3% | 1882.213 | 160 | 16253836 | 0 |
| TOOL_COMPUTE | 1375.000 | 42.3% | 1914.276 | 62 | 2234 | 0 |
| PROMPT_ASSEMBLY | 62.500 | 1.9% | 46.934 | 160 | 0 | 16075436 |
| GC | 0.000 | 0.0% | 0.000 | 4 | 0 | 0 |
| ORCH_SETUP | 0.000 | 0.0% | 0.252 | 10 | 0 | 0 |
| CONTEXT_MGMT | 0.000 | 0.0% | 9.040 | 222 | 19256973 | 0 |
| ORCH_DISPATCH | 0.000 | 0.0% | 2.365 | 284 | 0 | 0 |
| SERIALIZATION | 0.000 | 0.0% | 17.325 | 222 | 170386 | 3327307 |
| LOGGING | 0.000 | 0.0% | 2.072 | 80 | 0 | 0 |
| RESIDUAL | 406.250 | 12.5% | n/a | n/a | n/a | n/a |

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
| CH-01 | 46.9 | 100.0% | 100.0% |
| CH-02 | 171.9 | 36.4% | 36.4% |
| LH-01 | 515.6 | 90.9% | 93.9% |
| LH-02 | 140.6 | 88.9% | 100.0% |
| RE-01 | 15.6 | 0.0% | 0.0% |
| RE-02 | 281.2 | 0.0% | 0.0% |
| RH-01 | 312.5 | 25.0% | 25.0% |
| RH-02 | 187.5 | 91.7% | 91.7% |
| SH-01 | 781.2 | 28.0% | 32.0% |
| SH-02 | 390.6 | 60.0% | 60.0% |

### Pooled vs equal-weight (different questions)

| Metric | Pooled (headline table) | Equal-weight task average |
|---|---|---|
| TOOL_COMPUTE CPU share | 42.3% of batch CPU | 46.1% |
| Answers | What consumed this batch's total host capacity | What a typical task of each type costs (one session per task here) |

Use **pooled** for capacity planning (dominated by heavy outlier sessions). Use **equal-weight per-archetype** rows below for archetype characterization. Do not treat the overall equal-weight amenability mean as a representative headline — it averages a bimodal distribution.

### Archetype amenability (primary equal-weight table)

| Archetype | Tasks | Mean CPU ms | Strict amenable | Broad amenable |
|---|---|---|---|---|
| CH (code_heavy) | CH-01, CH-02 | 109.4 | 68.2% | 68.2% |
| LH (long_horizon) | LH-01, LH-02 | 328.1 | 89.9% ‡ | 97.0% ‡ |
| RE (reasoning_heavy) | RE-01, RE-02 | 148.4 | 0.0% | 0.0% |
| RH (rag_heavy) | RH-01, RH-02 | 250.0 | 58.3% ‡ | 58.3% ‡ |
| SH (search_heavy) | SH-01, SH-02 | 585.9 | 44.0% | 46.0% |

‡ **Small-base caution:** strict/broad percentages are of mean instrumented CPU near the Windows thread-time tick floor (~15 ms). High amenability % on RH/LH reflects sessions that barely ran local work, not hardware-friendly archetypes. Do not quote without absolute CPU ms; prefer Linux re-run for tick resolution.

**CH blend:** the CH archetype row averages tasks that can land in opposite behavior clusters — report CH-01 and CH-02 individually alongside the CH row (see per-task sections).

### Equal-weight category breakdown by archetype

Mean CPU share partitions instrumented CPU (~100% per task). Wall/session excludes concurrent tool-pool categories (†).

#### CH (code_heavy)

- tasks (2): CH-01, CH-02
- mean session wall: 2.42 s
- mean instrumented CPU: 109.4 ms
- mean amenable strict: 68.2%
- mean amenable broad: 68.2%
- partition wall fractions sum: 3.2% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)
- **Caveat:** CH-01 and CH-02 landed in opposite behavior clusters; see individual task sections below.

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| TOKENIZATION | direct | 54.7 | 68.2% | 74.8 | 3.1% |
| TOOL_COMPUTE | none | 54.7 | 31.8% | 106.2 | concurrent† |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 0.3 | 0.0% |
| LOGGING | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.2 | 0.0% |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | n/a |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 1.3 | 0.1% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.9 | 0.0% |

#### LH (long_horizon)

- tasks (2): LH-01, LH-02
- mean session wall: 4.32 s
- mean instrumented CPU: 328.1 ms
- mean amenable strict: 89.9%
- mean amenable broad: 97.0%
- partition wall fractions sum: 9.4% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| TOKENIZATION | direct | 296.9 | 89.9% | 398.9 | 9.1% |
| PROMPT_ASSEMBLY | partial | 15.6 | 7.1% | 10.2 | 0.2% |
| TOOL_COMPUTE | none | 15.6 | 3.0% | 53.2 | concurrent† |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 0.8 | 0.0% |
| LOGGING | partial | 0.0 | 0.0% | 0.1 | 0.0% |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.4 | 0.0% |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | n/a |
| SERIALIZATION | direct | 0.0 | 0.0% | 3.0 | 0.1% |

#### RE (reasoning_heavy)

- tasks (2): RE-01, RE-02
- mean session wall: 1.33 s
- mean instrumented CPU: 148.4 ms
- mean amenable strict: 0.0%
- mean amenable broad: 0.0%
- partition wall fractions sum: 0.8% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 148.4 | 100.0% | 162.0 | concurrent† |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 0.1 | 0.0% |
| LOGGING | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.1 | 0.0% |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | n/a |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.2 | 0.0% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 0.0% |
| TOKENIZATION | direct | 0.0 | 0.0% | 9.2 | 0.7% |

#### RH (rag_heavy)

- tasks (2): RH-01, RH-02
- mean session wall: 3.11 s
- mean instrumented CPU: 250.0 ms
- mean amenable strict: 58.3%
- mean amenable broad: 58.3%
- partition wall fractions sum: 4.6% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| TOKENIZATION | direct | 125.0 | 58.3% | 138.3 | 4.4% |
| TOOL_COMPUTE | none | 125.0 | 41.7% | 184.1 | concurrent† |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 0.4 | 0.0% |
| LOGGING | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.2 | 0.0% |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | n/a |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 4.0 | 0.1% |
| SERIALIZATION | direct | 0.0 | 0.0% | 1.2 | 0.0% |

#### SH (search_heavy)

- tasks (2): SH-01, SH-02
- mean session wall: 4.26 s
- mean instrumented CPU: 585.9 ms
- mean amenable strict: 44.0%
- mean amenable broad: 46.0%
- partition wall fractions sum: 7.9% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 343.8 | 54.0% | 451.6 | concurrent† |
| TOKENIZATION | direct | 226.6 | 44.0% | 319.8 | 7.5% |
| PROMPT_ASSEMBLY | partial | 15.6 | 2.0% | 7.6 | 0.2% |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 2.9 | 0.1% |
| LOGGING | partial | 0.0 | 0.0% | 0.9 | 0.0% |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.3 | 0.0% |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | n/a |
| SERIALIZATION | direct | 0.0 | 0.0% | 3.3 | 0.1% |

### CH-01

- sessions: agent_2
- instrumented CPU: 46.9 ms
- hardware amenable: strict 100.0% (46.9 ms), broad 100.0% (46.9 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOKENIZATION | direct | 46.9 | 100.0% | 64.5 | 10 | 568512 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 0.2 | 14 | 800401 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 1.2 | 10 | 0 | 559737 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.2 | 18 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.9 | 14 | 8799 | 248273 |
| LOGGING | partial | 0.0 | 0.0% | 0.0 | 5 | 0 | 0 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 22.1 | 4 | 437 | 0 |

### CH-02

- sessions: agent_3
- instrumented CPU: 171.9 ms
- hardware amenable: strict 36.4% (62.5 ms), broad 36.4% (62.5 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 109.4 | 63.6% | 190.2 | 5 | 428 | 0 |
| TOKENIZATION | direct | 62.5 | 36.4% | 85.0 | 12 | 725866 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 0.4 | 17 | 964569 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 1.4 | 12 | 0 | 714414 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.2 | 22 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.9 | 17 | 11400 | 260005 |
| LOGGING | partial | 0.0 | 0.0% | 0.0 | 6 | 0 | 0 |

### LH-01

- sessions: agent_8
- instrumented CPU: 515.6 ms
- hardware amenable: strict 90.9% (468.8 ms), broad 93.9% (484.4 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOKENIZATION | direct | 468.8 | 90.9% | 584.4 | 26 | 4964190 | 0 |
| TOOL_COMPUTE | none | 31.2 | 6.1% | 76.2 | 12 | 443 | 0 |
| PROMPT_ASSEMBLY | partial | 15.6 | 3.0% | 15.2 | 26 | 0 | 4936459 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 1.0 | 38 | 5650357 | 0 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.4 | 50 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 4.8 | 38 | 24156 | 732774 |
| LOGGING | partial | 0.0 | 0.0% | 0.1 | 13 | 0 | 0 |

### LH-02

- sessions: agent_9
- instrumented CPU: 140.6 ms
- hardware amenable: strict 88.9% (125.0 ms), broad 100.0% (140.6 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOKENIZATION | direct | 125.0 | 88.9% | 213.4 | 24 | 1978221 | 0 |
| PROMPT_ASSEMBLY | partial | 15.6 | 11.1% | 5.3 | 24 | 0 | 1948576 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 0.6 | 31 | 2254603 | 0 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.3 | 38 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 1.3 | 31 | 28389 | 330717 |
| LOGGING | partial | 0.0 | 0.0% | 0.1 | 12 | 0 | 0 |
| TOOL_COMPUTE | none | 0.0 | 0.0% | 30.1 | 7 | 151 | 0 |

### RE-01

- sessions: agent_6
- instrumented CPU: 15.6 ms
- hardware amenable: strict 0.0% (0.0 ms), broad 0.0% (0.0 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 15.6 | 100.0% | 0.9 | 1 | 15 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 0.1 | 9 | 49007 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.3 | 8 | 0 | 26399 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.1 | 10 | 0 | 0 |
| TOKENIZATION | direct | 0.0 | 0.0% | 5.6 | 8 | 33655 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.2 | 9 | 7419 | 29402 |
| LOGGING | partial | 0.0 | 0.0% | 0.0 | 4 | 0 | 0 |

### RE-02

- sessions: agent_7
- instrumented CPU: 281.2 ms
- hardware amenable: strict 0.0% (0.0 ms), broad 0.0% (0.0 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 281.2 | 100.0% | 323.1 | 1 | 21 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 0.1 | 9 | 82954 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.1 | 8 | 0 | 56338 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.1 | 10 | 0 | 0 |
| TOKENIZATION | direct | 0.0 | 0.0% | 12.9 | 8 | 66640 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.3 | 9 | 10438 | 36387 |
| LOGGING | partial | 0.0 | 0.0% | 0.0 | 4 | 0 | 0 |

### RH-01

- sessions: agent_4
- instrumented CPU: 312.5 ms
- hardware amenable: strict 25.0% (78.1 ms), broad 25.0% (78.1 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 234.4 | 75.0% | 329.1 | 6 | 183 | 0 |
| TOKENIZATION | direct | 78.1 | 25.0% | 108.2 | 14 | 903953 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 0.4 | 20 | 1193789 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 2.1 | 14 | 0 | 888015 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.2 | 26 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 1.1 | 20 | 15175 | 318998 |
| LOGGING | partial | 0.0 | 0.0% | 0.0 | 7 | 0 | 0 |

### RH-02

- sessions: agent_5
- instrumented CPU: 187.5 ms
- hardware amenable: strict 91.7% (171.9 ms), broad 91.7% (171.9 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOKENIZATION | direct | 171.9 | 91.7% | 168.5 | 16 | 1496513 | 0 |
| TOOL_COMPUTE | none | 15.6 | 8.3% | 39.1 | 7 | 271 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 0.4 | 23 | 1802812 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 6.0 | 16 | 0 | 1478897 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.2 | 30 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 1.4 | 23 | 16624 | 338113 |
| LOGGING | partial | 0.0 | 0.0% | 0.0 | 8 | 0 | 0 |

### SH-01

- sessions: agent_0
- instrumented CPU: 781.2 ms
- hardware amenable: strict 28.0% (218.8 ms), broad 32.0% (250.0 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 531.2 | 68.0% | 753.7 | 9 | 126 | 0 |
| TOKENIZATION | direct | 218.8 | 28.0% | 312.4 | 20 | 2602780 | 0 |
| PROMPT_ASSEMBLY | partial | 31.2 | 4.0% | 7.3 | 20 | 0 | 2574135 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.1 | 1 | 0 | 0 |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 2.8 | 29 | 3113196 | 0 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.3 | 38 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 4.7 | 29 | 27977 | 563704 |
| LOGGING | partial | 0.0 | 0.0% | 1.7 | 10 | 0 | 0 |

### SH-02

- sessions: agent_1
- instrumented CPU: 390.6 ms
- hardware amenable: strict 60.0% (234.4 ms), broad 60.0% (234.4 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOKENIZATION | direct | 234.4 | 60.0% | 327.3 | 22 | 2913506 | 0 |
| TOOL_COMPUTE | none | 156.2 | 40.0% | 149.6 | 10 | 159 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |
| CONTEXT_MGMT | partial | 0.0 | 0.0% | 3.0 | 32 | 3345285 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 8.0 | 22 | 0 | 2892466 |
| ORCH_DISPATCH | direct | 0.0 | 0.0% | 0.4 | 42 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 1.9 | 32 | 20009 | 468934 |
| LOGGING | partial | 0.0 | 0.0% | 0.1 | 11 | 0 | 0 |

## Process user/system split

- user: 3.156 s, system: 0.359 s
- per-category kernel-time attribution is approximate; category timers are user-space, syscall-heavy regions surface partly as system time

## Per-session summary

| Session | Task | Turns | Tool calls | Graph nodes | Dispatches | Wall s | Thread CPU ms |
|---|---|---|---|---|---|---|---|
| agent_0 | SH-01 | 10 | calculator:1, search:8 | 30 | 48 | 4.06 | 781.25 |
| agent_1 | SH-02 | 11 | retrieve:1, search:9 | 33 | 53 | 4.47 | 390.62 |
| agent_2 | CH-01 | 5 | calculator:1, code_exec:3 | 15 | 23 | 2.40 | 46.88 |
| agent_3 | CH-02 | 6 | calculator:1, code_exec:3, search:1 | 18 | 28 | 2.45 | 171.88 |
| agent_4 | RH-01 | 7 | retrieve:5, search:1 | 21 | 33 | 2.63 | 312.50 |
| agent_5 | RH-02 | 8 | calculator:1, retrieve:6 | 24 | 38 | 3.58 | 187.50 |
| agent_6 | RE-01 | 4 | calculator:1 | 8 | 12 | 1.44 | 15.62 |
| agent_7 | RE-02 | 4 | search:1 | 8 | 12 | 1.22 | 281.25 |
| agent_8 | LH-01 | 13 | retrieve:12 | 39 | 63 | 4.51 | 515.62 |
| agent_9 | LH-02 | 12 | calculator:3, retrieve:4 | 28 | 46 | 4.12 | 140.62 |

## Tool usage (all sessions including sub-agents)

| Tool | Calls | Result bytes |
|---|---|---|
| calculator | 8 | 303756 |
| code_exec | 6 | 329364 |
| retrieve | 28 | 1441680 |
| search | 20 | 1087415 |

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
python -m apu_characterization.experiments.single_agent_breakdown --profile mixed --seed 0 --sessions 10 --llm-scale 0.05
```
