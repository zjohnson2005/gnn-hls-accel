# DIAGNOSTIC — Phase 2 censor (absolute units)

Corpus is read-only. F3 implementation was **not** changed for this dump.

## SCOPE NOTE — regime mismatch with production agent workloads

Phase-2 ran at 1.3K -> 19.5K tokens; TraceLab's production floor is
~115K. These are different REGIMES, not just different magnitudes: at
19.5K with context ramping, an oracle can switch early while context is
small and cheap. At a 115K floor there is no cheap window -- the first
switch costs full price and so does every subsequent one. Early-switching
as a strategy does not exist at production scale. The Phase-2 conclusion
"F2 switching cost is negligible" was measured in a regime that does not
occur in production agent workloads.

## Part 1 recapitulation (F3 misapplication)

F3 divides aggregated per-trajectory **cloud inference seconds** by `effective_speedup` (8 when F3 off; 1.19 when F3 on). Oracle concurrency is 1 by construction; no cross-trajectory batching. F3 Shapley dominance is an artifact of applying a concurrency ceiling to sequential work.

## Part 3 — Outcome counts

- n_trajectories: **15** (manifest; user said 17 — actual normalized = 15)
- success (task_outcome=True): **0**
- fail (task_outcome=False, measured failure): **14**
- null (task_outcome=None): **1**
- censored=True (may overlap null): **1**

| trajectory_id | task_outcome | censored | turns | flags |
|---|---|---|---:|---|
| OA01-M-03-pydata__xarray-3364 | fail | False | 28 | nonstreaming_subject_default |
| OA01-M-04-matplotlib__matplotlib-25332 | fail | False | 11 | nonstreaming_subject_default |
| OA01-M-05-django__django-13925 | fail | False | 10 | empty_patch, nonstreaming_subject_default |
| OA01-M-06-sphinx-doc__sphinx-8435 | fail | False | 24 | nonstreaming_subject_default |
| OA01-M-07-mwaskom__seaborn-3407 | fail | False | 15 | nonstreaming_subject_default |
| OA01-M-08-pylint-dev__pylint-7228 | fail | False | 11 | nonstreaming_subject_default |
| OA01-M-09-scikit-learn__scikit-learn-13241 | fail | False | 41 | nonstreaming_subject_default |
| OA01-M-10-matplotlib__matplotlib-25433 | null | True | 51 | empty_patch, missing_subject_trajectory, nonstreaming_subject_default |
| OA01-M-11-scikit-learn__scikit-learn-25638 | fail | False | 29 | nonstreaming_subject_default |
| OA01-M-12-sympy__sympy-14308 | fail | False | 18 | nonstreaming_subject_default |
| OA01-M-13-django__django-12708 | fail | False | 43 | nonstreaming_subject_default |
| OA01-M-14-sympy__sympy-24152 | fail | False | 7 | nonstreaming_subject_default |
| OA01-P-00-pallets__flask-4992 | fail | False | 18 | nonstreaming_subject_default |
| OA01-P-01-django__django-14608 | fail | False | 12 | nonstreaming_subject_default |
| OA01-P-02-django__django-13590 | fail | False | 11 | nonstreaming_subject_default |

**Note:** 0 resolved / all measured rows are failures on OA-01 mini-swe-agent + GPT-4.1. Cross-check: published mini-SWE-agent GPT-4.1 SWE-bench numbers are nontrivial; this n=15 set is unrepresentative or truncated/hard-biased (see flags: empty_patch, turn_cap, nonstreaming_subject_default).

## a. Waterfall absolutes (F3 enabled — current engine)

| stage | frictions | mean_seconds | mean_usd | mean_joules | cloud_only_s | cloud_only_usd | local_route_frac |
|---|---|---:|---:|---:|---:|---:|---:|
| W0 | none | 15.881643 | 0.176015 | 0.000000 | 127.063561 | 0.176549 | 0.0013 |
| W1 | F1 | 16.110846 | 0.176015 | 3.438050 | 127.063561 | 0.176549 | 0.0013 |
| W2 | F1+F2 | 16.110846 | 0.176015 | 3.438050 | 127.063561 | 0.176549 | 0.0013 |
| W3 | F1+F2+F3 | 92.520375 | 0.150252 | 5476.456717 | 127.063561 | 0.176549 | 0.3612 |
| W4 | F1+F2+F3+F4 | 92.520375 | 0.150252 | 5476.456717 | 127.063561 | 0.176549 | 0.3612 |

Unreachable fraction (with F3): **0.689309** = (15.881643 − 92.520375) / (15.881643 − 127.063561)

## b. Shapley in absolute seconds (F3 enabled)

| friction | mean_marginal_seconds (absolute) | share_of_abs_total |
|---|---:|---:|
| F3 | 74.989403 | 0.978479 |
| F2 | 1.420126 | 0.018530 |
| F1 | 0.229203 | 0.002991 |
| F4 | 0.000000 | 0.000000 |

F1 absolute ~0.23 s and F2 absolute ~1.42 s are **genuinely small in wall-clock**, not merely small next to F3. F3's ~75 s absolute marginal is the concurrency-misapplication artifact from Part 1.

## c. Local-tier parameters actually used at runtime

| parameter | value | derived | source |
|---|---:|---|---|
| local_decode_ms_per_token | 8.0 | ~125.00 tok/s decode | local decode prior ~8 ms/token (small/mid local model); Phase 5 box calibration replaces |
| local_prefill_ms_per_token | 0.4 | ~2500.00 tok/s prefill | same source as F2Params.local_prefill_ms_per_token |
| local_power_w | 100.0 | — | illustrative GPU/NPU package draw during generation; Phase 5 RAPL/NVML replaces |
| local_usd_per_kwh | 0.12 | USD ≈ joules/3.6e6 × $/kWh | US average retail electricity order-of-magnitude (EIA-style); used only for local USD proxy |
| cloud input $/1M tok | 2.0 | — | OA-01 protocol_oa01_v1.json pricing_usd_per_1m_tokens.gpt-4.1.input |
| cloud output $/1M tok | 8.0 | — | OA-01 protocol_oa01_v1.json pricing_usd_per_1m_tokens.gpt-4.1.output |

- Oracle fraction of turns routed **local** at W0 (frictions off): **0.0013**
- Oracle fraction of turns routed **local** at W4 (all frictions): **0.3612**

**W0 routes nearly all turns to cloud** (then divides cloud time by assumed_concurrency=8). The naive ceiling is almost entirely the F3-off concurrency fantasy applied to logged cloud latencies — a parameter/modeling artifact, not a hybrid routing result.

## d. Median context_len_before by turn_index

| turn_index | n | median_context_len_before | p25 | p75 |
|---:|---:|---:|---:|---:|
| 0 | 15 | 1308.0 | 1246.0 | 1534.5 |
| 1 | 15 | 2216.0 | 1897.0 | 5884.5 |
| 2 | 15 | 3402.0 | 2429.5 | 6869.5 |
| 3 | 15 | 4917.0 | 2946.5 | 7459.0 |
| 4 | 15 | 5524.0 | 3141.5 | 7909.5 |
| 5 | 15 | 5729.0 | 3863.0 | 8870.0 |
| 6 | 15 | 5963.0 | 4192.5 | 9404.5 |
| 7 | 14 | 6683.0 | 4536.2 | 10049.0 |
| 8 | 14 | 6993.5 | 4878.5 | 10358.5 |
| 9 | 14 | 7101.0 | 5081.8 | 10726.0 |
| 10 | 13 | 6805.0 | 4941.0 | 9806.0 |
| 11 | 10 | 6882.5 | 5711.2 | 9928.0 |
| 12 | 9 | 6845.0 | 5678.0 | 10386.0 |
| 13 | 9 | 7213.0 | 6006.0 | 10676.0 |
| 14 | 9 | 7349.0 | 6329.0 | 10835.0 |
| 15 | 8 | 7705.5 | 6401.5 | 11733.5 |
| 16 | 8 | 8411.5 | 7486.0 | 11902.8 |
| 17 | 8 | 9071.5 | 7561.5 | 12044.2 |
| 18 | 6 | 9338.0 | 8268.8 | 11296.0 |
| 19 | 6 | 9606.0 | 8582.0 | 11362.8 |
| 20 | 6 | 9944.0 | 8813.5 | 11555.2 |
| 21 | 6 | 10813.0 | 9365.2 | 11948.0 |
| 22 | 6 | 11185.0 | 9506.0 | 12448.5 |
| 23 | 6 | 11410.5 | 9740.0 | 12542.5 |
| 24 | 5 | 11447.0 | 9245.0 | 11875.0 |
| 25 | 5 | 11986.0 | 9305.0 | 12338.0 |
| 26 | 5 | 12360.0 | 9540.0 | 12707.0 |
| 27 | 5 | 12652.0 | 9610.0 | 12892.0 |
| 28 | 4 | 11373.5 | 9807.8 | 12971.2 |
| 29 | 3 | 13163.0 | 11526.0 | 13361.0 |
| 30 | 3 | 13282.0 | 11614.5 | 13668.5 |
| 31 | 3 | 13584.0 | 11826.5 | 13999.5 |
| 32 | 3 | 13984.0 | 12057.0 | 14248.0 |
| 33 | 3 | 14156.0 | 12175.5 | 14432.5 |
| 34 | 3 | 14388.0 | 12320.5 | 14836.5 |
| 35 | 3 | 14732.0 | 12525.0 | 15053.5 |
| 36 | 3 | 14779.0 | 12581.0 | 15127.5 |
| 37 | 3 | 14838.0 | 12726.5 | 15531.0 |
| 38 | 3 | 14912.0 | 12803.5 | 15870.5 |
| 39 | 3 | 15235.0 | 12989.0 | 16154.0 |
| 40 | 3 | 15282.0 | 13166.5 | 16390.5 |
| 41 | 2 | 16627.5 | 15978.8 | 17276.2 |
| 42 | 2 | 16918.5 | 16369.2 | 17467.8 |
| 43 | 1 | 18312.0 | 18312.0 | 18312.0 |
| 44 | 1 | 18834.0 | 18834.0 | 18834.0 |
| 45 | 1 | 18974.0 | 18974.0 | 18974.0 |
| 46 | 1 | 19184.0 | 19184.0 | 19184.0 |
| 47 | 1 | 19335.0 | 19335.0 | 19335.0 |
| 48 | 1 | 19493.0 | 19493.0 | 19493.0 |
| 49 | 1 | 19542.0 | 19542.0 | 19542.0 |
| 50 | 1 | 0.0 | 0.0 | 0.0 |

Context median grows from 1308 (early turns) to 19542 (late turns with data) — F2 has structural support to grow with turn index. (A trailing turn_index with context_len_before=0 is a censored/sentinel row and must not be read as a flat curve.)
Note: last turn_index median is 0.0 — do not treat that as evidence the curve is flat.

## e. Per-turn F1 / F2 magnitudes vs local latency

- n_turns (oracle W0 paths): 329
- F1 seconds: median=0.010450, p05=0.010450, p95=0.010450
- F2 delta_seconds (all turns, 0 if no switch): median=0.000000, p95=0.000000, mean=0.000000
- F2 delta_seconds **on switches only** (n=1): median=0.000000, p95=0.000000
- Assumed local per-turn latency seconds: median=4.197600, p05=1.410400, p95=8.536240
- F1 median / local-latency median = 0.002490
- Turns where router_cost_ms alone exceeds assumed local turn latency: **1 / 329**

Active router_type=embedding, router_cost_ms=5.0. Embedding 5 ms does not exceed typical local turn work (seconds). LLM router (430 ms) would exceed the 5.4–8.4 ms crossover band (HEADLINE flag) but still is << median local turn latency on this corpus.

## Part 4 — Waterfall with F3 entirely OFF

| stage | frictions | mean_seconds | mean_usd | mean_joules | local_route_frac |
|---|---|---:|---:|---:|---:|
| W0 | none | 15.881643 | 0.176015 | 0.000000 | 0.0013 |
| W1 | F1 | 16.110846 | 0.176015 | 3.438050 | 0.0013 |
| W2 | F1+F2 | 16.110846 | 0.176015 | 3.438050 | 0.0013 |
| W4_noF3 | F1+F2+F4 | 16.110846 | 0.176015 | 3.438050 | 0.0013 |

Serial cloud_only baseline: **127.063561 s**
Unreachable fraction from **F1+F2+F4 only** (F3 off): **0.002062** = (15.881643 − 16.110846) / (15.881643 − 127.063561)

### Shapley among F1, F2, F4 only (F3 forced off)

| friction | mean_marginal_seconds | relative_share |
|---|---:|---:|
| F1 | 0.229203 | 1.000000 |
| F2 | 0.000000 | 0.000000 |
| F4 | 0.000000 | 0.000000 |

### Side-by-side: F3-enabled vs F3-disabled

| metric | F3 enabled | F3 disabled |
|---|---:|---:|
| W0 mean seconds | 15.881643 | 15.881643 |
| W4 / realizable mean seconds | 92.520375 | 16.110846 |
| cloud_only serial seconds | 127.063561 | 127.063561 |
| unreachable fraction | 0.689309 | 0.002062 |
| F3 Shapley absolute s | 74.989403 | 0 (disabled) |
| F1+F2+F4 absolute Shapley sum s | 1.649329 | 0.229203 |

**LOAD-BEARING RESULT:** With F3 off, F1+F2+F4 erase almost none of the naive headroom on this corpus. Decision cost and switching cost do **not** carry the thesis here. That must be reported plainly — it is cheaper to learn now than later.

## Guardrail notes

- No friction parameter was tuned.
- F3 code path was not fixed; only diagnosed and disabled for the re-run.
- SMOKE: 1 scaffold, 15 trajectories — corpus gate not met.
