# Cursor dispatch — C2b: the gate was wrong. Fix the crash and run.

Track: `agent`. Attrib frozen.

**This is the only spec in force.** It assumes the repo is exactly where the C2 pilot left it:
retrieval payloads implemented, `max_steps` raised, pilot `0fe5e4c7` run and crashed. Nothing else
has changed. Ignore any other prompt document referencing C3, C4, C5 or C6 — those were drafts and
were never issued.

---

## 1. The 20,000-token gate is wrong. Here is the derivation.

The gate was set on the premise that prefill must dominate `t_pred` before escalation can select on
context. **That premise is false when `n_out_pred` is constant — which it is, because `step_type` is
hardcoded to `tool_call_synthesis`.**

```
t_pred = context/R_prefill + n_out_pred/R_decode
                             └── constant
```

A constant added to a strictly increasing function leaves it strictly increasing. **Ranking steps by
`t_pred` is therefore identical to ranking them by context, no matter how large the constant is.**
Escalation removes the highest-context steps either way.

The constant only compresses the *range* of `t_pred`, which affects how finely the deadline grid must
be spaced. Stage 1's grid was already fine enough — it produced escalation rates of 51%, 13.7%,
9.8%, 5.9% and 0% across five deadlines.

## 2. What actually bounds the measurement

```
over_provisioning = peak_KV_unfiltered / peak_KV_filtered  ∝  C_max / C_survivor
maximum achievable = C_max / C_min      ← the trajectory's own context growth ratio
```

Escalate above a threshold and the survivors are the early steps; the best case is only step 0
surviving, giving `C_max/C_min`.

Stage 1 (`1a0166b9`) per-task context ratios, computed from its sealed context-by-step table:

```
1.178  1.192  1.237  1.248  1.263  1.268  1.274  1.277  1.285  1.288
1.293  1.307  1.335  1.336  1.387  1.508  1.510  1.592  2.537  2.814
                                                        mean = 1.456
```

**Stage 1 measured 1.243 against a ceiling of 1.456 — 85% of everything that workload could show.**
Seventeen of twenty trajectories were 2–3 steps and grew context by ~30%. Stage 1 did not fail to
detect the effect. It nearly saturated a task set with almost no context growth.

## 3. The pilot already passes the correct gate

```
C2T13    650 →  5,865    ratio  9.0×
C2T19    650 →  5,105    ratio  7.9×
C2T10    650 →  9,114    ratio 14.0×
                        median  9.0×
```

**Replace the gate:** median per-task context ratio ≥ **3.0**, which permits measuring
over-provisioning up to 3× — twice Stage 1's ceiling. The pilot cleared it by a factor of three.

Absolute peak context is reported as context, never as a gate.

**The C2 workload is correct and does not need redesigning.** Do not force larger retrievals. Do not
chase 20K. The only thing that went wrong was the crash.

## 4. Fix the crash

Pilot `0fe5e4c7` died at 9,114 tokens: free memory 70 MB against a 500 MB floor, 29 sustained
page-read samples above 1.0/s, canary drift 0.306 against 0.15. Every step re-prefills the whole
context — the cache probe confirmed no cross-call reuse — so prefill activation memory scales with
context on every step.

Three changes, all of which reduce memory and none of which reduce the context ratio below the gate:

**4.1 — Cap context at 7,000 tokens.** Terminate a trajectory when the *next* step's projected
context would exceed the cap; record `terminated_reason = "context_cap"`. That leaves ~2,100 tokens
of margin under the observed 9,114 wall, and still yields a ratio of ~10.8× — more than three times
the gate.

**4.2 — Lower `max_tokens` from 512 to 128.** Shorter generations reduce peak working memory, and
the pilot shows the budget is being wasted: many steps logged `tool=None` while consuming all 512
tokens, meaning the model generated prose instead of calling a tool.

**4.3 — Constrained decoding on tool-call steps.** Steps whose control flow expects a tool call
should emit valid schema and nothing else. A well-formed call is 20–40 tokens. This fixes the
`tool=None` defect and the memory pressure in one change. Report the mechanism used.

Set `n_out_pred` from the **measured median** after these changes, not from the cap. **Keep it
constant across step types** — that is what preserves context-selectivity, and it is the one
property the whole measurement depends on.

## 5. Re-pilot, briefly

≥5 tasks. The only question is whether trajectories now complete without tripping the memory or
canary gates.

Report:

- **per-task context ratio** — distribution and median. Gate: median ≥ 3.0.
- **blocks invalidated**, with reasons. Gate: zero memory or canary invalidations.
- measured output-length median, resulting `n_out_pred`, and the `t_pred` distribution.
- tool-call rate — fraction of steps emitting a well-formed call versus `tool=None`.

**Task success is not gated here.** E-FILTER Stage 1's endpoints are resource envelopes, not
accuracy. The pilot's 0/3 success matters for a later hardware experiment, not for this run — record
it and move on.

## 6. Then run E-FILTER

- **Deadline grid derived from the measured `t_pred` distribution**, ≥8 points spanning its full
  range. Record an amendment withdrawing the pre-registered 8 s deadline: it sat below the
  achievable floor, which is why P1–P3 returned UNDETERMINED rather than being tested.
- Corrected proxy `chars // 4 + <measured scaffold>` per AM-027, if not already landed. Report which.
- Paging gate exclusionary, baseline `e6bae93f`.
- Cloud backend that **raises** — Stage 1 makes no cloud calls, and an unexpected escalation must die
  loudly rather than silently produce a hybrid trajectory labelled local-only.
- P1–P5 evaluated at the material deadline on the derived grid. Materiality 1.2×.
- **P6 — over-provisioning rises with the trajectory context ratio.** Stage 1 gave 1.243×
  (CI 1.115–1.409) against a computed ceiling of 1.456. With a median ratio ≥3.0 the measured value
  should rise materially. **Falsified if it lands inside Stage 1's CI** despite a ceiling more than
  double.

**Report the computed ceiling `C_max/C_min` alongside the measured over-provisioning**, so the
result can be read as a fraction of what was achievable. Stage 1's 85% is only interpretable because
the ceiling was computed.

## 7. Record in C9

At 9,114 tokens the KV cache is 672 MB against a 2.6 GB model — that should fit. It did not, because
re-prefill activation memory scales with context on every step:

```
architectural ceiling   40,960 tokens (max_position_embeddings)
practical ceiling       ~9,100 tokens (memory exhaustion)
```

**4.5× below** what the architecture permits, with re-prefill working memory binding rather than KV
cache size. This contradicts the capacity arithmetic in the meeting brief, which reasons from KV
size alone. Flag it; the brief is the human's to amend.

## Report, in order

1. Re-pilot context ratios and invalidation count. Stop if median ratio < 3.0 or any memory/canary
   invalidation occurs.
2. Output-length median, `n_out_pred`, tool-call rate.
3. Derived deadline grid and the withdrawal amendment.
4. `over_provisioning(D)` with bootstrap CIs, peak resident KV primary, **plus the computed
   ceiling**.
5. P1–P6 verdicts.

## Standing constraints

Machine lock every timed block, canary either side, detached launch. No commit, push, raw mutation,
cloud call, or credential load. Deadlines reported in distribution units — no absolute wall-clock
claim while `R` is unverified. Every number carries its run_id per AM-027(b).
