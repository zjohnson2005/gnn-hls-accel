# Normalized censor corpus schema

One JSON object per trajectory (JSONL).

Required fields:
- `trajectory_id`, `scaffold`, `task_id`, `task_class`
- `logged_tier`: `local` | `cloud` (single-tier logged data)
- `task_outcome`: bool | null
- `outcome_source`: `swebench_exact` | `llm_judge` | `synthetic` | `unknown`
- `truncated`, `parse_failure`, `censored`
- `turns[]` with `turn_index`, `context_len_before`, `tokens_out`,
  `tool_type`, `step_type_semantic`, `logged_latency_ms`, `logged_cost_usd`,
  `necessary_prefill_tokens`, `cloud_success`, `local_success`, `local_observed`

There is no logged `route_local` action. Counterfactual local outcomes are
unobserved (`local_observed=false`) unless the source deployment was local.
