# Experiment 0R: real LangGraph agent CPU-time breakdown (openai, remote search deployment)

> **Publishable run.** Live OpenAI API agent decisions (`--backend openai`), real open-source tool bodies, audit PASS, Linux-resolution platform (or replication n≥5). Numbers may be used in research outputs subject to denominators and deployment caveats in VERIFIABLE_DATA.md and ATTRIBUTION.md.

Generated: 2026-07-08T13:18:01.396588+00:00 from `real_agent_breakdown_remote_search.json`.
All numbers below are read from that artifact.

## Setup

- setup record: digest `b375dc13337b83a8`, task suite `a88a9e1058964219` (see EXPERIMENT_SETUP.md)
- cpu (from setup record): Intel(R) Core(TM) Ultra 5 325
- git commit: `7decfdc59faababef3f4695622ba3eb75f7e39e6` (dirty tree: yes)
- python: 3.14.4
- platform: Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43
- cpu: unknown, logical cores: 8
- ram_gb: 7.56

### Protocol

- profile: `fanout`, seed: 1, sessions: 1, execution: threads/openai
- search locality: `remote`
- payload profile: `locality_ablation` (synthetic tool-result padding; see tool-locality ablation note)
- total CPU basis: sum(session process_time)
- mock LLM latency scale: 0.05 (scripted backend sleeps (wall only); openai backend ignores this)
- clocks: wall = perf_counter_ns; CPU = thread_time_ns per region; real-agent total CPU = process_time (all threads, including LangGraph tool executors)
- nesting: exclusive self-time accounting; an inner region pauses its parent
- timer overhead: 6964 ns per enter/exit pair
- batch wall time: 73.47 s

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

- total thread CPU: 233.37 ms
- instrumented: 234.34 ms
- residual: 0.00 ms (0.0% of total)
- limit: 15%  ->  PASS

## Breakdown (thread CPU, exclusive per category — pooled across all sessions)

*Denominators: n=1 seed(s)=[1], search=remote, batch host CPU=233 ms, batch wall=73.5 s, CPU% of wall≈1.78%, workers=1 (1 sessions sequential one-at-a-time)*

| Category | CPU ms | Share of total | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|
| FRAMEWORK | 215.637 | 92.4% | 3212.357 | 31 | 0 | 0 |
| ORCH_SETUP | 5.773 | 2.5% | 184.900 | 2 | 0 | 0 |
| TOKENIZATION | 3.599 | 1.5% | 248.871 | 13 | 46852 | 0 |
| THREADPOOL | 3.425 | 1.5% | 51.244 | 42 | 0 | 0 |
| GC | 3.324 | 1.4% | 49.720 | 78 | 0 | 0 |
| CLIENT_HTTP | 1.328 | 0.6% | 11749.091 | 2 | 0 | 26982 |
| ORCH_DISPATCH | 1.066 | 0.5% | 0.000 | 10 | 0 | 0 |
| HTTP_CLIENT | 0.140 | 0.1% | 15001.281 | 29 | 3359 | 363 |
| SERIALIZATION | 0.030 | 0.0% | 0.447 | 11 | 0 | 44599 |
| CLIENT_PARSE | 0.010 | 0.0% | 0.153 | 4 | 2103 | 0 |
| PROMPT_ASSEMBLY | 0.002 | 0.0% | 0.026 | 2 | 0 | 23162 |
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
| FO-01 | 234.3 | 96.5% | 98.6% |

### Per-task LLM I/O wait vs host CPU

Each row is one session. **LLM I/O wait** = HTTP_CLIENT wall (blocked on OpenAI). **Host CPU** = session process_time. I/O % and CPU % both divide by session wall; they are different axes (wait vs compute), not additive category wall fractions.

| Task | Session wall s | LLM I/O wait s | Non-LLM wall s | Host CPU ms | I/O % of wall | CPU % of wall | Tool CPU ms | Harness CPU ms | Tools |
|---|---|---|---|---|---|---|---|---|---|
| FO-01 | 13.11 | 11.75 | 0.00 | 233.4 | 89.6% | 1.78% | 0.0 | 15.3 | search×9 |
| **Total** | 13.11 | 11.75 | 1.36 | 233.4 | 89.6% | 1.78% | | | |

#### Per-task CPU category breakdown

**FO-01** — 233.4 ms host CPU, 13.11 s session wall — tools: search×9

| Category | CPU ms | Share of task CPU |
|---|---|---|
| FRAMEWORK | 215.6 | 92.0% |
| ORCH_SETUP | 5.8 | 2.5% |
| TOKENIZATION | 3.6 | 1.5% |
| THREADPOOL | 3.4 | 1.5% |
| GC | 3.3 | 1.4% |
| CLIENT_HTTP | 1.3 | 0.6% |
| ORCH_DISPATCH | 1.1 | 0.5% |
| HTTP_CLIENT | 0.1 | 0.1% |
| SERIALIZATION | 0.0 | 0.0% |
| CLIENT_PARSE | 0.0 | 0.0% |
| PROMPT_ASSEMBLY | 0.0 | 0.0% |
| RESIDUAL_UNATTRIBUTED | 0.0 | 0.0% |


### Pooled vs equal-weight (different questions)

*Denominators: n=1 seed(s)=[1], search=remote, batch host CPU=233 ms, batch wall=73.5 s, CPU% of wall≈1.78%, workers=1 (1 sessions sequential one-at-a-time). Comparison type: single-run sample unless replication_batch artifact.*

| Metric | Pooled (headline table) | Equal-weight task average |
|---|---|---|
| TOOL_COMPUTE CPU share | 0.0% of batch CPU | 0.0% |
| Answers | What consumed this batch's total host capacity | What a typical task of each type costs (one session per task here) |

Use **pooled** for capacity planning (dominated by heavy outlier sessions). Use **equal-weight per-archetype** rows below for archetype characterization. Do not treat the overall equal-weight amenability mean as a representative headline — it averages a bimodal distribution.

### Archetype amenability (primary equal-weight table)

| Archetype | Tasks | Mean CPU ms | Strict amenable | Broad amenable |
|---|---|---|---|---|
| FO (fanout) | FO-01 | 234.3 | 96.5% | 98.6% |

‡ **Small-base caution:** strict/broad percentages are of mean instrumented CPU near the Windows thread-time tick floor (~15 ms). High amenability % on RH/LH reflects sessions that barely ran local work, not hardware-friendly archetypes. Do not quote without absolute CPU ms; prefer Linux re-run for tick resolution.

**CH blend:** the CH archetype row averages tasks that can land in opposite behavior clusters — report CH-01 and CH-02 individually alongside the CH row (see per-task sections).

### Deployment model and headline reconciliation

This run models **production-shaped search** (remote API + I/O wait). The baseline `real_agent_breakdown.json` used **local in-process regex search**.

**Corrected headline framing:** local-search runs looked TOOL-dominated because the mock search tool intentionally scans a 50 MB corpus on-host. Under remote search, TOOL_COMPUTE falls and orchestration/serialization/tokenization (APU-relevant harness work) become the dominant *on-host* categories — reconciling this breakdown with the Phase 0 concurrency experiment's orchestration-dominant picture.

| Metric | Local search (baseline) | Remote search (this run) |
|---|---|---|
| Batch host CPU | 6203.1 ms | 233.4 ms |
| Pooled TOOL_COMPUTE share | 86.1% | 0.0% |
| Pooled ORCH share | 7.1% | 2.9% |
| ORCH measured (host %) | 7.1% | 2.9% |
| ORCH reconcile (host %) | 0.0% | 0.0% |
| Pooled harness_strict (ORCH_SETUP+ORCH_DISPATCH+TOKENIZATION+SERIALIZATION) | 11.3% | 4.5% |
| Pooled harness_broad (strict + HTTP + PROMPT + CONTEXT + LOGGING) | 13.6% | 99.0% |
| Equal-weight TOOL_COMPUTE share | 32.6% | 0.0% |

Sessions that invoked local search (SH, and CH-02 when the model chose search) move from the CPU-heavy cluster to I/O-dominated wall time; remaining TOOL_COMPUTE is code_exec and local retrieve only.

### Behavioral buckets (realized workload, not task labels)

Buckets are assigned from realized tool calls and turn count, not from task archetype labels. Task-label tables are prompt-intent only.

CPU floor for detailed per-task amenability: 200.0 ms

| Bucket | Label | Tasks | Mean host CPU ms | Mean strict amenable |
|---|---|---|---|---|
| B1_search_only | search only (no local code/retrieve) | FO-01 | 233.4 | 96.5% |

Task archetype labels (SH, RH, …) are prompt-intent only; use behavioral buckets for workload-ground-truth grouping.

### ORCH attribution (measured vs reconcile)

ORCH **measured** = LangGraph stream step residual. ORCH **reconcile** = session-end process CPU not caught by region tags, booked to ORCH_DISPATCH. See `ATTRIBUTION.md`.

- Pooled ORCH: 2.9% of batch host CPU
- ORCH measured: 2.9% of host
- ORCH reconcile: 0.0% of host
- Reconcile as % of total ORCH: 0.0%
- harness_strict (ORCH_SETUP+ORCH_DISPATCH+TOKENIZATION+SERIALIZATION): 4.5%
- harness_broad (strict + HTTP_CLIENT + PROMPT_ASSEMBLY + CONTEXT_MGMT + LOGGING): 99.0%
- Audit rollup: reconcile 0.0% of host CPU

### Accounting audit

- pass: **YES**
- publishable_ok: **YES**
- platform: `linux`
- warning: FO-01: remote-tool I/O % of wall is 114.4% (>100%) — HTTP_CLIENT wall includes mock search/retrieve waits concurrent with session clock; not an additive partition
- warning: Single-seed run (n=1); replication requires n≥5 seeds with medians and IQR before headline numbers are quotable

### Wall-time attribution integrity

CPU category shares partition instrumented CPU (exclusive nesting; invariant PASS). **Wall fractions are not a partition metric** in real-agent mode: TOOL_COMPUTE/GC timers run on LangGraph tool-pool threads while the stream thread's session clock is also advancing, so summing all category wall fractions can exceed 100%. ORCH stream steps now use perf_counter gaps minus tagged wall (not thread CPU).

† TOOL_COMPUTE/GC: report mean wall ms; wall/session is marked concurrent (same clock period as session wait, not additive).

| Task | Session wall s | All-category coverage | Partition coverage |
|---|---|---|---|
| FO-01 | 13.11 | 232.7% | 230.9% |

### Equal-weight category breakdown by archetype

Mean CPU share partitions instrumented CPU (~100% per task). Wall/session excludes concurrent tool-pool categories (†).

#### FO (fanout)

- tasks (1): FO-01
- mean session wall: 13.11 s
- mean instrumented CPU: 234.3 ms
- mean amenable strict: 96.5%
- mean amenable broad: 98.6%
- partition wall fractions sum: 230.9% (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)

| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |
|---|---|---|---|---|---|
| FRAMEWORK | direct | 215.6 | 92.0% | 3212.4 | 24.5% |
| ORCH_SETUP | direct | 5.8 | 2.5% | 184.9 | n/a |
| TOKENIZATION | direct | 3.6 | 1.5% | 248.9 | 1.9% |
| THREADPOOL | partial | 3.4 | 1.5% | 51.2 | 0.4% |
| GC | none | 3.3 | 1.4% | 49.7 | concurrent† |
| CLIENT_HTTP | overlap | 1.3 | 0.6% | 11749.1 | 89.6% |
| ORCH_DISPATCH | direct | 1.1 | 0.5% | 0.0 | 0.0% |
| HTTP_CLIENT | overlap | 0.1 | 0.1% | 15001.3 | 114.4% |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.4 | 0.0% |
| CLIENT_PARSE | direct | 0.0 | 0.0% | 0.2 | 0.0% |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 0.0% |
| RESIDUAL_UNATTRIBUTED | none | 0.0 | 0.0% | 0.0 | 0.0% |

### FO-01

- sessions: agent_0
- tool invocations: search×9
- instrumented CPU: 234.3 ms
- hardware amenable: strict 96.5% (226.1 ms), broad 98.6% (231.0 ms)

| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |
|---|---|---|---|---|---|---|---|
| FRAMEWORK | direct | 215.6 | 92.0% | 3212.4 | 31 | 0 | 0 |
| ORCH_SETUP | direct | 5.8 | 2.5% | 184.9 | 2 | 0 | 0 |
| TOKENIZATION | direct | 3.6 | 1.5% | 248.9 | 13 | 46852 | 0 |
| THREADPOOL | partial | 3.4 | 1.5% | 51.2 | 42 | 0 | 0 |
| GC | none | 3.3 | 1.4% | 49.7 | 78 | 0 | 0 |
| CLIENT_HTTP | overlap | 1.3 | 0.6% | 11749.1 | 2 | 0 | 26982 |
| ORCH_DISPATCH | direct | 1.1 | 0.5% | 0.0 | 10 | 0 | 0 |
| HTTP_CLIENT | overlap | 0.1 | 0.1% | 15001.3 | 29 | 3359 | 363 |
| SERIALIZATION | direct | 0.0 | 0.0% | 0.4 | 11 | 0 | 44599 |
| CLIENT_PARSE | direct | 0.0 | 0.0% | 0.2 | 4 | 2103 | 0 |
| PROMPT_ASSEMBLY | partial | 0.0 | 0.0% | 0.0 | 2 | 0 | 23162 |
| RESIDUAL_UNATTRIBUTED | none | 0.0 | 0.0% | 0.0 | 1 | 0 | 0 |

## Process user/system split

- user: 1.880 s, system: 1.640 s
- per-category kernel-time attribution is approximate; category timers are user-space, syscall-heavy regions surface partly as system time

## Per-session summary

| Session | Task | Turns | Tool calls | Graph nodes | Dispatches | Wall s | Thread CPU ms |
|---|---|---|---|---|---|---|---|
| agent_0 | FO-01 | 11 | search:9 | n/a | n/a | 13.11 | 233.37 |

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
python -m apu_characterization.experiments.real_agent_breakdown --backend openai --profile fanout --seed 1 --sessions 1 --llm-scale 0.05 --search-locality remote --payload-profile locality_ablation
```
