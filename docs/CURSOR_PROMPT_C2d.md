# Cursor dispatch — C2d: scope the gate, fix the output path, seal

Track: `agent`. Attrib frozen. Everything in C2b and C2c not restated here still stands.

---

## What pilot `a161f89e` settled

**Three problems are closed:**

```
teardown            works — free memory recovers (C2T13: 943 → 2,065 MB)
accumulation        FALSIFIED — free-before RISES across tasks:
                    1846 → 2085 → 2300 → 2382 → 2303 MB
C2T20 cap           correct behaviour — projected_next = 7,461 vs 7,000 cap
median ratio        7.12  ≥ 3.0 gate
```

The memory story is finished. Teardown plus the 7,000-token cap holds the machine steady at ~2.3 GB
free, against the 70 MB that killed `0fe5e4c7`.

**Two failures remain.**

## 1. Warmup page-reads — scope the gate to timed blocks. This defect is specification, not code.

C2c prescribed teardown-and-reload between tasks. A reload faults a 2.6 GB model in from disk, which
**generates page reads by construction.** The paging gate then invalidates on them.

The gate exists to detect whether a *measurement* was contaminated by paging. Setup, teardown,
reload and warmup are not measurements and inherently touch disk.

**Fix:** start the paging sampler when the timed block begins and stop it when the block ends.
Exclude setup, teardown, model load, warmup generation, and cooldown from the sampling window
entirely — not by filtering after the fact, but by not sampling outside the block.

Record `paging_window_start_utc` and `paging_window_end_utc` per block so the scope is auditable
rather than assumed.

**Do not loosen the threshold.** The threshold is correct; it was being applied to the wrong window.

## 2. The Unicode failure, and the class it belongs to

`UnicodeEncodeError` printing `→` under cp1252, after all tasks completed. Second run destroyed by
an output-path defect after the measurement was spent — `cb0ed2e3` was the first, a circular
reference at manifest emit.

**2.1 — Make the class impossible.** At process start, before any logging is configured:

```python
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```

Set `PYTHONIOENCODING=utf-8` in the detached launcher as well. Belt and braces — the launcher may
spawn through a shell that resets it.

**2.2 — Extend the startup dry-run to cover the output path it missed.** It currently exercises JSON
serialization, sealing and verification. It must also emit a synthetic log line **containing
non-ASCII** through the real logger and the real print path, so an encoding failure surfaces in two
seconds rather than after a completed sweep.

**2.3 — Add a test** that writes non-ASCII through the logging path with `stdout` forced to cp1252,
and asserts it does not raise.

**2.4 — Record in C9.** Two completed runs lost to write-path defects discovered only after the
measurement finished. The pattern is that the output path is exercised for the first time when the
data is already irreplaceable. The dry-run is the countermeasure and its coverage must match every
path the run actually uses.

## 3. Diagnose C2T13

`block_valid=False` on C2T13, cause not reported. Report which gate tripped, the measured values,
and the thresholds. If it was paging, re-evaluate it under the scoped window from §1 — it may not be
an invalidation at all.

## 4. Re-pilot and seal

≥5 tasks. Pass conditions, all three required:

- median per-task context ratio ≥ 3.0
- **zero invalidations inside timed blocks** — setup and teardown paging no longer counts
- **the run seals**, verified by `verify_sealed`

The seal is the gate that has failed twice now. Treat sealing as the deliverable, not as a
formality after it.

## 5. Then the full run

Exactly as C2b §6: deadline grid derived from the measured `t_pred` distribution with ≥8 points
spanning its range, the amendment withdrawing the pre-registered 8 s deadline, corrected proxy per
AM-027, exclusionary paging gate on baseline `e6bae93f` **scoped to timed blocks**, cloud backend
that raises, P1–P6 at materiality 1.2×, and the computed ceiling `C_max/C_min` reported alongside
the measured over-provisioning.

## Report, in order

1. Paging-window scoping — the recorded start/end timestamps for one block, demonstrating setup and
   teardown fall outside.
2. Dry-run extension — demonstrate it fails fast on a deliberately un-encodable log line.
3. C2T13's actual invalidation cause, re-evaluated under the scoped window.
4. Re-pilot: ratios, invalidations inside blocks, and **`verify_sealed` result**.
5. Then the full run.

## Standing constraints

Machine lock every timed block, canary either side with the double-sample from C2c §4, detached
launch. No commit, push, raw mutation, cloud call, or credential load. Thresholds do not move.
Every number carries its run_id per AM-027(b).
