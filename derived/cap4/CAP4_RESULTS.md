# CAP-4 results — prefill curve to failure (gpu_only / RESIDENT)

- **session_id / run_id:** `2b3316b6-7f6e-474f-9177-bd5a89aeb58c`
- **status:** `aborted`
- **abort_reason:** `SeamError`
- **abort_verbatim:** `cap4/gpu_only_u4/82000/1: 3 consecutive inadmissible blocks (['quiescence_refusal', 'quiescence_refusal', 'quiescence_refusal']); refusing to record a ceiling from a machine that will not hold still. Stop and report.`
- **stop_classification:** `quiescence_refusal_under_paging_pressure` — Sweep stopped on three consecutive quiescence refusals under paging pressure, not an allocation ceiling. No ALLOC_FAILURE cell was recorded. Prior C-2 f16 CL_OUT_OF_RESOURCES at n=8000 (c647f0c7) did not reproduce at 10× that depth under CAP-4.
- **pre-registration outcome:** **falsified**
- **predictions registered:** `2026-09-16T01:12:00+00:00`
- **ended_utc:** `2026-09-16T16:26:19.187873+00:00`

## Per-KV ceilings

| arm | highest PASS n | first fail n | class | verbatim (head) |
|---|---:|---:|---|---|
| `gpu_only_f16` | 76000 | None | None |  |
| `gpu_only_u8` | 76000 | None | None |  |
| `gpu_only_u4` | 76000 | None | None |  |

## Median prefill_s (PASS cells) with min/max

| n | `gpu_only_f16` median (min–max) | `gpu_only_u8` median (min–max) | `gpu_only_u4` median (min–max) |
|---:|---:|---:|---:|
| 12000 | 13.505 (13.047–14.842) | 13.277 (13.124–13.637) | 13.550 (13.003–13.565) |
| 16000 | 21.574 (21.461–21.740) | 21.900 (21.529–22.054) | 21.931 (21.621–22.297) |
| 20000 | 32.124 (32.100–33.616) | 32.065 (31.994–32.287) | 32.105 (32.035–33.592) |
| 26000 | 51.842 (51.715–51.873) | 52.299 (51.692–52.523) | 52.207 (51.795–52.389) |
| 32000 | 80.474 (77.485–127.243) | 94.596 (83.825–127.326) | 105.012 (79.994–133.023) |
| 40000 | 124.303 (123.330–128.813) | 153.845 (121.936–166.923) | 143.385 (125.571–189.205) |
| 46000 | 252.708 (172.022–254.463) | 230.360 (165.252–241.860) | 239.801 (168.246–249.965) |
| 52000 | 301.927 (217.927–320.399) | 216.644 (215.063–217.448) | 274.620 (218.659–368.632) |
| 58000 | 411.869 (387.919–434.650) | 370.803 (320.813–381.177) | 420.365 (364.799–429.785) |
| 64000 | 516.115 (390.557–558.383) | 328.815 (323.940–394.602) | 341.573 (322.199–381.938) |
| 70000 | 572.111 (555.241–640.647) | 568.354 (492.026–592.356) | 551.630 (453.517–552.356) |
| 76000 | 739.248 (674.963–773.181) | 660.427 (595.812–802.644) | 663.553 (660.324–673.217) |

## Power-law fit (prefill_s = C · n^b)

- `gpu_only_f16`: b=2.2516, C=7.04968e-09, fit_range_n=[12000, 76000], n_points=12, predict_46000_s=222.2417419276886
- `gpu_only_u8`: b=2.1244, C=2.52746e-08, fit_range_n=[12000, 76000], n_points=12, predict_46000_s=203.39908858596317
- `gpu_only_u4`: b=2.1512, C=1.98364e-08, fit_range_n=[12000, 76000], n_points=12, predict_46000_s=212.81882719704439

## Measured prefill at n=46000 vs pre-registered ~115 s

- `gpu_only_f16`: **252.707921875** s (predicted ~115 s; band [60.0, 230.0])
- `gpu_only_u8`: **230.360359375** s (predicted ~115 s; band [60.0, 230.0])
- `gpu_only_u4`: **239.800796875** s (predicted ~115 s; band [60.0, 230.0])
- P1 outcome: **falsified**

## Available MB (start/end median) by rung

| n | `gpu_only_f16` start→end | `gpu_only_u8` start→end | `gpu_only_u4` start→end |
|---:|---:|---:|---:|
| 12000 | 9563.5→9424.9 | 9300.2→9595.7 | 9595.6→9563.5 |
| 16000 | 9398.5→9404.2 | 9325.9→9326.0 | 9374.8→9372.3 |
| 20000 | 9490.1→9496.6 | 9494.9→9490.2 | 9488.5→9495.0 |
| 26000 | 9607.4→9610.2 | 9586.7→9579.8 | 9610.1→9586.6 |
| 32000 | 10979.2→11180.7 | 11181.2→11237.4 | 11259.8→11102.4 |
| 40000 | 11819.6→12042.9 | 12039.1→12026.1 | 12042.8→12039.3 |
| 46000 | 12012.9→13028.1 | 12890.3→12725.4 | 12843.8→12805.0 |
| 52000 | 12837.3→13230.5 | 12866.1→12837.2 | 13100.8→12855.2 |
| 58000 | 12715.9→13183.6 | 13135.9→12883.5 | 12883.3→12706.1 |
| 64000 | 12798.3→13220.2 | 12909.6→12984.1 | 12985.7→12833.4 |
| 70000 | 12908.8→13169.5 | 13145.9→13293.5 | 13292.5→12909.2 |
| 76000 | 13202.8→13205.6 | 12784.6→13242.5 | 13241.5→12777.5 |

- `gpu_only_f16` first Available-MB fall vs prior PASS rung: 16000
- `gpu_only_u8` first Available-MB fall vs prior PASS rung: 52000
- `gpu_only_u4` first Available-MB fall vs prior PASS rung: 16000

## Pre-registration

- **P1 (≈115 s @ 46k):** {'outcome': 'falsified', 'predicted_s': 115.0, 'measured_median_prefill_s_at_46000': {'gpu_only_f16': 252.707921875, 'gpu_only_u8': 230.360359375, 'gpu_only_u4': 239.800796875}, 'band_s': [60.0, 230.0]}
- **P2 (f16 < u8 < u4):** {'outcome': 'falsified', 'reason': 'joint_falsifier: all three reached 46000 without ALLOC_FAILURE', 'highest_successful_n': {'gpu_only_f16': 76000, 'gpu_only_u8': 76000, 'gpu_only_u4': 76000}, 'any_alloc_failure': False}
- **P3 (ALLOC binds):** {'outcome': 'falsified', 'any_alloc_failure': False, 'note': 'Primary rungs start at n>=12000; C-2 already showed TTFT SLO binding near 9750 for u8/u4 and f16 ALLOC at 8000 (c647f0c7). CAP-4 asks whether ALLOC binds before the extrapolated 46k point under interleaved per-KV gpu_only RESIDENT.'}

## Answers

- **(a)** {'question': 'Is ~2 minutes / ~115 s at 46000 measured, or only extrapolated?', '46000_reachable': True, 'measured_prefill_s_at_46000': {'gpu_only_f16': 252.707921875, 'gpu_only_u8': 230.360359375, 'gpu_only_u4': 239.800796875}, 'prediction_115s': {'outcome': 'falsified', 'predicted_s': 115.0, 'measured_median_prefill_s_at_46000': {'gpu_only_f16': 252.707921875, 'gpu_only_u8': 230.360359375, 'gpu_only_u4': 239.800796875}, 'band_s': [60.0, 230.0]}}
- **(b)** {'question': 'Does GPU allocation ceiling bind before SLO on gpu_only?', 'per_arm_first_failure_class': {'gpu_only_f16': None, 'gpu_only_u8': None, 'gpu_only_u4': None}, 'per_arm_first_failure_n': {'gpu_only_f16': None, 'gpu_only_u8': None, 'gpu_only_u4': None}, 'slo_already_binds_by_n12000': True, 'alloc_binds_before_46k': {'gpu_only_f16': False, 'gpu_only_u8': False, 'gpu_only_u4': False}, 'p3': {'outcome': 'falsified', 'any_alloc_failure': False, 'note': 'Primary rungs start at n>=12000; C-2 already showed TTFT SLO binding near 9750 for u8/u4 and f16 ALLOC at 8000 (c647f0c7). CAP-4 asks whether ALLOC binds before the extrapolated 46k point under interleaved per-KV gpu_only RESIDENT.'}}

## INF-5 run_environment (session slice)

- session_design: `interleaved`
- arm_order: `['gpu_only_f16', 'gpu_only_u8', 'gpu_only_u4']`
- available_mb_start/end: 9294.01171875 / 12783.484375
- prompt_render_sha256: `99811f58d3baf972e6462314e6a7e40ff301784562f362b6badbc9eda2c07245`

## Rungs completed per arm

- `gpu_only_f16`: [12000, 16000, 20000, 26000, 32000, 40000, 46000, 52000, 58000, 64000, 70000, 76000]
- `gpu_only_u8`: [12000, 16000, 20000, 26000, 32000, 40000, 46000, 52000, 58000, 64000, 70000, 76000]
- `gpu_only_u4`: [12000, 16000, 20000, 26000, 32000, 40000, 46000, 52000, 58000, 64000, 70000, 76000]

## POST-CAP4 fold-in

Generated: 2026-09-16T17:52:13.632559+00:00

### Timing variance result

On Platform A under CAP-4 interleaved gpu_only RESIDENT, within-rung prefill CV first exceeds ~10% at n=32000 on all three KV arms. That is the depth beyond which this platform stops reproducing prefill timing to the low-n instrument standard. CV is not monotonic thereafter (paging / quiescence pressure), but 32000 is the first crossing.

First n with CV > 10%: `gpu_only_f16`=32000, `gpu_only_u4`=32000, `gpu_only_u8`=32000

Low-n contrast: 0.03% cross-session canary agreement (`c4ddfd55-f64f-4c72-842c-a6470daaf5ca` vs W-2 ref); see `POST_CAP4.md`.

### Headline arithmetic (replaces 9,750→46,000 / ~2 min)

9,750 tokens @ 10 s TTFT SLO (c647f0c7 u8/u4) versus 46,000 tokens @ median prefill 230.4–252.7 s (full min–max across arms 165.3–254.5 s; 2b3316b6-7f6e-474f-9177-bd5a89aeb58c). Token depth ratio 4.72×; time ratio vs 10 s SLO is 23.0–25.3× (not ~12× / ~2 min).

Full note: `derived/cap4/POST_CAP4.md`. Prefill model tag: `MEASURED(2b3316b6)`.
