# DISPATCH K — Session residency fix + A/B gate

**Date:** 2026-08-10  
**Prior:** `DISPATCH_J_SESSION_RESIDENCY_DIAGNOSIS.md`

## Chosen fix approach

**Pass raw turns via `ChatHistory`; let GenAI apply the template once.**

- `history.set_tools(tools)`
- `history.set_extra_context({"enable_thinking": False})`
- **RESIDENT:** keep one `ChatHistory` per entry; `pipe.generate(history, cfg)` with
  `apply_chat_template=True` (required for ChatHistory). KV retained via history-prefix
  continuation in StatefulLLMPipeline.
- **NON_RESIDENT:** rebuild the same ChatHistory each step, render to string with the GenAI
  tokenizer, `pipe.generate([rendered], cfg)` with `apply_chat_template=False` (never enters
  chat mode → full cold prefill).

**Why not “raw string into `start_chat`”:** stateful string chat always wraps the prompt as a
user message and calls `apply_chat_template` **without** tools / `enable_thinking` — that is
exactly DISPATCH J. **Why not bypass chat entirely with TokenizedInputs:** ChatHistory is the
supported tools + thinking path *and* the stateful continuation path; TokenizedInputs would
reimplement delta alignment by hand without fixing the tools/thinking contract.

## Equivalence assertion

Before the first generate of each entry, `assert_first_turn_token_equivalence`:

1. RESIDENT intended render (GenAI ChatHistory) token IDs
2. NON_RESIDENT intended render (same ChatHistory string) token IDs — must match (1)
3. HF `render_bfcl_tools_style` token IDs — must match (1)
4. Render must end with thinking-off tail `</think>\n\n`

Offline smoke: `--mode session_residency_render_smoke` (all 20 paired entries).  
Unit: `tests/test_session_residency_render.py`.

Thinking-off at generate time: `assert_no_think_in_generation` on every completed text
(not a config read).

Full texts sealed as `model_result_raw` (heads retained).

## Estimate (before launch)

See `TIME_ESTIMATE_SESSION_RESIDENCY.md`: **central ~120 min, upper ~165 min**
(arm A NON_RESIDENT n=20 × ~55 s turn-1 cold prefills).

## Launch status

**BLOCKED_ON_OPERATOR** — AC OK; Available≈6589 MB (<7000); Cursor×16 + chrome×19.
Harness fixed; smoke + estimate + `OPERATOR_CMD_SESSION_RESIDENCY.md` ready.
No A/B accuracy / TTFT / identity results invented.

## Open question (post-run)

With double-templating and thinking removed, do RESIDENT and NON_RESIDENT produce identical
output? Answer from `session_residency_compare_*.json` → `output_identity` + accuracy +
TTFT/SLO + `over_generation` after a clean detached launch.
