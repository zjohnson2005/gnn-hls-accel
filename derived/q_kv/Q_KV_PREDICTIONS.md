# Q-KV predictions (pre-registered BEFORE measurement)

**Experiment:** KV precision vs BFCL multi-turn quality, controlled and interleaved.  
**Local only, $0 cloud.** Arms: `gpu_only` RESIDENT int4-4B at KV ∈ {f16, u8, u4}.  
**Entries:** same 200 as W-3 `6225d6e1` (pin `3502c535…`).  
**Registered:** 2026-09-15T16:58:00Z (before any Q-KV generation).

## W-3 unset arm — what it resolved to

Seal `6225d6e1` `session_residency_gpu_only_RESIDENT_report.json` →
`model.loads[0].kv_cache_precision`:

| field | value |
|---|---|
| requested | `null` |
| enforced | `false` |
| readback.normalized | **`dynamic`** |
| readback.to_string | `dynamic` |

W-3 is **not** an f16 pin. Treat W-3 as **unknown / dynamic** precision. Do not equate W-3 with the Q-KV `gpu_only_f16` arm without measurement.

## Hypothesis (from EMIT_GAP)

KV precision moves emission. Between-run gap: dynamic (W-3) 45/200 empty-turn vs u8 (R2a) 65/200, with the 45 ⊂ 65. Never measured under interleaved control. If true, KV is a quality axis and the D1 replay Pareto claim that `gpu_only|RESIDENT|u8|int4|4B` is dominated by `…|u4|…` (quality-neutral pruning) is wrong.

## Pre-registered predictions

### Emission success order
`f16 > u8 >= u4` (higher = more entries with parseable tool emission on every local turn).

### Emission failure counts (n=200)
| arm | predicted failures |
|---|---|
| f16 | **45** |
| u8 | **65** |
| u4 | **≥ 65** |

### Completion (trajectory_pass via W-3 scorer / `entry_quality.json`)

Order: **`f16 > u8 >= u4`**.

Absolute (stated before run; provisional because W-3 baseline is dynamic, not f16):

| arm | predicted trajectory_pass |
|---|---|
| f16 | **20 / 200** (0.10) |
| u8 | **14 / 200** (0.07) |
| u4 | **≤ 14 / 200** |

Rationale: W-3 int4 trajectory was 20/200 under dynamic KV; EMIT_GAP’s +20 emission failures on u8 imply a proportional completion drop (~30% relative → ~14/200). u4 is predicted no better than u8 on quality.

### Falsification
Falsified if the three arms **agree within paired-test resolution**: for both emission and completion, every pairwise McNemar exact two-sided test has p ≥ 0.05 (or zero discordant pairs). Then KV is not a quality axis at this resolution and u8-dominated-by-u4 pruning on the latency Pareto may stand.

### Analysis
Paired on entry; McNemar per pair (f16–u8, f16–u4, u8–u4); report 2×2 tables for emission and for completion.

## Machine-readable twin

`derived/q_kv/Q_KV_PREDICTIONS.json`
