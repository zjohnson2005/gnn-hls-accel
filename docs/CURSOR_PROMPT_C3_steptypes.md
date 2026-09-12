# Cursor dispatch — C3: widen `t_pred` via step types, then run E-FILTER

Track: `agent`. Replaces C2's corpus work as the **primary** route. Attrib frozen.

---

## The constraint that governs everything downstream

For a single fixed deadline to produce partial escalation on **two** hardware configurations — which
D2 requires — the spread of `t_pred` within a trajectory must exceed the hardware ratio:

```
fast arm:  t_pred ∈ [a/k, b/k]        slow arm:  t_pred ∈ [a, b]
shared D exists  ⟺  b/a > k
```

**Current spread: 14.10 / 13.33 = 1.058.** At a 2× hardware delta the fast arm escalates 0% and the
slow arm 100% — a local-versus-cloud comparison, not a hybrid one.

So widening `t_pred` is not an E-FILTER nicety. It is the precondition for every hardware experiment
that follows.

## Two routes, and this prompt takes the cheap one

```
t_pred = prompt/R_prefill  +  n_out_pred/R_decode
         └── long contexts   └── real step types
             (C2's route)        (this route)
```

`n_out_pred` is currently constant because `step_type` is hardcoded to `"tool_call_synthesis"` for
every step, and `StepType` admits only two values. Give it real types with genuinely different
medians and the decode term varies by an order of magnitude across steps, with no corpus, no raised
`max_steps`, and no longer runs.

Both routes remain valid and they compose. Take this one first because it is a labelling change,
not a data-collection project.

## C3.1 — Expand the step-type taxonomy

Amendment authorized. Expand `StepType` to a declared, frozen set. Suggested — adjust to what the
harness can actually distinguish, and justify any deviation:

```
planning            decomposition, strategy       long output
tool_call_synthesis emitting a structured call    very short output
tool_result_digest  reading a tool return         short output
reflection          reviewing trajectory state    short output
answer_synthesis    final response                long output
```

**Assignment must come from the agent's own control flow**, decided **before** the step runs and
recorded in `routing.step_type`. It must never be inferred post hoc from the output, or the label is
contaminated by the behaviour being measured.

Note the existing defect while you are here: the harness currently rewrites the label to
`answer_synthesis` **after** the routing decision, giving realized counts that disagree with what
the router consumed. Fix that — one label, decided once, used by both.

## C3.2 — Measure `n_out_pred` per type

Run a measurement pass to establish the per-type median output length. Do not guess these.

Freeze them before the main run, record them in the manifest, and use identical values across every
arm of every downstream experiment. **These are the numbers that create the spread**, so a wrong one
silently narrows it.

Report the resulting `t_pred` distribution and its spread `b/a`. **Gate: if `b/a < 2.5`, stop and
report** — that is insufficient headroom for a 2× hardware experiment plus margin, and the corpus
route becomes necessary after all.

## C3.3 — Land AM-025 stratification, now that it is possible

Per-step-type stratification was mandated by AM-025 and has been impossible because the taxonomy had
two values and only one was ever assigned. With real types:

- H1's falsification criterion applies **per type**, not to a pooled median.
- S1, S2, S5 and S8 report per-type as primary, pooled as secondary.
- Report the step-type mixture of the benchmark alongside every effect, so a reader can see what
  mixture the number is a property of.

## C3.4 — Then run E-FILTER amended

With the spread established:

- Derive the deadline grid from the measured `t_pred` distribution, ≥8 points spanning its full
  range. Record the amendment withdrawing the pre-registered 8 s headline deadline — it sat below
  the achievable floor and made P1, P2 and P3 vacuous.
- Land the corrected proxy `chars // 4 + <measured scaffold>` per AM-027.
- Paging gate exclusionary, baseline `e6bae93f`.
- Cloud backend that **raises** — Stage 1 makes no cloud calls, and an unexpected escalation must
  die loudly rather than silently produce a hybrid trajectory labelled local-only.
- P1–P5 re-evaluated at the material deadline on the derived grid. Materiality 1.2×.
- **P6 — the over-provisioning ratio increases with `t_pred` spread.** Stage 1 measured 1.243×
  (CI 1.115–1.409) with the mechanism at roughly 5% authority. If that reading is right, the ratio
  rises materially once the filter has real discriminating power. Falsified if the new ratio lies
  within Stage 1's CI.

The corpus route from C2 stays on the table as an **additive** widening — long contexts widen the
prefill term as well, and the two compose. It is no longer a blocker.

## Why this ordering is right

Step types are cheaper than a corpus, they unblock D2 as well as E-FILTER, and they settle an
outstanding amendment. Deferring the taxonomy as scope creep was a mistake — it is the shortest path
to the widest set of downstream results.

## Report

1. The frozen taxonomy, and how each type is decided from control flow.
2. Confirmation that the post-hoc relabel defect is fixed — one label, used by router and record.
3. Measured `n_out_pred` per type, with n and dispersion.
4. **The resulting `t_pred` distribution and its spread `b/a`.** Stop here if under 2.5.
5. The derived deadline grid and the withdrawal amendment.
6. E-FILTER results: `over_provisioning(D)` with bootstrap CIs, primary endpoint peak resident KV,
   stratified per step type.
7. P1–P6 verdicts.

Deadlines in distribution units — no absolute wall-clock claim while `R` is unverified.

## Standing constraints

Machine lock every timed block, canary either side, detached launch, no commit, no push, no raw
mutation, no cloud call, no credential load. Every number carries its run_id per AM-027(b).
