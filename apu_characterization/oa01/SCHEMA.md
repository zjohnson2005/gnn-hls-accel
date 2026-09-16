# OA-01 schema — authentic boundary trace

OA-01 is a separate validity class from TurnTrace v2. It reuses the v2 LCP,
replay, and taxonomy concepts, but it does not use in-subject stage timers.

## Raw records

### `oa01_api_boundary_v1`

One record per provider call. The proxy stores exact request and response body
bytes as base64 plus parsed JSON when valid. Timestamps are Unix nanoseconds at:

1. proxy request receipt;
2. upstream send;
3. upstream response headers;
4. first upstream response-body byte;
5. last upstream response-body byte; and
6. completion of relay to the subject.

Request/response bodies are not rewritten. Secret-bearing HTTP headers are
replaced in the archive with a SHA-256 digest. Usage accepts both APIs:

- Chat Completions: `prompt_tokens`, `completion_tokens`,
  `prompt_tokens_details.cached_tokens`;
- Responses: `input_tokens`, `output_tokens`,
  `input_tokens_details.cached_tokens`.

### `oa01_exec_event_v1`

Start/end events emitted by the process-level Docker executable wrapper. `exec`
events are tool spans. `run`, `inspect`, `stop`, and `rm` remain archived but
are not booked as agent tool execution.

### `oa01_env_snapshot_v1`

An asynchronous sidecar snapshot after each completed `docker exec`: image ID,
git commit, porcelain status, and binary diff. It does not block the subject's
tool call. The snapshot timestamp is first-class because the next subject
action may race it; such a race is documented, never silently reordered.

## Derived `TurnRecord`

One turn is one model call and its following tool calls. Turn 0 begins at
trajectory process launch so startup is retained. A later turn begins when its
request reaches the proxy. The turn ends when the next request reaches the
proxy, or at trajectory process exit for the final turn.

`t_orch_gap_ms` is:

`turn wall − union(API boundary span, docker exec spans)`

Spans are unioned, not naively summed. The trajectory conservation audit uses
the same intervals and permits only timestamp rounding tolerance.

### Cloud timing limitation

The pinned mini-SWE-agent `LitellmModel` calls `litellm.completion` without
streaming. OA-01 does not force streaming because that would alter the shipped
request. For such calls, first response-body byte arrives after the complete
generation and:

- `timing_method = nonstreaming_first_byte_includes_decode`;
- `t_model_observed_ms` is reported;
- `t_prefill_ms`, `t_decode_ms`, and `t_network_ms` are null; and
- `prefill_decode_network_not_isolated` is flagged.

If the shipped subject sends a streaming request, first-byte/body timing is
retained. `openai-processing-ms`, when present, is the prefill proxy and the
residual to first byte is network. No timing split is fabricated when the
provider isolate is absent.

This coarseness is an authenticity result, not a reason to transform the
request.

## Provider-cache three-way split

For each call, the proxy request's prompt-bearing fields are canonicalized and
encoded with the model's `tiktoken` encoding. LCP is against the immediately
preceding call in the same trajectory.

- `structurally_redundant_tokens = min(provider_input_tokens, local_LCP_tokens)`
- `provider_recovered_tokens = usage.*_tokens_details.cached_tokens`
- `actually_recomputed_redundant_tokens =
  max(0, structurally_redundant_tokens − provider_recovered_tokens)`
- `necessary_prefill_tokens =
  provider_input_tokens − structurally_redundant_tokens`

The currencies are reconciled with
`template_overhead_envelope_tokens = max(256, max(0, provider−local)+32)`.
The 256-token floor absorbs OpenAI's 128-token cache quantization plus local
JSON canonicalization mismatch against the provider's internal chat
serialization. `provider_cache_reconciliation` is flagged when recovered
exceeds structural plus this envelope. The violation is retained before the
required nonnegative clamp.

## Trajectory outcomes

`success` is nullable until the official SWE-bench evaluator runs. Agent
submission is not equated with benchmark success. `censored=true` with
`censor_reason` is distinct from failure. Subject crashes, empty patches,
format-error exits, and evaluation failures all remain in the corpus.

## Per-arm determinism deviation

OA-01 records the scaffold/provider sampling parameters but does not override
them and does not set a seed or temperature. Replay completeness is required;
reproduction is not. Only one smoke-level replay integrity check is gated.

