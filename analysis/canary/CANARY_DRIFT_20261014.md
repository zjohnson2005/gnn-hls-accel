# Canary drift refusals, 2026-10-12 to 2026-10-14 (task AA; analysis only)

No threshold changes, nothing run. Table:
`analysis/canary/CANARY_DRIFT_20261014.json`, made by
`tools/canary_drift_table.py`. Signed drift is t / ref - 1. ref is the
median of the session's calibration canaries, and it matches each gate's
recorded ref.

## How the gate works (from the records)
- The canary is a GPU cell: `gpu_only_f16`, 4,000 cached tokens + a 400-token
  delta. t1 is the turn-1 prefill, t2 the turn-2 delta prefill.
  - NPU-INT8 sessions use the int8 IR; everything else uses int4.
  - In NPU sessions it runs in the same process as the loaded NPU pipeline
    and the GPU reference pipeline.
- Calibration canaries:
  - T2S NPU: canaries 0-2.
  - XPS P1 / V5-CAL: canaries 1-3 (canary 0 is a warm-up and is discarded).
- Threshold = max(2 x calibration spread, healthy floor). Floors are
  t1 0.0771 and t2 0.1643. The T2S borrows the aipc-c1 floors: the launch log
  says "healthy floors are borrowed from aipc-c1".
- H1 launches record one opening canary, with no drift check.
- NPU-FORMAT-F1 (natstop_f1_b172b287) recorded no canary.

## T2S NPU-INT8 sessions (GPU canary while the NPU session runs)
| session | calib spread t1/t2 | thr t1/t2 | first checked canary: elapsed, t1, t2 | workload before it | later canaries t1 / t2 | result |
|---|---|---|---|---|---|---|
| 1024 1e79daa3 | 0.088/0.159 | 0.176/0.317 | 447 s, -12.3%, +0.7% | rungs 64, 960 (2 validity) | -2.7% / +1.5% | pass |
| 2048a 0fd9cd8c | 0.030/0.008 | 0.077/0.164 | 436 s, -8.8%, -1.2% | rungs 64, 1984 (2 validity) | none | TRIP t1 |
| 4096 63d35555 | 0.019/0.007 | 0.077/0.164 | 474 s, -7.0%, +3.7% | rungs 64, 4032 (2 validity) | +1.9..+2.2% / -1.4..+0.4% | pass |
| 2048b e8a27848 VOID | 0.029/0.020 | 0.077/0.164 | none (stopped) | none | none | VOID |
| 2048c 4f6a9102 | 0.029/0.026 | 0.077/0.164 | 449 s, -7.0%, +57.0% | rungs 64, 1984 (2 validity) | none | TRIP t2 |

- Host uptime 1.927-1.938 M s for every T2S session. The T2S is not
  rebooted (UNCOLD_UPTIME deviation).
- Power: no battery; High performance scheme; processor min/max 100 at
  launch.
- The NPU's own (non-gating) canary series is flat at 3.883-3.886 s in
  4096. Its single sample in 1024 is 4.116 s.

## XPS sessions (GPU only, no NPU)
| session | thr t1/t2 | checked canaries: t1 signed (t2 signed) | trip |
|---|---|---|---|
| P1 A5 e31a0a89 | 0.080/0.331 | -1.6..-3.7% (t2 -14..-25%) | none |
| P1 A5 824cad12 | 0.273/0.658 | +1.0, +2.6, **+15.8, +15.4**, +1.1% (t2 to +38%) | none (wide threshold) |
| P1 A0 bdc32a87 | 0.077/0.348 | -3.1, -0.7% (t2 -13, -17%) | none |
| V5-CAL u8 a178e9c5 | 0.077/0.164 | -1.5..-4.0% | none |
| V5-CAL u4 e1ed06b4 | 0.103/0.164 | +5.2, -3.0, 0.0% | none |
| P1 A4 [0:53] a766bd0b | 0.077/0.364 | -0.4..-3.8% (t2 -8..-25%) | none |
| P1 A4 [53:100] eb6cd6ce | 0.077/0.188 | +0.3%, **+14.9%** (t2 +18.3%) | TRIP t1 at canary 5 |

- eb6cd6ce tripped at elapsed 2404 s, uptime 2763 s. The window before the
  trip was the heaviest in the session: 8 entries, 76 steps, 757 s. The
  other windows had 49-58 steps and 471-561 s.
- XPS: on AC, charge 100% at every canary. Available memory 4.1-4.7 GB
  during P1 (6.6-6.9 GB before load). Process count 220-235.
- H1 opening canaries (t1/t2, single values): T2S int4 1.021-1.125 /
  0.439-0.500; XPS 2.587-2.610 / 0.996-1.049.

## Patterns (counts only)
1. **First check on T2S NPU sessions: t1 is faster.**
   - In all 4 NPU sessions that reached a checked canary, the first one
     (after rung 64 and the high rung, including 2 validity repeats) has t1
     7.0-12.3% below calibration.
   - Later canaries return to within 2.7% (1024: 1; 4096: 3).
   - It tripped only in 2048a. 2048a's calibration was tight (spread 0.030),
     so the 0.077 floor applied and -8.8% crossed it.
   - The other three did not trip:
     - 4096 (-7.0%) and 2048c's t1 (-7.0%) were just under the floor.
     - 1024 (-12.3%) passed only because its slow canary 0 (+8.8%) doubled
       its threshold to 0.176.
2. **2048c t2 is a single, different event.**
   - t2 was +57.0%, with t1 normal-ish.
   - Only this session had extra host activity: process count 111-119 at
     calibration vs 102-108 in the other NPU sessions; available memory
     38.2-39.4 GB vs 40.3-41.4 GB; committed memory 25.7-26.8 GB vs
     24.8-25.9 GB.
   - It started about 51 min after the operator stopped e8a27848.
     foreign_queue_evidence is empty. The extra processes are not named in
     any record, so they are unexplained.
3. **MAX_PROMPT_LEN: no pattern.**
   - The t1 effect appears at 1024, 2048 and 4096.
   - Of the 2048 attempts, one tripped on t1, one was void, and one tripped
     on t2.
4. **Elapsed time and uptime.**
   - The T2S trips came at the first checked canary (436 and 449 s), not
     late in the session.
   - The XPS t1 excursions of about +15% came mid-session: 824cad12 at
     uptime 3788-4314 s (passed), eb6cd6ce at 2763 s (tripped). They occur
     without any NPU.
5. **Threshold width decides the outcome as much as drift size.**
   - Same-size excursions passed in 824cad12 (+15.8%, threshold 0.273) and
     1e79daa3 (-12.3%, threshold 0.176).
   - They tripped in eb6cd6ce (+14.9%) and 0fd9cd8c (-8.8%), both at the
     0.077 floor.
6. **Shared GPU between sessions: none.**
   - No two T2S measurement sessions overlapped. a4284ab0 ended 23:09:41Z
     before 0fd9cd8c started (23:48Z).
   - 30caa847 started 01:57:11Z, after e8a27848's worker stopped (01:55:30Z).
   - Inside an NPU session, the GPU reference pipeline runs the paired
     validity generate between canaries.

## What would separate "NPU load perturbs the GPU canary" from "host drift"
- **Sham NPU session on the T2S:** the same launcher and canary schedule,
  NPU pipeline loaded, with each NPU probe replaced by an idle wait of equal
  wall time. Then a second variant with no NPU pipeline loaded.
  - If the first-check t1 drop of 7-12% persists with no NPU compute, it is
    not the NPU.
- **Split the first window:** add an unguarded (record-only) canary right
  after rung 64's paired GPU validity generate, and another right after its
  NPU decode.
  - This separates the GPU reference pipeline's first use from NPU decode.
  - All four first windows contain both.
- **Per-canary host record:** GPU and NPU clock, package power, temperature,
  and the process names that appeared since the last canary.
  - None is recorded now; the gates record the power plan once at launch.
  - The 2048c process-count jump cannot be attributed without names.
- **Operator activity log:** timestamps of every ssh/scp/poll on a host
  during a session. That would show whether operator activity lines up with
  process-count jumps like the one in 2048c.
- **XPS without NPU:** the +15% mid-session t1 excursions (824cad12,
  eb6cd6ce) already show host drift on a host with no NPU work. A repeat of
  the same P1 slice measures how often that happens.
