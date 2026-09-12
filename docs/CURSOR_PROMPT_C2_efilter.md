# Cursor dispatch — C2: E-FILTER amended run. Unblocked.

Track: `agent`. Supersedes Prompt C in `CURSOR_PROMPTS_next.md`. Attrib remains frozen.

---

## The freeze is lifted for this run, and here is the reasoning

E-FILTER's deliverable is `over_provisioning(D) = envelope_unfiltered / envelope_filtered(D)`.

Scale `R_prefill` and `R_decode` uniformly by any factor and every `t_pred` scales with them. This
run derives its deadline grid **from the measured `t_pred` distribution**, so the grid scales too,
and the same steps survive at the corresponding `D`. **The over-provisioning curve is invariant to
uniform throughput scaling** — it shifts horizontally, its shape does not change.

The unexplained 1.98× therefore invalidates *absolute* latency claims. It does not invalidate the
ratio this run exists to measure. Blocking C on A was a specification error.

What does distort the ratio is **non-uniform** variation — block 15's sporadic paging, which makes
`t_pred` inconsistent between steps inside a single run. That is handled by the gate, not by a
freeze.

**Consequence for the report:** state no absolute wall-clock target as achieved or missed. Report
deadlines only in units of the measured distribution. If a reader wants seconds, they get them with
the caveat that `R` is unverified pending A4.

## Why Stage 1 could not test its hypothesis

```
t_pred = prompt/1601.5 + 142/10.651
                         └── constant 13.332 s
```

`n_out_pred` is a per-step-type median and `step_type` is hardcoded, so the decode term is
**constant**. Prefill contributed 0.06–5.42%. Every step landed in a 0.77 s band on a 13.33 s floor.

The mechanism under test — escalation selects on size — needs the prefill term to matter. **Prefill
does not reach parity with decode until ~21,352 context tokens. Peak observed was 1,826.** The
instrument was pointed 11.7× below the regime it measures.

The hypothesis was not falsified. It was not tested.

## C2.1 — Tool payloads, the change that unblocks everything

Current tool returns are near-constant, so context grows ~164 tokens/step, linearly. Real retrieval
returns documents and is high-variance, and **that variance is what the filter selects on.**

Build a fixed, seeded corpus of document chunks. Retrieval returns **1–3 chunks of 500–2,000 tokens
each**, variable. Target context reaching **20,000–30,000 tokens** within a trajectory. Raise
`max_steps` to whatever that requires — likely 12–16.

Both changes are authorized here.

**Pilot gate:** run 2–3 tasks and report the context growth curve **before** the full run. If it
does not clear 20K, stop and report rather than entering the same dead regime twice.

This single change also moves peak KV from ~1.1% of the 12.5 GB budget to roughly 18% — the first
time the capacity claim is evaluated anywhere near the regime it concerns.

## C2.2 — Derive the deadline grid from data

The blueprint's own rule: grids come from measured `t_pred` distributions, never guessed. After the
pilot, compute the observed distribution and place **≥8 points spanning its full range**, from below
the minimum to above the maximum.

Record an amendment withdrawing the pre-registered 8 s headline deadline. Reason: it sat below the
achievable floor and made P1, P2 and P3 vacuous. **PRE-DATA** with respect to this run.

## C2.3 — Land the proxy correction

AM-027 authorized `chars // 4 + 621`, where 621 is the measured fixed chat-template scaffold. Bias
falls from **−77.4% to −1.03%**. Land it in the router for this run.

The scaffold constant is **per-model and per-template**. Re-measure it rather than inheriting it if
either changes, and record the measured value in the manifest.

## C2.4 — Carry forward everything A built

- **Paging gate, exclusionary.** Baseline-relative from `e6bae93f`: threshold 1.0 hard page
  reads/sec sustained over ≥2 consecutive samples, plus available memory ≥500 MB. Blocks that trip
  it are excluded from the ratio and **retained in `records[]` with reasons.**
- **Lifecycle.** Run directory created before the first step, per-block JSONL append with
  flush+fsync, summary and `.sealed` only at the end. A crash costs one block.
- **Startup dry-run** of the full output path before any measurement.
- **Flattened block record** — `validity` a sibling referencing `block_id`, never embedding the
  measurement.
- **Per-block telemetry** — memory before/after, page-read series, CPU total and per-core, canary
  either side, placement readback.
- Machine lock every timed block. Detached launch. No headroom refusal.

## C2.5 — Predictions

P1, P2 and P3 are re-evaluated at the material deadline **on the derived grid**, not at a fixed
wall-clock target. Materiality threshold stays 1.2×. P4 and P5 unchanged.

Add:

> **P6 — the over-provisioning ratio increases with peak context.** Stage 1 measured 1.243×
> (CI 1.115–1.409) at peak context 1,826, with the mechanism at roughly 5% authority. If that
> reading is right, the ratio should rise materially at 20–30K. **Falsified if** the ratio at 20K+
> lies within the CI of the ratio at 1.8K.

P6 is what converts Stage 1 from a failed test into a baseline point.

## Optional arm — memory-headroom escalation

From the collaborator meeting: a feasibility check on **memory headroom** as its own escalation
condition, not only a latency deadline. KV bytes are an exact function of context, so this makes
escalation context-selective by construction rather than through a prefill term contributing 5% of
the signal.

Run it as a **third arm** alongside latency-only, with headroom swept 50–150 MB — a range that
brackets the observed 48–135 MB of KV. Keep the pre-registered latency-only arm untouched so the
original claim stays evaluable.

Honest framing if it runs: this is a **mechanism** experiment, not a deployment one. An 80 MB
per-agent budget is not realistic on a 16 GB machine; realistic tightness arrives with concurrency.

Include it only if C2.1's pilot clears cleanly and the schedule allows. It is additive, not a
precondition.

## Report

1. **Pilot context-growth curve first.** Stop there if it does not clear 20K.
2. The derived deadline grid and the amendment withdrawing 8 s.
3. Measured template scaffold constant, and post-correction proxy bias.
4. run_id, blocks excluded with reasons, paging-gate verdicts.
5. `over_provisioning(D)` curve with bootstrap CIs, primary endpoint peak resident KV.
6. P1–P6 verdicts.
7. Deadlines reported in distribution units. **No absolute wall-clock claim.**

## Standing constraints

No commit, push, raw mutation, or credential load. Cloud calls are **not** part of Stage 1 — pass a
cloud backend that raises, so an unexpected escalation dies loudly rather than silently producing a
hybrid trajectory labelled local-only. Every number carries its run_id.
