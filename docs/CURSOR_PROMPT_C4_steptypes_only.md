# Cursor dispatch — C4: step types only. The context route is closed.

Supersedes C2 and C3. Track: `agent`. Attrib frozen.

---

## What pilot `0fe5e4c7` established

**The long-context route cannot reach the required spread on this machine.**

```
peak context reached        9,114 tokens   (C2T10, hit max_steps)
t_pred at   650 tokens      0.41 + 13.33 = 13.74 s
t_pred at 9,114 tokens      5.69 + 13.33 = 19.02 s
achieved spread b/a         1.385
required spread             ≥ 2.5
context required for 2.5    ~33,650 tokens
```

Not 2× short. **3.7× short**, and the machine stopped first: free memory 70 MB, sustained hard page
reads, canary drift 0.306.

**A capacity finding worth recording.** At 9,114 tokens the KV cache is 672 MB against a 2.6 GB
model — that should fit comfortably. It did not, because every step re-prefills the whole context
(no cross-call reuse), so prefill activation memory scales with context on **every step**.

```
architectural ceiling   40,960 tokens (max_position_embeddings)
practical ceiling       ~9,000 tokens (memory exhaustion)
```

The usable context is **4.5× below** what the architecture permits, and the binding constraint is
re-prefill working memory, not KV cache size. Record this in the C9 ledger. It contradicts the
capacity arithmetic currently in the meeting brief, which reasons from KV size alone.

**Do not retry the corpus route.** Forcing larger retrievals hits the memory wall sooner, not later.

## C4.1 — Step types, the only viable route to spread

```
t_pred = prompt/R_prefill  +  n_out_pred/R_decode
                              └── widen this
```

At short context with `n_out_pred` ranging 40 → 400:

```
0.41 +  40/10.651 =  4.17 s
0.41 + 400/10.651 = 37.96 s
spread b/a = 9.1
```

Nine-fold spread, no memory pressure, no corpus, in the regime the machine sustains.

Expand `StepType` to a declared, frozen set — adjust to what the harness can genuinely distinguish
and justify any deviation:

```
planning              decomposition, strategy      long output
tool_call_synthesis   emitting a structured call   very short output
tool_result_digest    reading a tool return        short output
reflection            reviewing trajectory state   short output
answer_synthesis      final response               long output
```

**Assignment comes from the agent's control flow, decided before the step runs**, recorded in
`routing.step_type`. Never inferred post hoc from output — that contaminates the label with the
behaviour being measured.

Fix the existing defect in the same pass: the harness currently rewrites the label to
`answer_synthesis` **after** the routing decision, so realized counts disagree with what the router
consumed. One label, decided once, used by both.

## C4.2 — Measure `n_out_pred` per type, then gate

Measure the per-type median. Do not guess. Freeze before the main run, record in the manifest, use
identical values across every arm of every downstream experiment.

**Gate: report the resulting `t_pred` spread `b/a`. If under 2.5, stop.** With the context route
closed there is no fallback, so a failure here is a genuine blocker and must be reported as one
rather than worked around.

## C4.3 — The task set must straddle local capability

**New gate, from the pilot's other failure.** Three tasks ran, **all `success=False`** — one wrong
answer, two hit `max_steps`. And `retrieve_documents` barely fired: many steps logged `tool=None`
while consuming all 512 output tokens, meaning the model generated prose instead of calling tools.

If the local model fails everything, the accuracy objective is pinned at the floor and
`Δaccuracy = 0 − 0 = 0` for any hardware comparison. **D2's headline dies with it.**

Requirements:

- **Local-only success rate must land in [0.2, 0.8]** on a ≥10-task pilot. Report it. Outside that
  band the task set is unusable for any accuracy-bearing experiment.
- **Tool-call rate must be materially above zero.** Report the fraction of steps that emitted a
  well-formed tool call versus `tool=None`. If a 4B model cannot reliably emit the tool schema,
  that is a workload-design problem to solve now, not during a measurement run.

If either fails, the fix is task and prompt design — simpler tasks, a stricter tool-forcing prompt,
or constrained decoding for the tool-call step type. Report which you chose and why.

## C4.4 — Then run E-FILTER

With spread established and the task set validated:

- Deadline grid derived from the measured `t_pred` distribution, ≥8 points spanning its full range.
  Amendment withdrawing the pre-registered 8 s deadline — it sat below the achievable floor and made
  P1–P3 vacuous.
- Corrected proxy `chars // 4 + <measured scaffold>` per AM-027.
- Paging gate exclusionary, baseline `e6bae93f`.
- Cloud backend that **raises** — Stage 1 makes no cloud calls; an unexpected escalation must die
  loudly rather than silently produce a hybrid trajectory labelled local-only.
- Stratified per step type, which AM-025 mandated and which is finally possible.
- P1–P5 at the material deadline on the derived grid, materiality 1.2×.
- **P6 — the over-provisioning ratio rises with `t_pred` spread.** Stage 1 gave 1.243×
  (CI 1.115–1.409) with the mechanism at ~5% authority. Falsified if the new ratio sits inside that
  CI.

## Report, in this order

1. The frozen taxonomy and how each type is decided from control flow.
2. Confirmation the post-hoc relabel is fixed.
3. Measured `n_out_pred` per type, with n and dispersion.
4. **`t_pred` spread `b/a`.** Stop if under 2.5.
5. **Local-only success rate and tool-call rate** on a ≥10-task pilot. Stop if success is outside
   [0.2, 0.8].
6. Derived deadline grid and the withdrawal amendment.
7. E-FILTER results — `over_provisioning(D)` with bootstrap CIs, peak resident KV as primary
   endpoint, stratified per step type.
8. P1–P6 verdicts.

Two gates before any full run. Both are cheap and both have already caught a dead regime once.

## Standing constraints

Machine lock every timed block, canary either side, detached launch. No commit, push, raw mutation,
cloud call, or credential load. Deadlines in distribution units — no absolute wall-clock claim while
`R` is unverified. Every number carries its run_id per AM-027(b).
