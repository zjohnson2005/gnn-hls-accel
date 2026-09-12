# Kernel-Power × acceptance repeat correlation (2026-08-06)

Analysed UTC: `2026-08-06T21:27:22.256863+00:00`

Report only. No re-measurement. Power policy / band / basis / repeats unchanged.

## Decisive table

| Verdict | Outlier | Coincidence | Note |
|:--|:--|:--|:--|
| `9e3ca312…` | arm_1 r0 | **none** | No Kernel-Power event inside any reconstructed repeat window for this pair. |
| `09dfe95d…` | arm_2 r2 | **outlier_only** | Outlier repeat window contains Kernel-Power event(s); clean repeats do not. Cause named for this pair. |

## pre_run_settle

With pre_run_settle (pair 2 / 09dfe95d), arm_1 CV improved 0.145→0.037, but arm_2 repeat 2 became the sole outlier (CV 0.159) during Modern Standby. Prior pair (9e3ca312) outlier was arm_1 repeat 0 with no Kernel-Power in-window. Dip is sporadic, not positional — settle is not a complete explanation.

## free_physical headroom risk

free_physical_bytes_at_peak differed ~1.47× between arms (2.688 GB vs 1.824 GB) while peak_working_set agreed to ~1.0002×. Headroom at peak is far less reproducible than consumption — direct risk to ceiling determination; understand before ceiling(A), not after.

Artifact JSON: `derived/fixed_throughput/kernel_power_repeat_correlation_20260806.json`
