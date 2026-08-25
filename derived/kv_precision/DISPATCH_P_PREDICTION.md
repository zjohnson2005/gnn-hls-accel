# DISPATCH P â€” PREDICTION (before interleaved launch)

**Status:** recorded before launch. Do not edit after the interleaved matrix starts.  
**Date:** 2026-08-12  
**Design change vs DISPATCH O:** one matrix, three KV precisions **interleaved** inside each randomized round, with an in-run drift canary. Sequential one-arm matrices are **superseded for precision comparison** (thermal confound).

## Grid

| axis | values |
|---|---|
| arms | `gpu_only_f16` (pinned f16), `gpu_only_u8`, `gpu_only_u4` |
| n_cached | 2000, 4000, 8000, 12000 |
| deltas | 50, 150, 400, 1000 |
| modes | RESIDENT **and** NON_RESIDENT at **every** delta |
| repeats | 3 |
| matrix cells | 3 Ã— 4 Ã— 4 Ã— 2 Ã— 3 = **288** |
| canary | `gpu_only_f16`, nc=4000, d=400, RESIDENT, every **N=12** matrix cells (+ start) |

Order of `(arm, n_cached, mode, delta)` is freshly randomized each repeat (existing matrix shuffle) so arm identity is not aligned with wall-clock / thermal phase.

## Why sequential DISPATCH O failed (link)

Sessions:

- u4: `99aa226c-f396-4388-bf92-17a9762389d8` (`dispatch_o_u4`, 22:54Zâ€“00:16Z)
- u8: `7f569929-4484-4af7-8231-5b535526f653` (`dispatch_o_u8`, 02:33Zâ€“~04:17Z)

Machine under continuous GPU load since ~20:27. Within **u8 alone**, nc=8000 RESIDENT turn1 cold prefill went **6.993 s â†’ 35.789 s (5.12Ã—)**; nc=2000 **~1.07â†’3.49 (3.3Ã—)**; nc=12000 up to **~74 s**. Turn2 drifted less (e.g. 3.150â†’4.831). Tier-2 / Available not the 2026-08-09 memory incident class â€” sustained-compute thermal. With one arm per matrix, **drift IS the arm variable**; â€œu4 25% faster than u8â€ is unsafe.

## What still stands (do not delete; do not re-measure)

| claim | status | citing |
|---|---|---|
| f16 ceiling 36500, `CL_OUT_OF_RESOURCES` | **stands** | session `2804d7fa-â€¦` |
| u8 ceiling â‰¥40000, `early_exit_position_limit` | **stands** | arm run `29253ddc-â€¦`, verdict `2d385fa3-â€¦`, session `37f78cb1-â€¦` |
| u4 ceiling (if sealed under DISPATCH O stage 1) | **stands as ceiling**, not as cross-precision delta comparison | ceiling_a artifacts |
| Old / sequential delta matrices | **superseded for cross-precision comparison**; may remain useful for within-session residency ratios only if canary/thermal admissibility is argued separately | `SUPERSEDED.json` on `99aa226c`, `7f569929`, prior unmatched grids |

## Predictions this dispatch settles

**P2â€² (replaces sequential P2):** under interleaved arms, median RESIDENT `turn2_prefill_s` at matched `(n_cached, delta)` shows **no material systematic win** for u4/u8 vs f16 within the canary-admissible window. If a precision effect exists, it must survive common-mode thermal.

**P3:** residency ratio at deltas 50 and 150 remains **< 0.5** for all three arms (KV retained).

**P4:** NON_RESIDENT scales with n_cached+delta; RESIDENT much more weakly with n_cached â€” readable because NON_RESIDENT runs at every delta.

**P5 (new):** canary turn1/turn2 relative drift stays within the in-run threshold derived from early canary variance; a trip is a **publishable abort**, not a silent degrade.

## Non-predictions

- No BFCL quality claim from this matrix.
- Do not cite 50 TOPS / ~120 GB/s / 1.38Ã— topology as measurements.
- Do not pool with contaminated sequential O cells for precision ranking.
