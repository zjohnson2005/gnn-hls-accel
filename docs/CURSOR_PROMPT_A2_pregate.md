# Cursor dispatch — A2 pre-launch: three fixes, commit prep, then rerun

Track: `agent`. Attrib frozen. Prompt C blocked.

---

## Orientation

Call `seam_status()`, `seam_pins()`, `seam_platform()`. Read AM-027(b) — every number carries a
run_id at the point of use.

The lifecycle repairs are accepted: cycle located at `$.records[0].validity.timed_measurement` and
fixed at the alias, startup dry-run, JSONL per-block append, partial-run semantics, paging
telemetry. Three problems remain and all three would cost a measurement window if discovered after
the sweep rather than before it.

---

## Fix A — the paging gate has no baseline, and this project has made that mistake before

**The defect.** `≥2 consecutive samples with hard_page_reads_per_s > 0` is an absolute threshold on
a **system-wide** counter. `\Memory\Page Reads/sec` is rarely a clean zero on Windows — a
background service waking, a memory-mapped read, anything touching disk registers on it. With
~1.4 GB free during a 46-minute sweep, two consecutive non-zero samples is not a high bar.

The failure mode is a completed sweep in which most blocks return `excluded_invalid`, discovered
only at the end.

**The precedent.** The first `PCORE_ONLY` measurement on this platform used absolute utilization
thresholds and reported 90% on cores 4–7. The quiesced re-run with baseline subtraction gave
4.7–6.7% — the 90% was a download. Same shape: an absolute gate on a noisy shared counter with no
idle reference.

**What to do, before the rerun and before the commit:**

1. **Idle baseline.** Machine quiesced, no inference. Sample `\Memory\Page Reads/sec` for ≥60 s at
   1 s intervals. Report the full distribution: median, p95, max, and **fraction of samples above
   zero**.
2. **Generation baseline.** One known-good generation block under the machine lock, same sampler.
   Report the same distribution.
3. **Then decide the threshold, and justify it from those two distributions:**
   - If both are cleanly zero — keep `> 0` as written and record the baselines as evidence.
   - If idle shows periodic non-zero — the gate becomes **baseline-relative**: threshold at idle p95
     plus a stated margin, with a minimum sustained duration. Record the baseline, the margin, and
     the resulting absolute threshold **in the manifest**, so the gate is reconstructible from the
     sealed run rather than from a config file that may drift.

Do not launch the sweep until this is settled. It is roughly two minutes of measurement to protect
forty-six.

---

## Fix B — validity and measurement are mutually contained

The cycle was `measurement["validity"] = block.record` with
`block.record["timed_measurement"]` aliasing back to `measurement`. The shallow snapshot breaks the
alias, but **the mutual containment is still the shape of the data**: the validity judgment lives
inside the thing it judges, and the thing it judges lives inside the judgment.

Flatten it. One block record, siblings not nesting:

```
{
  "block_id":      "<uuid>",
  "cell_id":       "C1" | "C2" | "C3" | "C4",
  "repeat_index":  0..6,
  "measurement":   { R_prefill, R_decode, wall_ns, ttft_ns, ... },
  "placement":     { ... },          # Fix C
  "canary":        { ... },          # Fix C
  "telemetry":     { memory, paging, cpu, package_temp },
  "validity":      { admissible: bool, reasons: [...], block_id: "<same uuid>" },
  "run_id":        "<run_id>",
  "timestamp_utc": "..."
}
```

`validity` references `block_id`; it never embeds the measurement. This removes the class of bug
rather than the instance, and it makes the analysis path simpler — reading a block no longer means
unwrapping a structure that contains a copy of itself.

Keep the `find_cycles` assert and the startup dry-run regardless. Belt and braces is correct here.

---

## Fix C — the instrument is missing from the block record

Per-block telemetry currently covers memory, paging, CPU, and `package_temp`. It does **not** list
affinity readback or canary drift.

**Affinity readback is not one field among several — it is the entire instrument for this
experiment.** C3 and C4 exist to answer "where did the threads actually run," and that question has
no answer without it. If placement only reaches the final aggregate, a mid-sweep crash loses it for
every block that already completed, and the partial-run machinery just built cannot recover it.

Required in `blocks.jsonl`, per block:

```
placement.affinity_requested        the mask requested, or null for C3/C4
placement.readback_after_spinup     process affinity mask + per-thread if obtainable
placement.readback_mid_generation   sampled during generation, not only before
placement.matches_request           bool | null   (null where nothing was requested)

canary.before_ns
canary.after_ns
canary.drift_pct
canary.admissible                   bool, against the stated drift threshold
```

**A requested affinity that readback contradicts is a finding, not a failure.** `mslice-a1a6`
returned UNCLEAR on all six confinement mechanisms, so pinning may not take. Record the
contradiction and continue; do not retry, do not adjust, do not treat it as an error condition.

Mid-generation readback matters as much as post-spinup: migration under contention is precisely
what C4 is designed to catch, and a mask sampled only before generation would miss it.

---

## Commit preparation — prepare, report, do not execute

Every run to date recorded `git.dirty_tree_allowed`, meaning **no manifest in this project
reconstructs its own run from `git_sha`.** That ends with this run.

Prepare — do not commit, do not push — a single commit containing:

- the lifecycle repairs already landed
- Fixes A, B and C from this document
- `GOVERNING_DOCS.sha256` — the AM-009 pin file, which has never been committed
- `.pre-commit-config.yaml` — the hook wiring, also never committed

Report:

1. the exact path list to be staged
2. anything in the working set that should be **excluded** — `_tmp_*`, `_oa01_*`, generated
   artifacts, and the 72 untracked files under `apu_characterization`, which `.gitattributes`
   identifies as a separate pre-existing project
3. confirmation that the pre-commit hooks are **installed**, not merely present in `tools/hooks/` —
   `raw/` is 6 MB against AM-014's 100 MB ceiling, pins verify, secret scan is clean, so nothing
   should refuse

Do not attempt the full tree cleanup. 181 untracked files is a separate task and must not consume a
quiet-machine window.

---

## The rerun

Unchanged in design. Four cells, readback is the instrument:

| Cell | Affinity requested | Machine |
|:--|:--|:--|
| C1 | P-cores | clean |
| C2 | LP-E cores | clean |
| C3 | none | clean |
| C4 | none | 4-process P-core burn |

≥7 repeats, randomized cell order, cooldown between blocks, machine lock per block, canary either
side. **~46 minutes** for the sweep — measured, not estimated.

Launch **detached**, with `--allow-dirty` removed. If the tree is dirty at launch, refuse and
report. Report the run_id before exiting.

**Killing early is now cheap.** Partial runs read as `PARTIAL/INCOMPLETE` with `allow_partial=True`.
If available memory trends toward 500 MB mid-sweep, kill it and keep the clean blocks rather than
choosing between a contaminated run and nothing.

### Reading the result

- **C1/C2 ≈ 1.98×** → placement explains the anomaly; the measurement freeze lifts.
- **C1/C2 well below 1.98×** → placement is insufficient; the cause is a power or clock operating
  point, for which this platform has no working detector. The worse outcome. Say so plainly.
- **C3 readback = P-cores, throughput ≈ C1** → unpinned defaults to P-cores on a clean machine.
- **C4 readback = LP-E or mixed, throughput ≈ C2** → contention-driven migration confirmed.
- **C4 readback = P-cores but throughput drops** → direct contention without migration. A different
  mechanism, equally reportable.

---

## Report

1. **Fix A first** — both page-read distributions, the threshold decided, and the justification. If
   the threshold changed, the manifest field recording it.
2. The flattened block-record schema, and one real example line from `blocks.jsonl`.
3. Confirmation that placement and canary fields are per-block, with a sample.
4. The staged path list and the exclusion list. Await commit.
5. After commit: run_id, the four-cell table with `R_prefill`, `R_decode`, CIs, readback-observed
   placement, canary drift, and available-memory range per cell.
6. C1/C2 ratio with CI against the 1.983× target.
7. One line: **placement, contention-driven migration, direct contention, or unexplained.**

Blocks excluded for paging or canary drift are reported as excluded with their reasons, never
silently dropped. Lead with anything inadmissible.

## Standing constraints

Machine lock every timed block, released before analysis. No commit, no push, no raw mutation, no
cloud call, no credential load. Thresholds do not move to make a run fit.
