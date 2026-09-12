# DISPATCH O — wall-clock estimate (from measured f16/u8 walls)

**Recorded before stage 1. No invented durations.**

```
central_estimate_h: 5.30
upper_estimate_h: 6.89
upper_exceeds_6h: true
```

**Upper > 6 h — do not auto-launch the full four-stage sequence overnight without operator acknowledgment of the overrun.** Stage 1 alone is ~1.2 h central.

## Sources (measured)

| Stage class | Citing artifact | Measured wall |
|---|---|---|
| ceiling `gpu_only` f16 | launch `ceiling_a_20260807_150154` → session `2804d7fa-…` | settle start 2026-08-07T19:01:54Z → done ~20:51:32Z = **6580 s = 1.828 h** (includes 300 s settle; died at 36500) |
| ceiling `gpu_only_u8` | launch `ceiling_a_20260810_150053` → session `37f78cb1-…` | settle start 2026-08-10T19:00:54Z → sealed heartbeat 20:12:07Z = **4265 s = 1.185 h** (`early_exit_position_limit`) |
| delta `gpu_only_u8` cells | session `4f1db452-…` OK cells | nc=4000 RES med **21.2 s** / NON **24.5 s**; nc=12000 RES **35.3 s** / NON **53.3 s** |
| inter-cell settle | `configs/delta_n.yaml` `recovery.settle_s` | **20 s** |
| pre-run settle | `isolation.pre_run_settle_s` | **300 s** per stage |

## DISPATCH O matrix shape (each of stages 2–4)

- arms: 1 (`gpu_only_u4` / `gpu_only_u8` / `gpu_only`)
- n_cached: {2000, 4000, 8000, 12000}
- deltas: {50, 150, 400, 1000} × RESIDENT **and** NON_RESIDENT (every delta)
- cells/round = 4 × 4 × 2 = **32**; × 3 repeats = **96 cells**

### Cell-time model (from u8 medians; nc=2000/8000 interpolated)

| n_cached | RES med (s) | NON med (s) | 12 RES + 12 NON (s) |
|---|---|---|---|
| 2000 | 12 | 14 | 312 |
| 4000 | 21.2 | 24.5 | 548 |
| 8000 | 28.3 | 38.9 | 806 |
| 12000 | 35.3 | 53.3 | 1063 |
| **compute subtotal** | | | **2729** |
| inter-cell settle | 95 × 20 | | 1900 |
| pre_run_settle | 1 × 300 | | 300 |
| **one delta matrix** | | | **4929 s = 1.37 h** |

## Four-stage total

| Stage | Central | Upper |
|---|---|---|
| 1. ceiling `gpu_only_u4` | 1.185 h (u8 early-exit twin) | 1.828 h (f16 full ladder if no early exit) |
| 2. delta `gpu_only_u4` | 1.37 h | 1.64 h (+20%) |
| 3. delta `gpu_only_u8` | 1.37 h | 1.64 h (+20%) |
| 4. delta `gpu_only` f16 | 1.37 h | 1.78 h (+20% and ×1.15 vs u8 cell times) |
| **total** | **5.30 h** | **6.89 h** |

### Upper-bound rationale

u4 ladder may early-exit like u8 (~71 min) or, if Hypothesis B reappears, run toward the f16 wall (~1.83 h). Delta upper allows +20% settle/queue inflation; f16 cells historically slower than u8 at nc=4000 in mixed-arm session `9f38eb15` — apply ×1.15 on stage 4. CellTimeoutS=1500 hits are failure data and grow the wall further.

## Gate

`upper_estimate_h: 6.89` **> 6.0** → prepare OPERATOR_CMD for all four stages; **do not auto-launch overnight** without noting the overrun. Stage 1 alone (~1.2 h central) is within a single session if preconditions pass.
