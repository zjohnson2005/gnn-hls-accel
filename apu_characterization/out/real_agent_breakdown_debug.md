# Experiment 0R: real LangGraph agent CPU-time breakdown (scripted, local search (baseline))

> **DEBUG ONLY — NOT VALID EXPERIMENTAL DATA.** This artifact used a mock or scripted decision path (no live OpenAI agent). Use only to verify instrumentation and invariants. Do not cite in papers, slides, or findings.

Generated: 2026-07-07T20:18:19.224199+00:00 from `real_agent_breakdown_debug.json`.
All numbers below are read from that artifact.

## Setup

- setup record: digest `66f54ae8c07ef581`, task suite `a88a9e1058964219` (see EXPERIMENT_SETUP.md)
- cpu (from setup record): unknown
- git commit: `d98b8d80538abf3f59fc00ca172491256478a65d` (dirty tree: yes)
- python: 3.14.0
- platform: Windows-11-10.0.26200-SP0
- cpu: Intel64 Family 6 Model 204 Stepping 3, GenuineIntel, logical cores: 8
- ram_gb: 15.6

### Protocol

- profile: `mixed`, seed: 0, sessions: 2, execution: threads/scripted
- search locality: `local`
- total CPU basis: sum(session process_time)
- mock LLM latency scale: 0.05 (scripted backend sleeps (wall only); openai backend ignores this)
- clocks: wall = perf_counter_ns; CPU = thread_time_ns per region; real-agent total CPU = process_time (all threads, including LangGraph tool executors)
- nesting: exclusive self-time accounting; an inner region pauses its parent
- timer overhead: 5938 ns per enter/exit pair
- batch wall time: 4.23 s

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

- total thread CPU: 2781.25 ms
- instrumented: 2781.25 ms
- residual: 0.00 ms (0.0% of total)
- limit: 15%  ->  PASS

## Breakdown (thread CPU, exclusive per category — pooled across all sessions)

*Denominators: n=1 seed(s)=[0], search=local, batch host CPU=2781 ms, batch wall=4.2 s, CPU% of wall≈59.70%, c=2*

| Category | CPU ms | Share of total | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|
| ORCH_DISPATCH | 1640.625 | 59.0% | 3857.786 | 59 | 0 | 0 |
| TOOL_COMPUTE | 875.000 | 31.5% | 1286.451 | 19 | 285 | 0 |
| TOKENIZATION | 187.500 | 6.7% | 343.565 | 40 | 1166303 | 0 |
| GC | 46.875 | 1.7% | 46.875 | 3 | 0 | 0 |
| ORCH_SETUP | 31.250 | 1.1% | 336.791 | 4 | 0 | 0 |
| SERIALIZATION | 0.000 | 0.0% | 7.492 | 19 | 0 | 1122188 |
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
| SH-01 | 1500.0 | 47.9% | 47.9% |
| SH-02 | 1281.2 | 89.0% | 89.0% |

### Per-task LLM I/O wait vs host CPU

Each row is one session. **LLM I/O wait** = HTTP_CLIENT wall (blocked on OpenAI). **Host CPU** = session process_time. I/O % and CPU % both divide by session wall; they are different axes (wait vs compute), not additive category wall fractions.

| Task | Session wall s | LLM I/O wait s | Non-LLM wall s | Host CPU ms | I/O % of wall | CPU % of wall | Tool CPU ms | Harness CPU ms | Tools |
|---|---|---|---|---|---|---|---|---|---|
| SH-01 | 2.50 | 0.00 | 2.50 | 1500.0 | 0.0% | 60.12% | 734.4 | 765.6 | calculator×1, search×8 |
| SH-02 | 2.16 | 0.00 | 2.16 | 1281.2 | 0.0% | 59.21% | 140.6 | 1140.6 | retrieve×1, search×9 |
| **Total** | 4.66 | 0.00 | 4.66 | 2781.2 | 0.0% | 59.70% | | | |

#### Per-task CPU category breakdown

**SH-01** — 1500.0 ms host CPU, 2.50 s session wall — tools: calculator×1, search×8

| Category | CPU ms | Share of task CPU |
|---|---|---|
| TOOL_COMPUTE | 734.4 | 49.0% |
| ORCH_DISPATCH | 578.1 | 38.5% |
| TOKENIZATION | 109.4 | 7.3% |
| GC | 46.9 | 3.1% |
| ORCH_SETUP | 31.2 | 2.1% |

**SH-02** — 1281.2 ms host CPU, 2.16 s session wall — tools: retrieve×1, search×9

| Category | CPU ms | Share of task CPU |
|---|---|---|
| ORCH_DISPATCH | 1062.5 | 82.9% |
| TOOL_COMPUTE | 140.6 | 11.0% |
| TOKENIZATION | 78.1 | 6.1% |


### Pooled vs equal-weight (different questions)

*Denominators: n=1 seed(s)=[0], search=local, batch host CPU=2781 ms, batch wall=4.2 s, CPU% of wall≈59.70%, c=2. Comparison type: single-run sample unless replication_batch artifact.*

| Metric | Pooled (headline table) | Equal-weight task average |
|---|---|---|
| TOOL_COMPUTE CPU share | 31.5% of batch CPU | 30.0% |
| Answers | What consumed this batch's total host capacity | What a typical task of each type costs (one session per task here) |

Use **pooled** for capacity planning (dominated by heavy outlier sessions). Use **equal-weight per-archetype** rows below for archetype characterization. Do not treat the overall equal-weight amenability mean as a representative headline — it averages a bimodal distribution.

### Archetype amenability (primary equal-weight table)

| Archetype | Tasks | Mean CPU ms | Strict amenable | Broad amenable |
|---|---|---|---|---|
| SH (search_heavy) | SH-01, SH-02 | 1390.6 | 68.5% | 68.5% |

‡ **Small-base caution:** strict/broad percentages are of mean instrumented CPU near the Windows thread-time tick floor (~15 ms). High amenability % on RH/LH reflects sessions that barely ran local work, not hardware-friendly archetypes. Do not quote without absolute CPU ms; prefer Linux re-run for tick resolution.

**CH blend:** the CH archetype row averages tasks that can land in opposite behavior clusters — report CH-01 and CH-02 individually alongside the CH row (see per-task sections).

### Behavioral buckets (realized workload, not task labels)

Buckets are assigned from realized tool calls and turn count, not from task archetype labels. Task-label tables are prompt-intent only.

CPU floor for detailed per-task amenability: 200.0 ms

| Bucket | Label | Tasks | Mean host CPU ms | Mean strict amenable |
|---|---|---|---|---|
| B1_search_only | search only (no local code/retrieve) | SH-01 | 1500.0 | 47.9% |
| B2_mixed_tools | search plus code and/or retrieve | SH-02 | 1281.2 | 89.0% |

Task archetype labels (SH, RH, …) are prompt-intent only; use behavioral buckets for workload-ground-truth grouping.

### Accounting audit

- pass: **YES**
- publishable_ok: **YES**
- platform: `win32`
- Windows tick: 15.625 ms (footnote-only below 200 ms/session)
- warning: Host CPU values appear quantized to 15.625 ms Windows thread-time ticks; per-task shares below ~200 ms/session are not quotable. Re-run on Linux with test_resolution PASS before publishing.
- warning: SH-01: reconcile gap 468.8 ms is 31% of process CPU — check attribution
- warning: SH-02: reconcile gap 953.1 ms is 74% of process CPU — check attribution

### Wall-time attribution integrity

CPU category shares partition instrumented CPU (exclusive nesting; invariant PASS). **Wall fractions are not a partition metric** in real-agent mode: TOOL_COMPUTE/GC timers run on LangGraph tool-pool threads while the stream thread's session clock is also advancing, so summing all category wall fractions can exceed 100%. ORCH stream steps now use perf_counter gaps minus tagged wall (not thread CPU).

† TOOL_COMPUTE/GC: report mean wall ms; wall/session is marked concurrent (same clock period as session wait, not additive).

| Task | Session wall s | All-category coverage | Partition coverage |
|---|---|---|---|
| SH-01 | 2.50 | 116.9% | 69.9% |
| SH-02 | 2.16 | 136.9% | 113.9% |

### Equal-weight category breakdown by archetype

Mean CPU share partitions instrumented CPU (~100% per task). Wall/session excludes concurrent tool-pool categories (†).

#### SH (search_heavy)

- tasks (2): SH-01, SH-02
- mean session wall: 2.33 s
- mean instrumented CPU: 1390.6 ms
- mean amenable strict: 68.5%
- mean amenable broad: 68.5%
- partition wall fractions sum: 91.9% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 820.3 | 60.7% | 1928.9 | 84.2% |
| TOOL_COMPUTE | none | 437.5 | 30.0% | 643.2 | concurrent† |
| TOKENIZATION | direct | 93.8 | 6.7% | 171.8 | 7.5% |
| GC | none | 23.4 | 1.6% | 23.4 | concurrent† |
| ORCH_SETUP | direct | 15.6 | 1.0% | 168.4 | n/a |
| SERIALIZATION | direct | 0.0 | 0.0% | 3.7 | 0.2% |

### SH-01

- sessions: agent_0
- tool invocations: calculator×1, search×8
- instrumented CPU: 1500.0 ms
- hardware amenable: strict 47.9% (718.8 ms), broad 47.9% (718.8 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| TOOL_COMPUTE | none | 734.4 | 49.0% | 1004.3 | 9 | 126 | 0 |
| ORCH_DISPATCH | direct | 578.1 | 38.5% | 1602.4 | 28 | 0 | 0 |
| TOKENIZATION | direct | 109.4 | 7.3% | 139.4 | 19 | 557040 | 0 |
| GC | none | 46.9 | 3.1% | 46.9 | 3 | 0 | 0 |
| ORCH_SETUP | direct | 31.2 | 2.1% | 119.4 | 2 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 3.2 | 9 | 0 | 537020 |

### SH-02

- sessions: agent_1
- tool invocations: retrieve×1, search×9
- instrumented CPU: 1281.2 ms
- hardware amenable: strict 89.0% (1140.6 ms), broad 89.0% (1140.6 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| ORCH_DISPATCH | direct | 1062.5 | 82.9% | 2255.4 | 31 | 0 | 0 |
| TOOL_COMPUTE | none | 140.6 | 11.0% | 282.2 | 10 | 159 | 0 |
| TOKENIZATION | direct | 78.1 | 6.1% | 204.1 | 21 | 609263 | 0 |
| ORCH_SETUP | direct | 0.0 | 0.0% | 217.4 | 2 | 0 | 0 |
| SERIALIZATION | direct | 0.0 | 0.0% | 4.3 | 10 | 0 | 585168 |

## Process user/system split

- user: 1.203 s, system: 0.312 s
- per-category kernel-time attribution is approximate; category timers are user-space, syscall-heavy regions surface partly as system time

## Per-session summary

| Session | Task | Turns | Tool calls | Graph nodes | Dispatches | Wall s | Thread CPU ms |
|---|---|---|---|---|---|---|---|
| agent_0 | SH-01 | 19 | calculator:1, search:8 | n/a | n/a | 2.50 | 1500.00 |
| agent_1 | SH-02 | 21 | retrieve:1, search:9 | n/a | n/a | 2.16 | 1281.25 |

## Tool usage (all sessions including sub-agents)

| Tool | Calls | Result bytes |
|---|---|---|
| calculator | 1 | 0 |
| retrieve | 1 | 0 |
| search | 17 | 0 |

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


## Reproduce

```
python -m apu_characterization.experiments.real_agent_breakdown --backend scripted --profile mixed --seed 0 --sessions 2 --llm-scale 0.05 --search-locality local
```
