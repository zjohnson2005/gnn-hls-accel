# Experiment 0R: real LangGraph agent CPU-time breakdown (scripted, remote search deployment)

> **DEBUG ONLY — NOT VALID EXPERIMENTAL DATA.** This artifact used a mock, scripted, or synthetic decision path (no live OpenAI agent). Use only to verify instrumentation and invariants. Do not cite in papers, slides, or findings. See VERIFIABLE_DATA.md.

Generated: 2026-07-08T01:30:55.811058+00:00 from `real_agent_breakdown_remote_search_debug.json`.
All numbers below are read from that artifact.

## Setup

- setup record: digest `fdf16030e576a11e`, task suite `a88a9e1058964219` (see EXPERIMENT_SETUP.md)
- cpu (from setup record): Intel(R) Core(TM) Ultra 5 325
- git commit: `84f0afeeb12156acf32754c6493c2c75ab2a9a4a` (dirty tree: yes)
- python: 3.14.4
- platform: Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43
- cpu: unknown, logical cores: 8
- ram_gb: 7.56

### Protocol

- profile: `fanout`, seed: 1, sessions: 1, execution: threads/scripted
- search locality: `remote`
- payload profile: `locality_ablation` (synthetic tool-result padding; see tool-locality ablation note)
- total CPU basis: sum(session process_time)
- mock LLM latency scale: 0.05 (scripted backend sleeps (wall only); openai backend ignores this)
- clocks: wall = perf_counter_ns; CPU = thread_time_ns per region; real-agent total CPU = process_time (all threads, including LangGraph tool executors)
- nesting: exclusive self-time accounting; an inner region pauses its parent
- timer overhead: 3648 ns per enter/exit pair
- batch wall time: 33.83 s

### What each category wraps in this harness

- `ORCH_SETUP`: REAL AGENT MODE: LangGraph first-step CPU residual (framework graph/session construction), the Phase 0 setup definition
- `ORCH_DISPATCH`: REAL AGENT MODE: LangGraph per-step CPU residual between stream events minus tagged tool CPU (completion handling, channel updates, handoff), the Phase 0 steady definition
- `SERIALIZATION`: json.dumps/loads of LLM responses and tool results, response parse
- `TOKENIZATION`: token counting of the full assembled prompt each turn plus the response body (tiktoken or len/4 fallback); models client-side context-window bookkeeping, so it scales with conversation length per turn
- `PROMPT_ASSEMBLY`: REAL AGENT MODE: inside the framework, not separable; included in the ORCH buckets
- `CONTEXT_MGMT`: REAL AGENT MODE: inside the framework (LangGraph state channels), not separable; included in the ORCH buckets
- `HTTP_CLIENT`: OpenAI backend: LangChain callback wraps each LLM call (request build, response parse; network wait costs ~zero thread CPU). Remote search: mock search round-trip wall (I/O wait) also in HTTP_CLIENT.
- `CLIENT_HTTP`: httpx/OpenAI transport send path (v2 thread hooks)
- `CLIENT_PARSE`: response body read, JSON decode, validation (v2)
- `FRAMEWORK`: LangGraph/LangChain executor and graph internals (v2)
- `THREADPOOL`: concurrent.futures worker dispatch wrapper (v2)
- `EVENT_LOOP`: asyncio.run / loop driver overhead (v2)
- `TOOL_COMPUTE`: Local tool bodies only (code_exec, retrieve, calculator). Search is remote: HTTP envelope + I/O wait, not TOOL_COMPUTE.
- `LOGGING`: REAL AGENT MODE: not separately instrumented; inside ORCH buckets
- `GC`: collector cycles via gc.callbacks (lower bound, excludes refcount frees)
- `RESIDUAL_UNATTRIBUTED`: process_cpu minus all tagged categories (v2 session-end gap)

## Accounting invariant

sum(category thread-CPU) + residual = total thread-CPU of the run:

- total thread CPU: 189.88 ms
- instrumented: 191.07 ms
- residual: 0.00 ms (0.0% of total)
- limit: 15%  ->  PASS

## Breakdown (thread CPU, exclusive per category — pooled across all sessions)

*Denominators: n=1 seed(s)=[1], search=remote, batch host CPU=190 ms, batch wall=33.8 s, CPU% of wall≈9.58%, workers=1 (1 sessions sequential one-at-a-time)*

| Category | CPU ms | Share of total | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|
| THREADPOOL | 60.854 | 32.0% | 65.946 | 81 | 0 | 0 |
| FRAMEWORK | 45.042 | 23.7% | 48.679 | 62 | 0 | 0 |
| TOKENIZATION | 38.022 | 20.0% | 270.510 | 11 | 23769 | 0 |
| ORCH_SETUP | 37.400 | 19.7% | 436.087 | 2 | 0 | 0 |
| ORCH_DISPATCH | 7.967 | 4.2% | 522.684 | 10 | 0 | 0 |
| HTTP_CLIENT | 1.601 | 0.8% | 3090.232 | 27 | 1323 | 429 |
| SERIALIZATION | 0.163 | 0.1% | 0.177 | 9 | 0 | 20796 |
| GC | 0.020 | 0.0% | 0.022 | 3 | 0 | 0 |
| RESIDUAL_UNATTRIBUTED | 0.000 | 0.0% | 0.000 | 1 | 0 | 0 |
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
- `CLIENT_HTTP` [overlap]: TLS/HTTP transport owned by NIC/DPU class devices
- `CLIENT_PARSE` [direct]: JSON and schema validation map to parse engines
- `FRAMEWORK` [direct]: LangGraph dispatch maps to Phase 2 orchestration kernels
- `THREADPOOL` [partial]: executor dispatch is partial copy/scheduling offload
- `EVENT_LOOP` [partial]: asyncio driver is partial overlap with runtime
- `TOOL_COMPUTE` [none]: application compute, not serving-harness work; out of APU scope by definition
- `LOGGING` [partial]: format-and-ship maps to telemetry offload engines
- `GC` [none]: CPython runtime internals, not a separable block
- `RESIDUAL_UNATTRIBUTED` [none]: unattributed gap; must be driven to zero in v2

strict = direct tiers; broad = direct + partial + overlap tiers. Base is the task's instrumented CPU; GC and RESIDUAL are process-global and excluded from per-task math.

### Summary

| Task | Instrumented CPU ms | Amenable strict | Amenable broad |
|---|---|---|---|
| FO-01 | 191.1 | 67.3% | 100.0% |

### Per-task LLM I/O wait vs host CPU

Each row is one session. **LLM I/O wait** = HTTP_CLIENT wall (blocked on OpenAI). **Host CPU** = session process_time. I/O % and CPU % both divide by session wall; they are different axes (wait vs compute), not additive category wall fractions.

| Task | Session wall s | LLM I/O wait s | Non-LLM wall s | Host CPU ms | I/O % of wall | CPU % of wall | Tool CPU ms | Harness CPU ms | Tools |
|---|---|---|---|---|---|---|---|---|---|
| FO-01 | 1.98 | 3.09 | 0.00 | 189.9 | 155.8% | 9.58% | 0.0 | 85.2 | search×9 |
| **Total** | 1.98 | 3.09 | -1.11 | 189.9 | 155.8% | 9.58% | | | |

#### Per-task CPU category breakdown

**FO-01** — 189.9 ms host CPU, 1.98 s session wall — tools: search×9

| Category | CPU ms | Share of task CPU |
|---|---|---|
| THREADPOOL | 60.9 | 31.8% |
| FRAMEWORK | 45.0 | 23.6% |
| TOKENIZATION | 38.0 | 19.9% |
| ORCH_SETUP | 37.4 | 19.6% |
| ORCH_DISPATCH | 8.0 | 4.2% |
| HTTP_CLIENT | 1.6 | 0.8% |
| SERIALIZATION | 0.2 | 0.1% |
| GC | 0.0 | 0.0% |
| RESIDUAL_UNATTRIBUTED | 0.0 | 0.0% |


### Pooled vs equal-weight (different questions)

*Denominators: n=1 seed(s)=[1], search=remote, batch host CPU=190 ms, batch wall=33.8 s, CPU% of wall≈9.58%, workers=1 (1 sessions sequential one-at-a-time). Comparison type: single-run sample unless replication_batch artifact.*

| Metric | Pooled (headline table) | Equal-weight task average |
|---|---|---|
| TOOL_COMPUTE CPU share | 0.0% of batch CPU | 0.0% |
| Answers | What consumed this batch's total host capacity | What a typical task of each type costs (one session per task here) |

Use **pooled** for capacity planning (dominated by heavy outlier sessions). Use **equal-weight per-archetype** rows below for archetype characterization. Do not treat the overall equal-weight amenability mean as a representative headline — it averages a bimodal distribution.

### Archetype amenability (primary equal-weight table)

| Archetype | Tasks | Mean CPU ms | Strict amenable | Broad amenable |
|---|---|---|---|---|
| FO (fanout) | FO-01 | 191.1 | 67.3% | 100.0% |

‡ **Small-base caution:** strict/broad percentages are of mean instrumented CPU near the Windows thread-time tick floor (~15 ms). High amenability % on RH/LH reflects sessions that barely ran local work, not hardware-friendly archetypes. Do not quote without absolute CPU ms; prefer Linux re-run for tick resolution.

**CH blend:** the CH archetype row averages tasks that can land in opposite behavior clusters — report CH-01 and CH-02 individually alongside the CH row (see per-task sections).

### Deployment model and headline reconciliation

This run models **production-shaped search** (remote API + I/O wait). The baseline `real_agent_breakdown.json` used **local in-process regex search**.

**Corrected headline framing:** local-search runs looked TOOL-dominated because the mock search tool intentionally scans a 50 MB corpus on-host. Under remote search, TOOL_COMPUTE falls and orchestration/serialization/tokenization (APU-relevant harness work) become the dominant *on-host* categories — reconciling this breakdown with the Phase 0 concurrency experiment's orchestration-dominant picture.

| Metric | Local search (baseline) | Remote search (this run) |
|---|---|---|
| Batch host CPU | 6203.1 ms | 189.9 ms |
| Pooled TOOL_COMPUTE share | 86.1% | 0.0% |
| Pooled ORCH share | 7.1% | 23.9% |
| ORCH measured (host %) | 7.1% | 23.9% |
| ORCH reconcile (host %) | 0.0% | 0.0% |
| Pooled harness_strict (ORCH_SETUP+ORCH_DISPATCH+TOKENIZATION+SERIALIZATION) | 11.3% | 44.0% |
| Pooled harness_broad (strict + HTTP + PROMPT + CONTEXT + LOGGING) | 13.6% | 100.6% |
| Equal-weight TOOL_COMPUTE share | 32.6% | 0.0% |

Sessions that invoked local search (SH, and CH-02 when the model chose search) move from the CPU-heavy cluster to I/O-dominated wall time; remaining TOOL_COMPUTE is code_exec and local retrieve only.

### Behavioral buckets (realized workload, not task labels)

Buckets are assigned from realized tool calls and turn count, not from task archetype labels. Task-label tables are prompt-intent only.

CPU floor for detailed per-task amenability: 200.0 ms

| Bucket | Label | Tasks | Mean host CPU ms | Mean strict amenable |
|---|---|---|---|---|
| B1_search_only | search only (no local code/retrieve) | FO-01 | 189.9 | 67.3% |

Task archetype labels (SH, RH, …) are prompt-intent only; use behavioral buckets for workload-ground-truth grouping.

### ORCH attribution (measured vs reconcile)

ORCH **measured** = LangGraph stream step residual. ORCH **reconcile** = session-end process CPU not caught by region tags, booked to ORCH_DISPATCH. See `ATTRIBUTION.md`.

- Pooled ORCH: 23.9% of batch host CPU
- ORCH measured: 23.9% of host
- ORCH reconcile: 0.0% of host
- Reconcile as % of total ORCH: 0.0%
- harness_strict (ORCH_SETUP+ORCH_DISPATCH+TOKENIZATION+SERIALIZATION): 44.0%
- harness_broad (strict + HTTP_CLIENT + PROMPT_ASSEMBLY + CONTEXT_MGMT + LOGGING): 100.6%
- Audit rollup: reconcile 0.0% of host CPU

### Accounting audit

- pass: **YES**
- publishable_ok: **YES**
- platform: `linux`
- warning: FO-01: I/O % of wall is 155.8% (>100%) — HTTP_CLIENT wall includes remote-tool waits concurrent with session clock; not an additive partition (see wall integrity table)

### Wall-time attribution integrity

CPU category shares partition instrumented CPU (exclusive nesting; invariant PASS). **Wall fractions are not a partition metric** in real-agent mode: TOOL_COMPUTE/GC timers run on LangGraph tool-pool threads while the stream thread's session clock is also advancing, so summing all category wall fractions can exceed 100%. ORCH stream steps now use perf_counter gaps minus tagged wall (not thread CPU).

† TOOL_COMPUTE/GC: report mean wall ms; wall/session is marked concurrent (same clock period as session wait, not additive).

| Task | Session wall s | All-category coverage | Partition coverage |
|---|---|---|---|
| FO-01 | 1.98 | 223.6% | 201.6% |

### Equal-weight category breakdown by archetype

Mean CPU share partitions instrumented CPU (~100% per task). Wall/session excludes concurrent tool-pool categories (†).

#### FO (fanout)

- tasks (1): FO-01
- mean session wall: 1.98 s
- mean instrumented CPU: 191.1 ms
- mean amenable strict: 67.3%
- mean amenable broad: 100.0%
- partition wall fractions sum: 201.6% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| THREADPOOL | partial | 60.9 | 31.8% | 65.9 | 3.3% |
| FRAMEWORK | direct | 45.0 | 23.6% | 48.7 | 2.5% |
| TOKENIZATION | direct | 38.0 | 19.9% | 270.5 | 13.6% |
| ORCH_SETUP | direct | 37.4 | 19.6% | 436.1 | n/a |
| ORCH_DISPATCH | direct | 8.0 | 4.2% | 522.7 | 26.4% |
| HTTP_CLIENT | overlap | 1.6 | 0.8% | 3090.2 | 155.8% |
| SERIALIZATION | direct | 0.2 | 0.1% | 0.2 | 0.0% |
| GC | none | 0.0 | 0.0% | 0.0 | concurrent† |
| RESIDUAL_UNATTRIBUTED | none | 0.0 | 0.0% | 0.0 | 0.0% |

### FO-01

- sessions: agent_0
- tool invocations: search×9
- instrumented CPU: 191.1 ms
- hardware amenable: strict 67.3% (128.6 ms), broad 100.0% (191.0 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| THREADPOOL | partial | 60.9 | 31.8% | 65.9 | 81 | 0 | 0 |
| FRAMEWORK | direct | 45.0 | 23.6% | 48.7 | 62 | 0 | 0 |
| TOKENIZATION | direct | 38.0 | 19.9% | 270.5 | 11 | 23769 | 0 |
| ORCH_SETUP | direct | 37.4 | 19.6% | 436.1 | 2 | 0 | 0 |
| ORCH_DISPATCH | direct | 8.0 | 4.2% | 522.7 | 10 | 0 | 0 |
| HTTP_CLIENT | overlap | 1.6 | 0.8% | 3090.2 | 27 | 1323 | 429 |
| SERIALIZATION | direct | 0.2 | 0.1% | 0.2 | 9 | 0 | 20796 |
| GC | none | 0.0 | 0.0% | 0.0 | 3 | 0 | 0 |
| RESIDUAL_UNATTRIBUTED | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |

## Process user/system split

- user: 0.120 s, system: 0.090 s
- per-category kernel-time attribution is approximate; category timers are user-space, syscall-heavy regions surface partly as system time

## Per-session summary

| Session | Task | Turns | Tool calls | Graph nodes | Dispatches | Wall s | Thread CPU ms |
|---|---|---|---|---|---|---|---|
| agent_0 | FO-01 | 11 | search:9 | n/a | n/a | 1.98 | 189.88 |

## Tool usage (all sessions including sub-agents)

| Tool | Calls | Result bytes |
|---|---|---|
| search | 9 | 0 |

## Tasks executed

### FO-01 (fanout)

Goal: Compare the weather, best food, and main attractions of Paris, Tokyo, and Cairo. Nine searches fan out in one turn; their completions land nearly simultaneously (dispatch burst), then one merge turn.

- turn 0: fan-out 9 calls [search: paris weather forecast rain; search: paris food recipe cheese; search: paris museum castle history; search: tokyo weather season wind; search: tokyo food fish dinner; search: tokyo city station bridge; search: cairo weather sun warm; search: cairo food bread market; search: cairo ancient museum empire]
- turn 1: reasoning only


## Reproduce

```
python -m apu_characterization.experiments.real_agent_breakdown --backend scripted --profile fanout --seed 1 --sessions 1 --llm-scale 0.05 --search-locality remote --payload-profile locality_ablation
```
