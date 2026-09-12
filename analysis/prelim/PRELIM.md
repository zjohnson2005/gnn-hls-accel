# PRELIM — Is tier placement a real tradeoff, or trivially one-sided?

> **STATUS: PHASE 1 COMPLETE (per-turn only).** Phases 3–4 (trajectory policies,
> sensitivity tornado) have not run. Parameter set: `censor/study_params.yaml`
> (schema-validated by `censor/validate_params.py`).

---

## AMENDED BY PHASE 2 — read before quoting anything below

Phase 2 (`analysis/prelim/phase2/PHASE2.md`) overturns two Phase-1 statements.
The tables below are left as generated; these two corrections override them.

**1. The `above_threshold` rows do not apply at context_floor.** Phase 1 carried
both OpenAI long-context bounds because the threshold was unsourced
(`confidence: guess`, guessed at 200K). Phase 2 Arm A3 located it in published
rate cards: **272,000 tokens**. context_floor is 115,440, which is below it.
At the median turn OpenAI bills the short-context column, so every
`above_threshold` row here is inapplicable — it becomes live only in the tail
(TraceLab p90 step prefix ~467K does cross). Quote the `below_threshold` rows for
median-turn claims.

**2. The Apple / `recomputes` `u* >= 17.8%` conditional does not survive.** That
number assumed local prefill throughput does not degrade with context — it used
pp512 at 115K, a 225x extrapolation. Phase 2 Arm B brackets the degradation and
inverts on it: u-star is 17.8% only at the optimistic (flat) edge, rises to **86.7%**
under a FLOP-counted attention-theoretic model, and exceeds 100% (impossible)
under the pessimistic model. **17.8% is the optimistic edge of a bracket, not a
threshold.** Every `recomputes` row is FRAGILE on the amortized comparison; every
`persists` row is ROBUST.

**What survives unchanged:** the `usd_marginal` verdict. Arm B's inverse
sensitivity puts the marginal flip rate at 0.09–86 tok/s against a plausible band
of 30.6–8,453 tok/s, so local wins on energy in every cell under every scaling
model. The cache-rent decomposition and the overstatement ratio are also
untouched (they are cloud-side arithmetic, independent of local prefill).

---

## 0. Lead framing — what you are actually buying from a provider

The majority of what you pay a provider for at production agent context lengths
is **rent on context residency, not computation**. Local hardware's structural
advantage is not cheaper compute — **it owns its memory outright**.

This framing came out of the data, not from us. TraceLab (arXiv:2606.30560)
reported prefix tokens at **59.5%** of real API spend. Our own Phase-1 model at
context_floor, with the scoped tool-result hit rate, reproduces the same shape:

| Component | USD / turn (OpenAI mid, below_threshold) | Share |
|---|---:|---:|
| Cache read (residency rent) | 0.0292195 | **73.2%** |
| Uncached prefill | 0.00749219 | 18.8% |
| Output | 0.00321 | 8.0% |
| **Total cache-aware** | **0.0399217** | 100% |
| Naive (all input uncached) | 0.302897 | — |
| Overstatement (naive / aware) | **7.59x** | — |

TraceLab's published prefix-spend share was 59.5%. Our model at the median turn
with a 97.5% hit rate puts residency rent at **73.2%** —
same qualitative conclusion (cache reads dominate). Exact match is not required;
the parameterization is consistent with the published spend shape.

SCOPING BIAS: per-request scoping uses tool-result hit rate
(0.975), not user-initiated (0.844). **Most
favorable to cloud.** No cloud number below may be quoted without this caveat.

### AMORTIZATION UNCERTAINTY

The local cost term carries **~75x uncertainty** — `capex_utilization` spanning
0.033–1.0 crossed with `assumed_lifetime_months` spanning 24–60 — arising from
**modeling choices with no empirical content**, before any watt is measured.
Local amortized cost is reported as an **interval, never a point estimate**.
Every published TCO analysis that picks one utilization and reports a point is
manufacturing agreement that the data does not support.

---

## 1. THE GATE — is there a regime where placement is non-trivial?

**Answer: YES**

On **usd_marginal** (energy only, utilization-independent): T1 beats T2 under BOTH `persists` and `recomputes`, on all three hw configs, at both longctx bounds. Local energy is negligible next to metered token pricing. That is the strongest possible local claim Phase 1 can make, and it holds even under the cloud-favorable SCOPING BIAS. Prefill is INTERPOLATED from pp512 (optimistic for local); a slower real 115K prefill raises T1 energy but is unlikely to close a ~50–1000x gap.

Placement is non-trivial on the **amortized** comparison under `local_kv_persistence: recomputes`. There, Strix Halo and Apple amortized intervals overlap T2, so the winner depends on capex_utilization x lifetime. Under `persists`, amortized T1 beats T2 across the entire swept util×life range on all three hw configs. Discrete GPU (RTX 5090 + host) still amortizes below T2 even under `recomputes` within the swept range, but its prefill rate is a bandwidth-scaled proxy with no published pp512 — weakest local row.

Gate conditioning (must travel with the verdict):

| `local_kv_persistence` | T1 beats T2 on usd_marginal (any hw/longctx)? | T2 beats T1 on usd_marginal (any)? | Amortized depends on util×life? |
|---|---|---|---|
| `persists` | True | False | False |
| `recomputes` | True | False | True |

`local_kv_persistence` is the OUTER LOOP. These two settings are **never
collapsed**. The amortized comparison is where the persistence setting matters:
under `persists`, local wins the swept range; under `recomputes`, utilization
decides for Strix/Apple.

Item D (interpolation families): Phase-1 per-turn results under `log_normal`
and `empirical_step` are **identical**.
Trajectory quantile interpolation does not enter per-turn formulas; the choice
drops off the caveat list for Phase-1 claims.

---

## 2. Central comparison (per turn)

OpenAI mid (`gpt-5.6-terra`). Longctx bounds reported separately — never a midpoint.
T1 = 7–8B class on each hw. Prefill INTERPOLATED from pp512.

#### `local_kv_persistence = persists`

| hw | longctx | T2 $/turn | T2 naive | overstate | T1 marg | T1 amort [lo,hi] | winner (marg / amort) |
|---|---|---:|---:|---:|---:|---:|---|
| strix_halo | below_threshold | 0.0399217 | 0.302897 | 7.59x | 3.95364e-05 | [0.00012928, 0.0068383] | T1_marginal / T1_amortized_always |
| strix_halo | above_threshold | 0.0782384 | 0.60419 | 7.72x | 3.95364e-05 | [0.00012928, 0.0068383] | T1_marginal / T1_amortized_always |
| apple_m_series | below_threshold | 0.0399217 | 0.302897 | 7.59x | 1.87979e-05 | [0.000164262, 0.0110388] | T1_marginal / T1_amortized_always |
| apple_m_series | above_threshold | 0.0782384 | 0.60419 | 7.72x | 1.87979e-05 | [0.000164262, 0.0110388] | T1_marginal / T1_amortized_always |
| discrete_gpu_rtx5090 | below_threshold | 0.0399217 | 0.302897 | 7.59x | 4.19735e-05 | [7.06458e-05, 0.00221412] | T1_marginal / T1_amortized_always |
| discrete_gpu_rtx5090 | above_threshold | 0.0782384 | 0.60419 | 7.72x | 4.19735e-05 | [7.06458e-05, 0.00221412] | T1_marginal / T1_amortized_always |

SCOPING BIAS attached to every T2 number: tool-result hit rate 0.975 (favorable to cloud).
AMORTIZATION UNCERTAINTY attached to every T1 amortized interval: utilization 0.033–1.0 x lifetime 24–60 mo (~75x).
Every T1 number: INTERPOLATED prefill from pp512 (optimistic for local).

#### `local_kv_persistence = recomputes`

| hw | longctx | T2 $/turn | T2 naive | overstate | T1 marg | T1 amort [lo,hi] | winner (marg / amort) |
|---|---|---:|---:|---:|---:|---:|---|
| strix_halo | below_threshold | 0.0399217 | 0.302897 | 7.59x | 0.000738167 | [0.00241373, 0.127675] | T1_marginal / depends_on_utilization_lifetime |
| strix_halo | above_threshold | 0.0782384 | 0.60419 | 7.72x | 0.000738167 | [0.00241373, 0.127675] | T1_marginal / depends_on_utilization_lifetime |
| apple_m_series | below_threshold | 0.0399217 | 0.302897 | 7.59x | 0.000544479 | [0.00475782, 0.319737] | T1_marginal / depends_on_utilization_lifetime |
| apple_m_series | above_threshold | 0.0782384 | 0.60419 | 7.72x | 0.000544479 | [0.00475782, 0.319737] | T1_marginal / depends_on_utilization_lifetime |
| discrete_gpu_rtx5090 | below_threshold | 0.0399217 | 0.302897 | 7.59x | 0.000441451 | [0.000743007, 0.0232867] | T1_marginal / T1_amortized_always |
| discrete_gpu_rtx5090 | above_threshold | 0.0782384 | 0.60419 | 7.72x | 0.000441451 | [0.000743007, 0.0232867] | T1_marginal / T1_amortized_always |

SCOPING BIAS attached to every T2 number: tool-result hit rate 0.975 (favorable to cloud).
AMORTIZATION UNCERTAINTY attached to every T1 amortized interval: utilization 0.033–1.0 x lifetime 24–60 mo (~75x).
Every T1 number: INTERPOLATED prefill from pp512 (optimistic for local).

### Cache overstatement (C3)

| longctx_bound | naive / cache-aware |
|---|---:|
| below_threshold | 7.59x |
| above_threshold | 7.72x |

Published TCO analyses that price all input uncached overstate cloud cost by
this factor at production context length under our scoped hit rate.

### Utilization threshold (C4)

Do **not** pick a utilization. Solve for it:

| kv | hw | longctx | u* @36mo | status | statement |
|---|---|---|---:|---|---|
| persists | strix_halo | below_threshold | 0.38% | threshold | Local (strix_halo, persists, below_threshold) wins only if the box is doing useful inference work at least 0.4% of its service life (at 36.0 months lifetime). |
| persists | strix_halo | above_threshold | 0.19% | threshold | Local (strix_halo, persists, above_threshold) wins only if the box is doing useful inference work at least 0.2% of its service life (at 36.0 months lifetime). |
| persists | apple_m_series | below_threshold | 0.61% | threshold | Local (apple_m_series, persists, below_threshold) wins only if the box is doing useful inference work at least 0.6% of its service life (at 36.0 months lifetime). |
| persists | apple_m_series | above_threshold | 0.31% | threshold | Local (apple_m_series, persists, above_threshold) wins only if the box is doing useful inference work at least 0.3% of its service life (at 36.0 months lifetime). |
| persists | discrete_gpu_rtx5090 | below_threshold | 0.12% | threshold | Local (discrete_gpu_rtx5090, persists, below_threshold) wins only if the box is doing useful inference work at least 0.1% of its service life (at 36.0 months lifetime). |
| persists | discrete_gpu_rtx5090 | above_threshold | 0.06% | threshold | Local (discrete_gpu_rtx5090, persists, above_threshold) wins only if the box is doing useful inference work at least 0.1% of its service life (at 36.0 months lifetime). |
| recomputes | strix_halo | below_threshold | 7.13% | threshold | Local (strix_halo, recomputes, below_threshold) wins only if the box is doing useful inference work at least 7.1% of its service life (at 36.0 months lifetime). |
| recomputes | strix_halo | above_threshold | 3.60% | threshold | Local (strix_halo, recomputes, above_threshold) wins only if the box is doing useful inference work at least 3.6% of its service life (at 36.0 months lifetime). |
| recomputes | apple_m_series | below_threshold | 17.83% | threshold | Local (apple_m_series, recomputes, below_threshold) wins only if the box is doing useful inference work at least 17.8% of its service life (at 36.0 months lifetime). |
| recomputes | apple_m_series | above_threshold | 9.04% | threshold | Local (apple_m_series, recomputes, above_threshold) wins only if the box is doing useful inference work at least 9.0% of its service life (at 36.0 months lifetime). |
| recomputes | discrete_gpu_rtx5090 | below_threshold | 1.27% | threshold | Local (discrete_gpu_rtx5090, recomputes, below_threshold) wins only if the box is doing useful inference work at least 1.3% of its service life (at 36.0 months lifetime). |
| recomputes | discrete_gpu_rtx5090 | above_threshold | 0.65% | threshold | Local (discrete_gpu_rtx5090, recomputes, above_threshold) wins only if the box is doing useful inference work at least 0.6% of its service life (at 36.0 months lifetime). |

TraceLab anchors for reading the threshold: dedicated-box uncapped generation
share **3.3%**; human-idle-capped-1h **14.5%**. If `u*` sits above 14.5%, a
dedicated TraceLab-shaped agent stream does not keep the box busy enough for
amortized local to win.

---

## 3. Policy comparison — does switching cost bind?

`<TBD: Phase 3 — trajectory sampling, P1–P4. Not in Phase 1 scope.>`

---

## 4. Top 5 parameters by influence

`<TBD: Phase 4 tornado. Not in Phase 1 scope.>`

Phase-1 qualitative ranking (not a tornado):

1. `local_kv_persistence` (guess; ~65x; can flip marginal winner)
2. `prefill_tok_per_sec_at_115k` (guess / INTERPOLATED; loads T1)
3. OpenAI longctx threshold (guess; ~2x T2)
4. `capex_utilization` x lifetime (guess; ~75x on amortized only)
5. hw class / decode rate (published ranges; second-order once prefill dominates under `recomputes`)

---

## 5. What we must measure on hardware, ranked

1. **`prefill_tok_per_sec_at_115k`** — still the top item, and Phase 2 sharpened
   it. Arm B brackets it at 34.5–1000 tok/s on Strix Halo (29x span) and shows
   the amortized `recomputes` verdict flips inside that band. Measure cold
   prefill at depths **512 / 8,192 / 32,768 / 65,536 / 115,440** — not a single
   115K number — so the sweep discriminates the three scaling models.
2. **`local_kv_persistence`** — not measurable, but *decidable*; ~65x swing in
   T1 prefill work. Phase 2 raised its importance: `persists` is ROBUST on every
   row, `recomputes` is FRAGILE on every row. Resolve by reading the serving
   stack, before any watt is measured.
3. **`capex_utilization` in a real deployment** — a deployment property; we
   report the required threshold rather than picking a value.
4. ~~OpenAI long-context threshold~~ — **RESOLVED** by Phase 2 Arm A3: published
   at 272K, above our 115,440 context_floor.
5. ~~Discrete-GPU KV feasibility at 115K~~ — **RESOLVED** by Phase 2 Arm C1 as
   arithmetic: a 30B-class model plus a context_floor KV cache does not fit 24GB
   under any quantization, and fits 32GB in exactly one (Qwen3-30B-A3B MoE,
   q4_k_m weights, q8_0 KV). The 8B class fits both cards, but not at fp16
   weights with fp16 KV.

---

## Guardrails in force

- `local_kv_persistence` is the OUTER LOOP everywhere. Never collapsed.
- Never a midpoint for the OpenAI long-context bound.
- Never a point estimate for amortized local cost; always `usd_marginal` separately.
- Every T1 number depending on 115K prefill is labeled INTERPOLATED.
- Phase 1 is per-turn only — no policy search, trajectory sim, DES, quality, or thermal.
- A finding that one tier dominates is a valid result and is reported plainly.
