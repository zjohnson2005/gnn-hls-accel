# Cursor dispatch — C6: cap context, restore the workload, run E-FILTER

Supersedes C2, C3, C4 and C5. Track: `agent`. Attrib frozen.

**This spec is derived from Stage 1's measured data rather than from a model of the mechanism.**
Three prior specs reasoned from theory and each got the lever wrong. The derivation below is
checkable against `1a0166b9`'s sealed context-by-step table.

---

## 1. What actually bounds the result

With `n_out_pred` **constant**, `t_pred` is strictly increasing in context, so ranking by `t_pred`
*is* ranking by context. **Escalation is 100% context-selective regardless of the decode floor.**
The floor only compresses the `t_pred` range, which affects deadline-grid resolution — and Stage 1's
grid was already fine enough, yielding escalation rates of 51%, 13.7%, 9.8%, 5.9%, 0%.

```
over_provisioning = peak_KV_unfiltered / peak_KV_filtered  ∝  C_max / C_survivor
max achievable     = C_max / C_min        ← the trajectory's own context growth ratio
```

Stage 1 per-task context ratios, from the sealed run:

```
1.178  1.192  1.237  1.248  1.263  1.268  1.274  1.277  1.285  1.288
1.293  1.307  1.335  1.336  1.387  1.508  1.510  1.592  2.537  2.814
                                                        mean = 1.456
```

**Stage 1 measured 1.243 against a 1.456 ceiling — 85% of everything the workload could show.**
Seventeen of twenty trajectories were 2–3 steps and grew context by roughly 30%. Stage 1 did not
fail to detect an effect; it nearly saturated a task set with almost no context growth.

**Correction to the record:** the previously stated requirement of ~20,000 or ~33,650 tokens was
derived from the belief that prefill must dominate `t_pred`. It need not. The requirement is on
**context ratio**, not absolute context.

## 2. The C2 workload was correct

```
C2T13   650 →  5,865    ratio  9.0×
C2T19   650 →  5,105    ratio  7.9×
C2T10   650 →  9,114    ratio 14.0×
```

Those support over-provisioning up to 14× — nearly ten times Stage 1's ceiling. **Restore the
retrieval payloads.** The pilot's only failure was the crash.

## 3. Cap context below the memory wall

Pilot `0fe5e4c7` died at 9,114 tokens with free memory 70 MB, sustained hard page reads and canary
drift 0.306. Every step re-prefills the full context (no cross-call reuse), so prefill activation
memory scales with context on every step.

**Cap trajectories at 8,000 tokens of context.** That yields a 12.3× ratio — four times Stage 1's
ceiling — while staying clear of the wall. Terminate a trajectory when the *next* step's projected
context would exceed the cap, and record `terminated_reason = "context_cap"`.

**Do not extend context past the cap to chase a bigger number.** More context buys nothing here and
costs the run.

## 4. Gate 1 — context ratio, not absolute peak

Pilot ≥5 tasks. Report **per-task `C_max/C_min`**, the distribution and the median.

**Pass: median per-task context ratio ≥ 3.0.** That permits measuring over-provisioning up to 3×,
which is twice Stage 1's ceiling and well inside what the C2 payloads already delivered.

Report absolute peak context as context, not as a gate.

## 5. Gate 2 — the task set must straddle local capability

Pilot `0fe5e4c7` ran three tasks, **all `success=False`** — one wrong answer, two hit `max_steps`.
`retrieve_documents` barely fired; many steps logged `tool=None` while consuming all 512 output
tokens.

If the local model fails everything, the accuracy objective is pinned at the floor and
`Δaccuracy = 0 − 0 = 0` for any hardware comparison. **D2's headline dies with it.**

On ≥10 tasks, report and gate on:

- **local-only success rate ∈ [0.2, 0.8]**
- **tool-call rate materially above zero** — fraction of steps emitting a well-formed call versus
  `tool=None`

Outside those bands the task set is unusable for any accuracy-bearing experiment. The fix is task
and prompt design, reported before any full run.

## 6. Shorten outputs — for three reasons, none of which is selectivity

`max_tokens=512` was being consumed with `tool=None`. A well-formed tool call is 20–40 tokens.

Apply **constrained decoding** to steps whose control flow expects a tool call, and lower
`max_tokens` accordingly. Set `n_out_pred` from the **measured median**, not from the cap. Keep it
**constant across step types** — that is what preserves context-selectivity.

Why this matters, precisely:

- **D2 needs `t_pred` spread.** Its two hardware arms must overlap at a shared deadline, requiring
  `b/a > k`. With the current 13.33 s floor, `b/a = 1.385` and a 2× hardware delta gives 0% and 100%
  escalation — a local-versus-cloud comparison, not a hybrid one. Shorter outputs fix this.
- **Memory.** Shorter generations reduce the pressure that crashed the pilot.
- **The `tool=None` defect and long outputs are the same failure**, and constrained decoding fixes
  both.

**It is not needed for E-FILTER's selectivity.** Prior specs claimed otherwise; that was wrong.

Report the resulting `t_pred` spread `b/a` as information. It gates D2, not this run.

## 7. Then run E-FILTER

- Deadline grid derived from the measured `t_pred` distribution, ≥8 points spanning its full range.
  Amendment withdrawing the pre-registered 8 s deadline — it sat below the achievable floor, which
  is why P1–P3 returned UNDETERMINED.
- Corrected proxy `chars // 4 + <measured scaffold>` per AM-027.
- Paging gate exclusionary, baseline `e6bae93f`.
- Cloud backend that **raises**; Stage 1 makes no cloud calls, and an unexpected escalation must die
  loudly rather than silently produce a hybrid trajectory labelled local-only.
- P1–P5 at the material deadline on the derived grid, materiality 1.2×.
- **P6 — over-provisioning rises with the trajectory context ratio.** Stage 1 gave 1.243×
  (CI 1.115–1.409) against a 1.456 ceiling. With a median ratio ≥3.0 the measured value should rise
  materially. **Falsified if it sits inside Stage 1's CI** despite a context ratio more than double.

P6 is now a sharp test, because the ceiling is computable in advance from the pilot's context
ratios. Report the predicted ceiling alongside the measured value.

## 8. Record in C9

At 9,114 tokens the KV cache is 672 MB against a 2.6 GB model — that should fit. It did not,
because re-prefill activation memory scales with context on every step:

```
architectural ceiling   40,960 tokens (max_position_embeddings)
practical ceiling       ~9,100 tokens (memory exhaustion)
```

**4.5× below** what the architecture permits, with re-prefill working memory binding rather than KV
size. This contradicts the capacity arithmetic in the meeting brief, which reasons from KV size
alone. Flag it — the brief is the human's to amend.

## Report, in order

1. Pilot per-task context ratios, distribution and median. **Stop if median < 3.0.**
2. Local-only success rate and tool-call rate on ≥10 tasks. **Stop if success outside [0.2, 0.8].**
3. Constrained-decoding mechanism, measured output-length median, resulting `n_out_pred` and
   `t_pred` spread `b/a`.
4. Derived deadline grid and the withdrawal amendment.
5. `over_provisioning(D)` with bootstrap CIs, peak resident KV primary, **plus the computed ceiling
   `C_max/C_min`** so the measured value can be read as a fraction of what was achievable.
6. P1–P6 verdicts.

## Standing constraints

Machine lock every timed block, canary either side, detached launch. No commit, push, raw mutation,
cloud call, or credential load. Deadlines in distribution units. Every number carries its run_id per
AM-027(b).
