# Cursor dispatch — Prompt A2: throughput integrity

Supersedes Prompt A. Track: `agent`. **Measurement freeze remains in force** — attrib does not
measure, and Prompt C stays blocked, until this reports a verdict.

---

## Orientation

Call `seam_status()`, `seam_pins()`, `seam_platform()`. The blueprint moved — **AM-027** landed
2026-08-04 and the pin changed; read it live, do not trust any hash quoted anywhere.

Read AM-027(b) before you write a number anywhere: **no quantitative claim leaves this repository
without a run_id attached at the point of use.**

## What happened since Prompt A

Three quiesce refusals, then a machine restart:

```
attempt 1   total CPU 56.79% > 20%   ·   P-core mean 32.40% > 30%   ·   avail 823 MiB < 2048
attempt 2   P-core mean 30.42% > 30%
attempt 3   abnormal exit after model load  ← the machine restarted
.locks/machine.lock  holds dead PID 25196
```

Two things follow, and the second matters more than the blockage.

**The hardened quiesce gate is working.** The old process-name allowlist would have passed all
three of those attempts and written `deviations: []`.

**Which is retroactive evidence.** The two runs behind the 1.98× were gated by the *old* check,
which could not see 56% CPU or 823 MiB of headroom. The machine is routinely contended and the
previous gate was blind to it. That raises the prior on contention as the cause **before you run
anything** — but it is not a verdict, and you will not report it as one.

## Step 0 — clear the lock correctly, not manually

`.locks/machine.lock` holds a pre-restart PID. Do not just delete it; fix the class of bug.

Extend the lock record to `(pid, boot_time, hostname)` and reclaim on these rules only:

- **`boot_time` differs from the current boot** → definitionally stale, reclaim automatically, log
  the reclamation with both boot times.
- **Same boot, PID not alive** → reclaim **only** behind an explicit flag, with a log line. Never
  auto-reclaim on PID liveness alone; a suspended or swapped process would be trampled.

`seam/locks.py` is a shared module. This change is authorized. Keep it minimal, add tests, and do
not alter the existing `exclusive()` contract.

Before anything else, confirm **no orphaned OpenVINO process** is holding the ~2.6 GB model from
the crashed attempt. 823 MiB available on a 16 GB machine points directly at that.

## Step 1 — the manifest diff. NO MEASUREMENT. DO THIS FIRST.

Prompt A specified this first and it did not happen. **It requires no quiesce, no lock, and no
machine state** — it is file reading, and it may resolve the entire question today.

Diff the sealed manifests of `d8f0875b-dfc5-473f-8260-8c8827d18295` and
`1a0166b9-cbaf-43f4-8d76-bcd7c01841e0` **field by field, complete**. Report every difference, not
a summary and not only the ones that look relevant.

Confirm or deny identity on each of these explicitly:

```
INFERENCE_NUM_THREADS          inferred thread count
SCHEDULING_CORE_TYPE           ENABLE_CPU_PINNING
process affinity mask          model IR sha256
OpenVINO / GenAI version       power plan
every environment variable the backend reads
```

**A thread-count or core-placement difference produces exactly 2×.** OpenVINO defaults to P-core
placement regardless of thread count (the A0 finding), so an 8→4 difference is both plausible and
invisible in utilization. If this resolves it, stop and report — do not proceed to Step 3 to
confirm a thing you have already explained.

## Step 2 — make quiesce refusals actionable

The gate currently reports thresholds crossed. It should report **what to close.**

On refusal, emit the top 10 processes by CPU and the top 10 by RSS, with names and PIDs, alongside
the failing measurements. A gate that says "56.79% > 20%" without naming the cause costs a human
round-trip every time it fires.

**Thresholds do not move.** Your instinct in the last report was right and it stands: a gate that
relaxes when it is inconvenient is not a gate.

## Step 3 — the 2×2, only if Step 1 did not resolve it

Under the machine lock, on a freshly-booted quiet machine:

```
                    clean                4-process CPU burn on P-cores
                     A1                            A2
```

Fixed prompt, fixed config, ≥5 repeats per cell, randomized order, cooldown between. Report
`R_prefill` and `R_decode` per cell with CIs.

**Burn reproduces ~2×** → contention confirmed, and the mechanism is that a second track held
P-cores OpenVINO selects by default. **Burn does not reproduce it** → contention excluded, the
cause is a power or clock operating point, and that is the worse outcome. Say which, plainly.

**Launch the sweep detached.** If the run is driven from inside this agent session, the session is
itself part of the contention it is trying to measure. Detach it, let it outlive the session, poll
for completion.

## Step 4 — the canary, because the authorized detector is dead

PDH `Processor Frequency` and `% of Maximum Frequency` return **nominal** clocks: unchanged between
idle and a 4-process burn, and identical across a 1.98× throughput difference. Detector (a) of the
three authorized on 2026-08-02 does not function on this platform. State that in the report as a
finding.

Implement a **calibrated compute canary** as the replacement — it needs no counter this platform
lacks. Fixed-work synthetic kernel of known size, pinned to the same cores as the workload, run
immediately before and immediately after every measurement block. Its runtime *is* the delivered
operating point. Declare a block invalid if the canary drifts beyond a stated threshold across it.

Secondary: `FrequencySampler.summary()` samples `mhz_per_cpu` then discards it, keeping only the
percentage. Retain both.

## Report

In this order:

1. Orphaned-process check and the lock reclamation, with the boot times.
2. **The manifest diff, in full.** If it resolves the 1.98×, stop here and say so.
3. The quiesce refusal reporting, demonstrated on a real refusal if one occurs.
4. The 2×2 table, if you got there.
5. Canary implementation and its measured drift on a known-clean block.

Then one line: **contention, configuration, or unexplained.** If unexplained, say unexplained — do
not offer a mechanism you cannot evidence, and do not lean on the quiesce-refusal history as proof.
That is a prior, not a result.

## Standing constraints

Machine lock on every timed block, released before analysis. Attrib remains frozen from
measurement. No commit, no push, no raw mutation, no cloud call, no credential load. Every number
in the report carries its run_id.
