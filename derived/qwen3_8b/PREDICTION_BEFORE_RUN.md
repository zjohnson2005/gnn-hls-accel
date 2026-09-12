# PRE-REGISTERED PREDICTIONS — Qwen3-8B-int4 on gpu_only

**Status:** PRE-DATA. Frozen 2026-08-24 before any Qwen3-8B-int4 transfer, load, or generate. Do not edit after 8B measurement starts.  
**Date:** 2026-08-24  
**Arm:** `gpu_only` (load `[GPU]`, generate GPU)  
**Model:** Qwen3-8B-int4 (OpenVINO IR; FetchedModelSpec required before any cited number)  
**Filter (blueprint §1.2):** additive — varies §2.1 model capability rung (~0.6B / 4B / 8B). Not recorded in §12.4.  
**M6:** recorded for a later gate; **not tested by this gate.**

## Derivation constants (operator-stated)

From Qwen3-4B-int4, session `41e419bd-f3e9-43b1-8364-0ebd89fa086b`:

| constant | operator-stated | sealed 41e419bd `d_peak_ws_slope.arms.gpu_only_f16` |
|---|---|---|
| intercept (peak_ws, n→0) | 3.08 GB | 3,077,246,657.81 B (3.077 GB) |
| f16 slope | 234,827 B/tok | 235,817.21 B/tok |
| decode | 19.85 tok/s @ gpu_only warm | not in that analysis block; 19.8565 tok/s appears on ceiling_a session `37f78cb1` `gpu_only_u8` n=10000 |

Registered bands below use the **operator-stated** constants. Sealed values are listed so a later reader can see the rounding. They do not change the falsifiers.

## Predictions this gate settles

**M1** 8B-int4 loads on `gpu_only` without `CL_OUT_OF_RESOURCES` at n=2000.  
Falsifier: load or first generate fails.

**M2** base footprint (peak_ws intercept, n→0) lands 4.8–6.0 GB.  
Falsifier: outside that band.

**M3** TTFT at n=5000 f16 lands 4–7 s, clearing the 10 s USER_FACING bound.  
Falsifier: >10 s, or <3 s (would mean the weight-scaling assumption is wrong).

**M4** decode lands 8–12 tok/s, clearing the 6 tok/s floor.  
Falsifier: <6 tok/s.

**M5** resident slope B/token is within 10% of 4B's 234,827 at f16  
(KV geometry unchanged: same layers × kv_heads × head_dim).  
Falsifier: outside 10%. If falsified, KV geometry differs and every capacity extrapolation in this thread is void.  
Band: [211,344.3, 258,309.7] B/tok.

**M6** cpu-p arm does NOT fit at n=12000 (4B already peaked 9.46–10.70 GB with 154–388 MB free).  
Not tested by this gate; recorded for later.

## What this gate must measure (no 8B number without a run_id)

| id | required observation | arm / precision |
|---|---|---|
| M1 | load + first generate at n=2000 | gpu_only |
| M2 | peak_ws vs n, intercept of linear fit (n→0) | gpu_only, same precision as slope |
| M3 | TTFT at n=5000 | gpu_only, KV f16 |
| M4 | decode tok/s (gpu_only warm) | gpu_only |
| M5 | resident peak_ws slope B/token at f16 | gpu_only, KV f16 |
| M6 | — | out of this gate |

USER_FACING SLO (existing session-residency definition): TTFT ≤ 10 s AND decode ≥ 6 tok/s.

## Non-predictions

- No BFCL quality claim from this gate.
- Do not cite 50 TOPS, ~120 GB/s, 180 TOPS, or the 1.38× topology figure as measurements.
- Do not treat M6 as tested if this gate never runs cpu-p at n=12000.
- Do not start 8B measurement until this file's hash is recorded in `predictions.json`.
