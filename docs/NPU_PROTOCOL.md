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
