# DISPATCH O — PREDICTION (before any stage launch)

**Status:** recorded before stage 1. Do not edit after u4 ceiling launches.  
**Date:** 2026-08-11  
**Grid (identical for u4 / u8 / f16 delta matrices):**

| axis | values |
|---|---|
| n_cached | 2000, 4000, 8000, 12000 |
| deltas | 50, 150, 400, 1000 |
| modes | RESIDENT **and** NON_RESIDENT at **every** delta |
| repeats | 3 |
| cells/precision | 4 × 4 × 2 × 3 = **96** |

## What stands (do not re-measure)

| precision | ceiling | citing |
|---|---|---|
| f16 (`gpu_only`) | 36500, `CL_OUT_OF_RESOURCES` | session `2804d7fa-…`, close-out `CLOSEOUT_gpu_only.md` |
| u8 (`gpu_only_u8`) | ≥40000, `early_exit_position_limit` | arm run `29253ddc-…`, verdict `2d385fa3-…`, session `37f78cb1-…` |

## Predictions (this dispatch settles)

### Ceiling (u4 only — stage 1)

**P1 — padded / dtype-scaled KV still dominates (Hypothesis A continuation).**  
u8 already moved the bind from memory wall (f16@36500) to position limit (≥40000). u4 is a further width shrink.  
**Prediction:** `gpu_only_u4` PASSes the top rung and trips `stop_if_ceiling_at_position_limit` / `early_exit_position_limit` (same class as u8). Ceiling is **padded-cache / position-bound**, not a new memory wall below 40960.

**Falsifier for P1:** u4 dies with `CL_OUT_OF_RESOURCES` (or peer GPU resource class) below the position limit → attention/workspace (Hypothesis B) re-enters for u4 specifically.

### Delta matrices (stages 2–4) — matched in-range grid

**P2 — no material improvement of RESIDENT turn-2 prefill from narrowing KV dtype at fixed (n_cached, delta).**  
Within the operating range (n_cached ≤ 12000, well below ceiling), turn-2 RESIDENT cost is dominated by delta prefill + session overhead, not by KV element width.  
**Prediction:** for matched cells, median `turn2_prefill_s` RESIDENT(u4) ≈ RESIDENT(u8) ≈ RESIDENT(f16) within noise (no systematic win from u4/u8 vs f16).

**P3 — residency ratio at small delta stays low.**  
**Prediction:** median RESIDENT/NON_RESIDENT `turn2_prefill_s` **< 0.5** at deltas 50 and 150 for all three precisions (KV retained; small-Δ regime). At delta=1000 the ratio may rise; do not treat a single large-Δ ratio as the session claim.

**P4 — NON_RESIDENT scales with n_cached+delta; RESIDENT scales much more weakly with n_cached.**  
Matched cold cells (every delta) make this readable; prior max-Δ-only matrices cannot.

## Non-predictions

- Do not claim BFCL quality from these matrices.
- Do not cite 50 TOPS / ~120 GB/s / 1.38× topology as measurements.
- Do not pool local/interactive cells with `ssh_detached` results.

## Supersession

Old delta matrices (unmatched grid / NON_RESIDENT-max-only / above operating range) are superseded for **comparative precision claims** — see per-session `SUPERSEDED.json` / `SEAL_POINTER` notes. Sealed trees are **not** deleted. Ceiling f16/u8 results above **stand**.
