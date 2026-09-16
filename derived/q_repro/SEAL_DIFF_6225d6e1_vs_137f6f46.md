# Q-REPRO — seal diff: W-3 `6225d6e1` vs Q-KV `137f6f46`

Field-by-field comparison of sealed artifacts (read-only). Written **before** Q-REPRO generation.

| field | W-3 `6225d6e1` | Q-KV `137f6f46` | same? |
|---|---|---|---|
| IR `ir_sha256` | `c1821f29332faa48871c7f16426a21443fbc701fa4e4c8a581a8c51ab7bf2cb2` | same model_spec pin | **yes** |
| model revision | `b467368d16b75df14055562fe927ae8e1f15f7ef` | same YAML `revision` | **yes** |
| model_spec | `Qwen3-4B-int4-ov.yaml` | same | **yes** |
| entry set | multi_turn_base prefix n=200 | same pin `3502c535…` | **yes** |
| residency | RESIDENT | RESIDENT | **yes** |
| placement | `gpu_only` | `gpu_only` (+ KV arms) | yes (topology) |
| **KV** | **unset → readback `dynamic`** | **pinned f16/u8/u4** | **NO** |
| max_new_tokens | 512 | 512 | yes |
| do_sample / greedy | False / greedy | False / greedy | yes |
| apply_chat_template | False | False | yes |
| step limit | `MAXIMUM_STEP_LIMIT=20` | same probe path | yes |
| prompt format | `bfcl_chat_history_tools_thinking_off` | same `run_multi_turn_agent_entry` | yes |
| tokenizer files (spec) | `tokenizer.json` sha `aeb13307…` etc. | same model_spec | yes |
| OpenVINO | `2026.2.1-21919-ede283a88e3-releases/2026/2` | same venv (H1/Q-KV era; Q-KV plan omitted stack in single-pipe mode) | **yes (inferred)** |
| OpenVINO GenAI | `2026.2.1.0-3123-7dea0459b2a` | same | **yes (inferred)** |
| scorer | multi_turn_checker + CAP-01; bfcl_eval `2025.12.17` | same pin in plan | yes |
| prompt render hash | **not recorded** in seal | **not recorded** | unknown |
| GPU driver version | **not recorded** in seal | **not recorded** | unknown |
| interleave / session | single arm, sequential 200 | block_interleave_single_pipe block=5, 3 arms | **NO** |
| launch context | W-3 dedicated session 2026-08-30 | Q-KV 2026-09-15; Available≈5.9 GB at start | **NO** |
| emission failures | 45/200 (`empty_turn_model_response`) | f16/u8/u4 = 62/65/71 | — |
| trajectory_pass | 20/200 | f16/u8/u4 = 10/13/11 | — |

## Material differences that can affect quality

1. **KV precision** (W-3 dynamic vs Q-KV pinned) — under test in Q-REPRO arm A vs B.
2. **Session / machine state / interleave** — between-run confound Q-REPRO removes by putting dynamic and f16 in one interleaved session.
3. **Prompt render hash / driver** — absent from both seals; cannot be compared from artifacts alone. Q-REPRO will record OpenVINO stack + per-cell KV readback for arm A.

## Same (not an explanation for 45 vs 62)

IR, revision, entries, scorer, greedy decode settings, step limit, prompt format path, tokenizer pin, residency, weight.
