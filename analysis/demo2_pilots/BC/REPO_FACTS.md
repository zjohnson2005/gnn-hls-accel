# Repo facts checked before registering the revised arms (Task BC part 1, 2026-10-21 ET)

Mac only, $0. Each fact cites its evidence. IR files were read from the pinned
HF revision; hashes match the pin (configs/models/Qwen3-4B-int4-ov.v2.yaml).

## 1. Which model the IR is: hybrid Qwen3-4B, not Instruct-2507
- Pin: OpenVINO/Qwen3-4B-int4-ov, revision b467368d16b75df14055562fe927ae8e1f15f7ef,
  ir_sha256 c1821f29... That revision is the repo's current main (HF API,
  2026-10-21; last commit 2026-02-24 "Update README.md").
- README.md (git blob 3ed9d327, matches the pin): base_model Qwen/Qwen3-4B.
- config.json (blob 8b3a6370, matches): Qwen3ForCausalLM,
  max_position_embeddings 40960, rope_scaling null, rope_theta 1000000,
  36 layers, 8 KV heads, head_dim 128.
- chat_template.jinja (blob 01be9b30) has the hybrid enable_thinking switch
  (empty `<think>\n\n</think>\n\n` when enable_thinking is false).
- So the public 2507-Instruct BFCL rows (26.5% / 24.5%) are the wrong
  comparator. This decides no number of ours.

## 2. Thinking is off in every arm, by the template route
- The runner renders with the HF template:
  `apply_chat_template(..., enable_thinking=False)` (render_bfcl_tools_style,
  tools/bfcl_feasibility_probe.py:536). The RESIDENT path passes a GenAI
  ChatHistory with `set_extra_context({"enable_thinking": False})`
  (build_bfcl_chat_history, :647). Neither relies on a generate() kwarg.
- The first turn of every entry must be byte-identical between the two
  renders and end with `</think>\n\n`, else the run is FATAL
  (assert_first_turn_token_equivalence).
- Every generated step is checked: a `<think>` in the output is FATAL
  (assert_no_think_in_generation).
- Recorded raw text: 2,139 step texts in 16 runs (all committed telemetry
  runs with --debug-raw-text, 39c1c131 included, plus cddcd9fd from the window
  copy; 8af10211 recorded no step text), 0 contain `<think>` (analysis/demo2_pilots/BC/output_tokens.json, sha256
  9591dbbb...).

## 3. The IR is AWQ without scale estimation, and probably data-free
- openvino_model.xml rt_info (blob aab6b029, matches): nncf 3.0.0,
  weight_compression mode int4_sym, group_size 128, ratio 1.0, awq True,
  **scale_estimation False**, gptq False, backup_mode int8_asym.
- openvino_config.json (blob ce5fb40a): quantization_config dataset null,
  num_samples null, default_config quant_method "awq".
- The README says scale_estimation True and dataset wikitext2. The IR's own
  rt_info disagrees with its card. Our v2 pin copied the card
  (scale_estimation: true, dataset: wikitext2), so **the v2 pin's recipe is
  wrong on two fields**. The pin files are not edited; a v3 pin is a decision
  for Zach.
- "Data-free" is INFERRED (dataset null), not read from NNCF source.
- "Swap every arm to the official AWQ+SE IR" is moot: we already run the
  official IR, and no AWQ+SE build of it is published.

## 4. The 18,500-token error in a5d19dcc is an OpenCL event error, in turn 2
- derived/delta_prefill/a5d19dcc-.../work/n18500.a0.result.json:
  failure_mode "turn2:RuntimeError"; message
  "Exception from src\inference\src\cpp\remote_tensor.cpp:77: Exception from
  src\plugins\intel_gpu\src\runtime\ocl\ocl_event.cpp:71: [GPU]
  clWaitForEvents, error code: -14 CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST".
- Turn 1 (single prefill of 18,500) completed; the +183-token delta failed.
  19,000, 21,500 and 31,000 failed in turn 1 with "[GPU] CL_OUT_OF_RESOURCES
  exception" (ocl_common.hpp:62, via infer_request.cpp:224); 50,000 with
  "could not execute a primitive" (oneDNN, primitive_onednn_base.h:550).
  CL_OUT_OF_RESOURCES is the total-budget class in the research's list.
- The 18,500 message names no allocation and is none of the three the
  research listed: an earlier enqueued GPU command failed and the wait
  reported it.
- max_new_tokens was 1 (turn 1) and 8 there, so "2 x prompt under SIZE_MAX"
  cannot be the binding allocation in a5d19dcc. available_mb at failure: 5,034.
- Cold TTFT in the same run (true default, XPS): 12,000 16.96 s; 16,500
  23.38 s; 17,500 26.25 s; 18,000 29.09 s.

## 5. max_new_tokens is 512 in every run; output tokens per step
- OpenVinoLocalBackend.max_new_tokens = 512 (tools/run_h1_hybrid.py:1344); every
  plan.json generation_config.max_new_tokens = 512 (18 runs). **Arm A does not
  run SIZE_MAX generation**; the research's "SIZE_MAX explains the 3-hour
  stall" does not apply to our runs.
- 2,177 local steps (output_tokens.json): p50 47, p90 126, p99 512, max 512.
  Steps not at the cap: n 2,061, p99 301, max 482.
- 116 steps hit 512. 112 are on entries that failed locally (loops, e.g. 123
  repeats place_order and invents `<tool_response>` blocks in 20 of them).
  4 are entry 101 turn 0 step 1 (prose listing a price series), on entries
  that passed.
- Output cap from data: 512 (the shared cap) is above every non-runaway step.
  Arm C's min(512, ceiling - prompt) is always 512 inside its budgets (ceiling -
  budget = 1,024). No new cap value.

## 6. Pipeline lifetime, "step 0", chat mode
- A new LLMPipeline is built at every entry's begin_entry (reload_prefix_cache,
  tools/run_h1_hybrid.py:1548, 1656). No prefix-cache reuse across tasks; each
  task's first prefill is cold. TTFT is timed from generate(), so load time is
  excluded; first-generate warm-up effects are not separated.
- The TTFT/decode trigger reads step 0 of each user turn (CLAUDE.md DEMO-1
  record; turn_meets_slo / decide_slo_escalate). Turn 0 step 0 is cold; later
  turns' step 0 are warm deltas under prefix caching.
- RESIDENT generate() takes a ChatHistory with apply_chat_template True; no
  start_chat; finish_chat at entry end (errors suppressed, _finish_chat_safe).
  GenAI #4632 (generate(ChatHistory) leaves the *stateful SDPA* pipeline in chat
  mode) does not apply: every valid arm A load reads back backend PA, and the
  pipeline is rebuilt per entry. finish_chat's suppressed exceptions are a
  standing deviation from the no-swallowing rule (recorded, not changed).

## 7. CACHE_DIR: unresolved, and excluded from every arm
- Our "compiled KV" readback is GenAI's PA property dump in the load log
  (seam/genai_runtime.py parse_genai_load_log), not the key_cache.* port type.
- 3a03221e: a later load with CACHE_DIR printed KV_CACHE_PRECISION dynamic and
  DYNAMIC_QUANTIZATION_GROUP_SIZE 0; the cached import path may skip property
  finalization. Whether the compiled KV is really different is NOT YET MEASURED.
- No DEMO-2 arm sets CACHE_DIR (registered rule). The $0 check is ladder L0
  (part 3), needed only if an arm ever adopts CACHE_DIR.

## 8. Host settings to hold fixed
- Drivers (window records 2026-10-21): XPS Intel(R) Graphics 32.0.101.8860,
  NPU 32.0.100.4778; T2S Arc B390 32.0.101.8509, NPU 32.0.100.4512.
- Power: the launch gate records scheme and processor throttle. XPS "Best
  Performance", AC 100/100 (p11b_x0_xps_armA_launch.txt); T2S "High
  performance", AC 100/100, no battery.
- **Shared GPU Memory Override: recorded nowhere** (no field in seam/ or
  tools/). From the next windows the scripts record dxdiag's per-adapter memory
  lines and the Intel GPU registry keys (part 4); the value itself is NOT YET
  MEASURED.

## 9. Official BFCL harness vs ours (bfcl_eval 2025.12.17, the wheel we execute)
Same: Qwen Hermes tools block and `<tool_call>`/`<tool_response>` layout (the
HF template we render matches QwenFCHandler._format_prompt), tool results in a
user turn, the BFCL executor and long_context flag, MAXIMUM_STEP_LIMIT 20 with
the same `> 20` check, no system prompt added.
Different:
1. Thinking: official renders no empty think block (thinking on, up to the
   token budget); ours forces it off.
2. Sampling: official temperature 0.001 (default); ours greedy.
3. Tokens per step: official min(4,096, 40,960 - prompt - 2); ours 512.
4. Context limit: official sets max_context_length = max_position_embeddings
   (40,960) and a prompt over it errors at the server; ours has none
   (runs past 40,960, BB).
5. History: official stores an assistant tool-call turn as content "" plus
   re-serialized tool_calls (and reasoning_content); ours stores the raw
   generated text (prose and invented `<tool_response>` included).
6. Parser: official `<tool_call>\n(.*?)\n</tool_call>` only; ours tries that,
   then a looser `<tool_call>\s*({...})\s*</tool_call>`, and skips non-JSON
   bodies.
7. Weights and runtime: official HF bf16 on vLLM/SGLang; ours the INT4 IR on
   OpenVINO GPU.
