# NPU-MAXLEN-DIAG decision rule v2 (pre-run)

Written and committed before tools/npu_maxlen_diag.py implements it and
before any v2 run. The script does not open this file. v1 is
derived/npu/diag/NPU_MAXLEN_DIAG_RULE.md, sha256
f7af7798e30410f17b3d6fb79695da6b77f250aea9cd8c67b146b57d84ee388d. v1 is
not edited. Everything
in v1 holds (purpose, measured basis, hypotheses, arms, readback sources,
definitions, D1-D4, precedence, outputs) except the changes below.

## Why v2

Run 1 (rule v1, derived/npu/diag/diag_20261007T180320Z/, git 22a1a9b) is
D4 and stays D4. pipeline_input_tokens was null for all 4 prompts, so
every prompt was truncation_unknown and band A was not accepted in either
arm. The instrument, not the hardware, caused the D4.

## Change 1: instrument for the pipeline input-token count

Cause in run 1: the script called pipe.generate(prompt_str, cfg,
streamer). On openvino-genai 2026.2.1 a single str input returns a plain
str, which carries no perf_metrics. The streamer counts output tokens
only.

v2 calls pipe.generate([prompt_str], cfg, streamer) (a one-element list).
That form returns DecodedResults. The input-token count is
DecodedResults.perf_metrics.get_num_input_tokens(). TTFT from
perf_metrics.get_ttft().mean is recorded beside the streamer TTFT.

Evidence, off the NPU (CPU, Mac, 2026-10-07): openvino-genai
2026.2.1.0-3123-7dea0459b2a (the same build string the T2S run reported),
openvino 2026.2.1, model OpenVINO/Qwen3-0.6B-int4-ov revision
f864c6106efb6c7f7b4ef274a78a98e37210dddd, rendered prompt of 18 tokens,
max_new_tokens 8, do_sample false:

    form=str  type=str            NO perf_metrics
    form=list type=DecodedResults num_input=26 num_gen=8   (apply_chat_template True)
    form=list type=DecodedResults num_input=18 num_gen=8   (apply_chat_template False)

The streamer received 8 tokens in every case. The same check is added, with
the script change, as tests/test_npu_maxlen_diag_api.py. It runs on CPU when openvino_genai
and a small IR are present, and is skipped otherwise.

Observation from the same evidence: with apply_chat_template True (the
GenerationConfig default, and what tools/run_npu_profile.py uses) the
pipeline wraps the already-rendered prompt in the chat template again,
adding 8 tokens. This matches run 1: K-NPUW 1500 was refused as "1508 is
passed". v2 keeps apply_chat_template True, set explicitly, so the
diagnostic sees the prompt exactly as the NPU-1 runner sends it. The
expected pipeline count is realized + 8. TRUNCATED stays as in v1
(pipeline count < realized count). The realized count stays the model
tokenizer's count of the rendered prompt.

## Change 2: band C, positive control on the cap

A third prompt per arm, target 2125, band C = realized tokens [2100,
2150]. With the re-wrap the pipeline sees about 2133, which is above 2048.

"Refused by the runtime length check": generate raised, and the
exception message contains "m_max_prompt_len" (the check text run 1
recorded: "Check 'data->input_ids.get_size() <= m_max_prompt_len'
failed"). The cap stated in the message ("up to N tokens") is parsed and
recorded. It is outside the rule.

- D1 SETTING_APPLIED (changed): in >= 1 arm, band B is accepted, not
  truncated, and valid, AND band C is refused by the runtime length check
  in that same arm. Such an arm is a D1 arm.
  - key_fix: K-NPUW is not a D1 arm.
  - readback_fix: in some D1 arm, r1 after load != 2048.
- D4 (changed only by adding band C to the band check): any realized
  count outside its band, now including band C, is D4.
- D2 and D3: unchanged. Band C does not enter them.
- D4 ordering is unchanged: the D4 checks (arm broken, realized out of
  band, band A not accepted-and-valid in any arm) run first; then D1, D2,
  D3; else D4.

## Change 3: explicit greedy config per call

Every generate call builds a fresh GenerationConfig with do_sample false,
max_new_tokens 8 (the runner's MAX_NEW_TOKENS), and apply_chat_template
true. The config as passed (do_sample, max_new_tokens,
apply_chat_template, and every other readable field) is recorded per
call. Run 1 already set do_sample false and max_new_tokens 8 on a fresh
config, but it did not record them.

## Unchanged

Arms K-DOC (MAX_PROMPT_LEN=2048, MIN_RESPONSE_LEN=8) and K-NPUW
(NPUW_LLM_MAX_PROMPT_LEN=2048), both with NPUW_LLM_PREFILL_CHUNK_SIZE=1024.
One child per arm, sequential, 600 s timeout. Bands A [850, 950] and
B [1450, 1550]. Readback sources r1 (the pinned copy of the runner's
readback), r2, r3. Validity per docs/NPU_PROTOCOL.md. Accepted,
TRUNCATED, TRUNCATION_UNKNOWN, B_OK, B_REJ as in v1. Actions per D-case
as in v1. Band A TTFT is recorded outside the rule.

## Output

derived/npu/diag/diag_<UTCstamp>/diag.json with rule_version 2.
Final stdout line: DIAG_VERDICT <D1|D2|D3|D4> <subcase> <out_dir>.
