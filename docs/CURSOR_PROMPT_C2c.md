# Cursor dispatch — C2c: release memory between tasks, then run

Track: `agent`. Attrib frozen. Supersedes C2b; everything in C2b that is not restated here still
stands.

---

## What pilot `1f92fc4a` established

**The measurement works.**

```
task     peak ctx   C_max/C_min   terminated      block valid
C2T13      4,878        5.98      context_cap        yes
C2T19      6,557        8.04      context_cap        yes
C2T10      6,703        8.34      submitted          yes
C2T20      1,203        1.45      context_cap        yes
C2T14      5,797        7.12      context_cap        yes
                       median 7.12  ≥ 3.0 gate       5/5 valid
```

5/5 tasks completed. All five blocks valid. Tools well-formed on every step — constrained decoding
worked. The context cap fired and held. **The ratio gate passes by 2.4×.**

The failure is a **post-run** invalidation: 7 sustained page-read samples and canary drift 0.258
against a 0.15 threshold. It happened after the last task, not inside any measured block.

## 1. The failure looks like accumulation, not a single oversized task

Reading the table as execution order, the run died after **C2T14 at 5,797 tokens** — while
**C2T10 at 6,703 passed earlier in the same run.** A smaller task failing later than a larger one
that succeeded is the signature of monotonic degradation across tasks.

The path is stateless, so KV should be released per call. That points elsewhere: allocator
fragmentation, harness-side transcript retention, uncollected Python objects, or OpenVINO internal
caches.

**Do not guess. Measure it.**

## 2. Instrument per-task memory — this is the diagnostic that picks the fix

Record and report, per task:

```
free_memory_mb_before_task
free_memory_mb_after_task
free_memory_mb_after_teardown        ← see §3
process_rss_before, process_rss_after
```

**Monotonic decline across tasks** → accumulation. Teardown is the fix and §3 applies.
**Flat until a spike on the last task** → that task is the cause, and the fix is ordering or capping.

Report the series either way. This is a five-line change and it decides everything downstream.

## 3. Explicit teardown between tasks

Between tasks, not between blocks:

1. Destroy the pipeline object. Call `gc.collect()`.
2. **Wait for free memory to recover above a declared threshold** — suggest the launch value minus
   10% — with a timeout.
3. Reconstruct the pipeline and run **one throwaway warm-up generation** before the next timed task,
   so the first step of each task does not pay a cold-load penalty that would inflate its timings.

Model load measured 3.1 s in an earlier run, so per-task reconstruction costs about a minute across
twenty tasks. That is cheap insurance.

**If free memory does not recover after teardown, that is a leak and it is a C9 finding.** Report it
rather than working around it — a measurement harness that leaks across tasks would have quietly
degraded every multi-task run this project has taken.

## 4. Split the after-canary to separate transient from persistent

Canary drift of 0.258 immediately after a heavy task may be measuring memory not yet reclaimed by
the OS rather than a genuine shift in the operating point.

Run the after-canary **twice**: once immediately, once after a short settle.

- **Both drifted** → persistent degradation. The block is genuinely inadmissible.
- **Second recovers** → transient reclaim. Record both values and treat the settled one as
  authoritative, with the transient recorded as evidence.

**Do not loosen the 0.15 threshold.** Add the second sample instead; the threshold is doing its job
and the question is which state it should be applied to.

## 5. Check the context cap — C2T20 is wrong

`C2T20` terminated on `context_cap` at **1,203 tokens** against a 7,000 cap, ratio 1.45. That should
not happen.

Determine which it is: the projection of next-step context is over-estimating badly, or the
termination reason is mislabelled and it stopped for another cause. Report the projected value that
triggered it.

This matters beyond one task — an eagerly firing cap silently truncates exactly the long
trajectories the measurement depends on, and it is the one task dragging the median down.

## 6. Re-pilot, then run

Re-pilot ≥5 tasks. Pass conditions:

- median per-task context ratio ≥ 3.0
- **zero memory or canary invalidations, including post-run**
- the run **seals**

Then proceed to the full E-FILTER run exactly as specified in C2b §6: deadline grid derived from the
measured `t_pred` distribution with ≥8 points, the amendment withdrawing the 8 s deadline, corrected
proxy per AM-027, exclusionary paging gate on baseline `e6bae93f`, cloud backend that raises, P1–P6
with materiality 1.2×, and the computed ceiling `C_max/C_min` reported alongside the measured
over-provisioning.

## Report, in order

1. **Per-task free-memory series** and whether the decline is monotonic. This picks the fix.
2. Teardown behaviour — does memory recover, and how far?
3. Double-canary result — transient or persistent?
4. C2T20's cap trigger — the projected value and whether the label is correct.
5. Re-pilot: ratios, invalidations, and whether it sealed.
6. Then the full run.

## Standing constraints

Machine lock every timed block, detached launch. No commit, push, raw mutation, cloud call, or
credential load. Thresholds do not move to make a run fit. Every number carries its run_id per
AM-027(b).
