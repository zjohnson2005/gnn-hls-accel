# DISPATCH L — Make NON_RESIDENT actually cold

**Date:** 2026-08-10  
**Prior:** `DISPATCH_K_SESSION_RESIDENCY_FIX.md` (ChatHistory equivalence OK; KV still warm)

## Symptom (third attempt)

NON_RESIDENT was not clearing / bypassing KV between turns on either arm:

- arm A median TTFT **2.55 s** vs ~**50 s** cold at ~3600 tok
- gpu_only turns 2+ avg **0.13 s** (~185-token delta, not full)
- `context_growth` / `per_turn_delta_tokens` BYTE-IDENTICAL across modes

Root cause: OpenVINO GenAI **2026.2.1** `LLMPipeline` uses ContinuousBatching on CPU/GPU with
**prefix caching ON by default** (maintainer note on [openvino.genai#2415](https://github.com/openvinotoolkit/openvino.genai/issues/2415)).
String `generate([full_prompt])` without `start_chat` still hits the shared-prefix KV cache.

## Chosen fix: (a) disable prefix caching

```python
sc = ov_genai.SchedulerConfig()
sc.enable_prefix_caching = False
ov_genai.LLMPipeline(model_dir, device, {"scheduler_config": sc}, **properties)
```

Applied only to **NON_RESIDENT** loads (`load_arm_pipeline(..., enable_prefix_caching=False)`).
**RESIDENT** keeps the LLMPipeline default (prefix caching ON) so history-prefix continuation
still works.

Inspected surface (2026.2.1):

| API | Verdict |
| --- | --- |
| `LLMPipeline.reset` / clear-KV | **absent** |
| `GenerationConfig` prefix/KV fields | **absent** |
| `finish_chat` | clears chat-mode KV only; NON_RESIDENT never enters chat |
| `SchedulerConfig.enable_prefix_caching` | **present**; CB default under LLMPipeline is ON |

## Rejected: (b) fresh LLMPipeline per turn

Rejected **unless (a) fails the positive control**. Reasons:

1. (a) is the property the stack documents for this exact behavior.
2. Reloading weights each turn conflates **load_s** with TTFT and multiplies wall time
   (arm A NON_RESIDENT already ~55 s cold prefills × n=20).
3. If (a) is insufficient, (b) remains the fallback; measure `model_load_s` separately
   from TTFT when that path is taken.

## Positive control (gate before matrix)

Mode: `session_residency_cold_control` (also `-ColdControl` on the ps1).

- 1 entry, NON_RESIDENT, assert turn-2
- `generate_input_tokens` / reported prefill == **full** conversation length, not delta
- turn-2 TTFT ≥ arm cold floor (`gpu_only` 1.0 s; `A` 20.0 s) and ≥ 0.40× length-scaled turn-1
- **FAIL LOUD** if turn-2 < 0.35× turn-1 (delta-sized)

Do **not** launch the four-cell matrix until this passes.

## Matrix (after control PASS)

Unchanged Dispatch K config: gpu_only/A × RESIDENT/NON_RESIDENT, n=20 each, ChatHistory fix,
full text sealing, detached via `-Orchestrate`.

## Launch status (this session)

**BLOCKED_ON_OPERATOR** — fix + control harness landed; control and matrix not executed.

| Check | Result |
| --- | --- |
| AC | PASS |
| Available ≥ 7000 | FAIL (~5936 MB) |
| Tier-1 | FAIL (Cursor ×16, chrome ×16) |
| Cold control | not run (cleanliness gate refused) |
| Four-cell matrix | not launched |

Operator command: `OPERATOR_CMD_SESSION_RESIDENCY.md`.

## Artifacts

- `tools/bfcl_feasibility_probe.py` — cold load path + control mode
- `tools/run_bfcl_session_residency.ps1` — `-ColdControl`; `-Orchestrate` gates on control
- Control report (after clean host): `derived/bfcl_feasibility/session_residency/_cold_control/session_residency_cold_control_<arm>.json`
