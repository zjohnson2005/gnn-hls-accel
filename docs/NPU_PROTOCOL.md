# NPU positive control

Registered before any NPU measurement. The runner that applies this rule
must not open a preregistration or a predictions file. The decision is
`seam.npu_validity.decide_npu_cell`.

Motivation: openvino.genai #3255 (NPU output is garbage past the prompt
limit) and openvino #35641 (int8 on NPU crashes at load).

## A cell may be timed only when it is valid

An NPU cell is valid only when both of these hold:

1. Its output parses with `seam.backends.local_openvino.parse_tool_calls`,
   the parser the GPU backend uses on the same prompt. Text with no
   `<tool_call>` envelope parses as no calls. A `<tool_call>` envelope
   that yields no call is a parse failure.
2. The output is non-degenerate. Token 4-grams are taken from the caller
   token ids when the cell has them, otherwise from whitespace tokens of
   the output text. If more than 50 percent of those 4-grams repeat an
   earlier 4-gram, the cell is refused. A fraction of exactly 0.5 is not
   a refusal. Fewer than 4 tokens produces no 4-gram and is not a repeat
   refusal.

## Infeasible cells are not timings

`NPUW_LLM_MAX_PROMPT_LEN` is a load-time setting, not a measured limit.
NPU-1 sets it at load for 1024, 2048, 4096, 8192, and then doubles until
the load fails. Record the requested value, the readback, the load time,
process memory, and `error_class` when the load fails. A readback that
does not match the requested value refuses the cell.

At each loaded setting, bisect the 10 s TTFT SLO from 64 up to that
setting. Record decode tok/s at the highest rung that passes. A prompt of
`MAX_PROMPT_LEN + 1` is infeasible and is not generated. The setting's
bound is `TOOLCHAIN_CAP` when the highest feasible rung passes the SLO.
`LATENCY` only when a timed rung fails the SLO. An infeasible or refused
rung is not a timing and is not `LATENCY`. `LOAD_FAIL` when the load fails.

The int4 IR is INT4_SYM group_size 128 (group-wise). A channel-wise IR
(group_size -1) is a later arm.

Record `NPUW_LLM_MAX_PROMPT_LEN` as loaded (`max_prompt_len`) and the
prompt length in the same token count the cell used. A prompt longer than
`MAX_PROMPT_LEN` is an infeasible cell. It is not a timing.

int8 weights on NPU are infeasible at load (`npu_int8_not_run_past_load`,
openvino #35641). Do not run the cell past load, and do not record a time.

## Paired GPU reference

Each NPU cell runs a paired GPU generation on the same prompt in the same
session. Record whether the NPU output text is an exact match to the GPU
output. A mismatch is recorded and is not a failure. A missing GPU output
refuses the cell.

## Failures

A refused or infeasible decision has `timed: false` and a `reason`. The
caller must not record a duration for that cell.
