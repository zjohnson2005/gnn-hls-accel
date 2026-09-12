# TIME ESTIMATE -- BFCL session-level residency A/B (DISPATCH K)

**Date:** 2026-08-10 · **Before launch** · **central_estimate_min: 120** · **upper_estimate_min: 165**

## Fix (harness)

ChatHistory path: raw messages + `set_tools` + `enable_thinking=False`. No pre-rendered
multi-role string into `start_chat` (DISPATCH J double-template / thinking-on root cause).
Arm A NON_RESIDENT restored to **n=20** (paired).

## Cells

| Cell | Arm | Mode | n | Basis | Estimate |
|---|---|---|---:|---|---|
| 1 | gpu_only | RESIDENT | 20 | F2-class multi-turn without over-gen; later-turn TTFT should drop | ~10-15 min |
| 2 | gpu_only | NON_RESIDENT | 20 | Full cold re-prefill each generate ~ F2 class | ~12-18 min |
| 3 | A | RESIDENT | 20 | Turn-1 cold ~55 s x 20 ~= 18 min; later turns delta-cheap | ~30-45 min |
| 4 | A | NON_RESIDENT | 20 | ~55 s x ~3.5 turns/entry x 20 ~= 64 min generates | ~65-85 min |

Plus model loads (4x), inter-cell settle, gold selftests, first-turn equivalence asserts: ~6-10 min.

## Totals

| Bound | Minutes | Hours |
|---|---:|---:|
| Central | **120** | 2.0 |
| Upper | **165** | 2.75 |

**Verdict vs dispatch gate:** arm A NON_RESIDENT n=20 is the expensive cell by construction
(~55 s turn-1 cold prefills). Central ~2 h; upper under 3 h. **OK to launch when clean.**

## Sources (not invented run numbers)

- DISPATCH J sealed turn-1 TTFT arm A NON_RESIDENT median **55.1 s** (range ~34-66 s)
- F2 sealed multi-turn wall: mean 26.21 s/entry (`DISPATCH_F2_PER_TURN_DIVERGENCE.md`)
- Context growth: first-turn prompts ~2.6k-4.4k tokens
