# Cursor dispatch — A4: the placement sweep, un-deferred

Track: `agent`. Attrib frozen. Prompt C blocked.

---

## What A3 settled and what it did not

Run `b2a75509-10e4-4352-8452-980a7e6a4b22`, 31 blocks, sealed.

**Falsified — paging as a smooth function of headroom:**

```
R_decode ~ free_mb      slope −1.720e−4   R² 0.011   fit 20.947 → 19.743
extremes ratio          0.9425  CI [0.8288, 1.0527]   vs 1.983 target
page-read median        slope +0.016784   R² 0.161   ← wrong direction
Phase 3 pretouch        2.29 GB / 1.9 s;  forced bottom R_decode 20.314 (nothing to fix)
```

**Not falsified — paging as a sporadic event.** Block 15 fell to **9.90 tok/s** against a 21.2–22.5
baseline with a page-read median of **99**. A 2.1× collapse, which is the anomaly magnitude, in one
block, co-occurring with heavy paging.

The correct conclusion is that paging behaves like a **switch, not a slope**. A regression was the
wrong instrument for it. It remains a live explanation for run-to-run variance and is now something
to *gate against*, not to *measure*.

**A known limitation of A3, recorded so it is not repeated:** achieved free memory ranged
379–7379 MB against targets of 1200–4687. A balloon can only lower free memory, never raise it, so
the top of the ladder was uncontrolled by construction, and memory was released mid-run by
something external. Every A3 regression is therefore observational, not experimental. The
`R_prefill` result — 4.9× faster at *low* memory, R² 0.528 — is implausible as physics and is
treated as an artifact of that uncontrolled axis. Do not carry it forward as a finding.

## What this run does

The 4-cell placement sweep, deferred in A3 for a hypothesis that has now been falsified.

| Cell | Affinity requested | Machine |
|:--|:--|:--|
| C1 | P-cores | clean |
| C2 | LP-E cores | clean |
| C3 | none | clean |
| C4 | none | 4-process P-core burn |

≥7 repeats per cell, randomized cell order, cooldown between blocks, machine lock per block, canary
either side. Budget ~46 minutes.

**Placement readback is the instrument**, per block, in `blocks.jsonl`:

```
placement.affinity_requested        mask, or null for C3/C4
placement.readback_after_spinup     process mask + per-thread where obtainable
placement.readback_mid_generation   sampled during generation, not only before
placement.matches_request           bool | null
```

Mid-generation readback is not optional. Migration under contention is exactly what C4 exists to
catch, and a mask read only at spin-up would miss it. **A requested affinity that readback
contradicts is a finding — record it and continue.** `mslice-a1a6` returned UNCLEAR on all six
confinement mechanisms, so pinning may not take.

## The paging gate is exclusionary again

Restore normal behaviour. A3's reporting-only override was scoped to A3 and ends with it.

Threshold as calibrated in `e6bae93f`: baseline-relative, `idle_p95 = 0.0`, margin 1.0, **1.0 hard
page reads/sec sustained over ≥2 consecutive samples**, plus available memory ≥500 MB. Record
`paging_gate` in the manifest with `baseline_run_id`.

**Blocks that trip it are excluded from the ratio but retained in `records[]` with reasons**, per
the standing rule. Never silently dropped.

Block 15 is why this matters: a single paged block at 9.90 tok/s inside a cell averaging 21+ would
drag that cell's mean by ~15% and could manufacture or mask a placement effect on its own.

## Characterize the block-15 event

Separately from the sweep, and worth doing because it is the only direct evidence that paging can
produce the anomaly magnitude:

Pull block 15 from `b2a75509` and report everything recorded around it — free memory before and
after, the full page-read sample series, CPU per core, canary drift, its ladder step, its position
in the sequence, and what the two blocks either side of it looked like. **The question is whether
anything distinguishes it in advance**, or whether it fired without warning.

If a precursor exists, the gate can be made predictive rather than retrospective. If not, that is
worth knowing too — it means paged blocks can only be excluded after the fact.

## Reading the result

- **C1/C2 ≈ 1.98×** → placement explains the anomaly. The freeze lifts.
- **C1/C2 well below 1.98×** → placement is insufficient. With paging-as-slope already falsified,
  the remaining candidates are sporadic paging events and a power or clock operating point for which
  this platform has no working detector. Say so plainly; do not reach.
- **C3 readback = P-cores, throughput ≈ C1** → unpinned defaults to P-cores on a clean machine.
- **C4 readback = LP-E or mixed, throughput ≈ C2** → contention-driven migration confirmed.
- **C4 readback = P-cores but throughput drops** → direct contention without migration.
- **Requested affinity not honoured in C1 or C2** → the placement question cannot be answered on
  this platform with this mechanism. Report it as such rather than reporting the throughput numbers
  as if the labels held.

## Launch

Reboot, Cursor closed, bare PowerShell, **detached**. Print `run_id=` and achieved free memory
before the sweep starts. **No headroom refusal** — take what the machine gives; A3 established that
decode throughput does not track free memory, so a specific ceiling is not required.

Killing early is cheap. Partial runs read as `PARTIAL/INCOMPLETE` with `allow_partial=True`, so if
something goes wrong mid-sweep the clean blocks survive.

## Still pending

Commit remains **AWAITING_COMMIT**. Do not stage, commit, or push. The one inconsistency in the
prepared list still stands: `raw/9b25332b` excluded as a failed attempt while `cb0ed2e3` retained as
failure evidence. Pick one policy, apply it to both, and add `b2a75509` to the list.

This run is diagnostic and may proceed under the dirty-tree allowance **provided that is recorded
prominently in the report.**

## Report

1. The block-15 characterization, first — it is the shortest path to a mechanism.
2. run_id, achieved free memory at launch, and the per-block JSONL path.
3. Four-cell table: `R_prefill`, `R_decode`, CIs, **readback-observed placement**, canary drift,
   free-memory range, and paging-gate verdict per cell.
4. Count and identity of blocks excluded, with reasons.
5. C1/C2 ratio with CI against **1.983×**.
6. One line: **placement, contention-driven migration, direct contention, sporadic paging, or
   unexplained.**

Every number carries its run_id per AM-027(b). Lead with anything inadmissible.

## Standing constraints

Machine lock every timed block, released before analysis. Canary either side. No commit, push, raw
mutation, cloud call, or credential load. Thresholds do not move to make a run fit.
