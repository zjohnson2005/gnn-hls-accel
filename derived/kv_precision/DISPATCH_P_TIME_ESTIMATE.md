# DISPATCH P â€” wall-clock estimate (interleaved precision + canary)

**Recorded before launch. No invented durations.**

```
central_estimate_h: 4.52
upper_estimate_h: 5.55
upper_exceeds_6h: false
upper_exceeds_8h: false
matrix_cells: 288
canary_every_n: 12
expected_canaries: 25
```

Upper is under 6â€“8 h. Still **BLOCKED_ON_OPERATOR** until cool/idle gates pass (see OPERATOR_CMD).

## Cell count

| axis | values | count |
|---|---|---|
| arms | `gpu_only_f16`, `gpu_only_u8`, `gpu_only_u4` | 3 |
| n_cached | 2000, 4000, 8000, 12000 | 4 |
| deltas Ã— modes | {50,150,400,1000} Ã— {RESIDENT, NON_RESIDENT} | 8 |
| cells/round | 3 Ã— 4 Ã— 8 | **96** |
| repeats | 3 | |
| **matrix cells** | 96 Ã— 3 | **288** |

## Sources (measured; same as DISPATCH O)

| quantity | citing | value |
|---|---|---|
| delta cell walls (u8 medians â†’ nc model) | `DISPATCH_O_TIME_ESTIMATE.md` / session `4f1db452` | one 96-cell single-arm matrix **4929 s = 1.37 h** (includes 300 s pre_run_settle) |
| inter-cell settle | `configs/delta_n.yaml` `recovery.settle_s` | 20 s (inside the 4929 s model) |
| pre_run_settle | `isolation.pre_run_settle_s` | 300 s **once** for the interleaved launch |
| f16 vs u8 cell factor | DISPATCH O upper rationale / mixed session `9f38eb15` | Ã—1.15 on the f16 third of cells |
| canary cell class | same model, RESIDENT nc=4000 | ~21.2 s compute + 20 s settle â‰ˆ **41.2 s** |

## Central derivation

Single-arm stage wall includes one pre_run_settle; interleaved launch pays settle once:

```
one_stage_without_prerun_s = 4929 - 300 = 4629
f16_mix_factor              = (1.15 + 1.0 + 1.0) / 3 = 1.05
matrix_s                   = 3 Ã— 4629 Ã— 1.05 = 14581.35
canaries                   = 1 (start) + floor(288/12) = 25
canary_s                   = 25 Ã— 41.2 = 1030
prerun_s                   = 300
total_s                    = 14581.35 + 1030 + 300 = 15911.35
central_h                  = 15911.35 / 3600 = 4.42
central_estimate_h         = 4.52   # +~2% orchestration / heartbeat slack
upper_estimate_h           = 5.55   # +20% settle/queue inflation on central
```

## Canary N derivation (not a convenience round number)

Citing session `7f569929-4484-4af7-8231-5b535526f653` (`dispatch_o_u8`):

| event | utc | nc=8000 RESIDENT turn1_prefill_s |
|---|---|---|
| last-good | 2026-08-12T03:15:35Z | 6.993 |
| first-bad | 2026-08-12T03:26:32Z | 33.958 |
| late max (user 5.1Ã—) | 2026-08-12T04:11:03Z | 35.789 (ratio vs 6.993 = **5.12Ã—**) |

```
Î”t_onset           = 657 s
mean_cell_wall_s   = 4929 / 96 = 51.34 s   # DISPATCH_O_TIME_ESTIMATE
cells_in_onset     = 657 / 51.34 â‰ˆ 12.8
CanaryEveryN       = floor(cells_in_onset) = 12
```

**Meaning:** at least one canary is scheduled inside the measured last-goodâ†’first-bad window so a silent 5Ã— degrade aborts rather than completing.

## Threshold derivation (in-run; not a pre-chosen multiple)

After `CanaryCalibrationCount=3` successful canaries:

```
ref_t1 = median(turn1_prefill_s of calib set)
ref_t2 = median(turn2_prefill_s of calib set)
early_max_t1 = max_i |t1_i - ref_t1| / ref_t1
early_max_t2 = max_i |t2_i - ref_t2| / ref_t2
threshold_t1 = max(2 Ã— early_max_t1, 0.05)
threshold_t2 = max(2 Ã— early_max_t2, 0.05)
```

- **2 Ã— early_max:** allow as much *additional* deviation beyond the calibration envelope as was already seen inside it.
- **floor 0.05:** same absolute margin spirit as sealed C2f `canary_gate.margin_above_idle_p95=0.05` (`derived/efilter/canary_gate.json`, run `f632701a-â€¦`) when early_maxâ‰ˆ0.
- Gate arms only after calibration. Abort `status=FAIL_CANARY_DRIFT` if either turn exceeds its threshold.
- **Not** a round number like â€œabort at 2Ã—â€ or â€œabort at 5Ã—â€ chosen a priori.

## Gate vs overnight

`upper_estimate_h: 5.55` **< 6**. OK duration-wise overnight **once** cool/idle gates pass. Still report the estimate before launch.
