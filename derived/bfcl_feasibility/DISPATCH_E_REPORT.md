# DISPATCH E — three feasibility probes

**Date:** 2026-08-10  
**Stack:** OpenVINO `2026.2.1-21919…`, openvino_genai `2026.2.1.0-3123…`  
**IR pin:** `c1821f29332faa48871c7f16426a21443fbc701fa4e4c8a581a8c51ab7bf2cb2`  
**Harness:** `tools/bfcl_feasibility_probe.py` (extended; no commit)

## Preconditions

| Check | Result |
| --- | --- |
| AC | Online (`BatteryStatus=2`, SoC 100%) |
| DryRunGate | **REFUSED** — Cursor + chrome Tier-1 resident; Available **~6188–6243 MB** < **7000** |
| Offline work | attention-window inventory + `KV_CACHE_PRECISION` Core smoke **DONE** |
| gpu_only accuracy / NPU load | **BLOCKED_ON_OPERATOR** — exact commands in `OPERATOR_CMD_DISPATCH_E.md` |

---

## 1. KV precision quality — gates ~5 h latency work

| Item | Finding |
| --- | --- |
| Exact property | **`KV_CACHE_PRECISION`** (OpenVINO device / LLMPipeline config; `openvino.Type`) |
| Levels requested | `f16` → `Type.f16`, `u8` → `Type.u8`, `u4` → `Type.u4` |
| Core set/get (same `ov.Core`) | **took_effect=true** for f16, u8, u4 — see `kv_precision_property_smoke.json` |
| LLMPipeline compile+AST matrix | **not run** (clean-host gate) |
| Accuracy f16 / u8 / u4 | **not measured** — do not invent |

**How effect is confirmed in the full probe:** one `ov.Core` sets `KV_CACHE_PRECISION`, readback must match, then `LLMPipeline(model, "GPU", {"KV_CACHE_PRECISION": Type…})` loads; post-load readback on the **same** Core must still match. (A fresh `Core()` does not observe another Core’s sticky property — that trap is recorded in the smoke.)

**Verdict (precision axis):** **LIVE pending accuracy** — property exists, is accepted on GPU for f16/u8/u4, and is not silently ignored at Core level. Axis life/death for the ~5 h ladder still requires the accuracy matrix (`run_gpu_kv_precision`). Until then: **BLOCKED_ON_OPERATOR**, not “axis dead.”

Operator command: see `OPERATOR_CMD_DISPATCH_E.md` §1.  
Expected artifact: `kv_precision_gpu_probe_report.json`.

---

## 2. Attention window support — ~10 min, may kill an axis

Inspected installed `openvino_genai` 2026.2.1 (no implementation).

| Question | Answer |
| --- | --- |
| `PipelineConfig` class? | **No** (`hasattr(..., "PipelineConfig")` is False) |
| Sliding-window / attention-sink KV eviction exposed? | **Yes** |
| Property / API names | **`SchedulerConfig.use_cache_eviction`** + **`SchedulerConfig.cache_eviction_config`** → **`CacheEvictionConfig`** |
| Sink field | `CacheEvictionConfig.start_size` (tokens retained at beginning) |
| Sliding recent field | `CacheEvictionConfig.recent_size` |
| Bound | `CacheEvictionConfig.max_cache_size` |
| Pipeline path | `ContinuousBatchingPipeline`, or `LLMPipeline(..., {"scheduler_config": SchedulerConfig(...)})` |
| Plain plugin props `ATTENTION_SINK` / `SLIDING_WINDOW`? | **Not** on Core `SUPPORTED_PROPERTIES` |
| Related (not eviction) | `SparseAttentionConfig` TRISHAPE: `num_retained_start_tokens_in_cache` / `num_retained_recent_tokens_in_cache` |

**Verdict (attention axis):** **EXISTS** — via GenAI `CacheEvictionConfig` / `use_cache_eviction`, not a bare plugin property and not `PipelineConfig`.

Artifact: `attention_window_inventory.json`.

---

## 3. NPU feasibility — ~15 min

| Item | Finding |
| --- | --- |
| Device present | `ov.Core().available_devices` includes **`NPU`** |
| Model | `models/Qwen3-4B-int4-ov` (INT4 IR; pin above) |
| Load attempt | **not run** (clean-host gate; Cursor/chrome resident) |
| Static-shape knobs (from GenAI/NPUW binaries + platform config) | `MAX_PROMPT_LEN` (GenAI), `NPUW_LLM_MAX_PROMPT_LEN`, `NPUW_LLM_PREFILL_CHUNK_SIZE` (platform default 2048 / 1024) |
| Context limit / compile errors | **unknown until `run_npu_load`** |

**Verdict (NPU axis vs footnote):** **UNRESOLVED — BLOCKED_ON_OPERATOR**. Static-shape requirements mean NPU is at best a **bounded compile-time context axis**, not a free dynamic-context peer of GPU; whether it is an axis or a footnote is exactly the load + `MAX_PROMPT_LEN` ceiling. Do not invent a pass.

Operator command: see `OPERATOR_CMD_DISPATCH_E.md` §2.  
Expected artifact: `npu_load_probe_report.json`.

---

## Verdict lines (summary)

1. **Precision axis:** LIVE pending accuracy (property `KV_CACHE_PRECISION` real on GPU for f16/u8/u4; accuracy matrix BLOCKED_ON_OPERATOR).
2. **Attention axis:** EXISTS (`SchedulerConfig.use_cache_eviction` + `CacheEvictionConfig.start_size`/`recent_size`).
3. **NPU axis vs footnote:** UNRESOLVED — load blocked; static-shape knobs present (`MAX_PROMPT_LEN` / `NPUW_LLM_*`).

## Artifact paths

| Path | Role |
| --- | --- |
| `derived/bfcl_feasibility/attention_window_inventory.json` | Probe 2 complete |
| `derived/bfcl_feasibility/kv_precision_property_smoke.json` | Probe 1 property effect (Core) |
| `derived/bfcl_feasibility/OPERATOR_CMD_DISPATCH_E.md` | Exact clean-host commands |
| `derived/bfcl_feasibility/DISPATCH_E_REPORT.md` | This report |
| `derived/bfcl_feasibility/kv_precision_gpu_probe_report.json` | Probe 1 accuracy (pending) |
| `derived/bfcl_feasibility/npu_load_probe_report.json` | Probe 3 load (pending) |
| `tools/bfcl_feasibility_probe.py` | Extended harness (modes above) |
