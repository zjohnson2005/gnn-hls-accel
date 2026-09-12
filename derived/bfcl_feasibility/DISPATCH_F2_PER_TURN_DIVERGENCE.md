# DISPATCH F2 — Per-turn scoring and divergence profile

**Source (v2 / post-tenacity):** `derived/bfcl_feasibility/multi_turn_gpu_probe_report.json`  
**Gold / entries:** `derived/bfcl_feasibility/multi_turn_probe_entries.json`  
**Analysis script (read-only):** `derived/bfcl_feasibility/dispatch_f2_per_turn_analysis.py`  
**Machine-readable output:** `derived/bfcl_feasibility/dispatch_f2_per_turn_analysis.json`  
**Trajectory-level (official):** 1/20 · wall-clock mean 26.21 s · max 138.64 s  

No GPU re-run. No prompt tuning. No agent-loop changes.

---

## 1. Per-turn accuracy

**Overall: 30 / 70 turns = 0.429**

| Entry | Correct / turns | Per-turn mask (T0…) | Trajectory `valid` |
|---|---|---|---|
| multi_turn_base_0 | 0/4 | F F F F | false |
| multi_turn_base_1 | 1/4 | F T T F | false |
| multi_turn_base_2 | 1/5 | F T F F F | false (force_quit @4/5) |
| multi_turn_base_3 | 1/2 | T F | false |
| multi_turn_base_4 | 2/3 | T T F | false |
| multi_turn_base_5 | 2/4 | F T T F | false |
| multi_turn_base_6 | 3/5 | F T T T F | false |
| multi_turn_base_7 | 2/3 | T F T | false |
| multi_turn_base_8 | 3/4 | T T F T | false |
| multi_turn_base_9 | 0/3 | F F F | false |
| multi_turn_base_10 | 2/5 | F T F T F | false |
| multi_turn_base_11 | 1/2 | T F | false |
| multi_turn_base_12 | **3/3** | T T T | **true** |
| multi_turn_base_13 | 0/2 | F F | false |
| multi_turn_base_14 | 3/4 | T T T F | false |
| multi_turn_base_15 | 3/5 | T T T F F | false (force_quit @4/5) |
| multi_turn_base_16 | 2/3 | F T T | false |
| multi_turn_base_17 | 0/3 | F F F | false |
| multi_turn_base_18 | 0/3 | F F F | false |
| multi_turn_base_19 | 1/3 | T F F | false |

### Does bfcl_eval expose per-turn scoring?

**No.** Official `bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker`:

- Returns a single `{valid: true}` or short-circuits at the **first** failing turn.
- Failure modes cite a turn index for empty/response mismatches (`… for turn N`); `instance_state_mismatch` does **not** put the turn index in `error_message`.
- Checks are **state + unordered execution-response subsequence**, not AST/call-list equality.
- There is **no** `correct_turns / total_turns` (or per-turn validity vector) in the return value.

The probe stores only `{valid, error_type, error_message}` per entry — not checker `details`.

### How per-turn scores were derived

Structural comparison of sealed `model_result_decoded` vs gold `reference` execute lists:

1. Flatten each turn’s decoded steps → list of execute-strings.
2. Parse each call to `(function_name, normalized args)`.
3. Turn is **correct** iff the multisets of signatures match exactly.

This is deliberately call-list–level (router-relevant). It is **stricter** than the official checker on some entries (e.g. `multi_turn_base_1` turn 0: model adds extra `pwd()` → structural fail; official state check still passes turn 0 and fails later). Official checker was re-invoked on sealed decoded trajectories only to recover first-fail turn indices (`official_rescore` in the JSON).

---

## 2. First-divergence profile

| First structural divergence turn | # entries |
|---|---|
| 0 | **11** |
| 1 | 4 |
| 2 | 2 |
| 3 | 2 |
| none (all turns correct) | 1 (`multi_turn_base_12`) |

| Primary divergence type (at first bad turn) | # entries |
|---|---|
| wrong_arguments | 9 |
| missing_required_call | 5 |
| wrong_function | 4 |
| extra_call | 1 |
| none | 1 |

**Reading:** Majority (11/20) diverge on **turn 0** — systematic early planning/path errors, not pure late-horizon accumulation. The remaining 8 failures first diverge on turns 1–3, so there is also genuine multi-step difficulty (auth/tweet content, find vs ls, send_message omission, wc mode spam, etc.).

**Dominant systematic pattern among turn-0 failures:** skipping or botching `cd` and composing paths in args instead (7/11 turn-0 first-divs have `cd` in `missing_required`). Examples:

- `base_0`: gold `cd→mkdir→mv(…, destination='temp')`; model `mkdir→mv(…, destination='temp/final_report.pdf')`
- `base_6` / `base_10`: gold `cd` + create; model creates in CWD without `cd`
- `base_5` / `base_9`: gold `cd` (or `cd+mv`); model emits `find` instead

Later-turn first divergences are more heterogeneous (wrong tweet payload, missing `authenticate_twitter`, empty turn, `wc(mode='lwc')` spam vs three separate `wc` calls).

Official first-fail turn (state/response checker on sealed decoded) matches structural first-div for most entries; notable exception: `base_1` structural T0 (extra `pwd`) vs official fail T1.

---

## 3. Context growth

**Measured in the sealed artifact** — no tokenizer reconstruction needed.

Field: `gpu_probe.per_entry[].prompt_tokens_first_step_per_turn` (prompt tokens at step 0 of each user turn, Qwen3-4B tokenizer as used by the probe). Also present: full `context_growth[]` with per-(turn,step) `prompt_tokens`.

| Entry | Prompt tokens @ first step of each turn | Δ (last − first) |
|---|---|---|
| multi_turn_base_0 | 4193, 4345, 4471, 4604 | +411 |
| multi_turn_base_1 | 2609, 2781, 2941, 3096 | +487 |
| multi_turn_base_2 | 3819, 4510, 4736, 5211 | +1392 |
| multi_turn_base_3 | 2629, 2812 | +183 |
| multi_turn_base_4 | 4394, 4493, 4621 | +227 |
| multi_turn_base_5 | 4200, 4330, 4509, 4753 | +553 |
| multi_turn_base_6 | 2824, 2956, 3130, 3301, 3420 | +596 |
| multi_turn_base_7 | 4413, 4558, 4682 | +269 |
| multi_turn_base_8 | 4427, 4621, 4995, 5775 | +1348 |
| multi_turn_base_9 | 2687, 2873, 3021 | +334 |
| multi_turn_base_10 | 2598, 2702, 2856, 2991, 3125 | +527 |
| multi_turn_base_11 | 4393, 4546 | +153 |
| multi_turn_base_12 | 2813, 2945, 3059 | +246 |
| multi_turn_base_13 | 4412, 4559 | +147 |
| multi_turn_base_14 | 3680, 3825, 4076, 4293 | +613 |
| multi_turn_base_15 | 4687, 4869, 5055, 5228 | +541 |
| multi_turn_base_16 | 2717, 2879, 3037 | +320 |
| multi_turn_base_17 | 3687, 3758, 4007 | +320 |
| multi_turn_base_18 | 4213, 4392, 4548 | +335 |
| multi_turn_base_19 | 3561, 3668, 3843 | +282 |

Report aggregate: first-step-per-turn mean **3864** tokens (n=68 turn starts); across all generations mean **4445** (n=180). Entry-level `context_growth_delta_tokens` (first→last generation prompt, including intra-turn tool steps) mean **760**, max **3924**.

Largest turn-start growth: `base_2` (+1392), `base_8` (+1348) — long tool/observation transcripts.

---

## 4. The one that passed

**`multi_turn_base_12`** — trajectory `valid=true`, structural **3/3** turns.

| Turn | Gold (= model) |
|---|---|
| 0 | `cd(folder='Documents')`, `touch(file_name='summary.txt')` |
| 1 | `echo(content='quantum computing', file_name='summary.txt')` |
| 2 | `wc(file_name='summary.txt', mode='w')` |

**Why tractable:**

- Short horizon (3 turns), single API (`GorillaFileSystem`).
- Linear, low-branching plan: cd → create → write literal → word-count.
- User text names the directory/file/content explicitly; no parallel multi-file ops, no auth, no content that must be reconstructed from prior tool outputs.
- Model emitted exact gold call lists (including `cd`), so state stayed aligned.
- Modest context: 2813 → 2945 → 3059 prompt tokens; wall 10.0 s.

Contrast with typical failures: missing `cd`, path composition in args, inventing `find`, or later turns that require copying tool-derived content into tweets/messages.

---

## Implications (for parent, not a descope)

- Trajectory all-or-nothing (1/20) understates usable per-turn signal (**30/70**).
- Turn-0 `cd`/cwd discipline is the strongest systematic failure mode for this probe — relevant to any per-turn router that would intervene early.
- Later-turn failures exist and are real; not all mass is on T0.
- Context growth is already instrumented; no gap for token series on this run.
