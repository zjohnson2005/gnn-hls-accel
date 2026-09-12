# CHARACTERIZATION — completion table (v2, anchor gate)

Every cell carries `external_anchor`, `regime` ∈ {ANCHORED, EXTRAPOLATED},
and (when EXTRAPOLATED) `extrapolation_distance`. **No cell is a FINDING
until its required anchors PASS, or it is explicitly marked EXTRAPOLATED.**

**OA-01 caveat (wherever this corpus is cited):** OA-01 apparatus: 0 RESOLVED / 14 FAILED / 1 CENSORED; 2 of 15 runs produced empty diffs; one truncated at our own 50-turn analysis cap against the scaffold's 250 step limit; retries died on RepeatedFormatError. One-sided 95% upper bound on true resolve rate is 18.1%.

**D1 headline correction:** Free-observable headline 73.3% (T1+T2+T3) drops to 26.1% once T3 progress signals are stripped. T3 detects thrashing, not wrongness. Treat 26.1% as the defensible floor for the free-verification premise; never quote 73.3% without 26.1% adjacent.

## The table (13 cells)

| # | metric | value or bracket | confidence | method | threshold | status | external_anchor | regime | extrapolation_distance |
|---|---|---|---|---|---|---|---|---|---|
| 1a | context_floor | 115,440 tok | published | TraceLab median step prefix | n/a | DONE | NONE (workload measurement, not a model prediction) | ANCHORED |  |
| 1b | delta_tokens_per_turn | 1,089 – 1,838 tok | published/estimated | TraceLab Table 3 | never collapse | DONE | NONE (workload measurement) | ANCHORED |  |
| 1c | turns per task | median 15, max 51 (OA-01) | measured | OA-01 atlas | n/a | DONE | NONE | ANCHORED |  |
| 2a | per-turn cost (C_energy / C_price / C_marg) | see energy_three_way.csv — three comparisons, never conflated | estimated | censor/energy_model.py | A_ENERGY_RATIO must PASS before energy findings | DONE | A_ENERGY_LOCAL, A_ENERGY_CLOUD, A_ENERGY_RATIO, A_CACHE_TIERS | ANCHORED for Mac Studio identity; EXTRAPOLATED for agent 115K workload | Energy identity validated on output-dominated Mac Studio queries; agent workload is prefill-dominated at ~560:1 in:out |
| 2b | cache rent / amortization collapse | 14.09x batch collapse 8K→context_floor | estimated | B(L)=(M−W)/(kv_pt·L) | A_BATCH_* disagreement ≤2x | DONE | A_BATCH_A100 (RetroInfer); A_BATCH_HERALD | ANCHORED |  |
| 2c | T_local/T_cloud and e* | 38/45 dead under 3-model bracket; see itemB_rerun under fitted α | estimated | censor/latency_ratio.py + prefill_scaling.py | ratio≥1 ⇒ dead on latency | DONE | NONE for prefill@115K | EXTRAPOLATED | 225x context length beyond pp512 published benchmark; fitted α (if available) measured to ≤64K on 0.5B Lunar Lake, applied at 115K on 7-8B target hw |
| 3a | local_kv_persistence | persists (llama.cpp default) | measured | source read + probe | n/a | DONE | NONE (direct measurement) | ANCHORED |  |
| 3b | KV feasibility at context_floor | 8B feasible on all 3 hw; RTX 5090 only if quantized | estimated | censor/kv_math.py | same arithmetic as A_BATCH_A100 | DONE | A_BATCH_A100 | ANCHORED |  |
| 4a | free verification fraction | 73.3% (T1+T2+T3) / 26.1% (T1+T2 only) | measured | per-turn tier classification | kill if T1+T2+T3 <50% (does not fire); defensible floor is 26.1% | DONE | NONE | ANCHORED |  |
| 4b | reversibility distribution | READ_ONLY 72.3%, IRREVERSIBLE 9.4%, AMBIGUOUS 1.2% | measured | full-string effect analysis | ambiguity bucket small | DONE | NONE | ANCHORED |  |
| 4c | escalation rate | not started — by instruction | — | requires sandboxed local-proposed actions | separate phase | BLOCKING-OPEN | NONE | EXTRAPOLATED | not yet measured |
| 4d | silent divergence | no value obtainable | — | requires ≥1 RESOLVED baseline | — | UNREACHABLE-WITH-CURRENT-CORPUS | NONE | EXTRAPOLATED | corpus has 0 RESOLVED |
| 4e | prompt_head_stability | stable (mini-swe-agent) | measured | append-only prefix + templates + provider cache | head mutation ⇒ 146x cliff | DONE | NONE (direct measurement) | ANCHORED |  |

## Anchor gate summary

| anchor | pass | disagreement |
|---|---|---|
| A_BATCH_A100 | PASS | 1.075x |
| A_BATCH_HERALD_8K | PASS | 1.176x |
| A_BATCH_HERALD_32K | PASS | 1.142x |
| A_ENERGY_CLOUD | PASS | 1.000x |
| A_ENERGY_LOCAL | PASS | 1.008x |
| A_ENERGY_RATIO | PASS | 1.006x |
| A_CACHE_TIERS | PASS | 1.000x |

Blocked regimes: none.

## Cache overstatement RANGE (G1)

Across provider tiers at 97.5% hit rate: **1.95x – 8.16x**. Never a single number. 0.1x read ⇒ ~8x; 0.5x read (gpt-4o) ⇒ ~2x.

Gemini storage rent (G3): $0.1169/hour at tool-result hit rate on the median turn (estimated). This is residency rent, explicitly metered by the hour — direct support for the cache-rent framing of Phase 1.

## Prefill exponent (H)

Fitted α = **0.344** (leave-one-out band [0.270, 0.454]), R²=0.888, n=5 depths.
Discrimination: Primary verdict=linear_attention_theoretic; ratio-error winner=linear_attention_theoretic; alpha=0.344 votes inconclusive. Excluded (log-error >2x best): ['optimistic_flat', 'quadratic_pessimistic'].
Item B re-run: 1/15 combinations survive (ratio < 1).

**Regime: EXTRAPOLATED.** Absolute rate does not transfer. Only the
exponent is claimed. Distance: measured to ≤64K on Lunar Lake + 0.5B;
applied at 115K on 7–8B target hardware.
