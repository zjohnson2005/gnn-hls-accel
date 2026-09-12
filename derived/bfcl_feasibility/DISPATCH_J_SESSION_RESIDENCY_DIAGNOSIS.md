# DISPATCH J — Session residency diagnosis (report only)

**Session:** `24634b40-3f38-40f4-b722-6127143d3500`  
**Artifacts:** `derived/bfcl_feasibility/session_residency/24634b40-3f38-40f4-b722-6127143d3500/`  
**Stack:** OpenVINO `2026.2.1`, OpenVINO GenAI `2026.2.1.0`  
**Probe:** `tools/bfcl_feasibility_probe.py` (`run_session_residency` / `compare_session_residency`)  
**Constraint:** diagnosis only — no probe changes, no re-run, no parameter tuning.

---

## Gate: tools present? **Y**

The all-turns median TTFT (gpu_only NON_RESIDENT **0.276 s**, arm A NON_RESIDENT **2.83 s**) does **not** imply few-hundred-token prompts. Those medians mix turn-1 cold prefills with later turns (and, on GPU, several later-turn TTFT samples that look anomalously low for multi-k prompts). **Turn-1** numbers match the Dispatch A/E tools-scale survey.

### Turn-1 `prompt_tokens` (five entries × four cells)

| entry | gpu_only N | gpu_only R | A N | A R | turn1 TTFT gpu N (s) | turn1 TTFT A N (s) |
|---|---:|---:|---:|---:|---:|---:|
| multi_turn_base_0 | 4193 | 4193 | 4193 | 4193 | 2.647 | 66.494 |
| multi_turn_base_1 | 2609 | 2609 | 2609 | 2609 | 1.861 | 34.269 |
| multi_turn_base_2 | 3819 | 3819 | 3819 | 3819 | 2.810 | 55.057 |
| multi_turn_base_3 | 2629 | 2629 | 2629 | 2629 | 1.815 | 34.491 |
| multi_turn_base_4 | 4394 | 4394 | 4394 | 4394 | 3.661 | 66.235 |

- gpu_only / A RESIDENT / A NON_RESIDENT turn-1 means: **3647.8** (n=20) / **3647.8** (n=20) / **3528.8** (n=5).  
- Median turn-1 TTFT: gpu_only NON_RESIDENT **2.56 s**; arm A NON_RESIDENT **55.1 s** (ladder-consistent with ~3600-token cold prefill).  
- Every turn-0 generate used `input_kind=full_prompt` with `generate_input_tokens == prompt_tokens`.

### BFCL tool definitions in rendered input? **Y**

Offline reconstruction via the same path as the probe (`tools_for_entry` → `render_bfcl_tools_style(..., enable_thinking=False)`):

- Prompts begin with `<|im_start|>system\n# Tools\n...` and a `<tools>...</tools>` block.
- Example `multi_turn_base_0`: **31/31** tool names present in the rendered string; `prompt_tokens=4193` matches the sealed report.
- Prompt tails end with the Qwen tools instruction, the user turn, then  
  `<|im_start|>assistant\n<think>\n\n</think>\n\n` (empty think closed — thinking intended off).

**Verdict:** the run measured the BFCL multi-turn tools task. The remainder of this note is not moot.

**Artifact gap:** sealed per-entry JSON does **not** store full `generate` input strings or full assistant texts (only `model_result_raw_heads` ≤300 chars, decoded calls, and token counts). Turn-0 prompts below are reconstructed deterministically from entry messages + tools. Later-turn histories cannot be fully rebuilt without the missing assistant bodies.

---

## Defect 1 — device-independent over-generation

### Observation (sealed)

| cell | mean gen tokens / turn-metric | median | hit `max_new_tokens=512` | mean `n_generations` / turn |
|---|---:|---:|---:|---:|
| gpu_only NON_RESIDENT | 44.2 | 32 | 0/68 | 2.65 |
| gpu_only RESIDENT | 430.0 | 512 | 39/70 | 1.53 |
| A NON_RESIDENT | 33.6 | 22 | 0/18 | 2.11 |
| A RESIDENT | 416.5 | 512 | 37/70 | 1.59 |

Context-growth deltas in the compare reports (425.9 vs 193.4 gpu_only; 355.4 vs 161.5 arm A) are the session-level consequence of this over-generation, driving ~3.4× session latency on both arms.

### Output shape (same turn-0 full prompt)

NON_RESIDENT heads (both arms): `<tool_call>{"name": ...}</tool_call>` (or short non-think prose).  
RESIDENT heads (both arms): `<think>\nOkay, the user wants...` and often burn the 512-token cap before a usable tool call.

On the shared 5-entry prefix, A RESIDENT has **18/18** first-step heads containing `<think>`; A NON_RESIDENT has **0**.

### Root cause (continuation / chat construction — not silicon)

Harness facts (`run_multi_turn_agent_entry`):

1. **Same** `GenerationConfig`: `max_new_tokens=512`, `do_sample=False`, `apply_chat_template=False`.
2. **Same** turn-0 harness string: `render_bfcl_tools_style` full tools prompt (`generate_input_tokens` identical).
3. **Only structural difference at turn 0:** RESIDENT calls `pipe.start_chat()` before the first `generate`; NON_RESIDENT never enters chat mode (`finish_chat` between turns is a no-op if chat was never started).
4. After the first generate, RESIDENT sends `format_residency_delta_messages(pending_delta)` (bare user/tool text, **no** chat-template / tools re-wrap; assistant text deliberately omitted from the delta). NON_RESIDENT always re-sends the full accumulated tools-style prompt.

OpenVINO GenAI contract (docs / DeepWiki / `GenerationConfig` wording):

- Chat template is applied automatically to string inputs.
- `apply_chat_template` is documented as controlling **non-chat** scenarios.
- `start_chat()` chat examples pass **plain user text**, not a pre-rendered multi-role template.

**Mechanism:** RESIDENT feeds an already-templated BFCL tools prompt into an active `start_chat` session. Chat mode treats that string as a new user utterance and re-applies the chat template. A HF-tokenizer proxy of that re-wrap (user content = full pre-rendered prompt, default thinking path) first diverges at **character 12**:

| side | prefix at first diff |
|---|---|
| harness full prompt (NON_RESIDENT path) | `<\|im_start\|>system\n# Tools\n...` |
| chat re-wrap proxy (RESIDENT path) | `<\|im_start\|>user\n<\|im_start\|>system\n# Tools\n...` |

The re-wrap ends at a fresh `<|im_start|>assistant\n` **without** the closed empty `<think></think>` that `enable_thinking=False` put on the original prompt — so greedy decode emits a real `<think>` block and commonly hits `max_new_tokens=512`. That is why RESIDENT fails to terminate turns the way full re-render does: not a different `GenerationConfig` field in our code, but **chat-mode re-templating + thinking-on decode** (and then bloated history / empty `decode_execute_qwen` on many turns).

`format_residency_delta_messages` is a secondary amplifier on later steps (tiny deltas into an already-wrong chat state). The defect is present on **turn 0 step 0** before any delta is sent, on **both** GPU and CPU.

Stop criteria in the harness (`decode_execute_qwen` → break on empty execute) are shared; they do not explain the 2.2× token inflation. The model simply never emits a clean tool-call under the chat-mode prompt the way it does under the cold full prompt.

---

## Defect 2 — GPU-specific accuracy loss

### Observation (sealed compare)

| arm | NON_RESIDENT per-turn acc | RESIDENT per-turn acc | paired turns differing |
|---|---:|---:|---:|
| gpu_only | 30/68 = **44.1%** | 13/70 = **18.6%** | **21/68** |
| A (compare JSON) | 4/18 = **22.2%** | 15/70 = **21.4%*** | **2/18** |

\*Compare’s RESIDENT rate for arm A uses all **20** RESIDENT entries (70 turns); NON_RESIDENT is only **5** entries (18 turns). On the **paired 5-entry** slice only: A NON_RESIDENT **4/18 (22.2%)** vs A RESIDENT **2/18 (11.1%)** — a real drop, but only **2** turns flip correctness, so the headline “22.2% → 21.4%” overstates stability.

gpu_only RESIDENT: `n_decoded_steps==0` on **38/70** turns (no parseable tool call).  
gpu_only NON_RESIDENT: mostly 1 decoded step per turn.

### First diverging turn — three gpu_only entries

Rendered inputs were **not** saved. Below: harness-recorded kinds/sizes + offline reconstruction / proxy where possible.

#### 1) `multi_turn_base_4` — first accuracy diverge at **turn 0** (N True, R False)

| | NON_RESIDENT | RESIDENT |
|---|---|---|
| `input_kind` | `full_prompt` | `full_prompt` |
| `generate_input_tokens` | 4394 | 4394 |
| `generated_tokens` | 18 | 512 |
| `n_decoded_steps` | 1 | 0 |
| head | `<tool_call>{"name":"ls","arguments":{"a":true}}</tool_call>` | `<think> Okay, the user is asking to see the list of files...` |

**Harness-side first diff:** none — identical reconstructed tools prompt (31–32 tools in `<tools>`).  
**Stack-side first diff (chat re-wrap proxy vs full prompt):** character **12** (`system` vs `user\n<|im_start|>system`).

#### 2) `multi_turn_base_11` — first accuracy diverge at **turn 0** (N True, R False)

| | NON_RESIDENT | RESIDENT |
|---|---|---|
| `input_kind` | `full_prompt` | `full_prompt` |
| `generate_input_tokens` | 4393 | 4393 |
| `generated_tokens` | 54 | 512 |
| head | `I'll list all the files in the '/temp' directory...` | `<think> Okay, the user wants to display all available files...` |

Same pattern: harness strings identical; stack re-wrap proxy differs at char **12**.

#### 3) `multi_turn_base_1` — first accuracy diverge at **turn 3** (N True, R False)

| | NON_RESIDENT | RESIDENT |
|---|---|---|
| `input_kind` | `full_prompt` | `delta_continuation` |
| `generate_input_tokens` | 3096 | **12** |
| `generated_tokens` | 28 (then step1 55) | 512 |
| `n_decoded_steps` | 1 | 0 |
| decoded | `tail(file_name='log.txt',lines=20)` | `[]` |
| head | `<tool_call>{"name":"tail",...}</tool_call>` | `<think> Okay, the user wants to see the last 20 lines...` (truncated at 300 chars) |

**Harness-side first diff:** position **0** — entirely different strings (full tools re-render vs 12-token delta). Histories already diverged from turn 0 (thinking vs tool_call), so later full prompts are not comparable as “same conversation, different residency.” Full assistant texts needed to dump byte-identical reconstructions were **not** sealed.

### Equivalence claim

**Is `start_chat` continuation equivalent to full re-render on GPU but not on CPU?**  
**No.** It is **not equivalent on either device**.

- Both arms’ RESIDENT cells emit `<think>` and ~10× more tokens under the same harness.
- GPU shows a large paired accuracy collapse (21/68 turns differ).
- CPU (arm A) shows the same over-generation failure mode; paired accuracy only flips 2/18 turns on a **5-entry / 18-turn** sample. That is too thin to claim “CPU equivalence” or to treat “no difference” as a device finding. Fair 5-entry rates are 22.2% → 11.1%, not “flat.”

Same harness code; the accuracy *severity* gap is in the **GPU vs CPU GenAI execution stack** (how chat-mode + greedy decode interacts with the malformed/re-templated prompt), not in a GPU-only construction branch in our probe.

---

## Arm A confidence caveat

- NON_RESIDENT: **5 entries, 18 turns** (explicit reduced cell; cold prefill ~34–66 s).
- Paired differ count **2/18** — compatible with noise plus a shared failure mode that often makes **both** arms wrong on the same gold turn.
- Do **not** read “22.2% → 21.4%” as evidence that residency is accuracy-neutral on CPU. The compare mixes unequal denominators; the paired slice is underpowered.

---

## Summary answers (dispatch return)

| Item | Result |
|---|---|
| Tools present | **Y** |
| Turn-1 token table | ~2609–4394 (mean ~3600); see table above |
| Defect 1 root cause | `start_chat` + pre-rendered tools prompt → chat-mode re-template / thinking-on decode; shared on GPU and CPU; deltas amplify later |
| Defect 2 first-diff | Turn-0 divergences: harness inputs identical; stack re-wrap proxy differs at char 12. Later diverge (`base_1` t3): full vs 12-token delta (diff at 0); full texts not sealed |
| Equivalence claim | **Not** equivalent on GPU-only-or-CPU; both broken; GPU accuracy damage larger; arm A underpowered |
| Median TTFT scare | Invalidated — all-turns median ≠ turn-1; turn-1 matches tools-scale prefills |
