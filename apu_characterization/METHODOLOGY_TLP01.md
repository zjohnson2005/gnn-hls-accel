# TLP-01 methodology: limits of turn-level parallelism (v2)

Protocol template: `tlp01/protocol_tlp01_v2.json` (supersedes `protocol_tlp01_v1.json`).

## Document map (repo paths)

| Conversational name | Use instead |
|---|---|
| TLP-01 thesis / execution spec v1 | historical; see v2 redirect |
| TLP-01 v2 speculation frontier | `METHODOLOGY_TLP01.md` + `tlp01/protocol_tlp01_v2.json` |
| Promotion one-pager | `PROMOTION_SUMMARY.md` |

Authoritative on-disk paths:

- Methodology: `apu_characterization/METHODOLOGY_TLP01.md`
- Protocol template: `apu_characterization/tlp01/protocol_tlp01_v2.json`
- Predictions: `apu_characterization/PREDICTIONS_TLP01.md`
- Promotion summary: `apu_characterization/PROMOTION_SUMMARY.md`
- Arm README: `apu_characterization/tlp01/README.md`
- Died ledger: `apu_characterization/tlp01/died_ledger.json`

---

# PART I: THE THESIS

## I.1 The claim

Modern in-order agent harnesses often execute the turn loop with limited
overlap. Parallel and speculative systems already exist (PASTE/B-PASTE, SPORK,
LLMCompiler, GAP — see related-work). TLP-01's claim is narrower and ownable:
agent workloads contain measurable *latent* turn-level parallelism; a
trace-driven limit study can bound the ceiling (M1/M2/M3) and map the
speculation-economics frontier (M4 policy × penalty phase diagram). The study
does **not** claim to be first to parallelize agents.

## I.2 The mapping (load-bearing)

| Microarchitecture concept | Agent analog | Formal role shared |
|---|---|---|
| Instruction | Turn (model call + pre/post) or tool call | Unit of work with defined inputs/outputs |
| Register/memory dependence | Data dependence via tokens/values | The thing that FORCES ordering |
| Program order | Harness execution order | Order used vs order required |
| Cycle time | T_orch (measured) + per-stage decomposition | Non-overlappable per-unit cost |
| Pipeline stall | Model wait with idle orchestration | Time the machine could overlap |
| Branch | Model's next-action decision | Control dependence at execute |
| Branch predictor | Next-dispatch predictor over tool history | Speculation target |
| Misprediction penalty | Speculative context-build waste | Economics of speculation |
| Issue width | Concurrent independent tool calls / turns | Parallel resources |
| ROB / scoreboard | Session table + pending-turn tracker (ACU) | Structure that makes OoO safe |
| ILP limit study (Wall 1991) | THIS STUDY | Founding measurement |

Honest disanalogies: (1) turn latencies are wildly variable — report both
unit-count (turns-in-flight) and time-weighted (critical-path) speedup; the
latter is load-bearing; (2) dependences flow through natural-language content,
so detection has a judgment component — that is the methodological heart
(Part II.2).

## I.3 Why a limit study

Wall's "Limits of Instruction-Level Parallelism" (1991) answered the ceiling
question before the machines existed. The agent field is at the same
pre-machine moment: schedulers and parallel tool-call proposals exist, but
nobody has measured the ceiling. TLP-01 is the founding measurement.

## I.4 Prior results under this frame

- Mock latency sweep → cycle-time characterization
- SEARCH-01 → stall demonstration (in-order ceiling)
- Delegation tax → inter-unit communication cost
- Speculation economics (20 µs vs 10 ms) → misprediction-penalty analysis
- MCP-01 → instruction-encoding cost
- CAP-01 → IPC-to-performance (units retired per budget → capability)
- Praetor/Senatus → first machine designed against measured limits
  (datapath / control). Positioning only — never a measured TLP-01 claim.

---

# PART II: EXECUTION

## II.0 Design summary

Three phases. **T0** trace collection. **T1** dependence-graph construction
with a three-tier oracle. **T2** scheduling simulation across M0–M5. No bare
metal. No live model calls after T0. Trace-driven simulation on ordinary
hardware.

## II.1 Phase T0 — Trace collection

A trace is one session's ordered event log: turns, tool calls, delegation
hops, stage timings, harness execution order, and optional `dep_refs`.
Schema frozen in `protocol_tlp01_v2.json` (`tlp01_trace_v2`); traces hashed
and never edited in place (append-only store; bad sessions discarded whole
and re-run under a new attempt id).

Sources:

- **S1** — extraction from existing replication / live-ladder artifacts
  (standing task classes). Required for v1. `dep_refs` is null (legacy).
  S1 anchors the SERIAL end of the task spectrum for oracle calibration;
  it is not the basis for the ceiling claim.
- **S2** — fresh multi-tool live OpenAI traces (10 templates × 5 seeds =
  50 sessions, temp 0) with Tier-0 `from_result` instrumentation. Required
  for v1. Templates (including serial negative controls `MT-SER-01/02`)
  are pre-registered in `tlp01/s2_task_manifest.json`.
- **S3** — Claude Code adapter arm. Optional; absence is a stated scope
  limit (died-ledger #1).

### Tier-0 (`dep_refs`) — honest limits

S2 tools accept optional `from_result=<prior result_id>`. The harness
resolves IDs at dispatch and logs each explicit reference into `dep_refs`.
These edges are ground truth by construction and sit **above** the
Tier-S/Tier-C bracket (named Tier-0 in the taxonomy).

Honest limits (do not overclaim):

- Tier-0 captures only dependencies the model routes through structured
  arguments. Implicit influence (reasoning shaped by content never cited
  via `from_result`) remains Tier-S/C territory.
- Presence of a `dep_ref` is proof of dependence. **Absence is silence,
  not evidence of independence** — analyses that use Tier-0 must report
  S1/S2 coverage separately.
- G-D extension (enforced in T1): every Tier-0 edge must also appear in
  Tier-C (`Tier-0 ⊆ Tier-C`). If Tier-C's conservative net misses an edge
  the harness proved, Tier-C's threshold is broken — a free calibration
  check on the bracket.

## II.2 Phase T1 — Dependence graphs

Per session: a DAG. Nodes = turns and tool calls. Edges = ordering-forcing
dependences.

| Tier | Role | Headline |
|---|---|---|
| Tier-0 (structured `dep_refs`) | Ground truth by construction (S2) | Above S/C; coverage-limited |
| Tier-S (syntactic) | Precise; undercounts (misses paraphrase) | TLP ceiling |
| Tier-C (conservative-complete) | Overcounts; brackets truth with S | TLP floor |
| Tier-J (judged) | Characterizes S–C gap only | Never load-bearing |

**The bracket, not a point, is the honest headline.** Control dependences
are tracked separately; the machine-model ladder states which speculation
can break.

## II.3 Phase T2 — Machine-model ladder

| Model | Isolates |
|---|---|
| M0 | In-order baseline; validates simulator (G-V) |
| M1 | Absolute TLP ceiling (oracle OoO, ∞ width) |
| M2 | M1 + real T_orch — floor tax on parallelism |
| M3 | Finite width w ∈ {2,4,8,∞} — width knee |
| M4 | Realistic control speculation (+ software / Praetor Tier-D penalties) |
| M5 | M4 + provider rate limits — deployable today |

Headline chart: speedup vs model, one line per dependence tier, per task
class. Quotable: M1 Tier-S = available TLP; M4 Tier-C = harvestable now;
M2−M1 = floor tax on parallelism.

## II.4 Gates (frozen)

| Gate | Rule |
|---|---|
| G-V | M0 makespan within ±5% of recorded |
| G-D | Tier-S ⊆ Tier-C on every trace; Tier-0 ⊆ Tier-C when instrumented |
| G-A | DAG + event conservation + work conservation |
| G-R | n=5 seeds; bands never points |
| G-J | Tier-J ships only with human κ; below 0.6 → appendix |

Timer-resolution floors inherited (CAP-01 died-ledger #5). Thresholds do
not move after measurement.

## II.5 Claim rungs (two independent tracks)

See `PREDICTIONS_TLP01.md`. Ceiling track 1a/2a/3a and frontier track 1b/2b/3b
are independent; report both. No rung is a failure.

## II.5b Speculation frontier (M4 flagship, v2)

Policy space: no-speculation (= M3 zero), always-top-1, confidence-gated,
breadth-K for K∈{2,3,5}. Penalty axis: 10 ms … 20 µs (Praetor Tier D —
position only). Phase diagram: x=penalty (log), y=predictor top-1 accuracy,
cells = throughput-maximizing policy. Boundary location is Tier A/B; only
Praetor's axis position is Tier D. Bystander contention is secondary.

## II.6 Blocked claims

Frozen in `protocol_tlp01_v2.json` → `blocked_claims` and
`VERIFIABLE_DATA.md`:

- Never quote a TLP point — always S/C bracket with tier named.
- Never present M1 as achievable; M4/M5 are deployable claims.
- Never let Tier-J into a headline number.
- Never generalize beyond traced classes/harnesses; S3 absence stated.
- Never "first to parallelize" / "nobody harvests TLP".
- Phase-boundary location is never Tier-D-dependent.
- M4 Praetor 20 µs penalty is Tier D — labeled every time; promotion path csynth.

## II.7 Cost and sequencing

T0 S1 free; S2 small API cost; T1/T2 pure compute. No bare-metal dependency.
Runs in parallel with MCP-01 and CAP-01 without competing for hardware.
