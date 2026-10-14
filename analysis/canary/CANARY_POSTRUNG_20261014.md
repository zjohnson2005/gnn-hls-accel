# NPU-INT8: first post-arm canary shift (task AJ, 2026-10-14; analysis only)

New file; analysis/canary/CANARY_DRIFT_20261014.md is unchanged. Sealed data
from derived/npu/sealed_<run>/work/canaries. Signed t1 = t1 / calibration
median - 1. Times ET. Thresholds and the two-sided rule are not touched.

## Per session

| session | sched | uptime | record-only t1 | calib t1 x3 | first window (probes before the first check) | gap s | first post-arm t1 / t2 | later post-arm t1 |
|---|---|---|---|---|---|---|---|---|
| 1024 1e79daa3 | old | 1.91M | - | 1.2226 1.1239 1.0892 | 64 x3, 960 validity | 417 | 0.9853 (-12.3%) / 0.5117 | 1.0939 (-2.7%), 49 s later, after 960 timing x2 |
| 2048a 0fd9cd8c | old | 1.93M | - | 1.1225 1.0872 1.0896 | 64 x3, 1984 validity + 1 timing | 406 | 0.9941 (-8.8%) / 0.5090 | none (TRIP) |
| 4096 63d35555 | old | 1.93M | - | 1.0980 1.1214 1.1002 | 64 x3, 4032 x3 | 444 | 1.0231 (-7.0%) / 0.5318 | 1.1216 1.1223 1.1242 (+1.9 to +2.2%) |
| 2048c 4f6a9102 | old | 1.94M | - | 1.2076 1.1689 1.1732 | 64 x3, 1984 validity + 1 timing | 418 | 1.0907 (-7.0%) / 0.7811 (+57%) | none (TRIP t2) |
| 8192 3b36e9e4 | old | 5.4k | - | 1.0866 1.1177 1.1191 | 64 x3, 8128 x3 | 211 | 1.0235 (-8.4%) / 0.5385 | none (TRIP) |
| 2048d 9acabbf7 | amended | 11.6k | 1.0837 | 1.0897 1.0804 1.1161 | 64 x3, 1984 validity + 1 timing | 152 | 1.0207 (-6.3%) / 0.4799 | 1.0829 (-0.6%), 28 s later, after 1984 timing x1 |
| 8192 c759d72f | amended | 14.9k | 1.1175 | 1.3077 1.2164 1.2402 | 64 x3, 8128 x3 | 210 | OTHER (CL_OUT_OF_RESOURCES) | none |
| 4096 0965a50b | amended | - | not copied | median 1.209 (reported) | not copied | - | -13.2% (reported; about 1.05) | none (REFUSED) |

- "gap s" is from the last calibration canary to the first post-arm
  canary.
- In amended sessions the warm rung (64 tokens: NPU 64 + GPU 64 + NPU 1 + 1)
  runs between the record-only canary and calibration.
- 0965a50b figures are Zach's report, not sealed. The evidence is still on
  the T2S.

## 1. Is the first post-arm canary systematically faster?

- Yes. In all 7 sessions with a value, t1 at the first post-arm check is
  6.3% to 13.2% below the calibration median: 6 sealed, 1 reported.
- Absolute level: first post-arm t1 = 1.023 +/- 0.037 s (n = 6 sealed)
  against calibration medians of 1.116 +/- 0.032 s.
- Scale with the preceding rung height: no. Spearman rho(shift, high rung)
  = 0.17 over highs 960 / 1984 x3 / 4032 / 8128.
- Scale with time since calibration: no. rho(shift, gap) = -0.09 over gaps
  of 152-444 s.
- Host uptime: the shift appears both before the 2026-10-14 08:29 AM reboot
  (uptime about 1.9 M s) and after it (5k-12k s).
- t2 at the first check shifts -2.4% to +7.2% (all inside the 0.164 t2
  floor), except for 2048c's host event (+57%).
- n is small (6 sealed). These are counts and rank correlations, not tests.

## 2. Does calibration capture a pre-rung state the checks never return to?

- No, not a persistent one. Later post-arm canaries return to the
  calibration level:
  - 1024: -2.7%
  - 4096: +1.9 to +2.2%, three canaries over 20 min
  - 2048d: -0.6%, 28 s after the dip
- The low reading is a transient at the first post-arm check only. It
  shows up after windows with very different content: 64 + 960 validity,
  64 + 1984, 64 + 4032 x3, 64 + 8128 x3.
- Every first window is the first time in the session that the GPU
  reference pipeline generates at the session's high rung, after NPU decode
  at that rung. Later windows (mid rungs, also with paired GPU generates)
  are not followed by a dip. This is consistent with a "first large paired
  generate" effect, but the data cannot separate it from any other one-time
  event in that window.
- The amendment's 64-token warm rung did not move calibration toward the
  dip state:
  - 2048d: calibration median vs record-only +0.6% (reading B)
  - 8192 c759d72f: +11.0% (inconclusive; calibration slower)
  - 0965a50b: calibration median 1.209, about 9% above the old-schedule
    mean
- So the warm rung at 64 does not reproduce whatever the high-rung first
  window does. Under the amendment, the first check still dips
  (2048d -6.3%, 0965a50b -13.2%).

## What this means for the floors (no change made)

- With a tight calibration, the t1 threshold sits at the 0.0771 floor.
- The transient is -6.3% to -13.2%, so the first check trips whenever the
  dip exceeds 7.7%: 4 of 7 sessions (2048a, 8192 pre, 0965a50b, plus 1024
  had it not been for its widened threshold).
- This is systematic, not random. Repeating a session without a protocol
  change has a roughly even chance of the same outcome. That is why 8192
  attempt 3 is skipped today.

## What would separate the explanations (see the window-2 draft)
- Repeat the first window inside calibration (warm at the high rung, with
  its paired GPU generate) and check whether calibration then reads about
  1.02.
- Run the canary in a child process to remove the shared in-process GPU
  state. If the in-process canary dips and a child-process canary taken at
  the same point does not, the coupling is in-process.
