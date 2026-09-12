# Cursor dispatch — C5: shorten the decode floor. Supersedes C2, C3, C4.

Track: `agent`. Attrib frozen.

---

## Correction to C4 — it would have produced a null by construction

C4 proposed widening `t_pred` by varying `n_out_pred` across step types. **That breaks the
mechanism E-FILTER tests.**

The primary endpoint is peak resident KV, which is `context × 73,728`. The hypothesis is that
escalation removes big-**context** steps. Widening through `n_out_pred` makes the filter select on
predicted **output length** instead — and planning steps have long output with *short* context, so
they would escalate while contributing nothing to the memory peak. Context would contribute 0.41 s
out of a 4–38 s range: noise.

The only step that would reliably escalate is `answer_synthesis`, which happens to be both last
(peak context) and long-output. Removing it drops peak context by one step of growth — 5–10%,
under the 1.2× materiality threshold. **The run would return ≈1.05 and look like a falsification of
a hypothesis it never tested.**

Do not implement variable `n_out_pred` for E-FILTER.

## The correct derivation

```
spread = (P_max + F) / (P_min + F)

P = context / R_prefill          F = n_out_pred / R_decode      ← constant decode floor
```

`F → 0` ⟹ spread → `C_max/C_min`.  `F → ∞` ⟹ spread → 1.

**The context ratio already available is 9114/650 = 14.0.** The decode floor drags it to 1.385.

Solving for the floor that reaches 2.5 with `P_max = 5.691`, `P_min = 0.406`:

```
(5.691 + F)/(0.406 + F) ≥ 2.5   ⟹   F ≤ 3.117 s   ⟹   n_out_pred ≤ 33 tokens
```

| `n_out_pred` | floor | @650 | @9114 | spread |
|--:|--:|--:|--:|--:|
| 142 (current) | 13.33 s | 13.74 | 19.02 | 1.39 |
| 50 | 4.69 s | 5.10 | 10.38 | 2.03 |
| 33 | 3.10 s | 3.51 | 8.79 | 2.50 |
| 25 | 2.35 s | 2.75 | 8.04 | 2.92 |

`C_min ≈ 650` is floored by the **621-token template scaffold** measured in B3 — you cannot start
below the template, so `P_min` is fixed and the only levers are the decode floor and `C_max`.

**Keeping `n_out_pred` constant is required**, not incidental: it is what makes escalation purely
context-selective, which is what the memory endpoint measures.

## C5.1 — Fix the tool-call failure and the decode floor together

They are the same defect. `max_tokens=512` was being consumed with `tool=None` — the model generated
prose instead of emitting tool calls. A well-formed tool call is 20–40 tokens.

- Apply **constrained decoding** to steps whose control flow expects a tool call, so the model emits
  valid schema and nothing else. Report the library or mechanism used.
- Lower `max_tokens` to a value consistent with the target floor. Report what was chosen.
- Measure the resulting output-length distribution and set `n_out_pred` from the **measured
  median**, not from the cap.

**Target `n_out_pred` ≤ 30 tokens**, giving spread ≈2.9 at current context — comfortable margin over
the 2.5 gate, and over the 2.0 that D2's two-arm overlap will need.

Do not shorten `answer_synthesis` if it degrades task success. Report the median per step type even
though a single pooled constant is used for routing; if the final step genuinely needs long output,
report that and we will reconsider whether it is routed at all.

## C5.2 — Gates, both cheap, both stopping conditions

**Gate 1 — spread.** Report the measured `t_pred` distribution and `b/a`. **Stop if under 2.5.**

**Gate 2 — the task set must straddle local capability.** Pilot `0fe5e4c7` ran three tasks, all
`success=False` — one wrong answer, two hit `max_steps`. If the local model fails everything, the
accuracy objective is pinned at the floor and `Δaccuracy = 0 − 0 = 0` for any hardware comparison.
**D2's headline dies with it.**

On a ≥10-task pilot, report and gate on:

- **local-only success rate ∈ [0.2, 0.8]** — solvable sometimes, not never
- **tool-call rate materially above zero** — fraction of steps emitting well-formed calls versus
  `tool=None`

Outside those bands the task set is unusable for any accuracy-bearing experiment, and the fix is
task and prompt design, reported before any full run.

## C5.3 — What is NOT changing

**No corpus work.** Pilot `0fe5e4c7` established the long-context route is closed on this machine:
peak 9,114 tokens against ~33,650 required, and it died at free memory 70 MB with sustained page
reads and canary drift 0.306. Forcing larger retrievals hits the memory wall sooner, not later.

**Record the capacity finding in C9.** At 9,114 tokens the KV cache is 672 MB against a 2.6 GB
model — that should fit. It did not, because every step re-prefills the whole context (no
cross-call reuse), so prefill activation memory scales with context on every step:

```
architectural ceiling   40,960 tokens (max_position_embeddings)
practical ceiling       ~9,000 tokens (memory exhaustion)
```

**4.5× below** what the architecture permits, with re-prefill working memory binding rather than KV
size. This contradicts the capacity arithmetic currently in the meeting brief, which reasons from KV
size alone. Flag it; the brief is the human's to amend.

**Step types remain deferred.** Expanding the taxonomy is still wanted for AM-025 stratification and
would serve D2's spread requirement independently — but it must not be used to widen `t_pred` for
E-FILTER. Two different requirements; keep them separate.

## C5.4 — Then run E-FILTER

- Deadline grid derived from the measured `t_pred` distribution, ≥8 points spanning its full range.
  Amendment withdrawing the pre-registered 8 s deadline — it sat below the achievable floor and made
  P1–P3 vacuous.
- Corrected proxy `chars // 4 + <measured scaffold>` per AM-027.
- Paging gate exclusionary, baseline `e6bae93f`.
- Cloud backend that **raises** — Stage 1 makes no cloud calls; an unexpected escalation must die
  loudly rather than silently produce a hybrid trajectory labelled local-only.
- P1–P5 at the material deadline on the derived grid, materiality 1.2×.
- **P6 — the over-provisioning ratio rises with `t_pred` spread.** Stage 1 gave 1.243×
  (CI 1.115–1.409) with the mechanism at ~5% authority. Falsified if the new ratio sits inside that
  CI.

## Report, in order

1. Constrained-decoding mechanism, `max_tokens` chosen, and the **measured output-length
   distribution** with per-step-type medians.
2. `n_out_pred` set from the measured median, and the resulting decode floor `F`.
3. **`t_pred` spread `b/a`.** Stop if under 2.5.
4. **Local-only success rate and tool-call rate** on ≥10 tasks. Stop if success is outside
   [0.2, 0.8].
5. Derived deadline grid and the withdrawal amendment.
6. E-FILTER results — `over_provisioning(D)` with bootstrap CIs, peak resident KV primary.
7. P1–P6 verdicts.

## Standing constraints

Machine lock every timed block, canary either side, detached launch. No commit, push, raw mutation,
cloud call, or credential load. Deadlines in distribution units — no absolute wall-clock claim while
`R` is unverified. Every number carries its run_id per AM-027(b).
