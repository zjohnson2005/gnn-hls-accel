# Prior-art citation rules (Angles 1-5)

Nature: report-generation and derivation-document work only. Does NOT change
any experiment config, seed, scale, gate, or arm label. Apply when generating
or regenerating reports after runs complete. No em dashes anywhere.

Standing rule (A7): wherever a report makes a novelty-adjacent statement
("first measurement of X," "unmeasured before"), it must name the nearest
prior work and state the specific delta in one sentence. Novelty claims
without a named nearest neighbor do not ship.

## MCP-01 external anchors

The MCP tax report cites arXiv:2601.17549 only as an external comparison.
The paper reports 12.4 ms/message median for stdio, 23.7 ms/message for
HTTP/SSE, and 8.3 ms/message median overhead for its proposed authentication
extension. These values must never appear in an "ours" table or plot series.
Every comparison states that hosts, SDKs, message shapes, and latency
definitions differ.

Permitted positioning: MCP-01 decomposes a controlled protocol message into
host CPU-busy categories and wait, and separates pinned-SDK overhead from a
raw JSON-RPC implementation. It does not claim those external medians were
measured by this repository, nor that the external paper used this taxonomy.

## Angle 1: Universality (`harness_universality_report.md` and per-harness drafts)

The claim "nobody compared frameworks" is FALSE and must not appear anywhere.

Prior art to cite:

- AutoAgents (Rust) benchmark, Feb 2026 (dev.to writeup; repo
  github.com/liquidos-ai/autoagents-bench): Rust agent framework vs
  LangChain/LangGraph/LlamaIndex/PydanticAI on live gpt-4o-mini. Found ~5x
  memory gap (Rust ~1.0 GB vs Python avg ~5.1 GB) but latency clustered
  5,700-7,000 ms across ALL frameworks because the live LLM round-trip
  dominates. Their limitations: blocking responses only, model-specific,
  streaming unprofiled.
- The 2,000-run multi-framework benchmark (aimultiple): LangGraph fastest on
  latency across five tasks, CrewAI ~3x token footprint on single-tool flows;
  measured agent-to-agent handoff latency and explicitly dismissed it as
  minimal at the millisecond level.
- Trade benchmarks quoting end-to-end seconds-scale latencies and
  token-overhead percentages (LangGraph ~1.2 s / ~5% token overhead vs
  AutoGen ~2.1 s / ~24% on 10-step pipelines).
- Adjacent agent-overhead characterization that must be named with any scoped
  novelty sentence: Raj et al. (arXiv 2511.00739), Agent-X
  (arXiv 2605.10380), and PASTE (arXiv 2603.18897).

Permitted positioning sentence: published framework comparisons commonly
report end-to-end wall or token metrics at live-API latencies, where this
per-turn floor is difficult to separate from model wait. The scoped
differentiator here is a controlled-latency measurement of the
model-latency-invariant, tool-excluded per-turn orchestration floor under
latency collapse, with category decomposition and derived hardware budgets.
Keep the named adjacent works above in the same paragraph. Do not claim
"first" or "unmeasured before" without that named-neighbor sentence in the
same paragraph; prefer the controlled-latency wording above.

Angle 1C (Rust) specifically: cite AutoAgents as the existing Rust-vs-Python
comparison and state the differentiation plainly: they answered "is a Rust
framework viable" (yes, and 5x lighter in memory); this work answers "what is
the software lower bound of the per-turn harness floor," which their
live-model setup did not separate from LLM-wait noise (their latency spread
sat inside model wait). If practical, note their memory finding as
corroborating that Python runtime weight is real; memory is not our axis but
it supports the runtime-cost narrative.

Optional, only if zero-cost: check whether AutoAgents' public benchmark tasks
map onto any of the 14-task shapes; if one does, note the correspondence for
comparability. Do not add new runs for this.

## Angle 2: Overlap (`overlap_decomposition.md`)

The latency-hiding technique space is crowded. Write against it, not as if
empty.

Prior art to cite:

- Sutradhara (arXiv 2601.12967): orchestrator-engine co-design on vLLM;
  overlaps tool execution with LLM prefill via tool-aware prompt splitting,
  streams tool dispatch during decode, semantic cache management; 15% median
  first-token-response reduction, 10% overall latency. Also: tool calls
  account for 30-80% of first-token-response latency at production scale, and
  sequential orchestration wastes intra-request parallelism.
- Speculative tool calls (arXiv 2512.15834): breaks sequential dependency of
  tool calls; notes eviction/rescheduling overheads persist even with prefix
  caching.
- IdleSpec (arXiv 2605.22154): exploits idle time during tool waits for
  speculative planning.
- SpecEyes (arXiv 2603.23483): lifts speculation to the agentic level;
  formalizes agentic depth D with end-to-end latency growing linearly in D
  and concurrency collapse from per-query serial state.
- Streaming-RAG headroom characterization (arXiv 2606.20113): quantifies the
  input-hideable fraction of tool latency; methodological kin (characterizing
  hideable vs not).

Mandatory framing: the overlappable share of the floor is CONCEDED to
Sutradhara-class software up front, stated as an upper bound on what software
pipelining can hide. The deliverable's headline is the POST-SERIAL RESIDUE,
defined explicitly as: the per-turn cost that remains dependency-serialized
behind the final token AFTER Sutradhara-class overlap, speculative tool
calling, and idle-time speculation are applied. That literature is the reason
the residue number matters. The scoped delta is that this mock/debug_only arm
reports the post-serial residue under the stated dependency cut; do not claim
that adjacent systems never measured agent overhead.

Motivation sentence: the existence and rapid growth of an entire software
latency-hiding ecosystem for agents is itself evidence the latency is real
and painful; this measurement isolates the part of it that the ecosystem
cannot reach.

STREAM_OVERLAPPABLE remains BY_CONSTRUCTION under the non-streaming mock.

## Angle 3: Velocity law (`agent_velocity_law.md`)

No repositioning of the law. Supporting citations only:

- SpecEyes' qualitative statement (latency grows linearly in agentic depth D)
  as the nearest prior formal statement; the law here is the turn-rate
  version with measured constants and an empirical fit, which is new.
- The practitioner floor intuition (inference is 60-75% of agentic wall
  clock; fixed overhead sets a floor on end-to-end speedup) as the
  industry-side qualitative precedent the law quantifies.

## Angle 4: Delegation tax (`delegation_tax_report.md`)

- SpecEyes: agentic depth D and linear latency explosion (their regime:
  multimodal GPU-side agents; this work: harness cost per delegation hop at a
  fast tier, unmeasured by them).
- The multi-framework benchmark's agent-to-agent handoff measurement,
  dismissed as minimal at millisecond level: cite as the exact measurement
  this arm takes seriously instead of discarding, since at fast-tier
  latencies millisecond-level per-hop cost is no longer negligible by this
  project's own crossover result.

## Angle 5: Throughput demo (`reasoning_throughput_demo.md`)

- SpecEyes' observation that the serial agentic loop leaves hardware
  parallelism idle and that prior methods never question the loop itself, as
  the qualitative statement of the thesis this demo measures (exploration
  rate pinned to the harness ceiling, not the model).

## turn_path_derivation.md: software co-design point of comparison

Short section, three claims:

1. Sutradhara is the best published software integration of orchestrator and
   engine: 15% median FTR reduction, 10% overall. That is what tight software
   co-design achieves on the same problem class.
2. The derived turn-path structure targets (a) the post-serial residue (from
   Angle 2 / `overlap_decomposition.md`) that overlap cannot hide, (b) the
   tail-determinism requirement (software co-design does not bound jitter;
   cite F-B), and (c) the fast-inference regime where the floor is majority
   of the turn, where a 15%-class software improvement does not change the
   asymptote (cite `agent_velocity_law.md` ceilings).
3. Keep English only. No stray non-English characters.
