# Seal census

Run directories: 163. Tracked 162, untracked 1.

## 4a verify_seal counts

| status | n |
|---|---:|
| MATCH | 14 |
| MATCH_LEGACY_SELF_REF | 3 |
| MISMATCH | 6 |
| UNSEALED | 140 |

## 4c paper numbers

| claim | run_id | status |
|---|---|---|
| cold limit 9750 | c647f0c7-5cc9-47bb-a491-3450533c34d1 | UNSEALED |
| 46k retention TTFT 230-253 s | 2b3316b6-7f6e-474f-9177-bd5a89aeb58c | MATCH@derived/cap4/sealed_2b3316b6-7f6e-474f-9177-bd5a89aeb58c |
| residency 5.17x | cb781dbf-3486-4fbc-a69a-34026f801abe | MATCH@derived/bfcl_feasibility/x2_feasibility_table/sealed_cb781dbf-3486-4fbc-a69a-34026f801abe |
| residency 5.17x pair | 9fdedb46-3318-4abc-a56f-50b7d23d25ca | MATCH@derived/bfcl_feasibility/x2_feasibility_table/sealed_9fdedb46-3318-4abc-a56f-50b7d23d25ca |
| tier 3.09x | c647f0c7-5cc9-47bb-a491-3450533c34d1 | UNSEALED |
| tier 3.09x pair | 322b2f86-9571-46ae-be6a-ba1cec44e018 | UNSEALED |
| tier 1.14x | 5c714535 | NOT_IN_TREE |
| tier 1.14x pair | 051d2681 | NOT_IN_TREE |
| weight 1.25x | fea55e0c-b9f8-4ba9-b5ea-558401910d74 | UNSEALED |
| placement 19.5x | d3dcbd3b-5107-4b5e-a0dd-402f99f6f90c | UNSEALED |
| prefill exponents 2.12-2.25 | 2b3316b6-7f6e-474f-9177-bd5a89aeb58c | MATCH@derived/cap4/sealed_2b3316b6-7f6e-474f-9177-bd5a89aeb58c |
| prefill exponent 1.85 | 65e33de8-ac07-405a-a1f8-53698974afe9 | MATCH@derived/cap4/sealed_65e33de8-ac07-405a-a1f8-53698974afe9 |
| within-platform prediction 0.6% error |  | NOT_LOCATED |
| 8B SLO limit 3156 | 322b2f86-9571-46ae-be6a-ba1cec44e018 | UNSEALED |
| 8B allocation ceiling 3312 | 322b2f86-9571-46ae-be6a-ba1cec44e018 | UNSEALED |

## 4d cross-platform field flags

| pair | flags |
|---|---|
| 4B limit aipc vs evo | CONFOUNDED(KV_CACHE_PRECISION) |
| 8B limit aipc vs evo | none |

## 4e values without a figure run_id

| value | class |
|---|---|
| slo_s 10.0 | CONFIG |
| workload_max_tokens 7743 | MEASURED_ORPHAN |
| bfcl_tool_schema_tokens 2598 | MEASURED_ORPHAN |
| first SLO miss n=734 | MEASURED_FOUND |
| median prefill 10.86 s | MEASURED_FOUND |
| CL_OUT_OF_RESOURCES n=3312 | MEASURED_FOUND |
| passing prefill ~3.2 s | MEASURED_FOUND |
| memory_wall n=7937, 3 repeats | MEASURED_FOUND |
| first SLO miss n=10000, prefill ~10.08 s | MEASURED_FOUND |
| f16 REFUSED_LOW_OVER_SLO n=8000 | MEASURED_FOUND |
| schema_share 0.823 | DATASET_DERIVED |

Citations recorded: 2365. Full rows are in SEAL_CENSUS.json.
