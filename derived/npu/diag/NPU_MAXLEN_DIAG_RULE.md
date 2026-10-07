# NPU-MAXLEN-DIAG decision rule (pre-run)

Written and committed before tools/npu_maxlen_diag.py is committed and
before any diagnostic run. The script does not open this file.

## Purpose

Diagnostic, not a measurement. Nothing from it is cited as a result. It
decides how the NPU-1 MAX_PROMPT_LEN ladder continues after 28cf811d
(request 2048) was refused at load: load_s 94.72, max_prompt_len_readback
1024, "readback does not match the requested MAX_PROMPT_LEN", UNGUARDED
(refused before arming). Outputs go to derived/npu/diag/.

## Measured basis

- 680b031a (UNGUARDED, sealed): readback 1024, ttft_limit_n 960;
  prompt_length at 960 is 960, 960, 960; at 1024 null, null, null; flat
  prefill about 1.30 s near 1024.
- 04d189da (guarded 1024 rerun, armed, not yet sealed): readback 1024,
  passed, TOOLCHAIN_CAP, limit expected 960 (to confirm).

## Hypotheses

- (a) Setting not applied. The runner passes NPUW_LLM_MAX_PROMPT_LEN
  (tools/run_npu_profile.py:541). The OpenVINO GenAI NPU docs pass
  MAX_PROMPT_LEN, with MIN_RESPONSE_LEN, in the LLMPipeline config.
- (b) The readback reads the device default, not the compiled pipeline.
  The runner tries pipe.get_property("NPUW_LLM_MAX_PROMPT_LEN") and, on
  any exception, core.get_property("NPU", "NPUW_LLM_MAX_PROMPT_LEN")
  (tools/run_npu_profile.py:554-562). The XPS pilot read 1024, the value
  the device reports before any load.
- (c) A genuine runtime clamp at 1024 for this toolchain
  (openvino 2026.2.1, openvino-genai 2026.2.1.0, requirements.lock.txt).

## Arms

Each arm runs in its own child process, one after the other. Two
pipelines are never loaded at once. Child timeout 600 s. Both arms pass
NPUW_LLM_PREFILL_CHUNK_SIZE=1024, as the runner does (launch_boot1.ps1
passes --prefill-chunk-size 1024). Same int4 IR
(configs/models/Qwen3-4B-int4-ov.yaml), device NPU.

- K-DOC: LLMPipeline config MAX_PROMPT_LEN=2048 and MIN_RESPONSE_LEN=8.
  8 is the runner's decode length (MAX_NEW_TOKENS = 8,
  tools/run_npu_profile.py:41). NPUW_LLM_MAX_PROMPT_LEN is not passed.
- K-NPUW: NPUW_LLM_MAX_PROMPT_LEN=2048 exactly as the runner passes it
  today. Reproduces 28cf811d. MAX_PROMPT_LEN and MIN_RESPONSE_LEN are not
  passed.

## Per arm

1. Readback before load: r1 and r2 (below).
2. Load. Record load time and the load exception, if any.
3. Readback after load: r1, r2, r3.
4. Two greedy prompts, max_new_tokens 8, built by the NPU-1 runner's
   prompt builder (seam.tools.boot4_text.rendered_exact_prompt, chat
   template applied, thinking disabled, filler unit from
   configs/delta_n.yaml, salt "npu"). Targets 900 and 1500. The realized
   count is the model tokenizer's count of the rendered prompt. Band A is
   [850, 950], band B is [1450, 1550].
   generate is called directly. No pre-generate length check is applied,
   so the runtime, not our readback, decides acceptance.

Per prompt, record: accepted or refused (with exception class and
message), pipeline-reported input token count (perf_metrics
get_num_input_tokens, if exposed), TTFT, output text, validity, and the
child exit code in hex.

## Readback sources

- r1: the runner's readback sequence, unchanged: pipe.get_property then
  core.get_property fallback, as in tools/run_npu_profile.py:554-562.
  Before load there is no pipeline, so r1 before load is the core
  fallback alone. The runner has no standalone readback function (it is
  inline in run_hardware) and the runner is not edited for this
  diagnostic, so the script carries a verbatim copy of that sequence and
  a test pins the copy to the runner's source text.
- r2: core.get_property("NPU", p), before and after load, for every name
  p in core.get_property("NPU", "SUPPORTED_PROPERTIES") that contains
  PROMPT, RESPONSE, or NPUW_LLM.
- r3: anything the loaded pipeline exposes. Record each attempt and its
  result, including "not exposed".

## Definitions

- Validity, per docs/NPU_PROTOCOL.md: the output parses with the GPU
  parser (seam.npu_validity.output_parses), and the share of repeated
  4-grams (seam.npu_validity.fourgram_repeat_fraction over whitespace
  tokens of the output text, as the runner does) is not above 0.5.
- TRUNCATED: pipeline-reported input tokens < realized count.
- Accepted: generate returned without exception, AND the pipeline
  reported an input token count, AND that count is not below the realized
  count. TRUNCATED counts as not accepted. A missing pipeline count is
  TRUNCATION_UNKNOWN and also counts as not accepted. A refusal is an
  exception from generate.
- B_OK(arm): band B prompt accepted and valid in that arm.
- B_REJ(arm): band B prompt refused or TRUNCATED in that arm.

## Decision rule

Classified by code (classify(results) in the script) from the recorded
fields. Precedence is top to bottom.

- D4 INCONCLUSIVE, checked first: any arm with a load failure, child
  crash, child timeout, non-zero exit, or missing result; any realized
  count outside its band; band A not accepted-and-valid in any arm.
  Action: no ladder run; report to Zach.
- D1 SETTING_APPLIED: B_OK in >= 1 arm.
  Subcases (both can hold; reported as key_fix, readback_fix,
  key_fix+readback_fix, or none):
  - key_fix: K-NPUW is not B_OK (hypothesis a).
  - readback_fix: in some B_OK arm, r1 after load != 2048
    (hypothesis b).
  Action: NPU_PROTOCOL amendment (documented key and/or the readback
  replaced by the source that tracks the request, or by a realized-
  capacity check: a cap-64 prompt must be accepted and valid at load),
  committed before any rerun. Then rerun 2048, then 4096, 8192 per the
  ladder. 28cf811d stays REFUSED and is kept.
- D2 RUNTIME_CLAMP: B_REJ in both arms (band A already accepted and valid
  in both arms by the D4 check).
  Action: hypothesis (c). Prediction (a) is falsified at 2048.
  4096/8192/16384 become load-only checks under an amendment. The NPU-1
  limit rests on 04d189da.
- D3 ACCEPTED_INVALID: band B accepted (not truncated) in >= 1 arm, and
  invalid in every arm where it is accepted (so no arm is B_OK).
  Action: no ladder run; report to Zach.
- D4 INCONCLUSIVE: anything else (for example band B accepted-and-invalid
  in neither arm while TRUNCATION_UNKNOWN in one).
  Action: no ladder run; report to Zach.

## Recorded, outside the rule

TTFT of the band A prompt in each arm, against the flat ~1.30 s prefill
seen near 1024 in 680b031a.

## Output

derived/npu/diag/diag_<UTCstamp>/diag.json and per-arm stdout/stderr
logs. Final stdout line: DIAG_VERDICT <D1|D2|D3|D4> <subcase> <out_dir>.
