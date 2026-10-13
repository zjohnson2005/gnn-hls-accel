# DEMO-1 design: what inference configuration buys in hybrid execution

Design only. This file contains no predictions; they go in the DEMO-1
preregistration, committed before any DEMO-1 run. Registry row: DEMO-1
(CHANGED 2026-10-12; the v1 design is SUPERSEDED).

## Thesis

Headline (amendment docs/amendments/DEMO1_AMEND_2026-10-13c_CONFIG.md,
2026-10-13):

"On a fixed device, the inference configuration (placement, residency, KV
precision, weight precision, retention, model export) sets the context range
in which a local turn meets the latency SLO. A hybrid agent's routing, cloud
spend and latency follow from where its trajectory lands relative to that
range. Configuration changes on the same hardware move hybrid outcomes by
amounts comparable to a hardware upgrade, and the size of each effect,
including when it is zero, can be predicted before the run from sealed
limits and the workload's trajectory."

Hypothesis, not a finding: these knobs are commonly held fixed or unreported
in hybrid-execution studies. It needs search evidence in
docs/RELATED_SEARCHES.md before any paper use.

Primary axis: one-factor configuration contrasts on the XPS GPU 4B
(placement V1/V2, retention V3/V4, residency V4 -> V5a, KV precision V5a ->
V5b); the XPS vs T2S platform pairs at matched configuration are the
yardstick.

Previous thesis (2026-10-12, kept for the record; the cloud-turn taxonomy
below still holds):
> Every cloud turn in hybrid execution buys one of three things:
>
> - Capability: the local model cannot do the turn. Triggers: no parseable
>   tool call, step budget, tool execution error.
> - Latency: the local model could answer, but this configuration is too
>   slow at this n_ctx (the turn exceeds the latency target).
> - Context: n_ctx lies beyond every consumer configuration's envelope.
>
> Hardware configuration changes only the latency purchase, and only for
> turns whose n_ctx lies between configurations' envelopes. It also changes
> local-turn speed everywhere. Through test-time compute (C4) it can buy back
> capability: a faster configuration fits more retries or thinking inside the
> same budget.

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

## K rule (OBS_MASK treatment for V4; fixed 2026-10-12, before the prereg)

K is the treatment that places long_context in the hardware-sensitive band
(10,000, 18,500]. OBS_MASK keeps the first K whitespace tokens of every tool
observation (seam.retention_prompt.mask_observation, local and cloud).

Rule: K is the smallest value in the sweep {256, 512, 1024, 1536, 2048,
4096, 8192, 16384} that puts at least 90% of the jump entries in the band.
- Jump entries: the 40 long_context entries with a gold turn above 10,000
  under FULL.
- In the band: the entry's largest gold turn n_ctx under K is in
  (10,000, 18,500].
- Measured on the gold sizing in analysis/demo1/atlas/
  (tools/h1_context_sizing.py).
- If no K qualified, V4 would fall back to the labeled trace replay.

Applied to the existing sweep, in-band jump entries per K:

| K | 256 | 512 | 1024 | 1536 | 2048 | 4096 | 8192 | 16384 |
|---|---|---|---|---|---|---|---|---|
| in band | 0/40 | 10/40 | 37/40 | 20/40 | 5/40 | 1/40 | 1/40 | 1/40 |

So K = 1024. It is the only swept K at or above 90% (0.925).

Notes:
- The band is not monotone in K. A small K shrinks the ~31.7k
  get_stock_info output below the band, and a large K leaves it above.
- At K 4096 and above the output is not truncated. mask_observation still
  collapses whitespace, which changes n_ctx by a few tokens.
- The prereg reports V4 predictions at every swept K, not only at K = 1024.

## V3 / V4 pairing (2026-10-12)

V3 (FULL) and V4 (OBS_MASK, K = 1024) run on the same 15 entries, so V3 vs
V4 measures retention value on identical tasks. The pin is
derived/h1_hybrid/demo1/DEMO1_PAIRED_15.json (sha256
71faf5455559887cf0aa3c7a8317fab641b27c939b0643e501eeab5f63f9c080).
- Eligible: entries whose largest gold turn exceeds 18,500 under FULL (a
  context jump) and lies in (10,000, 18,500] under K = 1024. That is 36
  entries.
- Draw: random.Random(20260930).sample 15, kept in file order.

This replaces two earlier pins for V3 and V4: DEMO1_LONGCTX_15 for V3, and
DEMO1_LONGCTX_OBSK1024_15 for V4, which shares 8 entries with the new pin.
The earlier V4 pin included multi_turn_long_context_59, whose FULL peak
(11,057) is already in band. Under FULL that entry would add latency spend
to V3, so V3 would no longer test context spend only. Both earlier pins stay
committed and accepted by the runner, unused by DEMO-1.

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
