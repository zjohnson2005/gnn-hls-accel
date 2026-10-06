# 680b031a binding, corrected

The sealed summary records `binding: LATENCY`. That label does not match
the registered rule. The run tree was not edited.

Rule (`docs/NPU_PROTOCOL.md`): `TOOLCHAIN_CAP` when the highest feasible
rung passes the 10 s SLO. `LATENCY` only when a timed rung fails that SLO.
An infeasible or refused rung is not a timing and is not `LATENCY`.

`680b031a` (boot `792e909d`): readback 1024, `ttft_limit_n` 960. The 960
rung is timed and passes. The 1024 rung has `prefill_s` null on all three
repeats (`status` REFUSED, `error_class` other). That is not a timed SLO
miss. The separate `over_max` record is `prompt_length` 1025,
`reason` `prompt_longer_than_max_prompt_len`, and `generated` false. Under
the rule the binding is `TOOLCHAIN_CAP` with `ttft_limit_n` 960.
`tools.run_npu_profile.bind_setting` now applies that rule. The run
file is left as written.

This run is UNGUARDED (`derived/VOIDS/notes/680b031a.md`). Prediction b
in `derived/npu/NPU1_PREREG.json` is not scored from it.

## Realized prompt tokens

`prompt_length` on the 960 rung is 960, 960, 960. `prompt_length` on the
1024 rung is null, null, null. The 1024 repeats do not record a realized
token count.

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

Same boot. The cell is the int8 load. `generated` is false, `status` is
`infeasible`, `reason` is `npu_int8_not_run_past_load`. `error_class` is
null. `load_error` is null. The summary records no exception text.
