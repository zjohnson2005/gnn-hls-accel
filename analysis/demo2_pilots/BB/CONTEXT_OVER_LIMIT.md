# Local generates past Qwen3-4B's 40,960 positions (Task BB part 2, 2026-10-21 ET)

Data: analysis/demo2_pilots/BB/context_over_limit.json (sha256
3bdd341893721b351e713a4dcdec37f8431196d3f4411f3df06dbf07df8c0eef), from
context_over_limit.py.

Method:
- Runs with per-step raw text were replayed through the runner's render path,
  with the pinned HF tokenizer and the BFCL executor. Every replayed turn's
  step-0 size matched the recorded prompt_tokens: 15 runs, all entries "replay".
- DEMO-1 slo_escalate cells have no step texts, so only each local turn's
  step-0 n_ctx is counted (a lower bound).
- 8af10211 comes from its step_log.

Scope: 30 run directories, 3,350 local generates (or step-0 turns, where per-step
data is missing).
- Above 40,960 (the model's max_position_embeddings): **43 generates in 8 runs**.
- Above 32,768 (Qwen3's native context): **161 generates**.

## Generates above 40,960
| run | host | arm | entries (steps > 40,960, max prompt) | entry outcome |
|---|---|---|---|---|
| 841b84e4 | XPS | i8 (A), LONGCTX 1-14, unsealed partial | 112 (1, 40,997); 117 (3, 43,961) | both local fail |
| 162a9b5c | XPS | u4, LONGCTX 1-14 | 112 (1, 40,997); 117 (3, 43,974) | both local fail |
| 15367c3a | XPS | i8 (A), LONGCTX 15-30 | 135 (4, 43,245); 138 (5, 67,947) | both local fail |
| 1a634610 | T2S | i8 (A), LONGCTX 0-13 | 112 (1); 117 (3, 43,961) | both local fail |
| 3aa565da | T2S | u4, LONGCTX 0-13 | 112 (1); 117 (3, 43,974) | both local fail |
| daa6c026 | T2S | i8 (A), LONGCTX 15-29 | 135 (4, 43,245); 138 (5, 67,947) | both local fail |
| 108d5f43 | T2S | u4, LONGCTX 15-29 | 135 (4, 43,150) | local fail |
| 8af10211 | T2S | i8 (A), 123 alone, unsealed | 123 (5 of 6 steps, 89,660) | turn budget fired at 600 s, progressing |

- Every entry with a step above 40,960 is a local fail. All of them are
  long_context entries that also fail in other ways, so this is not a causal
  claim.
- BASE_30 runs (39c1c131, b90f1d5b, 1f3a261a, 6c610aa6, 09932887, 16996cdb,
  4d8e2fb1, cc32619a, 03632ad3, 640ec474) have none; their max is 6,382.
- DEMO-1 cells (f7343708, b026f3fd, 71d33f7a+ab88f47f, a678926e, a4284ab0,
  30caa847, f7de976b, 86d0f4cf, b323f0e5) have none; their max step-0 is 12,686.
  1acc8c58 is CPU, with no local turns.

Timing (MEASURED wall per step; the step with the large new block is the slow
one):

| step | XPS (TTFT / wall) | T2S (TTFT / wall) |
|---|---|---|
| 117 t3s1, 43,119 | 336.8 s / 388.2 s | 77.7 s / 109.7 s |
| 135 t1s1, 42,438 | 480.2 s / 533.4 s | 73.0 s / 104.5 s |
| 138 t0s3, 66,694 | 707.6 s / 779.5 s | 161.6 s / 197.2 s |

The XPS takes 3.5-5.1x the T2S wall on the same step (DERIVED ratio). Later
steps that reuse the prefix are seconds on both hosts.

## What this means for "context held"
- Arm A's 43,961-token prompts (117 turn 5, XPS and T2S) and the 67,947-token
  ones (138) are above 40,960. They ran with no error, so the runtime "held" them.
- But the model was run beyond its trained positions. "Context held" in the
  thesis sense (the model works at that context) is **not valid** above 40,960.
- Any context-held figure must stop at 40,960, or report turns above it
  separately as "accepted by the runtime, outside the model's positions".
- P6's n_ctx_over_window list (AZ) includes 43,245, 43,961 and 67,947. The P6
  verdict (band 20,000-23,850) is unaffected.
- The 34,066-40,923 turns are above 32,768 (Qwen3's native window without RoPE
  scaling) but inside 40,960. This note makes no claim about them.

## Does OpenVINO GenAI 2026.2.1 enforce a limit? No, by default.
Source checked: openvino.genai tag 2026.2.1.0, commit 7dea0459b2a. That is the
build on both hosts ("2026.2.1.0-3123-7dea0459b2a").
- `src/cpp/include/openvino/genai/generation_config.hpp:635-636`:
  `max_new_tokens = SIZE_MAX`, `max_length = SIZE_MAX`.
- `src/cpp/src/continuous_batching/pipeline_impl.cpp:292`: the only length check
  on a request is `OPENVINO_ASSERT(sampling_params_copy.max_length > prompt_len, ...)`.
  With max_length SIZE_MAX it never fires. Our config sets max_new_tokens 512 and
  leaves max_length unset.
- `max_position_embeddings` is read only by the text-embedding (RAG) pipeline
  (`src/cpp/src/rag/text_embedding_pipeline.cpp:38-54`) and by CLIP for images
  (`src/cpp/src/image_generation/models/clip_text_model.cpp:35`). The LLM /
  continuous-batching path never reads it.
- Tokenizer truncation is off unless max_length is passed:
  `src/cpp/src/tokenizer/make_tokenizer_stateful.cpp:212-223`. is_max_length_set
  defaults false, and the truncation length is then int32 max - 64.
- Our harness's --context-window is off by default. So nothing in the default
  stack refuses or warns on an 87,392-token prompt.
- The 8af10211 run confirms it: 87,392-89,660-token prompts were accepted with no
  error line.
- NOT VERIFIED: whether the host model dir's generation_config.json sets
  max_length. The runs show it is not below 89,660.
