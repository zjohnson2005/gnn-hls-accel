# Thesis: hardware configuration as a design space (2026-10-15)

Zach's configuration thesis. It is the project-level statement of what the
work claims; the paper abstracts (docs/PAPER_ISPASS_ABSTRACT.md,
docs/PAPER2_ABSTRACT.md, docs/PAPER_ERN_ABSTRACT.md) say how each paper
uses it. Registered by docs/amendments/THESIS_AMEND_2026-10-15.md, which
supersedes the thesis wording of earlier registered files without changing
any prediction, band, test or verdict.

## Core idea

Hybrid device-cloud research treats the local hardware configuration as a
fixed variable. Our work treats it as a design space. We measure
configurations on fixed hardware and observe their downstream effects on the
objectives.

## Four objectives that trade against one another

| objective | measured as |
|---|---|
| turn latency | TTFT / TTA |
| memory cost | peak working set / KV bytes |
| task quality | pass rate |
| context held before failure | largest context served before an SLO breach, a memory wall or a toolchain cap |

Cloud $ is reported as a hybrid outcome next to the four objectives. It is
not a fifth objective of the device configuration.

## Six configuration axes

1. placement (CPU / GPU / NPU)
2. session residency
3. KV / cache precision
4. weight precision
5. model tier / size
6. context window / retention

Open naming decision for Zach: the papers name the sixth axis differently.
ISPASS says "context budget" and treats retention separately; ERN says
"attention window"; the repo says "retention". Pick one name per paper and
say in each which knob it is.

## Coverage rule

Not every configuration has to move every objective. At least one
configuration must move each objective noticeably. That is already met:

| objective | axis | evidence | run_id(s) |
|---|---|---|---|
| latency | placement | warm TTA GPU 2.47 / 3.26 s vs CPU 9.29 / 11.17 s at 4k / 6k (3.4-3.8x, "about 4x") | ac4e5472 |
| memory cost and context held | KV precision | resident-session limit f16 / u8 / u4 = 15,000 / 20,000 / 26,500 | 553b3a5c, cf3555d5, e4a22dac |
| context held | placement | GPU 10,000 vs CPU 468 tokens at the 10 s SLO | c2246b1f, 7f232f86 |
| quality | placement | hybrid passes 3 -> 22 of 30 (GPU V1 -> CPU V2, same entries) | f7343708 -> 1acc8c58 |
| quality | retention | hybrid passes 4 -> 6 of 15 (V3 FULL -> V4 OBS_MASK, XPS) | 71d33f7a + ab88f47f -> a678926e |

Notes. The placement quality change is a hybrid outcome: V2 escalated every
entry at turn 0, so its 22 passes are cloud passes bought by placement. The
retention change is b 0, c 2, p 0.5 (analysis/demo1/KNOB_VS_UPGRADE_20261014b.json),
not significant.

## NOT the thesis

- "configuration sets each device's limits" (that is mechanism, or one
  objective)
- "better hardware performs better"
- "configuration only changes the latency purchase" (the old DEMO-1 wording)
- the XPS vs T2S contrast (that is a yardstick, not the claim)

## Working leap for Paper 2 and ERN (HYPOTHESES, not findings)

Hardware configuration is a hidden variable in hybrid execution and the
largest lever in the system. A hybrid result reported on one fixed
configuration is a result about that configuration.

Each sub-claim below is a hypothesis with its evidence status. None is a
finding until its test runs.

### H-A Attribution

Much of the cloud bill is caused by configuration rather than task
difficulty.

- Evidence: in V2 1acc8c58 all $8.90 was escalated at turn 0 by placement
  (TTFT 28.2-77.2 s at n_ctx 2,167-4,895, above the 10 s SLO).
- Test: DEMO-2 trigger_class split. Prediction (DEMO2_PREREG_v1): 48/60
  mechanical escalations under the default configuration (D-X, D-T), 0-3
  under tuned (T-X 0-3, T-T 0).
- Status: one supporting cell; split not yet measured.

### H-B Lever size

Configuration moves outcomes more than the routing policy does.

- Evidence, on DIFFERENT entry sets: placement +$0.297/task (f7343708 ->
  1acc8c58, BASE_30); retention -$0.124/task on XPS (71d33f7a + ab88f47f ->
  a678926e, PAIRED_15); routing policies $0 / $0.081 / $0.041 per task
  (d482c621, W-3 200: slo_escalate $0, emission_escalate $16.12,
  full_signal_bounceback $8.17).
- Test: a same-entry policy x configuration factorial (row LEVER-FACTORIAL;
  first two columns d482c621 GPU and H1-CPU).
- Status: not comparable yet (entry sets differ).

### H-C Rank reversal

Which router wins depends on the device configuration, with the model held
fixed.

- Evidence: slo_escalate made 0 cloud turns on XPS GPU (d482c621) but
  escalated 100% of entries on XPS CPU (1acc8c58). Different entry sets
  (W-3 200 vs BASE_30).
- Test: H1-CPU vs d482c621 on the W-3 pin, with a matched-rate random
  escalation baseline.
- Status: one policy's behavior differs; no ranking measured yet.

### H-D Substitution

A configuration change can substitute for buying hardware.

- Test: DEMO-2 T-X vs D-T (predicted $0.046 vs $0.356/task: tuned 16 GB XPS
  vs default 64 GB T2S), gated on passes (non-inferiority margin 0.15).
- Status: NOT YET MEASURED.

## Literature-required wording (search 2026-10-15)

Source: docs/literature/2026-10-15/LIT_CHECK_HYBRID_CONFIG_20261015.md and
the log section "2026-10-15 hybrid configuration sweep" in
docs/RELATED_SEARCHES.md.

- Claim rank reversal from hardware configuration **with the model fixed**.
  Model-size reversal is already published (EC2-Bench 2610.17816, STEPGATE
  2610.07816, CARGO 2607.20481).
- Say "configuration-aware" or "feasibility-aware" routing, never
  "hardware-aware routing" (HW-Router 2608.14575 holds that term and assumes
  quality is hardware-independent).
- Never write "existing routers are reactive". Pre-generation routers exist.
  Write instead: neither pre- nor post-generation routers model a runtime or
  hardware feasibility boundary.
- Switch cost: claim the device-cloud asymmetry, not "first to price switch
  cost". "Whose Turn Is It?" 2610.19292 prices it, cloud-only.
- Joint provisioning plus routing: claim it with device memory / hardware
  cost against a priced cloud API. RouterWise 2604.10907 has done it for
  datacenters.
- "No single configuration wins": cite ConfigSpec 2604.09722 as precedent
  (hybrid speculative decoding, no quality, no routing).
- Platform speed is not configuration. TMO 2502.11007 and EdgeWise
  2610.17560 report device-insensitivity, but only across speed, never under
  memory limits.
- "Prior work holds configuration fixed" is supported by the 2026-10-15
  search of hybrid papers only; keep the search log citation
  (docs/RELATED_SEARCHES.md, 2026-10-15 section) next to it.

## Decision rules for every future experiment

Also in CLAUDE.md ("Thesis and decision rules").

1. Name the configuration axis moved on fixed hardware.
2. Report every objective it measures, and cloud $ for hybrid cells.
3. The control is the default configuration run as a real hybrid, never an
   all-cloud or all-local run.
4. Hardware change is a yardstick only.
5. Limits, canaries and gates are infrastructure.
6. Priorities come from the papers: ISPASS first, then Paper 2 and ERN, with
   DEMO-2 in time for Oct 26.
