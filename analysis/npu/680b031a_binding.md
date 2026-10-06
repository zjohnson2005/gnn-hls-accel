# 680b031a binding, corrected

The run tree is not in this clone. Nothing here edits it. The summary on
the host records `binding: LATENCY`. That label does not match the
registered rule.

Rule (`docs/NPU_PROTOCOL.md`): `TOOLCHAIN_CAP` when the highest feasible
rung passes the 10 s SLO. `LATENCY` only when a timed rung fails that SLO.
An infeasible or refused rung is not a timing and is not `LATENCY`.

Operator reading of `680b031a` (boot `792e909d`): readback 1024,
`ttft_limit_n` 960, passing rungs prefill about 1.30 s, the 1024 rung
`prefill_s` null and refused as `prompt_longer_than_max_prompt_len`.
Under the rule the 1024 rung is not a latency miss, and 960 passes, so
the binding is `TOOLCHAIN_CAP` with `ttft_limit_n` 960.
`tools.run_npu_profile.bind_setting` now applies that rule. The run
file is left as written.

This run is UNGUARDED (`derived/VOIDS/notes/680b031a.md`). Prediction b
in `derived/npu/NPU1_PREREG.json` is not scored from it.

## Realized prompt tokens

`rendered_exact_prompt` builds a chat-template prompt whose harness token
count equals the requested `n`. The cell then records the pipeline count
(`perf_metrics.get_num_input_tokens`) as `prompt_length`. A requested
1024 can exceed `NPUW_LLM_MAX_PROMPT_LEN` 1024 on that second count. The
integers for the 960 and 1024 rungs are `prompt_length` on each repeat in
the host `summary.json`. They are not copied into this file.

## Prefill shape

Passing rungs from 64 through 960 are about 1.30 s. That is the shape
expected when the static prefill is padded to `NPUW_LLM_PREFILL_CHUNK_SIZE`
1024 (`openvino#34617`, already the runner's `prefill_chunk_citation`).
Later settings (2048, 4096, 8192) need the per-rung `prefill_s` list and
the realized `prompt_tokens` list, which `summarize_rung` now writes, to
see whether the cost steps once per 1024-token chunk. An untimed rung
still stores `prefill_s: null`; the protocol does not record a duration
for a refused cell.

## NPU-2 `27b4841d`

Same boot. The cell is the int8 load. The runner does not generate.
`error_class` and the exception text are `summary.json` fields
`error_class` and `load_error` on the host tree. This clone does not
contain that file, so those two strings are not restated here.
