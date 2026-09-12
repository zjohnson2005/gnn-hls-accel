# PREDICTION — before KV precision ladder + delta-prefill (u8, u4)

> **SUPERSEDED for DISPATCH O predictions by** `derived/kv_precision/DISPATCH_O_PREDICTION.md` (2026-08-11).  
> Reason: DISPATCH O adds matched in-range delta grid + u4 ceiling-only ladder (u8 ceiling already sealed). Hypothesis A/B framing below still historically valid; do not use this file's delta grid description for new runs.

**Status:** recorded before launch. Do not edit after the chain starts.

**Open question (2026-08-09):** `gpu_only` f16 died at **36500** with `CL_OUT_OF_RESOURCES`. Peak working-set slope ~**171.7 KB/token** vs nominal KV **73.7 KB/token** → **2.30×** amplification, matching the **2.33×** decode-traffic factor. Mechanism unknown.

Citing close-out: `derived/ceiling_a/2804d7fa-d9d1-4d76-b376-48104d47b607/CLOSEOUT_gpu_only.md` (session `2804d7fa-…`, arm run `693b44d2-…`).

## Arms

| Arm | Topology | `KV_CACHE_PRECISION` |
|---|---|---|
| `gpu_only` (prior) | load `[GPU]`, generate GPU | unset (observed f16 on GPU) |
| `gpu_only_u8` | same | `u8` |
| `gpu_only_u4` | same | `u4` |

Readback must match request on every cell; mismatch → failed cell, not a measurement.

## Hypotheses (this run settles)

**Hypothesis A — padded KV dominates the 2.30×.**  
If the amplification is mostly padded / oversized KV storage, shrinking element width (f16→u8→u4) reduces the binding footprint enough that the ceiling moves past the model **40960** position limit (bind → position). Prediction under A: `gpu_only_u4` (and possibly `u8`) PASSes the top rung and trips `stop_if_ceiling_at_position_limit`.

**Hypothesis B — attention workspace dominates.**  
If most of the 2.30× is attention / activation workspace that does not scale with KV dtype, then only the ~1× KV component shrinks. Prediction under B: ceiling moves far less than the dtype byte ratio (u8 ≈½, u4 ≈¼ of f16 KV bytes); still memory-bound well below 40960, likely still `CL_OUT_OF_RESOURCES` class.

## What would distinguish them

| Observation | Favors |
|---|---|
| u4 (or u8) ceiling at position limit (40960) | A |
| u4 ceiling still ~mid-30k with same failure class | B |
| Ceiling scales roughly with dtype bytes (f16:36500 → u8:~higher → u4:position) | A |
| Ceiling barely moves across f16/u8/u4 | B |

Delta-prefill matrix (n_cached ∈ {4000,12000}, deltas ∈ {100,400,1000,2000}) records latency under the same precision arms; residency falsification unchanged (RESIDENT turn-2 vs NON_RESIDENT at max delta).

## Non-predictions

- Do not claim BFCL quality from this chain (prior AST: f16 17/20, u8 16/20, u4 17/20 — quality only).
- Do not cite 50 TOPS / ~120 GB/s / 1.38× topology as measurements.
