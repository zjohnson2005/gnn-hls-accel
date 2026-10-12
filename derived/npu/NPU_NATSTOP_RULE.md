# NPU-NATSTOP decision rule (pre-run)

Written and committed before tools/npu_natstop.py exists and before any run.
The script does not open this file (tests/test_npu_profile.py asserts it).
Diagnostic for NPU-1, not a measurement. Nothing it times is cited.

## Question

Does the NPU end or degenerate where the GPU writes text, and does the chat
template cause it?

## Measured basis

- Every sealed NPU-1 capacity-check P1 text is degenerate: "</think>"
  repeats at 960 (34c2240f), 1984 (f704d565, ca3467ad), 8128 (413d4a2e),
  16320 (d626d0bc) and 32704 (3a672cd5); backtick repeats at 4032
  (47630f52). Those P1 generates forced 8 tokens (min_new_tokens 8).
- 8ccfb38c (no forced tokens): P1 text empty; rung rows streamed at most one
  token. The GPU wrote text on the same prompts.
- Amendment 2026-10-08c: the validity rule (whitespace 4-grams over 8 forced
  tokens) cannot separate real from degenerate text, so the 768 limit is not
  cited and NPU-1 prediction (b) is not scored until this diagnostic and a
  validity amendment.

## Arms

Same IR on both devices: configs/models/Qwen3-4B-int4-ov.yaml (Qwen3-4B
int4, INT4_SYM group_size 128).

- Device NPU: LLMPipeline(ir, "NPU", MAX_PROMPT_LEN=2048,
  MIN_RESPONSE_LEN=8, NPUW_LLM_PREFILL_CHUNK_SIZE=1024) (amendment
  2026-10-07, as tools/run_npu_profile.py loads it).
- Device GPU: LLMPipeline(ir, "GPU"), the paired GPU pipeline of
  tools/run_npu_profile.py.
- Template SINGLE: the prompt is pre-rendered with the chat template
  (thinking disabled); GenerationConfig.apply_chat_template = False;
  list-form generate([prompt], cfg, streamer). This is the NPU-1 runner
  since 2026-10-07.
- Template DOUBLE: the same pre-rendered prompt with
  apply_chat_template = True, so the pipeline wraps it in the template again
  (NPU-1 before 2026-10-07; NPU-MAXLEN-DIAG v2 measured +8 tokens).
- Generation: greedy (do_sample False), max_new_tokens 64, min_new_tokens
  not set (no forced tokens).
- Prompts: the NPU-1 rung prompt builder
  (seam.tools.boot4_text.rendered_exact_prompt, the configs/delta_n.yaml
  filler unit, salt "npu") at 64, 768, 960 and 1984 realized tokens.
  1984 = 2048 - 64, the P1 length at this setting.

Cells: 2 devices x 2 templates x 4 lengths = 16. Each cell runs in its own
child process that loads one pipeline, generates once, writes its record
and exits. Children run one after another, so two NPU pipelines are never
loaded at once. Order: for each length ascending, NPU SINGLE, NPU DOUBLE,
GPU SINGLE, GPU DOUBLE. Child timeout 600 s.

## Recorded per generate

full text; generated token ids (first 64, as the streamer received them);
completion count (perf_metrics generated-token count, and the streamer
count); first-token id and its decoded text; stop reason; TTFT (streamer
wall to the first token, and perf_metrics TTFT); pipeline input count
(perf_metrics input-token count); realized prompt count (tokenizer count of
the rendered prompt); child exit code. Also recorded, outside the rule: load
time, the pipeline's eos and stop token ids, kv room (NPU: 2048 + 8 minus the
pipeline input count), versions, git head, watchdog state.

## Definitions (each computed by code from the recorded fields)

- cell ok: the child exited 0, its record is complete, the load did not
  fail, generate returned, and the pipeline input count is reported.
  For SINGLE, the pipeline input count also equals the realized count.
- ids(c): the generated token ids of cell c.
- stop reason: "max" when the completion count is >= 64; "EOS" when it is
  below 64 (the pipeline stopped by itself: an end or stop token, or, on
  the NPU, kv room); "error" when generate raised. The last id and whether
  it is in the pipeline's eos/stop set are recorded.
- real text: the full text with every "<think>" and "</think>" removed,
  then whitespace stripped.
- id repeat fraction: share of 4-grams of ids(c) that repeat an earlier
  4-gram (seam.npu_validity.fourgram_repeat_fraction over token ids, not
  whitespace words). Null below 4 ids.
- degenerate(c): cell ok and (real text is empty, or id repeat fraction
  > 0.5).
- ends at once(c): cell ok, stop reason "EOS", and real text empty.
- fails(c): ends at once(c) or degenerate(c).
- writes text(c): cell ok and not fails(c).
- matches(npu, gpu): both cells ok, and either both have at least 16 ids
  and their first 16 ids are equal, or both have fewer than 16 ids and
  their id lists are equal. The GPU reference for an NPU cell is the GPU
  cell with the same template and length (same input text, same
  generation config).

## Verdict (code-classified; first match wins)

Precondition G: every GPU SINGLE cell writes text (all 4 lengths).
If G fails, the GPU reference is unusable: N4.

- N1: G, and for every length, matches(NPU SINGLE, GPU SINGLE).
  Meaning: the NPU writes what the GPU writes when nothing is forced; the
  degenerate NPU-1 text came from forced tokens. Action: the validity
  amendment uses real-token checks; NPU-1 bisections can proceed.
- N2: G, and for every length, fails(NPU SINGLE), writes text(GPU
  DOUBLE), and matches(NPU DOUBLE, GPU DOUBLE).
  Meaning: template interaction on the NPU path. Action: the validity
  amendment must choose the template per device, with the reason.
- N3: G, and for every length, fails(NPU SINGLE) and fails(NPU DOUBLE).
  Meaning: NPU output is invalid on this toolchain. Action: NPU-1 limits
  become validity-bound; no NPU generation result is usable.
- N4: anything else, including a load failure, a crash or timeout, a cell
  not ok, or a result that differs by length. Action: report to Zach; no
  rule change.

A length that satisfies one case and another length that satisfies a
different case is N4 (mixed by length).

## Not in the rule

TTFT, load time, kv room, first-token text, and the eos/stop membership of
the last id are recorded and reported, not used. Nothing is cited.

## Output

derived/npu/natstop_<run_id>/: plan.json (written at start), one
cell_<device>_<template>_<n>.json per child with its stdout/stderr logs,
and summary.json (all cells, the per-cell definitions above, verdict,
ended_utc). Final stdout line: NATSTOP_VERDICT <N1|N2|N3|N4> <out_dir>.
Launcher: tools/launch_t2s_natstop.ps1 (-Detach, -Rehearsal); log
derived/c2_ttft/_launches/npu-natstop_<UTC stamp>.log.
