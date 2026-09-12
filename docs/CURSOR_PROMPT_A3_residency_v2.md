# Cursor dispatch — A3 v2: residency sweep, no headroom gate

Supersedes `CURSOR_PROMPT_A3_residency.md`. Track: `agent`. Attrib frozen. Prompt C blocked.

---

## Two corrections to the previous spec

**Phase 1 is deleted.** It asked whether page reads vanish at high headroom. Phase 2's
highest-memory blocks answer exactly that, so Phase 1 was a redundant gate that cost a reboot and
produced a refusal. Read the fork off the top of the sweep instead.

**The 8,192 MB headroom threshold is removed.** The launch refused at 7,960 MB, which is
functionally identical and satisfies the actual requirement — enough free memory that a 2.6 GB
model plus KV plus runtime stays resident. An arbitrary round number should never have been a
launch gate.

**Replace target levels with achieved values.** The old design specified `{10 GB, 4 GB, 1.5 GB}`
and would fail if a target was missed. The new design takes whatever the machine offers at the top
and ballons down from there, recording what was *achieved* rather than what was *requested*.

## The experiment

One continuous sweep. Everything fixed except free memory.

```
free memory      a ladder from whatever the machine gives at launch down to ~1.2 GB,
                 in ~6 steps, spaced roughly evenly in GB
repeats          ≥5 per step
constant         prompt, n_out, model, quantization, execution target, thread count,
                 power plan — identical in every block
```

**Do not gate on hitting a target.** Set the balloon, read back achieved free memory, record both,
proceed. A step that lands at 5.3 GB instead of 5.0 GB is fine — the analysis uses the achieved
value.

The balloon must **allocate and touch** its memory so the pages are genuinely resident. Reserved-
but-untouched memory does not create pressure and would make the whole ladder fictional.

**Interleave the steps.** Not all of one then all of another — alternate in a randomized sequence
with **at least three crossings** across the ladder, and report the block-position slope as a drift
check. Thermal and position drift would otherwise ride along exactly where the effect is expected.

## The analysis is a regression, not a comparison

This is the important change. The output is **not** three buckets compared pairwise. It is:

```
R_decode   ~  f(achieved_free_memory_mb)
R_prefill  ~  f(achieved_free_memory_mb)
hard_page_reads_per_s  ~  f(achieved_free_memory_mb)
```

Report slope, R², and the fitted values at the two extremes with CIs. A curve over six points is
more informative than three buckets and it is immune to missing a target.

**The headline number:** the ratio of fitted `R_decode` at the highest achieved free memory to
fitted `R_decode` at the lowest, with CI, against the **1.983×** target.

## The gate override — unchanged and critical

**The paging gate is reporting-only for this run. It does not exclude.**

Paging is the independent variable. A gate that drops paged blocks would discard exactly the data
the experiment exists to collect. Record `paging_gate.verdict` on every block with its reasons, and
analyse every block regardless. Restore exclusionary behaviour immediately afterwards, and note the
override prominently in the manifest so no downstream reader mistakes this for a gated run.

## Per-block record

```
free_memory_mb_target, free_memory_mb_achieved_before, _after
balloon_bytes_requested, balloon_bytes_touched
hard_page_reads_per_s: samples, median, p95, max, fraction_above_threshold
R_prefill, R_decode, wall_ns, ttft_ns
canary_before_ns, canary_after_ns, drift_pct, admissible
paging_gate.verdict          ← recorded, NOT applied
cpu_pct_total, cpu_pct_per_core
placement.readback_after_spinup, placement.readback_mid_generation
block_position, ladder_step_index
```

## Launch

Reboot, Cursor closed, bare PowerShell, launch **detached**. Print `run_id=` and the achieved free
memory at launch **before** starting the sweep, so a mis-launch is visible immediately rather than
inferred from a missing directory later.

**No headroom refusal.** Take what the machine gives. If the top of the ladder is 6 GB rather than
8, record 6 and proceed — the sweep needs *spread*, not a specific ceiling.

Budget roughly 30 minutes for ~6 steps × 5 repeats plus ballooning and cooldowns.

## Conditional Phase 3 — forced residency

Only if page reads persist at the **top** of the ladder:

1. After model load, **pre-touch** the mapped weight region — sequential read of every page.
   Record the time it takes and how the page-read rate responds.
2. If that is insufficient, raise the process minimum working set via `SetProcessWorkingSetSize`.
   Record whether it was granted.

Then repeat one block at the **bottom** of the ladder with residency forced. If throughput recovers,
residency is the mechanism, and pre-touching becomes standing measurement protocol — which would
apply **retroactively to every run this project has taken**, including the two behind the 1.98× and
the 15.801/8.401 core contrast.

## Reading the result

- **`R_decode` rises with free memory, page reads fall** → paging explains the 1.98×; the placement
  question is moot and the freeze lifts.
- **Extremes ratio ≈ 1.98×** → the anomaly is reproduced on demand. Strongest possible verdict.
- **Throughput flat while page reads vary** → paging is a confound to control, not the cause. Pin
  memory high and run the 4-cell placement sweep as originally designed.
- **Throughput varies but page reads do not** → neither hypothesis holds. Report unexplained rather
  than reaching for a mechanism.

## Still pending

Commit remains **AWAITING_COMMIT**. Do not stage, commit, or push. Resolve the one inconsistency in
the prepared list: `raw/9b25332b` is excluded as a failed attempt while `cb0ed2e3` is retained as
failure evidence — pick one policy and apply it to both.

This run is diagnostic, so it may proceed under the existing dirty-tree allowance **provided that
fact is recorded prominently in the report.**

## Report

1. Achieved free-memory ladder — target versus achieved at every step.
2. The three regressions with slope, R², and fitted extremes with CIs.
3. Extremes ratio against 1.983×.
4. Block-position drift slope.
5. Phase 3 only if the top of the ladder still shows paging.
6. One line: **paging, placement, both, or unexplained.**

No block is dropped. Every block is analysed and reported with its gate verdict attached.

## Standing constraints

Machine lock every timed block, released before analysis. Canary either side of every block. No
commit, push, raw mutation, cloud call, or credential load. The gate override is temporary, scoped
to this run, and recorded in the manifest.
