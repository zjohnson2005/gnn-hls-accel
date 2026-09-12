# Cursor dispatch — C2g: find the memory consumer, cap lower, run

Track: `agent`. Attrib frozen. Everything in C2b–C2f not restated here still stands.

---

## Where `bf458efb` got to

```
pos  task     ratio   canary  paging  note
 0   C2T13      —      True     —     discarded warm-up, drift 0.012
 1   C2T19    8.04     True    True
 2   C2T10    8.34     True    True
 3   C2T20    1.45     True    True
 4   C2T14    7.12     True   False   memory 27 MB < 500 + paging
 5   C2T09    7.63     True   False   paging only
                    median ratio 7.63 ≥ 3.0
```

**Sealed. Canary threshold derived at 0.27, zero canary trips.** The discard-first warm-up worked —
0.012 drift on the discarded task against the 4.69 it replaced confirms first-task settling was the
cause.

One blocker: a memory-floor trip at 27 MB.

## 1. This gate is not getting scoped, and here is why

Paging and canary gates detect **contamination** — whether a measurement is trustworthy. Scoping
them per endpoint is legitimate because contamination follows a causal path and some endpoints are
not on it.

**The memory floor is a stability gate.** It exists to prevent the crash that killed `0fe5e4c7` at
70 MB, not to protect data quality. At 27 MB an allocation failure or OOM kill loses the entire run
regardless of which endpoint mattered.

> **Contamination gates are scoped by causal path. Safety gates are respected.**

Three scoped gates would have been a pattern rather than a principle. This one stands.

## 2. The arithmetic does not explain 27 MB — find what does

```
0fe5e4c7    9,114 context, no cap    →  70 MB free, crashed
bf458efb    7,000 cap                →  27 MB free, survived
```

**A tighter cap reached lower free memory.** So context alone is not the driver.

At 7,000 tokens the KV cache is 516 MB against a 2.6 GB model — that does not reach 27 MB from a
~2.3 GB starting point. **Prefill activation memory is the likely consumer and it is unmeasured.**

Instrument it. Per task, report:

```
free_memory_mb_min                 and the step_idx and context at which it occurred
process_rss_peak                   and the step_idx at which it occurred
free_memory_mb_at_task_start / _end / _after_teardown
```

Per step, on the deepest few steps of each task:

```
rss_before_generate, rss_peak_during_generate, rss_after_generate
```

**The question is whether peak memory tracks context linearly or superlinearly.** Linear implies KV
plus a constant; superlinear implies attention activations scaling with context², which would mean
the cap must be far tighter than the KV arithmetic suggests.

Report the relationship. It decides whether capping is sufficient or whether §4 is required.

## 3. Lower the cap to 5,000 — it costs nothing

```
cap 7,000    ratio ceiling ~10.8×
cap 5,000    ratio ceiling  ~7.7×      still 2.5× above the 3.0 gate
KV at 5,000  369 MB
```

The observed median ratio is 7.63 and the gate is 3.0. **Dropping the cap to 5,000 leaves ample
margin on the only thing the ratio gate measures**, while removing 2,000 tokens of activation
pressure at the deepest steps.

Do not go below 5,000 without cause — the ratio ceiling and the gate would start to converge.

## 4. Investigate chunked prefill — the real fix if it exists

If §2 shows peak memory scaling superlinearly with context, capping is treating a symptom.

Chunked prefill processes the prompt in fixed-size segments, bounding activation memory
**independently of context length**. OpenVINO exposes `NPUW_LLM_PREFILL_CHUNK_SIZE` on the NPU
path; determine whether an equivalent exists for the CPU path — a plugin property, a config key, or
a pipeline option.

If it does: enable it, record the chunk size in the manifest, and re-measure the memory relationship
from §2. That would decouple memory from context entirely and lift the cap constraint for every
future run.

If it does not: report that plainly. It becomes a platform limitation worth recording in C9 —
*"on this stack, usable agent context is bounded by prefill activation memory, not by KV cache
size,"* which is the sharper version of the capacity finding already recorded.

## 5. Re-pilot

≥5 tasks plus the discarded warm-up, cap at 5,000. Pass conditions:

- median per-task context ratio ≥ 3.0
- the run seals
- **zero memory-floor trips**
- canary and paging admissibility recorded per block, scoped per endpoint

Paging trips remain non-fatal per C2e. Canary trips remain non-fatal per C2f. **Only the memory
floor blocks clearance.**

## 6. Then the full run

As C2b §6: deadline grid derived from the measured `t_pred` distribution with ≥8 points spanning its
range, amendment withdrawing the pre-registered 8 s deadline, corrected proxy per AM-027, paging and
canary gates scoped per endpoint, memory floor enforced, cloud backend that raises, P1–P6 at
materiality 1.2×, and the computed ceiling `C_max/C_min` reported alongside the measured
over-provisioning.

## Report, in order

1. **Peak memory versus context** — linear or superlinear, with the per-step RSS series that shows
   it. This decides whether the cap is sufficient.
2. Whether chunked prefill is available on the CPU path, and if so its effect on that relationship.
3. Re-pilot at cap 5,000: ratios, memory minima, seal result, admissibility per block.
4. Then the full run.

## Standing constraints

Machine lock every timed block, detached launch. No commit, push, raw mutation, cloud call, or
credential load. Thresholds are derived from baselines and recorded — never chosen to make a run
pass. Every number carries its run_id per AM-027(b).
