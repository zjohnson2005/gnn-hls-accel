# Cursor dispatch — D1: the hardware arm. The headline experiment.

Track: `agent`. Runs **after** C2 (E-FILTER amended). Attrib frozen.

---

## What this experiment is for

Every experiment run so far holds hardware constant. This one varies it.

```
E-FILTER (C2)   fix hardware, vary policy   →  the hardware REQUIREMENT
D1 (this run)   fix policy, vary hardware   →  the ROUTING and its OUTCOME
```

Together they close the loop that forces a design-space search. Alone, neither does.

**The sentence this run exists to produce:**

> At identical tasks, seeds and policy, changing only the hardware configuration changed cloud
> spend by X% and task accuracy by Y points — **in opposite directions.**

That proves hardware moves the objectives, that it moves them against each other, and therefore
that the part cannot be chosen by reasoning. Escalation *rate* alone is not the result — anyone can
compute that from a throughput ratio on a napkin. **The result lands on cost and accuracy.**

## D1.0 — Preflight: find a usable hardware axis

The axis must change `R_prefill` and `R_decode` **without touching model quality**, or the accuracy
half of the headline is confounded and worthless.

Candidates, in order of preference:

| Axis | Quality-safe? | Status |
|:--|:--|:--|
| Sustained power limit | yes | **unverified** — may be locked on this platform |
| `INFERENCE_NUM_THREADS` 8 vs 4 | yes | available; proxies core count, a real BOM coordinate |
| Core type P vs LP-E | yes | **blocked** — `mslice-a1a6` UNCLEAR on all six mechanisms |
| Quantization INT4 vs INT8 | **no** | different models, different accuracy. Disqualified. |

Test power cap first: set each available cap, measure `R_decode` on a fixed prompt, ≥5 repeats
under the machine lock. **Report the achieved throughput delta.** If power capping is locked or
yields under ~1.3×, fall back to thread count and say so.

Whichever axis is chosen, record it and its measured delta in the manifest. **Do not proceed
without a material, quality-safe delta** — report and stop instead.

## D1.1 — The two arms

```
ARM_FAST    chosen axis at its high setting
ARM_SLOW    chosen axis at its low setting
```

**The isolation invariant governs.** Between arms, *only* `R_prefill` and `R_decode` may differ.
Identical tasks, seeds, prompts, step types, `n_out_pred`, deadline, confinement mechanism,
reasoning mode, model IR, quantization, corpus, and tool world. Enforced in code with a test that
fails on violation.

Deadline: **one** value, fixed across both arms, chosen from C2's derived `t_pred` distribution at a
point where escalation is neither 0% nor 100% in either arm. Per-arm quantile deadlines would
destroy the rescaling check and manufacture the effect.

`n_out_pred` frozen before the run, identical across arms.

Interleave arms block by block. Do not run all of one then all of the other.

## D1.2 — What gets measured

Cloud is **enabled** for this run. Per step:

```
assigned_target, escalated (bool), t_pred, t_actual
prompt_tokens, completion_tokens, cache_read, cache_creation
completion_chars, completion_bytes        ← tokenizer-independent, per AM-021
usd_cost                                   ← from the ledger, verified 11/11
task_success                               ← the accuracy currency
wall_ns, ttft_ns, energy if available
```

Per task: success, total cost, JCT, escalation count.

**Cost budget.** Two arms × 20 tasks × a handful of escalated steps is on the order of a dollar
against $50 with $0.15 spent. Set a hard ceiling anyway and abort on breach.

## D1.3 — The primary endpoints

```
Δcost      = (cost_SLOW − cost_FAST) / cost_FAST
Δaccuracy  = success_rate_FAST − success_rate_SLOW      (percentage points)
```

Paired bootstrap over tasks, ≥10,000 resamples, with CIs on both.

**Pre-register the signs before running:**

> **P-D1a.** `Δcost` is **negative** — the slower arm escalates more, so it spends more on cloud.
> Wait: state the sign you actually predict and justify it. The slower arm escalates *more*, so
> cloud cost **rises** on the slow arm. Predict `cost_SLOW > cost_FAST`.
>
> **P-D1b.** `Δaccuracy` is **negative** — the *faster* arm keeps more work on the weaker local
> model, so its accuracy is lower. Opposite direction to cost.
>
> **P-D1c.** The two escalation-rate curves collapse under horizontal scaling by the measured
> throughput ratio: `escalation_rate_SLOW(D) ≈ escalation_rate_FAST(D · R_FAST/R_SLOW)`.

**Materiality:** `|Δcost| ≥ 20%` and `|Δaccuracy| ≥ 3 pp` to be called material. Below that,
reported as null.

**P-D1c is the self-check.** If the curves do not collapse, something other than compute speed is
driving the partition, and the isolation invariant was violated somewhere. Report the failure
prominently rather than smoothing it.

## D1.4 — The outcome that is also a result

If `Δaccuracy` comes back null while `Δcost` is material, the headline becomes:

> Changing only the hardware changed cloud spend by X% **at statistically equal accuracy** —
> money left on the table by a silicon choice.

Weaker than the opposite-directions version, cleaner to defend, and it still forces the search.
Design so that either outcome is reportable and the run cannot be wasted.

If **both** come back null, that is a genuine negative: hardware does not materially affect hybrid
execution outcomes for this workload, and the project's premise needs revisiting. Report it plainly.
Better in month two than month twelve.

## D1.5 — Carry forward

Paging gate exclusionary, baseline `e6bae93f`. Lifecycle: run dir before the first step, per-block
JSONL with flush+fsync, seal at the end. Startup dry-run. Flattened block record. Canary either
side. Machine lock per timed block. Detached launch. Placement readback recorded per block even
though placement is not the variable — it is free and it guards against the A4 question
contaminating this one.

Corrected proxy `chars // 4 + <measured scaffold>` per AM-027.

## Report

1. Preflight: the axis chosen, and its measured throughput delta with CI.
2. Isolation-invariant test result — what was verified identical between arms.
3. Escalation rate per arm at the fixed deadline.
4. **`Δcost` and `Δaccuracy` with paired bootstrap CIs.** The headline.
5. P-D1c rescaling collapse, with the residual.
6. Blocks excluded, with reasons. Total cloud spend against the ceiling.
7. One line stating whether the headline sentence is supported, and in which of the three forms.

Every number carries its run_id per AM-027(b). Report deadlines in distribution units; `R` remains
unverified in absolute terms pending A4.

## Standing constraints

No commit, push, or raw mutation. Cloud calls **are** authorized for this run, within the declared
ceiling, with the ledger recording every call. No credential value is logged, printed, hashed, or
committed — provider, model ID, and pricing table version only.
