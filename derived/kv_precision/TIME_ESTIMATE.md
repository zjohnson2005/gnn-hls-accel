# KV precision chain — wall-clock estimate (from measured f16 cells)

> **SUPERSEDED for DISPATCH O timing by** `derived/kv_precision/DISPATCH_O_TIME_ESTIMATE.md` (2026-08-11).  
> Reason: old chain shape (30 cells/arm, NON_RESIDENT max-only, nc={4000,12000}); DISPATCH O is 96 cells/precision on nc={2000,4000,8000,12000}, d={50,150,400,1000}, NON_RESIDENT every delta. File retained for citation of f16 ceiling wall (1.828 h).

**Recorded before launch.** Do not invent durations; cite sealed f16 artifacts.

```
central_estimate_h: 4.74
upper_estimate_h: 5.50
```

## Sources

| Stage class | Citing artifact | Measured wall |
|---|---|---|
| ceiling `gpu_only` (f16 default) | launch `ceiling_a_20260807_150154` → session `2804d7fa-…` | `pre_run_settle_start` 2026-08-07T19:01:54Z → `ceiling_a.done` 2026-08-07T20:51:32Z = **6580 s = 1.828 h** (includes 300 s settle; 54 cells; died at 36500) |
| delta-prefill `gpu_only` @ n_cached=4000 | sealed `9f38eb15-…` per-cell elapsed | RES/NON cells **~20–25 s** (median ~22 s) |
| delta-prefill `gpu_only` @ n_cached=12000 | sealed `d5c98342-…` OK gpu_only cells | **~46–71 s** (use **50 s** median for estimate; one hung cell excluded) |
| inter-cell settle | `configs/delta_n.yaml` `recovery.settle_s` | **20 s** |
| pre-run settle | `isolation.pre_run_settle_s` | **300 s** per matrix / included in ceiling wall |

## Matrix shape (this chain, per arm)

- arms: 1 (`gpu_only_u8` or `gpu_only_u4`)
- n_cached: {4000, 12000}
- deltas: {100, 400, 1000, 2000} RESIDENT; NON_RESIDENT at 2000 only
- cells/round = 2 × (4 + 1) = **10**; × 3 repeats = **30 cells**

### Delta matrix wall (one arm)

| Component | Calc | Seconds |
|---|---|---|
| nc=4000 cells | 15 × 22 s | 330 |
| nc=12000 cells | 15 × 50 s | 750 |
| inter-cell settle | 29 × 20 s | 580 |
| pre_run_settle | 1 × 300 s | 300 |
| **subtotal** | | **1960 s = 0.544 h** |

## Chain total

| Stage | Estimate |
|---|---|
| ladder gpu_only_u8 | 1.828 h (f16 measured; same protocol) |
| delta gpu_only_u8 | 0.544 h |
| ladder gpu_only_u4 | 1.828 h |
| delta gpu_only_u4 | 0.544 h |
| **central_estimate_h:** | **4.74** |
| **upper_estimate_h:** | **5.50** |

### Upper bound rationale

If Hypothesis A holds and the ladder PASSes through 40000 to the position-limit early exit, wall is similar to (or slightly longer than) the f16 run that already exercised 40000 FAIL cells + bisect (~1.83 h). Allowing +20% on each ladder → 2.2 h × 2 + 0.54 × 2 = **5.48 h**. Still ≤ 6 h.

If a cell hits `CellTimeoutS=1500` repeatedly, wall grows; that is failure data, not a reason to coarsen the ladder.

## Gate

`upper_estimate_h: 5.50` ≤ 6.0 → chain may launch when AC + tier-1 + Available gates pass.
