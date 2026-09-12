# Cursor dispatch — A2 rerun: fix the run lifecycle, then re-measure

Track: `agent`. Attrib still frozen from measurement. Prompt C still blocked.

---

## What happened, precisely

Run `cb0ed2e3-ed70-4627-b231-51016d2b255b`:

```
10:09:16  raw integrity OK on both prior runs
10:11:35  backend loaded — Qwen3-4B-int4-ov@b467368d16b7+int4_sym, cpu-p, 3.1s
10:11:35  powerstate captured — AC online, battery 100%, Best Performance
   …      46 minutes. No log output whatsoever.
10:57:37  git.dirty_tree_allowed  →  rawstore.run_created  →  manifest.emit_started
10:57:37  ValueError: Circular reference detected
          manifest.py:439 → rawstore.write_json → json.dumps
          cycle shape: dict → list → dict → dict → back to an ancestor
```

**The sweep completed.** Every measurement was taken and every one was lost, because the run
directory did not exist until four seconds before the crash.

## The defects, in order of severity

**D1 — the run lifecycle writes nothing until the end.** `rawstore.run_created` fires *after* the
sweep. This is not a crash-recovery problem, it is an architectural one: it also makes per-block
progress unobservable, makes partial results impossible when a run must be killed, and grows
process memory monotonically through the run. Resident set reached 5.4 GB against a 2.6 GB model.

**D2 — the entire output path is exercised for the first time after the measurement is spent.**
A serialization bug costs 46 minutes when it should cost 2 seconds.

**D3 — the circular reference.** Real, but the cheapest of the three, and the one most likely to be
patched badly.

**D4 — 46 minutes of silence.** Nothing was logged between backend load and manifest emit. Even had
serialization succeeded, there would be no per-block record proving the cells ran as designed. And
because available memory was not sampled per block, **we cannot rule out that the lost sweep was
paging** — you were at 1.4 GB free, and a paged block produces exactly the kind of wrong throughput
number this whole experiment exists to diagnose.

## Fix 1 — reorder the run lifecycle

```
  now:   measure everything  →  create run dir  →  write summary  →  seal
  want:  create run dir  →  [ measure block  →  append record ] ×N  →  write summary  →  seal
```

Create the run directory and write an in-progress marker **before the first cell**. Append each
block's result to a JSONL as it completes — one line per block, flushed and `fsync`'d. Write the
aggregate summary and `.sealed` only at the end.

This is consistent with the write-once discipline in spec §9.1: appending new records is not
mutation, and the tree hash in `.sealed` is computed at the end over whatever is there. **A
directory without `.sealed` is an incomplete run**, which `verify_sealed()` already distinguishes.
Do not treat an unsealed directory as corrupt — treat it as partial, and make the analysis path
able to read partial runs explicitly labelled as such.

A crash must cost one block. Not a run.

## Fix 2 — dry-run the entire output path at startup

Before any measurement, before the model is loaded: construct a **synthetic** summary object of the
same shape the real one will have, write it through the real `write_json` / `emit` path into a
temporary run directory, seal it, verify the seal, and delete it.

That exercises serialization, disk space, directory creation, the manifest schema, and the seal
operation in about two seconds. Any of those failing after 46 minutes of measurement is an
unforced error.

Make this unconditional, not a flag. It is cheap enough that there is no reason to skip it.

## Fix 3 — locate the cycle, do not silence it

**Do not pass `default=str` or `default=repr` to `json.dumps`.** That converts a structural bug
into a corrupted summary that serializes cleanly and lies.

Find the path:

```python
def find_cycles(obj, path="$", ancestors=frozenset()):
    """Report key paths where a container references one of its own ancestors."""
    oid = id(obj)
    if oid in ancestors:
        return [path]
    if isinstance(obj, (dict, list, tuple)):
        ancestors = ancestors | {oid}
        found = []
        items = obj.items() if isinstance(obj, dict) else enumerate(obj)
        for k, v in items:
            sub = f"{path}.{k}" if isinstance(obj, dict) else f"{path}[{k}]"
            found += find_cycles(v, sub, ancestors)
        return found
    return []
```

Run it on the real summary object and **report the key path in your writeup.** Suspect the newly
added affinity-readback and process-table structures first — `psutil.Process` objects and anything
holding a parent reference are the usual sources.

The path also tells you whether those structures are shaped the way the analysis expects, which is
worth knowing independently of the crash.

## Fix 4 — per-block observability

Each appended block record carries, at minimum:

```
cell_id, repeat_index, affinity_requested, affinity_readback_before, affinity_readback_mid
R_prefill, R_decode, wall_ns, ttft_ns
canary_before_ns, canary_after_ns, canary_drift_pct
available_memory_mb_before, available_memory_mb_after, page_reads_per_sec
package_temp (null on this platform), cpu_pct_total, cpu_pct_per_core
lock_acquired_utc, lock_released_utc
timestamp_utc
```

**`available_memory_mb` and `page_reads_per_sec` are not optional.** A block that ran while the
machine was paging is inadmissible, and right now there is no way to tell after the fact. Declare a
block invalid if available memory drops below 500 MB or hard page reads are sustained non-zero
during it.

Also extend the status file with `cell N of 4, repeat M of 7`. During the lost run it was possible
to confirm the process was alive but not that the sweep was advancing — a heartbeat thread beats
whether or not the worker is stuck.

## The rerun

Unchanged from the resume prompt. Four cells, readback is the instrument:

| Cell | Affinity requested | Machine |
|:--|:--|:--|
| C1 | P-cores | clean |
| C2 | LP-E cores | clean |
| C3 | none | clean |
| C4 | none | 4-process P-core burn |

≥7 repeats, randomized cell order, cooldown between, machine lock per block, canary either side.
Affinity readback mandatory in every cell **including C3 and C4 where nothing is requested** — a
requested affinity that readback contradicts is a finding, not a failure.

Budget **~46 minutes** for the sweep; that is now measured rather than estimated.

Reading the result:

- **C1/C2 ≈ 1.98×** → placement explains the anomaly; the freeze lifts.
- **C1/C2 well below 1.98×** → placement is insufficient and the cause is a power or clock operating
  point. Worse outcome. Say so plainly.
- **C3 readback = P-cores, throughput ≈ C1** → unpinned defaults to P-cores when clean.
- **C4 readback = LP-E or mixed, throughput ≈ C2** → contention-driven migration confirmed.
- **C4 readback = P-cores but throughput drops** → direct contention without migration. Different
  mechanism, equally reportable.

## Before you start

The lost run recorded `git.dirty_tree_allowed` — it is not reproducible from `git_sha` alone.
Nothing has been committed since 2026-07-30 and four days of work exists only in the working tree,
which a crash of the wrong kind would take with it. **Raise this to the human before the rerun**;
committing is not yours to do, but flagging it is.

Do not reuse run_id `cb0ed2e3`. Confirm `raw\cb0ed2e3` holds nothing usable and leave it in place as
the record of the failure.

## Report

1. The cycle's key path, from `find_cycles`. Name it explicitly.
2. Confirmation that the dry-run guard fails fast on a deliberately broken summary — demonstrate it.
3. run_id of the rerun, and the per-block JSONL path.
4. The four-cell table: `R_prefill`, `R_decode`, CIs, **readback-observed placement**, canary drift,
   and available-memory range per cell.
5. C1/C2 ratio with CI against the 1.983× target.
6. One line: **placement, contention-driven migration, direct contention, or unexplained.**

Every number carries its run_id per AM-027(b). Lead with anything inadmissible. A block excluded
for paging or canary drift is reported as excluded, not silently dropped.

## Standing constraints

Machine lock every timed block, released before analysis. Launch detached; report the run_id before
exiting. Thresholds do not move. No commit, no push, no raw mutation, no cloud call, no credential
load.
