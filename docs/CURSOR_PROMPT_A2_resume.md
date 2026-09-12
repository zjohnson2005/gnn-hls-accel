# Cursor dispatch — A2 resume: the placement experiment

Track: `agent`. Measurement freeze still in force for attrib. Prompt C still blocked.

---

## Machine state — verified quiesced, 2026-08-04 09:51 local

```
total CPU              4.64 – 7.57%      against a 20% bar
available memory       3,612 – 3,625 MB  against a 2,048 MB floor
mc-fw-host (PID 4776)  0 – 0.78%         was 98.2%, finished on its own
```

`Restart-Service` was refused by McAfee self-protection — the error moved from "cannot open" to
"cannot stop" under elevation, which confirms the handle opened and the stop was blocked. Moot: the
process went idle without intervention. **Do not attempt to stop it.**

Headroom is thinner than it looks — 3.6 GB free on 16 GB with a 2.6 GB model to load. Launch
detached so Cursor can be closed.

## What Step 1 established, and what it leaves open

The sealed-manifest diff found **no configuration difference**. Both runs: `INFERENCE_NUM_THREADS=4`,
same inferred threads, `SCHEDULING_CORE_TYPE` unset, `ENABLE_CPU_PINNING` unset, no affinity
requested, identical model IR SHA-256, identical OpenVINO/GenAI versions, same power plan.

So configuration is eliminated. **Four threads, eight cores, nothing pinned, and — critically —
no affinity readback in either run.** Where those threads actually ran is unrecorded.

Line up the magnitudes:

```
unexplained run-to-run shift        1.983×
measured P-core vs LP-E (5eb09eba)  1.881×
```

Close enough to be one mechanism. **The hypothesis is that the two runs landed on different core
clusters**, and that `mc-fw-host` saturating a P-core is what pushed one of them off.

## The experiment — four cells, and readback is the instrument

Not a load 2×2. The question is *where the threads ran*, so observe placement rather than infer it.

| Cell | Affinity requested | Machine | What it answers |
|:--|:--|:--|:--|
| **C1** | P-cores | clean | fast baseline |
| **C2** | LP-E cores | clean | slow baseline — **C1/C2 is the placement effect** |
| **C3** | none | clean | where does unpinned land when nothing competes? |
| **C4** | none | 4-process P-core burn | does it migrate under contention? |

Fixed prompt, fixed config, **≥7 repeats per cell**, randomized cell order, cooldown between,
machine lock held per block, canary before and after every block.

**Affinity readback is mandatory in every cell**, including C3 and C4 where nothing is requested.
Capture the process affinity mask and per-thread placement if obtainable, sampled *after* threads
spin up and again mid-generation. Also capture `OPENVINO_LIB_PATHS`, which Step 1 identified as
read at runtime and uncaptured.

**A requested affinity that readback contradicts is a finding, not a failure** — record it and
carry on. `mslice-a1a6` returned UNCLEAR on all six confinement mechanisms, so pinning may not
take. Readback is what makes that visible instead of silent.

## Reading the result

- **C1/C2 ≈ 1.98×** → placement fully explains the anomaly. Report it and the freeze lifts.
- **C1/C2 well below 1.98×** → placement is not sufficient; something else moved. That is the worse
  outcome and it means power or clock operating point. Say so plainly rather than reaching.
- **C3 readback = P-cores, throughput ≈ C1** → unpinned defaults to P-cores on a clean machine.
- **C4 readback = LP-E or mixed, throughput ≈ C2** → **contention-driven migration confirmed**, and
  you have the mechanism rather than the correlation.
- **C4 readback = P-cores but throughput drops** → direct contention without migration. Different
  mechanism, equally reportable.

Report the canary drift per block alongside every cell. A cell whose canary moved is not admissible
regardless of what its throughput says.

## Launch

**Detached**, outliving this session. Report the run_id before you exit so it can be polled. Do not
hold the session open babysitting it — the session is itself contention.

If the quiesce gate refuses mid-sequence, it refuses. Report which cell and what the refusal named.
**Thresholds do not move.**

## Report

1. run_id, and the canary drift per block.
2. The four-cell table: `R_prefill`, `R_decode`, CIs, and **the readback-observed placement** for
   each.
3. C1/C2 ratio with CI, against the 1.983× target.
4. C3 and C4 readback — where threads actually landed.
5. One line: **placement, contention-driven migration, direct contention, or unexplained.**

Every number carries its run_id, per AM-027(b). If the answer is unexplained, say unexplained — the
quiesce-refusal history is a prior, not evidence, and it does not go in the verdict.

## Standing constraints

Machine lock every timed block, released before analysis. Attrib frozen. No commit, no push, no raw
mutation, no cloud call, no credential load.
