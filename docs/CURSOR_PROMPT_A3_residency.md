# Cursor dispatch — A3: the residency experiment

Track: `agent`. Attrib frozen. Prompt C blocked. **The 4-cell placement sweep is deferred, not
cancelled** — see §1.

---

## Orientation

Call `seam_status()`, `seam_pins()`, `seam_platform()`. Read AM-027(b): every number carries a
run_id at the point of use.

## 1. Why the placement sweep is deferred

Fix A's baselines, sealed as `e6bae93f-998c-42c4-ac8c-6351cf389f57`:

```
              median    p95        max       fraction >0
idle           0.0      0.0        595       1.7%
generation     0.0      5,104      5,380     29.7%
```

**Five thousand hard page reads per second during generation, in sustained runs.** The machine is
going to disk while producing tokens.

The likely mechanism is demand-paging of memory-mapped model weights. OpenVINO mmaps the IR;
decode streams the full weight set once per token; with ~1.4 GB free against a 2.6 GB model the OS
cannot hold it resident, so weight pages are evicted and faulted back on the critical path.

**This now outranks core placement as the explanation for the 1.98×**, because it accounts for
every observation placement only partly covered:

| Observation | Placement | Paging |
|:--|:--:|:--:|
| uniform across prefill and decode | ✓ | ✓ |
| no configuration difference in the manifests | ✓ | ✓ |
| no frequency change | ✓ | ✓ (I/O stall, not clock) |
| stable plateaus *within* a run | partial | ✓ (steady-state residency) |
| differs *between* runs | requires migration | ✓ (free memory differed at launch) |
| every authorized detector blind | unexplained | ✓ (none watched memory) |

Running the 4-cell sweep now yields one of two useless outcomes: most blocks `excluded_invalid`
under the new gate, or throughput varying with memory state rather than affinity. Test the cheaper
hypothesis first.

## 2. THE CRITICAL DESIGN CONSTRAINT

**For this experiment the paging gate is reporting-only. It does not exclude.**

Paging is the *independent variable* here, not a confound. A gate that drops paged blocks would
discard exactly the data the experiment exists to collect. Record `paging_gate.verdict` on every
block, carry the reasons, and analyse every block regardless.

Restore exclusionary behaviour immediately afterwards. Note the override explicitly in the manifest
so no downstream reader mistakes this run for a gated one.

## Phase 1 — re-baseline at maximum headroom

Reboot. Log in. Wait for startup services to settle. Open nothing.

Under the machine lock, with ≥8 GB available:

1. Idle sampler, ≥60 s at 1 s intervals — same sampler as `e6bae93f`.
2. One generation block, same sampler, same prompt and `n_out` as the Fix A generation baseline.

Report both distributions against `e6bae93f`'s. **This is the fork:**

- **Page reads → ~0 during generation at high headroom** → residency is the variable, and Phase 2
  is the experiment that closes it.
- **Page reads persist at ≥8 GB free** → demand-paging happens regardless of headroom, residency is
  not achieved by having memory, and Phase 3 becomes necessary.

Report Phase 1 before starting Phase 2.

## Phase 2 — throughput against free memory

The main experiment. Everything fixed except available memory.

```
free-memory levels   { ~10 GB (fresh boot), ~4 GB, ~1.5 GB }
repeats              ≥7 per level
constant             prompt, n_out, model, quantization, execution target,
                     thread count, power plan, deadline — all identical
```

Constrain memory with a **balloon process** that allocates and *touches* the required amount, so
the pages are genuinely resident and not merely reserved. Verify the achieved free-memory level by
reading it back before each block; record both target and achieved.

**Interleave the levels.** Do not run all of one level then all of another — thermal and
block-position drift would confound the comparison exactly where it matters. Alternate in a
randomized sequence with **at least three crossings between levels**, and report the
block-position slope as a drift check.

Per block record, in `blocks.jsonl`:

```
free_memory_mb_target, free_memory_mb_achieved_before, _after
hard_page_reads_per_s: samples, median, p95, max, fraction_above_threshold
R_prefill, R_decode, wall_ns, ttft_ns
canary_before_ns, canary_after_ns, drift_pct, admissible
paging_gate.verdict          ← recorded, NOT applied
cpu_pct_total, cpu_pct_per_core, placement readback
block_position, level_sequence_index
```

**The headline output:** `R_decode` and `R_prefill` plotted against achieved free memory, with the
page-read rate on the same axis.

## Phase 3 — forced residency, only if Phase 1 says page reads persist

If the weights will not stay resident on their own, force them and re-measure:

1. After model load, **pre-touch** the mapped weight region — sequential read of every page — and
   record how long it takes and how page-read rate responds.
2. If pre-touching is insufficient, raise the process minimum working set via
   `SetProcessWorkingSetSize`. Record whether it was granted; it may require privilege.

Then repeat one Phase 2 block at the lowest memory level with residency forced. **If throughput
recovers, residency is the mechanism and pre-touching becomes a standing part of the measurement
protocol** — which would apply to every run this project has taken, retroactively.

Do not skip to Phase 3. It is only meaningful if Phase 1 shows paging survives high headroom.

## Reading the result

- **`R_decode` tracks free memory, page reads inversely** → paging explains the 1.98×. The placement
  question is moot, the freeze lifts, and pre-touching becomes protocol.
- **Throughput flat while page reads vary** → paging is a confound to control, not the cause. Pin
  memory high and run the 4-cell placement sweep as originally designed.
- **Throughput varies and page reads do not** → neither hypothesis holds; something else moves with
  memory pressure. Report it as unexplained rather than reaching.
- **Low-memory throughput ≈ 1.98× below high-memory** → the anomaly is reproduced on demand, which
  is the strongest possible form of this verdict.

## Still pending

Commit is **AWAITING_COMMIT** and unchanged. Do not stage, do not commit, do not push. The prepared
list stands; resolve one inconsistency in it — `raw/9b25332b` is excluded as a failed attempt while
`cb0ed2e3` was retained as failure evidence. Pick one policy and apply it to both.

Launch detached with `--allow-dirty` removed once the commit lands. Until then, Phase 1 may run
under the existing dirty-tree allowance **only if** you record that fact prominently in the report —
Phase 1 is diagnostic, not a result.

## Report

1. Phase 1 distributions against `e6bae93f`, and which fork you are on. Stop and report before
   Phase 2.
2. Phase 2: the `R_decode` versus free-memory table, page-read rate per level, and the
   block-position drift slope.
3. The ratio between the highest and lowest memory levels, with CI, against the **1.983×** target.
4. Phase 3 only if Phase 1 required it.
5. One line: **paging, placement, both, or unexplained.**

Blocks are never dropped in this run. Every block is analysed and reported with its gate verdict
attached.

## Standing constraints

Machine lock every timed block, released before analysis. Canary either side of every block. No
commit, no push, no raw mutation, no cloud call, no credential load. The paging gate override is
temporary, scoped to this run, and recorded in the manifest.
