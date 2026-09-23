# WITHDRAWN / HELD

Registry of operating-limit claims taken out of the paper line, or held until a parity re-measure. Date is the registry date.

## WITHDRAWN

- 2026-09-23. Within-platform prediction 0.6% error. No located source. A search of `derived/` and `docs/` did not find a run_id for this figure. It is withdrawn until a manifest is found.

- 2026-09-23. Per-policy local TTFT from `d482c621-4292-4281-b6a1-8635e5eeb6da`. Arm-order prefix-cache contamination, recorded in `derived/h1_hybrid/analysis_d482c621/ORDER_AUDIT.json`.

## HELD

- 2026-09-23. Tier 3.09x, weight 1.25x, 4B cross-platform ratio (9,750 vs 18,687), and schema share 0.823. Pending KV-parity re-measure (`derived/c2_ttft/PARITY_REMEASURE_PREREG.json`). Confounding fields from `derived/OPLIMIT_PARITY.json`:
  - tier 3.09x: arm_id, KV_CACHE_PRECISION, model_dir
  - weight 1.25x: arm_id, KV_CACHE_PRECISION, model_dir
  - 4B cross-platform: arm_id, KV_CACHE_PRECISION
  - schema share 0.823 (2598/3156): KV_CACHE_PRECISION on the 3156 denominator (`322b2f86`, gpu_only_f16). The numerator is a dataset token count, not a run field.

- 2026-09-23. 9,750 anchor (`c647f0c7`). Pending guarded re-measure. The canary never armed. The reconstruct seal is labeled RECONSTRUCTED_UNGUARDED.

- 2026-09-23. HELD. Cited workload max 7743. Trajectory-derived, no run_id. `derived/dataset/BFCL_TOKEN_COUNTS.json` keeps `workload_max_tokens_dataset` 5036 and records `workload_max_tokens_observed` 6279 from sealed `d482c621-4292-4281-b6a1-8635e5eeb6da` (policy slo_escalate, entry multi_turn_base_180, turn 5, 1924 local turns).
