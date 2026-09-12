# DISPATCH F — multi-turn 0/20 forensics (capability or harness?)

**Date:** 2026-08-10  
**Source artifact:** `derived/bfcl_feasibility/multi_turn_gpu_probe_report.json`  
**Code path:** `tools/bfcl_feasibility_probe.py` → `run_gpu_multi_turn` / `run_multi_turn_agent_entry` / `decode_execute_qwen`  
**Scope:** REPORT ONLY — no probe-loop, prompt, or scoring changes.

## Verdict

**Primary: (d) plumbing — checker received empty decoded trajectories.**  
**Secondary: (c) the tool-execution / multi-step inner loop never advanced** (exactly one generation per user turn; zero decoded steps everywhere).

**Not (a).** The 0/20 is not a model capability ceiling.  
**Not primarily (b).** Offline re-parse of sealed turn-0 heads extracts valid `<tool_call>` JSON for **17/20** entries; decode never reaches that path in-loop because `decode_execute_qwen` dies on import first.

Root cause (reproduced in the same venv):  
`decode_execute_qwen` does `from bfcl_eval.model_handler.utils import convert_to_function_call`. That module imports `tenacity` at import time. **`tenacity` is not installed** (`pip show tenacity` → not found). CAP-01 shims stub java/js parsers but do not stub `tenacity`. The agent loop wraps decode in bare `except Exception: break`, so every step silently terminates the turn with no decoded execute list. The checker then scores `model_result_decoded = [[], …]` → `multi_turn:empty_turn_model_response` on all 20.

Why single-turn and gold looked fine:
- A2 AST uses `extract_tool_calls_ast` — never imports `model_handler.utils`.
- Gold selftest feeds GT execute strings straight into `multi_turn_checker` — never calls `decode_execute_qwen`.

Why 8.9 s/entry fits: mean ~3.5 generations/entry (70 gens / 20), not a deep tool loop; wall time is user-turn count × one generate each.

## max_new_tokens

| Item | Value |
| --- | --- |
| In effect (`gpu_probe.max_new_tokens`) | **512** |
| CLI / function default | 512 |
| Latency-harness 64? | **No** — not the failure mode |

Completion tokens per generation: mean 39.8, max 155 (n=70). Truncation at 64 is ruled out.

## Artifact gap (plumbing evidence)

`model_result_raw_heads` stores **only the first 300 characters** per generation (`t[:300]`). Full turn-1 text is **not sealed**. For short completions that fit in 300 chars (e.g. base_0/1/5), the head is effectively complete; for longer gens (e.g. base_2, 155 completion tokens) the sealed head is truncated mid-string. Exception type/message from decode was **not logged**.

## Aggregate

| Metric | Value |
| --- | --- |
| Accuracy | 0/20 |
| Checker `error_type` | `multi_turn:empty_turn_model_response` ×20 |
| Total user turns (gold) | 70 |
| Total generations executed | 70 (exactly 1 per user turn) |
| Total decoded tool steps | **0** |
| Entries with any multi-step turn | **0** |
| `force_quit` / max-step | never |
| Context growth | assistant text only (no tool messages); e.g. base_0 `n_messages` 1→3→5→7 |

## Per-entry summary (5 dimensions)

Legend: **loop gens** = generations the harness ran per user turn; **gold steps** = execute-strings per gold turn; **term** = why the inner step loop stopped (inferred: decode exception → break); **checker got** = `model_result_decoded`.

| id | loop gens vs gold turns/steps | turn-1 parseable? (from ≤300-char head) | termination | checker received | notes |
| --- | --- | --- | --- | --- | --- |
| multi_turn_base_0 | 4×[1] vs gold 4 turns steps [3,2,1,4] | yes (2 tool_calls in head) | decode fail → break; no tool exec | `[[],[],[],[]]` empty | |
| multi_turn_base_1 | 4×[1] vs [1,2,2,1] | yes (`pwd`) | same | empty ×4 | |
| multi_turn_base_2 | 5×[1] vs [2,1,1,3,1] | no tool_call in head (prose) | same | empty ×5 | head truncated |
| multi_turn_base_3 | 2×[1] vs [1,4] | yes (`find`) | same | empty ×2 | |
| multi_turn_base_4 | 3×[1] vs [1,1,1] | yes (`ls`) | same | empty ×3 | |
| multi_turn_base_5 | 4×[1] vs [2,2,2,1] | yes (`find`) | same | empty ×4 | |
| multi_turn_base_6 | 5×[1] vs [2,1,1,1,4] | yes (`touch`) | same | empty ×5 | |
| multi_turn_base_7 | 3×[1] vs [2,1,1] | yes (2 tool_calls) | same | empty ×3 | |
| multi_turn_base_8 | 4×[1] vs [1,1,2,1] | yes (`grep`) | same | empty ×4 | |
| multi_turn_base_9 | 3×[1] vs [1,3,1] | tag present; head cuts mid-JSON | same | empty ×3 | head truncated |
| multi_turn_base_10 | 5×[1] vs [2,3,1,3,1] | yes (`mkdir`) | same | empty ×5 | |
| multi_turn_base_11 | 2×[1] vs [1,1] | yes (`ls` after prose) | same | empty ×2 | |
| multi_turn_base_12 | 3×[1] vs [2,1,1] | yes (2 tool_calls) | same | empty ×3 | |
| multi_turn_base_13 | 2×[1] vs [2,1] | no tool_call in head (prose) | same | empty ×2 | |
| multi_turn_base_14 | 4×[1] vs [2,1,1,3] | yes (2 tool_calls) | same | empty ×4 | |
| multi_turn_base_15 | 5×[1] vs [1,1,1,3,1] | yes (`touch` after prose) | same | empty ×5 | |
| multi_turn_base_16 | 3×[1] vs [4,1,1] | yes (`cp`) | same | empty ×3 | |
| multi_turn_base_17 | 3×[1] vs [1,2,3] | no tool_call in head (prose) | same | empty ×3 | |
| multi_turn_base_18 | 3×[1] vs [5,2,2] | yes (`cp`) | same | empty ×3 | |
| multi_turn_base_19 | 3×[1] vs [1,3,1] | yes (`find`) | same | empty ×3 | |

All scores: `valid=false`, `error_type=multi_turn:empty_turn_model_response`, message `Model response list is empty for turn 0`.

## Verbatim turn-1 raw heads (sealed, ≤300 chars)

### multi_turn_base_0 (completion_tokens=51; head appears complete)

```
<tool_call>
{"name": "mkdir", "arguments": {"dir_name": "temp"}}
</tool_call>
<tool_call>
{"name": "mv", "arguments": {"source": "final_report.pdf", "destination": "temp/final_report.pdf"}}
</tool_call>
```

Offline: `extract_tool_calls_qwen` → 2 calls. In-loop: never converted (import fails).

### multi_turn_base_1 (completion_tokens=15; head appears complete)

```
<tool_call>
{"name": "pwd", "arguments": {}}
</tool_call>
```

Offline: 1 call extracted. In-loop: same import failure.

### multi_turn_base_5 (completion_tokens=25; head appears complete)

```
<tool_call>
{"name": "find", "arguments": {"path": ".", "name": "analysis_report.csv"}}
</tool_call>
```

Offline: 1 call extracted. In-loop: same import failure.

## What must be true before re-scoring capability

1. `decode_execute_qwen` must succeed without swallowed import errors (e.g. install `tenacity`, or stop importing the heavy `model_handler.utils` module for a pure `convert_to_function_call`).
2. Log decode exceptions / keep full raw generations (not 300-char heads only).
3. Re-run the 20-entry agent loop; only then can (a) vs (b) be judged.

Until then: **0/20 stands as a harness/plumbing null result, not a model finding.**
