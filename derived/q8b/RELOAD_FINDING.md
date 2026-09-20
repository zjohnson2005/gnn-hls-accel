# Q-8B reload finding (smoke)

**Measured:** 2026-09-16 via `tools/smoke_q8b_reload.py`  
**Artifact:** `derived/q8b/_reload_smoke/report.json`  
**Not a quality session** — load/switch only; no BFCL generate.

## Verdict

**Arm switch reloads** (drop prior pipe, load target IR). Simultaneous dual
residency was **not** attempted in this smoke (by design). Code path:
`apply_model_spec` is process-global; `load_arm_pipeline` compiles from
`MODEL_DIR`. Holding both tiers resident would require two
`LLMPipeline` objects (~6.68 GiB IR alone); the full runner tries that only
when `available_mb ≥ 10000`, else uses block-interleave reload.

On this host at smoke time Available was ~7.5–8 GB → full session would select
**block_interleave_single_pipe** (explicit reload on switch).

**Update (Q8B-FIX):** dual-resident is no longer auto-tried. Default is always
single-pipe; dual is opt-in and **known-broken** citing void `b1a291f0`
(`derived/q8b/DUAL_RESIDENCY_FINDING.md`).

## Measured reload costs

| step | arm | reason | load_s |
|---|---|---|---:|
| 1 | int4_4B | initial_4b | 7.202 |
| 2 | int4_8B | switch_4b_to_8b | 13.522 |
| 3 | int4_4B | switch_8b_to_4b | 6.431 |

## Timing contamination

**Does not contaminate decode/TTFT fields.** Each `model_load` event sets
`excluded_from_decode_metrics=true` and `generate_issued=false`. In the full
runner, `cell_wall_s` and turn `ttft_s` / `decode_tok_s` start **after**
`_ensure_arm` returns (reload complete). Reload lives only in
`reload_events.json`.
