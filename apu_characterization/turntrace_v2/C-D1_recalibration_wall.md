# C-D1 — Recalibration report + CPU wall-clock projection

> Provisional forever. CPU numbers contextualize only; never headline.
> No APU / hardware-advantage claims.

## Model pin

| Field | Value |
|-------|-------|
| Lock file | `model_lock_rev_c.json` |
| Model | `Qwen2.5-1.5B-Instruct` |
| Quant | `Q4_K_M` |
| File | `qwen2.5-1.5b-instruct-q4_k_m.gguf` |
| SHA256 | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` |
| Engine | llama.cpp `b10012-win-cpu` |
| `n_ctx_pinned` | 16384 |
| Tool-role remap | **false** (TinyLlama allowlist must not transfer) |

## Feasibility (this host)

| Probe | Result |
|-------|--------|
| Load + complete at 16K | PASS (`t_prefill_ms≈264271` at `engine_tokens_in=16383`) |
| TT-DOC 20K box target | **Deferred** — not CPU-feasible here (KV/RAM floor + multi-minute prefills). Fallback: calibrate through 16K; Class I on cpu_prebox TT-EDIT/TT-RET only. |

## Prefill calibration f(n)

| Field | Value |
|-------|-------|
| Grid requested | 1024, 2048, 4096, 8192, 12288, 16384, 20480 |
| Grid measured | 1023–16385 (20K skipped; deferred on this host) |
| Attempt 1 | FAILED quadratic R²=0.98812 (8K outlier / RAM pressure); archived |
| Attempt 2 | PASS — server `-c 16896`, settle_s=1.0 |
| Reps / point | 5 |
| Temperature | 0 |
| Quadratic R² (held-out) | **0.997745** (≥0.99) |
| Piecewise R² (held-out) | 0.977771 (not used for wall booking) |
| Conservative booking | quadratic intercept books as **necessary** |
| Artifact | `apu_characterization/out/turntrace_v2/rev_c_cp2/calibration/prefill_profile.json` |

## Wall-hours projection (Class I + ablations)

| Field | Value |
|-------|-------|
| Plan | `class_i` — TT-EDIT + TT-RET, seeds 0–4, harnesses raw_python+langgraph |
| Cells | A vs B-CACHE; A vs B-APPEND+B-LAYOUT |
| Target | `cpu_prebox` |
| Projected prefill hours | 8.084 |
| Projected wall hours | **9.701** (×1.20 multiplier) |
| Exceeds 24h? | **no** (launch authorized by projection gate) |
| total_calls | 1520 |
| Artifact | `apu_characterization/out/turntrace_v2/rev_c_cp2/wall_projection_class_i.json` |

## Actual wall hours (post-run)

| Field | Value |
|-------|-------|
| Collection started | `FILL` |
| Collection finished | `FILL` |
| Actual wall hours | `FILL` |
| Notes | `FILL` |
