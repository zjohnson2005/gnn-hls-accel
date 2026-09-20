# CAP-4 results — prefill curve to failure (gpu_only / RESIDENT)

- **session_id / run_id:** `65e33de8-ac07-405a-a1f8-53698974afe9`
- **status:** `aborted`
- **abort_reason:** `Stop-Process -Force`
- **abort_verbatim:** `Worker killed with Stop-Process -Force on evo-t2 after completing n=94000 (all three KV arms PASS every rung through 94k; next rung would be 100000). finally skipped; no summary.json (same gap as 2b3316b6). Artifacts copied to aipc-c1 for reconstruct+seal.`
- **stop_classification:** `force_killed_no_summary` — Worker was killed (Stop-Process -Force / equivalent); finally did not run, so summary.json was absent. Completed cells are retained as aborted data. Not an allocation ceiling and not a quiescence-refusal stop.
- **pre-registration outcome:** **falsified**
- **predictions registered:** `2026-09-16T01:12:00+00:00`
- **ended_utc:** `2026-09-20T20:55:50.616257+00:00`

## Per-KV ceilings

| arm | highest PASS n | first fail n | class | verbatim (head) |
|---|---:|---:|---|---|
| `gpu_only_f16` | 94000 | None | None |  |
| `gpu_only_u8` | 94000 | None | None |  |
| `gpu_only_u4` | 94000 | None | None |  |

## Median prefill_s (PASS cells) with min/max

| n | `gpu_only_f16` median (min–max) | `gpu_only_u8` median (min–max) | `gpu_only_u4` median (min–max) |
|---:|---:|---:|---:|
| 12000 | 4.549 (4.545–4.558) | 4.530 (4.526–4.539) | 4.520 (4.517–4.553) |
| 16000 | 7.392 (7.383–7.395) | 7.376 (7.361–7.393) | 7.375 (7.316–7.383) |
| 20000 | 11.111 (11.074–11.113) | 11.071 (11.054–11.086) | 11.058 (11.050–11.085) |
| 26000 | 17.649 (17.648–17.703) | 17.673 (17.667–17.678) | 17.606 (17.540–17.626) |
| 32000 | 25.635 (25.581–25.674) | 25.542 (25.520–25.542) | 25.566 (25.531–25.672) |
| 40000 | 38.946 (38.903–38.975) | 38.858 (38.853–38.882) | 38.839 (38.822–38.885) |
| 46000 | 50.748 (50.687–50.828) | 50.627 (50.617–50.756) | 50.673 (50.614–50.759) |
| 52000 | 64.106 (64.053–64.346) | 63.951 (63.905–64.348) | 64.134 (63.944–64.725) |
| 58000 | 79.128 (78.962–80.022) | 79.283 (78.979–80.320) | 79.728 (78.738–80.142) |
| 64000 | 95.856 (95.847–96.372) | 95.968 (95.818–96.205) | 96.020 (95.832–96.026) |
| 70000 | 116.401 (116.126–117.100) | 116.605 (116.346–117.197) | 116.533 (116.020–116.813) |
| 76000 | 138.444 (138.114–138.548) | 138.253 (137.581–138.331) | 138.616 (138.293–138.992) |
| 82000 | 164.030 (163.666–164.376) | 164.176 (163.643–164.447) | 163.600 (163.296–164.106) |
| 88000 | 192.224 (191.406–192.420) | 191.851 (191.729–191.873) | 191.382 (191.290–192.052) |
| 94000 | 228.699 (222.289–233.345) | 229.115 (222.835–231.943) | 228.397 (222.573–230.107) |

## Power-law fit (prefill_s = C · n^b)

- `gpu_only_f16`: b=1.8911, C=8.10657e-08, fit_range_n=[12000, 94000], n_points=15, predict_46000_s=53.279283459692124
- `gpu_only_u8`: b=1.8932, C=7.92209e-08, fit_range_n=[12000, 94000], n_points=15, predict_46000_s=53.23130467169574
- `gpu_only_u4`: b=1.8936, C=7.88272e-08, fit_range_n=[12000, 94000], n_points=15, predict_46000_s=53.218688762787075

## Measured prefill at n=46000 vs pre-registered ~115 s

- `gpu_only_f16`: **50.747792968** s (predicted ~115 s; band [60.0, 230.0])
- `gpu_only_u8`: **50.627007812** s (predicted ~115 s; band [60.0, 230.0])
- `gpu_only_u4`: **50.673039062** s (predicted ~115 s; band [60.0, 230.0])
- P1 outcome: **falsified**

## Available MB (start/end median) by rung

| n | `gpu_only_f16` start→end | `gpu_only_u8` start→end | `gpu_only_u4` start→end |
|---:|---:|---:|---:|
| 12000 | 60086.3→60077.1 | 60080.7→60087.7 | 60093.7→60089.2 |
| 16000 | 60082.7→60080.2 | 60076.3→60076.4 | 60080.1→60082.7 |
| 20000 | 60064.0→60070.3 | 60069.0→60066.9 | 60072.4→60061.7 |
| 26000 | 60055.4→60065.6 | 60062.3→60069.6 | 60072.4→60057.8 |
| 32000 | 60061.9→60054.9 | 60054.8→60055.3 | 60060.3→60062.0 |
| 40000 | 60050.9→60044.6 | 60030.1→60051.1 | 60046.3→60029.9 |
| 46000 | 60050.7→60043.2 | 60047.4→60049.0 | 60052.0→60047.7 |
| 52000 | 60030.1→60035.7 | 60038.0→60045.3 | 60043.8→60038.2 |
| 58000 | 60035.2→60023.1 | 60035.5→60032.4 | 60022.2→60034.0 |
| 64000 | 60026.7→60031.6 | 60029.5→60027.0 | 60030.0→60027.1 |
| 70000 | 60006.5→60007.7 | 59999.3→60006.8 | 60007.4→59999.9 |
| 76000 | 59988.6→59987.6 | 59975.5→59990.6 | 59990.2→59989.2 |
| 82000 | 59984.6→59978.5 | 59978.1→59977.7 | 59977.4→59969.1 |
| 88000 | 59800.6→59822.7 | 59947.2→59801.0 | 59945.9→59947.7 |
| 94000 | 56983.5→55879.8 | 59159.3→56983.9 | 59806.0→59160.0 |

- `gpu_only_f16` first Available-MB fall vs prior PASS rung: 16000
- `gpu_only_u8` first Available-MB fall vs prior PASS rung: 16000
- `gpu_only_u4` first Available-MB fall vs prior PASS rung: 16000

## Pre-registration

- **P1 (≈115 s @ 46k):** {'outcome': 'falsified', 'predicted_s': 115.0, 'measured_median_prefill_s_at_46000': {'gpu_only_f16': 50.747792968, 'gpu_only_u8': 50.627007812, 'gpu_only_u4': 50.673039062}, 'band_s': [60.0, 230.0]}
- **P2 (f16 < u8 < u4):** {'outcome': 'falsified', 'reason': 'joint_falsifier: all three reached 46000 without ALLOC_FAILURE', 'highest_successful_n': {'gpu_only_f16': 94000, 'gpu_only_u8': 94000, 'gpu_only_u4': 94000}, 'any_alloc_failure': False}
- **P3 (ALLOC binds):** {'outcome': 'falsified', 'any_alloc_failure': False, 'note': 'Primary rungs start at n>=12000; C-2 already showed TTFT SLO binding near 9750 for u8/u4 and f16 ALLOC at 8000 (c647f0c7). CAP-4 asks whether ALLOC binds before the extrapolated 46k point under interleaved per-KV gpu_only RESIDENT.'}

## Answers

- **(a)** {'question': 'Is ~2 minutes / ~115 s at 46000 measured, or only extrapolated?', '46000_reachable': True, 'measured_prefill_s_at_46000': {'gpu_only_f16': 50.747792968, 'gpu_only_u8': 50.627007812, 'gpu_only_u4': 50.673039062}, 'prediction_115s': {'outcome': 'falsified', 'predicted_s': 115.0, 'measured_median_prefill_s_at_46000': {'gpu_only_f16': 50.747792968, 'gpu_only_u8': 50.627007812, 'gpu_only_u4': 50.673039062}, 'band_s': [60.0, 230.0]}}
- **(b)** {'question': 'Does GPU allocation ceiling bind before SLO on gpu_only?', 'per_arm_first_failure_class': {'gpu_only_f16': None, 'gpu_only_u8': None, 'gpu_only_u4': None}, 'per_arm_first_failure_n': {'gpu_only_f16': None, 'gpu_only_u8': None, 'gpu_only_u4': None}, 'slo_already_binds_by_n12000': True, 'alloc_binds_before_46k': {'gpu_only_f16': False, 'gpu_only_u8': False, 'gpu_only_u4': False}, 'p3': {'outcome': 'falsified', 'any_alloc_failure': False, 'note': 'Primary rungs start at n>=12000; C-2 already showed TTFT SLO binding near 9750 for u8/u4 and f16 ALLOC at 8000 (c647f0c7). CAP-4 asks whether ALLOC binds before the extrapolated 46k point under interleaved per-KV gpu_only RESIDENT.'}}

## INF-5 run_environment (session slice)

- session_design: `interleaved`
- arm_order: `['gpu_only_f16', 'gpu_only_u8', 'gpu_only_u4']`
- available_mb_start/end: 60262.15625 / 49961.3046875
- prompt_render_sha256: `5c6e763670a4f4ba5897b703d296b8c923f54b576315c2163a3902660c254e74`

## Rungs completed per arm

- `gpu_only_f16`: [12000, 16000, 20000, 26000, 32000, 40000, 46000, 52000, 58000, 64000, 70000, 76000, 82000, 88000, 94000]
- `gpu_only_u8`: [12000, 16000, 20000, 26000, 32000, 40000, 46000, 52000, 58000, 64000, 70000, 76000, 82000, 88000, 94000]
- `gpu_only_u4`: [12000, 16000, 20000, 26000, 32000, 40000, 46000, 52000, 58000, 64000, 70000, 76000, 82000, 88000, 94000]

