# DEMO-1 v2 design: what hardware configuration buys in hybrid execution

Design only. This file contains no predictions; they go in the DEMO-1
preregistration, committed before any DEMO-1 run. Registry row: DEMO-1
(CHANGED 2026-10-12; the v1 design is SUPERSEDED).

## Thesis

Every cloud turn in hybrid execution buys one of three things:

- Capability: the local model cannot do the turn. Triggers: no parseable
  tool call, step budget, tool execution error.
- Latency: the local model could answer, but this configuration is too
  slow at this n_ctx (the turn exceeds the latency target).
- Context: n_ctx lies beyond every consumer configuration's envelope.

Hardware configuration changes only the latency purchase, and only for
turns whose n_ctx lies between configurations' envelopes. It also changes
local-turn speed everywhere. Through test-time compute (C4) it can buy back
capability: a faster configuration fits more retries or thinking inside the
same budget.

## Model: envelope x trajectory

- Envelope: the sealed cold limits, the largest n_ctx whose cold prefill
  meets the 10 s target.

  | configuration | limit (tokens) | run |
  |---|---|---|
  | XPS CPU 4B | 468 | 7f232f86 |
  | XPS GPU 4B u8 | 10,000 | c2246b1f |
  | T2S GPU 8B u8 | 16,437 | 56c116a6 |
  | T2S GPU 4B u8 | 18,500 | d2d5cc4a |
  | T2S NPU 4B | no usable envelope | N3, natstop_6b39a76e |

- Trajectory: the per-turn n_ctx distribution of a workload (its atlas).
- Hardware-attributable spend of a configuration: cloud spend on turns whose
  n_ctx is above that configuration's sealed limit and at or below 18,500,
  the best consumer limit. Turns above 18,500 are context spend for every
  consumer configuration measured.

## Claims mapped onto the model

- C1 (operating limit) sets the edge: where the envelope ends for a configuration.
- C2 (retention) moves trajectories relative to the edge.
- C3 (routing and cost): cost = trajectory mass beyond the edge x price.
- C4 (budget-quality) is the time side of the envelope: local turns inside
  the edge have time left for test-time compute.
- C5 (space shape) is where the edges sit, and their slope, per platform.
  Prefill exponents are 1.85 on T2S (65e33de8) and 2.12-2.25 on XPS
  (2b3316b6), so the edges spread differently as the target moves.
- Configuration knobs that move the edge: KV precision, residency,
  placement, model tier.

## Layers

- E, envelopes: the sealed limits above. $0.
- T, trajectory atlas (ENV-ATLAS): per-turn n_ctx for each workload x
  retention arm, computed offline with tools/h1_context_sizing.py. $0.
- P, predictions: prereg (local share, $/task, spend split, trigger mix per
  cell), committed before any V run.
- V, validation cells. NON_RESIDENT throughout. One routing policy in every
  cell.

  | cell | workload | configs | tests |
  |---|---|---|---|
  | V1 | multi_turn_base, 30 entries | XPS GPU vs T2S 4B | hardware-attributable spend about 0; same routing |
  | V2 | multi_turn_base, 30 entries | XPS CPU | escalation at turn 0; spend almost all latency |
  | V3 | multi_turn_long_context, 15 entries | XPS GPU vs T2S 4B | same escalation turn; context spend |
  | V4 | in-band cell | XPS GPU vs T2S 4B | the XPS escalates where the T2S stays local (the live side-by-side segment) |

  V4 source:
  - First choice: a retention arm that puts long_context into
    (10,000, 18,500], if the atlas finds one.
  - Otherwise: a labeled trace-driven replay of
    corpus/normalized/trajectories.jsonl.

## Outputs

- In-band share per workload: the share of turns in (10,000, 18,500].
- Prediction error: predicted vs measured local share and $/task per cell.
- Spend split, capability / latency / context, per configuration x workload.
- XPS->T2S upgrade value in $ per 1,000 tasks per workload. Break-even only
  with cited hardware prices, never guessed.
- Retention value per configuration.

## Spend

- DEMO-1 ceiling: $200, approved by Zach 2026-10-12.
- Hard per-cell caps; cheapest cells first.
- If V3 or V4 would exceed its cap, shrink n before changing the design.
