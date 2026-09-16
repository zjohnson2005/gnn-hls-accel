# CAP-01 methodology: capability scaling under a fixed budget

Protocol template: `cap01/protocol_cap01_v2.json`.

## Document map (repo paths)

Prompt / conversation aliases that are **not** files in this repo:

| Conversational name | Use instead |
|---|---|
| `CAP01_Capability_Scaling_Arm_Spec.md` | `METHODOLOGY_CAP01.md` + `cap01/protocol_cap01_v2.json` |
| "v2 redirect doc" / five-domain redirect prompt | already folded into `protocol_cap01_v2.json` and this methodology (supersedes v1 corpus/analysis) |

Authoritative on-disk paths:

- Methodology: `apu_characterization/METHODOLOGY_CAP01.md`
- Protocol template: `apu_characterization/cap01/protocol_cap01_v2.json`
- Predictions: `apu_characterization/PREDICTIONS_CAP01.md`
- Arm README: `apu_characterization/cap01/README.md`
- Verification audit: `apu_characterization/cap01/cap01_verification_audit.md`
- Died ledger: `apu_characterization/cap01/died_ledger.json`
- Prior template (historical): `apu_characterization/cap01/protocol_cap01_v1.json`

## Scope and validity

CAP-01 tests whether a measured turn-path floor changes solve rate for a
best-of-N verification loop under a fixed task budget. It does not measure
general intelligence, arbitrary agent architectures, or a live model during
timed execution.

Real model candidates are generated offline before measurement, frozen per
task, and replayed in one seed-determined order. For a given task and seed,
LangGraph, Rust, and raw Python receive prefixes of the same candidate
sequence and the same latency-draw sequence. This matched-pair property is the
causal mechanism of the arm.

Passing bare-metal artifacts use the narrow `capability_scaling` validity
class. WSL2 smoke artifacts are `debug_only`. Neither class licenses
production CPU-share claims.

## Pre-measurement lock

The source protocol is a template until P0 is complete. The lock command
requires:

- a 250-task corpus manifest with 50 tasks in each of function-calling,
  text-to-SQL, code synthesis, math, and structured extraction, with source,
  version, provenance, license, verifier, and contamination note per task
- a pool manifest with at least 2,048 real model candidates per task
- a generation configuration with model, temperature, prompt template, and
  token provenance
- a pinned verifier manifest, including the adopted BFCL checker hash
- a single 50-shuffle calibration/classification manifest covering all five
  domains after every pool exists

It writes a new immutable locked protocol. It never edits or silently replaces
the source template.

The pool depth is 2,048 rather than the initial target of 128. This amendment
was made before data because a 128-candidate pool would be exhausted well
before the 5 ms primary cells, forcing all harnesses to the same outcome
for pool-censoring reasons. Pool exhaustion remains a hard gate even at the
larger depth.

## Corpus calibration

The calibration pass verifies every candidate and evaluates 50 deterministic
pool shuffles per task:

- SATURATED: P(solved by N=4) > 0.9
- DEAD: P(solved by N=2,048) < 0.05
- SCALING: all other tasks

The original DEAD-at-128 label is retained as secondary context. The primary
analysis population is SCALING; all tasks remain in a secondary analysis.
Classification is frozen once over the complete five-domain corpus before
timing begins. A domain with fewer than 20 SCALING tasks is flagged before P2
and requires an explicit protocol amendment.

## Five-domain corpus and contamination

CAP-01 v2 uses only single-generation, static-verifier tasks:

- BFCL v4 single-turn and parallel-call subsets; Multi-Turn is excluded
- BIRD static single-shot text-to-SQL; interactive modes are excluded
- HumanEval+ preferred for code synthesis, with MBPP as fallback
- exact-answer MATH/AIME-style problems; proof-graded items are excluded
- fixed-document structured extraction with JSON Schema and double-keyed truth

Multi-turn service tasks, multi-step shell tasks, BIRD interactive mode, and
BFCL Multi-Turn are deferred to CAP-02 because they require live-environment
interaction and cannot preserve CAP-01's frozen matched-pair mechanism.

D3/D4 memorization risk is disclosed per task. Recent or perturbed variants
are preferred where practical. Any residual memorization changes absolute
solve-rate level, but frozen candidate replay keeps it from becoming a
between-harness confound.

D5 normalization is frozen in the protocol before generation: NFKC and
whitespace normalization, task-declared date ordering, path-declared
currency/percent handling, null/missing distinction, exact field names, and
order-sensitive arrays except at explicitly frozen paths.

## Timed loop

Each harness implements the same state machine:

1. request the next frozen candidate
2. wait for the seeded lognormal model latency
3. receive the candidate
4. run the deterministic local verifier
5. record the verdict
6. stop on success or repeat while budget remains

The lognormal median is one of 4000, 1000, 100, 20, 10, or 5 ms and sigma is
0.6, matching the promoted collapse sweep. The draw seed is derived from task
ID and experiment seed, never from harness.

Session setup completes before the task-ready barrier. The primary budget uses
`CLOCK_MONOTONIC`. A candidate counts only when its verifier verdict lands
before the deadline. Work in flight at the deadline is abandoned. The loop
does not sleep past the remaining budget.

Verifier CPU is `TOOL_COMPUTE`: excluded from strict floor and included in
process CPU. G7 includes measured verifier wall in the attainable-rate
denominator because omitting it would make verifier-heavy cells fail for a known,
non-harness cost.

## Matrix

Primary axes:

- harness: LangGraph, Rust, raw Python
- model-latency median: 4000, 1000, 100, 20, 10, 5 ms
- wall budget: 2 s, 10 s
- seed: 0 through 4
- instrument mode: throttle

The fixed budget is a production resource ceiling, not a claim about user
wait tolerance. D1 function-calling and D5 extraction use 2 s as their primary
tier. D2 text-to-SQL, D3 code, and D4 math use 10 s. Every domain still runs
both tiers; the other tier is a pre-registered secondary.

Measurement is strictly serial and resume-markered. The 2 s tier completes
first, followed by the 10 s tier. Analysis may fan out only over immutable
completed run directories.

The optional energy variant covers the 10 s tier at 4000 and 5 ms. It runs
only on a qualifying bare-metal RAPL host after observer validation. RAPL
unavailability is a recorded drop, not a wall-primary failure.

## Frozen gates

- G1: standing TurnTrace accounting and 15 percent residual limit.
- G2: budget overshoot no greater than 2 percent; no more than 1 percent of
  task-cells violate; candidates started equals counted plus abandoned.
- G3: consumed candidate IDs are a prefix of the seed-ordered pool and all
  harness prefixes share the same underlying sequence. Any divergence or pool
  exhaustion fails.
- G4: every verdict is re-executed once offline. A flip removes that task
  globally and appends a ledger entry.
- G5: all five seeds are present per required cell.
- G6: each harness floor is re-measured at the 20 ms anchor on the target
  host. A reference-band miss recalibrates the x-axis and does not abort.
- G7: measured candidates/s is within 25 percent of the rate implied by actual
  latency draws, host-measured floor, and measured verifier wall. Violations
  remain visible.
- G8: in-situ TOOL_COMPUTE wall parity across harnesses. Because all harnesses
  share one verifier callable, G8 tests harness dispatch into that shared
  verifier — not independent verifier implementations. Un-sharing the
  verifier re-opens Axis 1 / G8. Half-width is
  max(relative ±15% of median, absolute ±0.25 ms, max within-harness IQR).

Thresholds do not move after measurement. Died-ledger entry #5 records one
exception: G8's absolute/IQR floors were amended mid-audit after relative-only
±15% falsely failed sub-millisecond domains. That amendment is instrument
physics, not convenience, and extracts the standing rule that any future gate
over sub-millisecond quantities freezes a timer-resolution floor at protocol
freeze time, not at failure time.

## Statistics and verdict

The single primary test is 5 ms, each domain at its own frozen primary tier,
SCALING tasks pooled across all five domains, LangGraph versus Rust. The exact
two-sided McNemar test operates on the pooled matched task-seed discordances.
Effect size is paired solve-rate difference in percentage points with a
task-clustered 10,000-resample BCa interval. Leave-one-seed-out sensitivity
must preserve effect direction.

The exhaustive secondary family is Holm-corrected: five per-domain primary
contrasts, five off-tier contrasts, pooled LangGraph versus raw Python at
domain-primary tiers, and pooled plus per-domain 4000 ms positive controls.
If the positive-control null fails in any domain or pooled, CAP-01 flags the
domain confound and stops before a headline.

The capability-versus-floor fit is descriptive over only three measured
x-coordinates. It prices the axis and is not inferential evidence for a law.

## Tier D quarantine

No Praetor arm runs. The 10 to 50 microsecond Tier D interval is rendered only
as a dashed extension beyond raw Python with this label:

> Tier D design target - projection from measured relationship, not a result.
> Promotion path: csynth.

The caption states that this is a 10x to 20x extrapolation beyond the last
measured floor and inherits both fit and measurement uncertainty. Phrasing
that says Praetor achieves, solves, or recovers a measured value is blocked.

## Rust harness bar (before primary-cell re-run)

"Builds cleanly" is **not** an acceptable bar for the LangGraph-vs-Rust
primary comparison. MCP-01 raw stdio showed that payload-scaling copy paths
can look like physics until measured. Before Axes 1/3/4 G8/G3/clock re-runs
that include Rust:

1. `cargo test` in `cap01/rust_harness` must be non-empty and green (parse /
   escape / large-content extract smoke).
2. Python `test_harnesses.py` must pass `test_actual_rust_binary_contract` and
   `test_rust_large_payload_is_not_echoed` (response echoes ids only; 256 KiB
   content must not appear in the response).

Compile-only green without those smokes does not clear the Rust column.

## Uniform-zero protocol (triage acceptance gate)

A domain that triages at **uniform zero** (every task `probable_DEAD` / p̂≈0 at
n=16) on a **gold-verified** verifier is **not** yet accepted as capability
DEAD. Before acceptance, run this recursion in order:

1. **Prompt-completeness audit** — render the exact generation prompt for a
   fixed sample of tasks. Confirm the prompt contains every artifact solving
   requires (e.g. BIRD schema DDL for text-to-SQL; target JSON Schema body for
   structured extraction). Distinguish corpus-field gaps from template-
   interpolation gaps. Healthy band spreads on other domains already prove
   those prompts are solvable; do not re-audit them under this clause.
2. **Perturbed-gold canonicalization check** — re-serialize gold answers with
   meaning-preserving surface changes (JSON key shuffle / whitespace; SQL
   casing; etc.). All must still pass. This catches verifiers that compare raw
   strings while gold self-check passes trivially. Permanent gate:
   `tests/cap01/test_verifier_ground_truth.py`
   (`test_verifier_canonicalization_invariance_perturbed_gold`).
3. **Frontier-model probe** — after any prompt/verifier fix, run a small
   frontier probe (e.g. gpt-4o, 5 tasks × 4 candidates) through the same pinned
   verifier and **exact** post-fix rendered prompt. Pre-registered reading:
   - frontier ≈ 0 and target model ≈ 0 → still broken; do not accept DEAD
   - frontier scores well and target model ≈ 0 → DEAD is model-relative
     capability data for the study model; accept with this evidence attached

"DEAD because unsolvable-as-prompted" is an instrument bug. "DEAD for the
target model, solvable by a stronger one" is a CAP-01 finding. Ledger every
scoring- or prompt-relevant change; re-lock; re-triage only the affected
domains.
