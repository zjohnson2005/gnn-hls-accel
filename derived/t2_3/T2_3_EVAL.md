# T2-3 evaluation — Platform A CAP-4 vs T2S (evo-t2)

- **evaluated_utc:** `2026-09-20T20:57:22.689395+00:00`
- **predictions:** `derived/t2_3/T2_3_PREDICTIONS.json` (registered `2026-09-20T14:55:13+00:00`)
- **Platform A anchor:** `2b3316b6-7f6e-474f-9177-bd5a89aeb58c` (`MEASURED(2b3316b6)`)
- **T2S measurement:** `65e33de8-ac07-405a-a1f8-53698974afe9` — executed on **evo-t2**, sealed on **aipc-c1** (cross-host reconstruct)
- **T2S seal tree_sha256:** `932cfd68384282412832041d23ce9a072c34aadef827a56853a8d6d17795b582`
- **T2S status:** `aborted` (`Stop-Process -Force`; highest PASS n=94000)

## Headline

P1 partially holds on the preferred non-collapsed depth arm (u8 @46k ≈2.33× ≈ BW ratio). P3 misses at depth (absolute prefill much faster than BW scale). Therefore: bandwidth predicts decode better than it predicts prefill; replay cannot use one ratio for both when predicting a third platform. P2 falsified (exponent ≈1.85 not 2.1–2.2). P4 held in measured sweep. P5 untested.

If P1 holds and P3 misses: bandwidth predicts decode, compute predicts prefill — one BW ratio cannot serve both when projecting a third platform. Observed here: P1 partial hold (u8@46k); P3 miss at 46k.

## P1 — decode ratio at depth vs ~2.6×

- **verdict:** `partial_hold`
- Primary depth claim (u8 @ n=46000): ratio 2.3348 within [2.0, 3.4]. f16 @12k and u4 @46k outside band; f16 @46k excluded (A collapsed). Decode scales nearer the theoretical BW ratio than absolute prefill does.

| n | arm | decode A (tok/s) | decode T2S | ratio | band [2.0, 3.4] |
|---:|---|---:|---:|---:|:---:|
| 12000 | `gpu_only_f16` | 17.3476 | 22.3445 | 1.2880 | N |
| 12000 | `gpu_only_u8` | 19.8481 | 26.4741 | 1.3338 | N |
| 12000 | `gpu_only_u4` | 19.3888 | 28.1968 | 1.4543 | N |
| 46000 | `gpu_only_f16` | 1.1589 | 10.5423 | 9.0969 | N — Platform A f16 decode collapsed at n=46000 (~1.16 tok/s); ratio not BW-efficiency eligible |
| 46000 | `gpu_only_u8` | 6.3858 | 14.9099 | 2.3348 | Y |
| 46000 | `gpu_only_u4` | 4.9472 | 17.8480 | 3.6077 | N |

Citing: A=`2b3316b6-7f6e-474f-9177-bd5a89aeb58c`; B=`65e33de8-ac07-405a-a1f8-53698974afe9`.

## P2 — fitted prefill exponent vs 2.1–2.2

- **verdict:** `falsified`
- T2S prefill exponents on matched fit_range_n=[12000,76000] are b≈1.85 across all three arms (below predicted 2.1–2.2 and below falsify floor 1.9). Shift vs Platform A exceeds 0.3. Prefill scaling is not the same power-law as Platform A.

| arm | A b [12k,76k] | T2S b [12k,76k] | Δb | T2S b [12k,94k] |
|---|---:|---:|---:|---:|
| `gpu_only_f16` | 2.2516 | 1.8487 | -0.4029 | 1.8911 |
| `gpu_only_u8` | 2.1244 | 1.8509 | -0.2736 | 1.8932 |
| `gpu_only_u4` | 2.1512 | 1.8533 | -0.2979 | 1.8936 |

## P3 — prefill absolute vs BW-scaled prediction

- **verdict:** `partial`
- scale = 102/273 = 0.373626
- At n=12000, measured/predicted prefill ∈ [0.89, 0.91] (within [0.7, 1.4]). At n=46000, measured/predicted ∈ [0.54, 0.59] — outside band; T2S is substantially faster than BW-scaled absolute prediction. Prefill at depth is compute-shaped, not pure BW.

| n | arm | A prefill_s | T2S | predicted | meas/pred | in [0.7,1.4] |
|---:|---|---:|---:|---:|---:|:---:|
| 12000 | `gpu_only_f16` | 13.5048 | 4.5492 | 5.0458 | 0.9016 | Y |
| 12000 | `gpu_only_u8` | 13.2771 | 4.5298 | 4.9607 | 0.9131 | Y |
| 12000 | `gpu_only_u4` | 13.5503 | 4.5202 | 5.0628 | 0.8928 | Y |
| 46000 | `gpu_only_f16` | 252.7079 | 50.7478 | 94.4183 | 0.5375 | N |
| 46000 | `gpu_only_u8` | 230.3604 | 50.6270 | 86.0687 | 0.5882 | N |
| 46000 | `gpu_only_u4` | 239.8008 | 50.6730 | 89.5959 | 0.5656 | N |

Representative claim (f16): predicted ~5.05 s @12k / ~94.4 s @46k; measured 4.5492 s / 50.7478 s (run_id `65e33de8-ac07-405a-a1f8-53698974afe9`).

## P4 — paging boundary

- **verdict:** `held_within_measured_sweep`
- No paging-driven quiescence loss on T2S through n=94000 (all three arms PASS). Platform A (2b3316b6-7f6e-474f-9177-bd5a89aeb58c) lost quiescence at n=82000. Kill occurred before n=100000 rung.
- Predicted ~328k onset: **impractical** — Each deep rung already ~40 min wall and growing superlinearly (prefill_s ~ n^1.85); reaching ~328k under the CAP-4 interleaved protocol is not a practical measurement on this session budget. P4 within-sweep claim (no paging ≤82k / through 94k) is the evaluable bound from 65e33de8.

## P5 — 8B allocation ceiling

- **verdict:** `untested` — No Qwen3-8B-int4-ov arm on T2S in 65e33de8 (4B CAP-4 only).

## Timing variance (CV)

- Platform A (`2b3316b6-7f6e-474f-9177-bd5a89aeb58c`): first n with CV>10% = **32000** (all arms).
- T2S (`65e33de8-ac07-405a-a1f8-53698974afe9`): CV **never** exceeds 10% through n=94000; no first-crossing.

| platform | arm | n | CV | CV% |
|---|---|---:|---:|---:|
| A | `gpu_only_f16` | 12000 | 0.0676 | 6.76 |
| A | `gpu_only_f16` | 32000 | 0.2935 | 29.35 |
| A | `gpu_only_f16` | 46000 | 0.2080 | 20.80 |
| A | `gpu_only_f16` | 76000 | 0.0684 | 6.84 |
| A | `gpu_only_u4` | 12000 | 0.0239 | 2.39 |
| A | `gpu_only_u4` | 32000 | 0.2502 | 25.02 |
| A | `gpu_only_u4` | 46000 | 0.2031 | 20.31 |
| A | `gpu_only_u4` | 76000 | 0.0101 | 1.01 |
| A | `gpu_only_u8` | 12000 | 0.0197 | 1.97 |
| A | `gpu_only_u8` | 32000 | 0.2223 | 22.23 |
| A | `gpu_only_u8` | 46000 | 0.1944 | 19.44 |
| A | `gpu_only_u8` | 76000 | 0.1542 | 15.42 |
| T2S | `gpu_only_f16` | 12000 | 0.0014 | 0.14 |
| T2S | `gpu_only_f16` | 32000 | 0.0018 | 0.18 |
| T2S | `gpu_only_f16` | 46000 | 0.0014 | 0.14 |
| T2S | `gpu_only_f16` | 82000 | 0.0022 | 0.22 |
| T2S | `gpu_only_f16` | 94000 | 0.0243 | 2.43 |
| T2S | `gpu_only_u4` | 12000 | 0.0044 | 0.44 |
| T2S | `gpu_only_u4` | 32000 | 0.0029 | 0.29 |
| T2S | `gpu_only_u4` | 46000 | 0.0014 | 0.14 |
| T2S | `gpu_only_u4` | 82000 | 0.0025 | 0.25 |
| T2S | `gpu_only_u4` | 94000 | 0.0174 | 1.74 |
| T2S | `gpu_only_u8` | 12000 | 0.0015 | 0.15 |
| T2S | `gpu_only_u8` | 32000 | 0.0005 | 0.05 |
| T2S | `gpu_only_u8` | 46000 | 0.0015 | 0.15 |
| T2S | `gpu_only_u8` | 82000 | 0.0025 | 0.25 |
| T2S | `gpu_only_u8` | 94000 | 0.0205 | 2.05 |

Full T2S CV table: `derived/t2_3/T2_3_TIMING_VARIANCE.json`.

