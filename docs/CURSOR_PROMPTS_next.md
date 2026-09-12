# Three dispatch prompts — copy the section you need

**Ordering matters.** A is a measurement freeze and blocks C. B needs no measurement and runs
during the freeze. Both tracks stop measuring until A reports.

---
---

# PROMPT A — Throughput integrity. **MEASUREMENT FREEZE.**

Track: `agent`. Attrib track is frozen from measurement until this reports.

## Orientation

Call `seam_status()`, `seam_pins()`, `seam_platform()`. Read `docs/EXPERIMENT_escalation_filter.md`
and the E-FILTER results report.

## The problem

Two sealed runs, 23 minutes apart, nominally identical config, zero quiesce deviations:

```
pilot  d8f0875b   R_prefill 3174.6   R_decode 21.21
full   1a0166b9   R_prefill 1601.5   R_decode 10.651
ratio               1.983              1.992
```

A uniform ~2× on **both** phases. Both series are stable plateaus, not noise — full-run CV 0.036
across 8 scored generations. The authorized frequency detector reported 100% of maximum on all 8
CPUs in **both** runs.

Until this is explained, **no throughput number this project has produced can be trusted**,
including numbers already in external documents. Nothing else proceeds.

## Step 1 — diff the manifests before running anything

Compare the two sealed manifests **field by field**, complete, no summarising. Report every
difference, not just the ones that look relevant.

Specifically confirm or deny that these were identical: `INFERENCE_NUM_THREADS`, thread-count
inference, `SCHEDULING_CORE_TYPE`, `ENABLE_CPU_PINNING`, process affinity mask, model IR hash,
OpenVINO version, power plan, and any environment variable read by the backend.

**A thread-count or core-placement difference between runs produces exactly 2×.** Recall that
OpenVINO defaults to P-core placement regardless of thread count (the A0 finding), so a 8→4 thread
difference is both plausible and invisible in utilization. This may resolve the whole thing without
a single measurement — check it first.

## Step 2 — reproduce it deliberately

If step 1 does not resolve it, run a 2×2 under the machine lock:

```
                    clean machine        4-process CPU burn on P-cores
lock held               A1                          A2
```

Fixed prompt, fixed config, ≥5 repeats per cell, randomized order, cooldown between. Report
R_prefill and R_decode per cell with CIs.

**If the burn reproduces ~2×, contention is confirmed** and the cause is that attrib's
`runtime-pilot` held 314% CPU on the same four P-cores OpenVINO selects by default. If the burn
does **not** reproduce it, contention is excluded and the cause is a power or clock operating
point — say so plainly, because that is a much worse problem.

## Step 3 — the lock is asymmetric, which means there is no lock

E-FILTER's dispatch never required the machine lock; only attrib's did. **A lock one side takes and
the other ignores is not a lock.** This is a specification defect, not an agent error.

Make it symmetric: every timed block in **every** track wraps in
`seam.locks.exclusive(repo_root / ".locks" / "machine")`. Acquire, measure, release, never held
across analysis. Record acquire/release timestamps in the sealed summary.

## Step 4 — quiesce is checking the wrong thing

`quiesce.forbidden_processes` verifies a **process-name allowlist and never measures load**. It
recorded `deviations: []` for a run that may have been contended. A name list cannot see an
unlisted process, and every future track will be unlisted.

Replace or supplement with **measured** system load: total CPU utilization sampled across the
quiesce window, per-core utilization on the P-cores specifically, and available memory. Fail the
gate on measured load above a declared threshold, not on a name match.

## Step 5 — the authorized throttle detector is inert

PDH `Processor Frequency` and `% of Maximum Frequency` return **nominal** clocks: 2100.0 ×4 P and
1600.0 ×4 LP-E, unchanged between idle and a 4-process burn, and identical across a 1.98×
throughput difference. Detector (a) of the three authorized on 2026-08-02 does not work on this
platform. Say so in the report.

Implement a **calibrated compute canary** as the replacement, because it needs no counter that
this platform lacks: a fixed-work synthetic kernel of known size, run immediately before and
immediately after every measurement block, pinned to the same cores as the workload. Its runtime is
a direct measure of the delivered operating point. Declare a block invalid if the canary drifts
more than a stated threshold across it.

Secondary defect to fix while you are there: `FrequencySampler.summary()` samples `mhz_per_cpu` and
then discards it, keeping only the percentage. Retain both.

## Report

Step 1's manifest diff in full. Then the 2×2 table if you ran it. Then a plain verdict:
**contention, configuration, or unexplained.** If unexplained, say so — do not offer a mechanism you
cannot evidence.

Do not resume any other measurement until this reports.

---
---

# PROMPT B — Offline analyses. No measurement. Runs during the freeze.

Track: `agent`. Pure analysis over sealed data — no new runs, no lock needed.

## B1 — INT4/INT8 provenance forensics

The project's headline dequantization result is **INT4 15.1 tok/s vs INT8 7.4 tok/s = 2.04×**. The
unexplained session shift is **1.98×**. Those are the same number and the coincidence has to be
resolved.

Find the sealed run or runs behind 15.1 and 7.4. Report:

- run IDs, timestamps, and whether the two arms came from **one run or two**
- if one run: were the arms **interleaved and randomized**, or measured in blocks?
- if two runs: how far apart, and what does the manifest diff show?
- the warmup throughput series for each arm, so a plateau shift is visible if present
- whether a calibrated canary or any within-run stability check existed at the time

**Verdict, one of three:** SURVIVES (interleaved within one run, randomized), CONTAMINATED (separate
sessions or blocked arms — the ratio cannot be distinguished from the session shift), or UNKNOWN
(provenance insufficient to tell).

This gates an external communication. Report the verdict prominently and do not soften it.

Apply the same test to the **29%-of-bandwidth-ceiling** figure, which depends on which operating
point the machine was in.

## B2 — The tail-latency replay

The run produced a genuine finding: no deadline on the grid delivers the p95 target, because
escalation triggers on *predicted* latency while the predictor's length term is a **median**, so
the filter never orders steps by *realized* latency.

Test whether that is structural or an artifact of the estimator choice. Re-run the offline replay
on sealed run `1a0166b9` with `n_out_pred` set to the **p90** of realized completion length instead
of the median, then again at **p99**. Report for each:

- p95 realized step latency achieved, against the 23.52 s unfiltered baseline
- escalation rate at the material deadline
- KV over-provisioning ratio
- whether any grid point now delivers a tail target

Also report the **realized completion-length distribution** over all 51 steps: mean, median, p90,
p99, max, CV, and a histogram. **This is the diagnostic that decides the claim.** If the
distribution is tight, the median is adequate and the finding is weak. If it is heavy-tailed, a
point estimate is structurally inadequate for tail control and the finding generalizes to every
router in the length-prediction literature.

No new measurement — this is a replay over data you already hold.

## B3 — The proxy's template blindness

The `chars // 4` proxy regresses on native tokens with slope 0.9594 and intercept **637.13 tokens**
at R² 0.9983. Linear and badly offset, not noisy. The intercept is chat-template overhead the proxy
cannot see, because it counts message content characters only.

Report what fraction of the 637 tokens is template scaffolding by rendering an empty conversation
through the template and counting. Propose the corrected proxy — content estimate **plus** measured
template token count — and report the residual bias after correction. Do not land the change in the
router yet; the pre-registration froze the predictor and changing it is a human authorization.

## B4 — Emit the degenerate statistic as null

`p95_required_decode_rate` in the unfiltered block is computed at the 1e9 sentinel and returns
~1.9e-7 tok/s — arithmetically correct, meaningless, and quotable by accident. Emit `null` with a
reason field rather than a number.

---
---

# PROMPT C — E-FILTER, amended run. **Blocked until Prompt A reports.**

Track: `agent`. Do not start until the throughput integrity verdict exists.

## Why the first run could not test its hypothesis

```
t_pred = prompt/1601.5 + 142/10.651
                         └── constant 13.332 s
```

`n_out_pred` is a per-step-type median and step_type is hardcoded, so the decode term is
**constant**. Prefill contributes 0.06–5.42%. Every step lands in a 0.77 s band on a 13.33 s floor.

The mechanism under test — escalation selects on size — requires the prefill term to matter.
**Prefill does not reach parity with decode until ~21,352 context tokens. Peak observed was 1,826.**
The instrument was pointed 11.7× below the regime it measures.

The hypothesis was **not falsified. It was not tested.** P1/P2/P3 returned UNDETERMINED because the
8 s headline deadline sat *below* the 13.33 s floor, making every prediction there vacuous. The 8 s
was an illustrative figure that should never have entered a pre-registration; that is a
specification error, not a result.

## C1 — Tool payloads, so context reaches the regime

The current tool world returns almost nothing: context grows ~164 tokens/step, linearly, because
returns are near-constant in size. Real retrieval returns documents and is high-variance — and that
variance is exactly what the escalation filter selects on.

Change the tool world to return **realistic document chunks**: variable payloads, roughly
500–2,000 tokens each, one to three per retrieval call, drawn from a fixed seeded corpus so runs
are reproducible. Target a context growth rate that reaches **20,000–30,000 tokens** within the
trajectory.

Raise `max_steps` to whatever that requires — likely 12–16. Both changes are authorized here; they
were correctly withheld before.

**Report the projected growth curve from a 2–3 task pilot before the full run.** If it does not
clear 20K, say so and stop rather than proceeding into the same dead regime twice.

This single change also moves peak KV from 1.1% of the 12.5 GB budget to roughly 18%, which is the
first time the capacity claim is evaluated anywhere near the regime it concerns.

## C2 — Derive the deadline grid from data

The blueprint's own rule: deadline grids come from measured `t_pred` distributions and are never
guessed. Honour it. After the pilot, compute the observed `t_pred` distribution and place **≥8 grid
points spanning its full range**, from below the minimum to above the maximum.

Record an amendment noting that the pre-registered 8 s headline deadline is withdrawn and replaced
by a data-derived grid, with the reason: it sat below the achievable floor and made three
predictions vacuous. **PRE-DATA** with respect to the amended run.

## C3 — Re-state the predictions against the new grid

P1, P2 and P3 are re-evaluated at the material deadline on the derived grid, not at a fixed
wall-clock target. Keep the 1.2× materiality threshold. Keep P4 and P5 as written.

Add one: **P6 — the over-provisioning ratio increases with peak context.** The first run measured
1.243× at peak context 1,826, which the analysis reads as a lower bound obtained with the mechanism
at ~5% authority. If the reading is right, the ratio should rise materially at 20–30K. Falsified if
the ratio at 20K+ is within CI of the ratio at 1.8K.

P6 is the prediction that converts the first run from a failed test into a baseline point.

## C4 — Carry forward

Machine lock on every timed block, per Prompt A. Hardened quiesce with measured load. Calibrated
canary before and after each block. Everything else in the pre-registration stands — stratification
by `step_idx`, `cache_instrumented` reported, KV geometry read back from the device rather than
assumed, sealed runs, manifests, replay importing `policy.decide` rather than reimplementing it.

`step_type` remains hardcoded and remains a recorded limitation. Do not expand the taxonomy here.

## Report

Pilot growth curve first, and stop there if it does not clear 20K. Then the derived grid, then the
predictions, then the envelope curve. Lead with anything that failed.
