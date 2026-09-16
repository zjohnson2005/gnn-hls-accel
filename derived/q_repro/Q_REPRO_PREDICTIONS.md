# Q-REPRO predictions (pre-registered BEFORE measurement)

**Registered:** 2026-09-15T21:35:00Z  
**Question:** Does sealed W-3 quality (`6225d6e1`: 45 emission failures, 20 completions) reproduce under its exact KV-unset config, interleaved with pinned f16?

## Arms (one session, interleaved, 200 entries each)

| arm | config |
|---|---|
| A `gpu_only` | KV unset / dynamic — exact W-3 configuration |
| B `gpu_only_f16` | KV f16 pinned — Q-KV best arm (internal control) |

## Outcomes (do not adjust)

| result | interpretation |
|---|---|
| A ≈ 45 failures and ≈ 20 completions; B ≈ 62 failures | dynamic KV is materially different from pinned f16. Report arm A readback. |
| A ≈ 62 (like Q-KV f16) | W-3 does **not** reproduce. Quality instrument unstable across sessions; every sealed quality number (incl. emission OR 4.57 from 6225d6e1/1d8db970) needs a stability statement before the paper. |

No third outcome is pre-registered as preferred. Report what happens.

## Logging

Arm A: KV readback on **every cell** (load-time Core assert + per-cell `read_kv_cache_precision("GPU")`).

## Seal diff

See `SEAL_DIFF_6225d6e1_vs_137f6f46.md` (written before this run).
