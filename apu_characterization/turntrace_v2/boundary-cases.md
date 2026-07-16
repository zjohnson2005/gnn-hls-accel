# TurnTrace v2 — step-boundary edge cases

Locked decision: **one model call = one step**. Parallel tool calls after that call are `fanout_siblings` on that step, not separate steps.

Log every real-framework edge case here. Do not silently special-case in code without an entry.

| ID | Observed behavior | Resolution | Date |
|----|-------------------|------------|------|
| B0 | Spec baseline | step = model call; tools are fanout | 2026-07-15 |
| B1 | LangGraph harness emits multiple tools from one agent node | Single CallRecord; `fanout_siblings = n_tools - 1`; semantic label joins tool names with `+` | 2026-07-15 |
| B2 | Framework batches multiple tool results into one synthetic user/tool message before next model call | Still one prior step; next model call is a new step. Retemplating of history → LCP may break; count as new + `retemplated_tokens` | open (watch in C1/LangGraph live) |
| B3 | Harness issues a model call with no tools (pure generate / plan) | `is_tool_call=false`, `tool_class=none`, semantic = graph node or call-site tag | 2026-07-15 |
| B4 | Streaming tool-call args arrive across chunks | One step; assemble args before tool dispatch; timing still bounds the single model call | open |
| F2 | Cold cache-verification sample measured ~22 ms for ~576-token prefill (f(n)≈3 s) | **Root causes:** (1) Verification labeled the *second* post-reset call as cold after a discarded fill — that second call was a warm hit. (2) `/slots/N?action=erase` returns **HTTP 501** on this llama-server build unless started with `--slot-save-path`, so erase cannot be relied on. **Fix:** cold = `cache_prompt=false` (forced recompute) on a unique-nonce prefix; warm = prime with `cache_prompt=true` then extended prefix; reject `t_prefill < 0.25×f(n)` as `implausible_cold_sample`. Clear-cache latches `_slots_unsupported` after the first 501 so trajectory loops do not storm erase endpoints. **Scope:** llama.cpp **CPU** `llama-server` without `--slot-save-path` — do **not** assume the same latch on L1a/L1b/L2/L3 (ROCm/Vulkan/HIP). Box-arrival runbook must re-verify cache-clear semantics per backend before enabling warm/cold cells. | 2026-07-15 |
| F3 | `prefix_hit` / reconciliation looked inconsistent; multi-turn deltas went negative | TinyLlama `/apply-template` **drops `tool` role messages**, so `engine_tokens_in` omitted tool JSON while `requested_tokens_in` summed contents → negative `token_reconciliation_delta`. **Fix:** tool→user remap is **allowlisted to TinyLlama** (or explicit `remap_unsupported_roles=True`); P2/P3 tool-capable models pass `tool` through unchanged so a real template bug surfaces as F3 anomaly, not a silent rewrite. | 2026-07-15 |
| F1b | First dry-run corpus: 30/30 `profile_drift` despite extended grid | Attribution used default quadratic `predict_ms` while acceptance was piecewise; first measured turn lacked calibration-style warm-up; continuous CPU decode duty-cycle thermally inflated corpus prefills vs cold 1-token grid. **Fix:** prefer piecewise when its R² gate passed; discard one warm-up completion at trajectory start; recalibrate with chat-shaped prompts + `measure_max_tokens=24` + settle; brief cool-down between trajs. | 2026-07-15 |

When adding rows: prefer the mined PrefixSpan taxonomy for Layer 1 grouping if disagreement with assigned labels exceeds 50% (see §4c).
