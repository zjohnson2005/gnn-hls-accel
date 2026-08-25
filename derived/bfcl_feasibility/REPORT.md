# BFCL feasibility probe (DISPATCH A2)

**Status:** acquire + tokenize + AST gold path **DONE**. 20-entry `gpu_only` matrix **BLOCKED_ON_OPERATOR**.

**AC:** Online (BatteryStatus=2, PowerLineStatus=Online).  
**IR pin:** `c1821f29332faa48871c7f16426a21443fbc701fa4e4c8a581a8c51ab7bf2cb2` present in `configs/models/Qwen3-4B-int4-ov.yaml`.  
**Artifacts:** `inventory.json`, `probe_entries.json`, `tokenize_report.json`, probe script `tools/bfcl_feasibility_probe.py`.

---

## 1. Real BFCL acquired

| Field | Value |
| --- | --- |
| Package | `bfcl_eval` **2025.12.17** (Apache-2.0) |
| Location | `apu_characterization/out/cap01/live_sources/bfcl-wheel/unpacked/` |
| Upstream | https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard |
| Questions | `bfcl_eval/data/BFCL_v4_*.json` (JSONL) |
| Ground truth | `bfcl_eval/data/possible_answer/BFCL_v4_*.json` (JSONL `ground_truth`) |
| AST checker | `bfcl_eval.eval_checker.ast_eval.ast_checker` via CAP-01 shims (`apu_characterization/cap01/bfcl_cap01_checker.py`) |
| Multi-turn checker | `bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker` (state/execution; **not** AST) |

### Categories obtainable (with answer counts)

| Category | Questions | Answers |
| --- | ---: | ---: |
| simple_python | 400 | 400 |
| simple_java | 100 | 100 |
| simple_javascript | 50 | 50 |
| parallel | 200 | 200 |
| parallel_multiple | 200 | 200 |
| multiple | 200 | 200 |
| live_simple | 258 | 258 |
| live_parallel | 16 | 16 |
| live_parallel_multiple | 24 | 24 |
| live_multiple | 1053 | 1053 |
| multi_turn_base | 200 | 200 |
| multi_turn_long_context | 200 | 200 |
| multi_turn_miss_func | 200 | 200 |
| multi_turn_miss_param | 200 | 200 |
| memory | 155 | 155 |
| web_search | 100 | 100 |
| irrelevance / live_irrelevance / live_relevance / format_sensitivity | present | no `possible_answer` |

Probe selection: **5** `simple_python` + **5** `parallel` + **10** `multi_turn_base` (first turn only for generation).

AST gold selftest (materialized `possible_answer` → `ast_checker`): **10/10 valid**.

---

## 2. Prompt format vs sealed timing arm — DIVERGES

| Axis | Sealed `gpu_only` timing cells | BFCL labelling prompt |
| --- | --- | --- |
| `enable_thinking` | False | False (same) |
| `load_sequence` / `generate_device` | `[GPU]` / `GPU` | same (when run) |
| `GenerationConfig.apply_chat_template` | False (pre-rendered) | False (pre-rendered) |
| `tokenizer.apply_chat_template` tools | **not passed** | **`tools=[...]` required** |
| System prefix | none (user-only) | Qwen `# Tools` + `<tools>` schemas + `<tool_call>` instructions |

**Finding:** BFCL requires the chat-template tools block. That is a real divergence from the timing arm. Formats are **not** close enough to compare latency cells to labelling prompts without a re-measure under the tools format. Do not silently adopt tools for timing claims; do not strip tools to rescue scores.

Token delta (BFCL tools style − timing style), Qwen3-4B tokenizer:

| Category | timing mean | bfcl+tools mean | Δ mean |
| --- | ---: | ---: | ---: |
| simple_python | 30.8 | 229.2 | +198.4 |
| parallel | 46.0 | 254.6 | +208.6 |
| multi_turn_base | 44.2 | 3619.5 | +3575.3 |
| overall (n=20) | 41.3 | 1930.7 | +1889.4 |

---

## 3. Accuracy / wall-clock — BLOCKED (no invented scores)

`gpu_only` DryRunGate **REFUSED**:

- Tier-1 resident: Cursor (~2.3 GiB private), chrome (~1.8 GiB), msedge
- Available MBytes **5913** < `pre_run_available_mb_min` **7000**

Per-category AST accuracy and wall-clock per entry: **not measured**. Do not invent.

When clean, run:

```text
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; .\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py --mode run_gpu --out derived\bfcl_feasibility"
```

Prefer after closing Cursor/Chrome/Edge on the XPS (same cleanliness bar as `tools/run_gpu_only_matrix.ps1`). See `OPERATOR_CMD.md`.

**Scoring note:** single-turn → CAP-01 `ast_checker`. Multi-turn → official `multi_turn_checker` only; this probe retains first-turn generations but does **not** claim AST accuracy for multi-turn.

---

## 4. Opus 5 labelling-slice cost ($5 / $25 per 1M, no cache)

Assumptions: mean BFCL-tools prompt tokens from this probe; **256** completion tokens/entry.

| Slice | N | Est. USD |
| --- | ---: | ---: |
| Primary: all answered non-multi_turn BFCL v4 | 2756 | **~$20.97** |
| Alternate: + multi_turn_* (800) at multi-turn mean prompt | 3556 | **~$40.57** |
| This 20-entry probe (if labelled by Opus) | 20 | ~$0.32 |

---

## Verdict

**Competitiveness of Qwen3-4B on real BFCL: UNKNOWN — BLOCKED_ON_OPERATOR.**

No gpu_only generations were run; no accuracy numbers exist to claim near-zero or competitive. The acquire/score path is wired and gold-validates 10/10 on AST. The decisive 20-entry matrix requires a clean XPS session (command above).

**Legitimate intermediate findings (no GPU needed):**

1. Real BFCL v4 (2025.12.17) is on disk under CAP-01; ground truth is `possible_answer/`.
2. Labelling prompts **must** diverge from sealed timing prompts (tools block; +~200 tok single-turn, +~3.6k multi-turn).
3. Multi-turn is not an AST category — do not plan a labelling build that AST-scores multi-turn.
