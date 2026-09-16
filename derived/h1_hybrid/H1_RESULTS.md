# H-1 results (R2a / R2b)

Sealed arms (read-only):

| arm | run_id | policy | tree |
|---|---|---|---|
| R2a | `86d0f4cf-e8c2-4ce5-96da-04c6a9c129f3` | `slo_escalate` | `derived/h1_hybrid/slo_escalate_86d0f4cf-…` |
| R2b | `8ffd8371-ac15-492b-afb7-a45e4fae2c1b` | `emission_escalate` | `derived/h1_hybrid/emission_escalate_8ffd8371-…` |

Scorer assert (same path/version as W-3 `6225d6e1`): plan.json
`checker=bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker`,
`wrapper=apu_characterization.cap01.bfcl_cap01_multi_turn_checker`,
`bfcl_eval_version=2025.12.17`. Wrapper SHA-256
`b3b307ca71c19ef969977f478bb169edb701f202a1b4c94ff13cef31858062bc`
(see `derived/h1_hybrid/h1_analyze.json`).

**BFCL trajectory_pass was not persisted** in sealed H1 trees (no
`model_result_decoded` / `score` on the ledger). Completion in the
prediction sense cannot be recomputed from `turn_ledger.json`. Emission /
SLO / $ / walls are ledger-measured.

Machine-readable twin: `derived/h1_hybrid/h1_analyze.json`
(generator: `tools/h1_analyze_sealed.py`).

## Predicted vs measured

| arm | field | predicted | interval | measured | error | inside? |
|---|---|---:|---|---:|---:|---|
| R2a | cloud $ | 0.0000 | [0, 0] | 0.0000 | 0 | yes |
| R2a | completion (BFCL) | 0.1000 | — | **UNAVAILABLE** | — | — |
| R2a | operational completion | — | — | 0.985 | — | — |
| R2a | emission (entry all-emit) | 0.7750 | — | 0.6750 | −0.100 | — |
| R2a | SLO frac (over turns) | 1.0000 | — | 1.0000 | 0 | — |
| R2a | SLO frac (mean over entries) | 1.0000 | — | 1.0000 | 0 | — |
| R2a | session time sum (s) | 2641.5 | — | 4137.0 | +1495.6 | — |
| R2b | cloud $ | 13.0812 | [11.8752, 14.2871] | **17.4679** | **+4.3867** | **no — FALSIFIED** |
| R2b | completion floor / indep (BFCL) | 0.1000 / 0.2463 | — | **UNAVAILABLE** | — | — |
| R2b | operational completion | — | — | 0.985 | — | — |
| R2b | emission (entry all-emit) | floor 0.775 / indep 0.921 | — | 0.6750 | — | — |
| R2b | SLO frac (over turns) | 1.0000 | — | 0.8210 | −0.179 | — |
| R2b | session time sum (s) | 1983.7 | — | 4178.2 | +2194.4 | — |
| R2b | n_escalated | 45 | — | 65 | +20 | — |

R2b cloud-$ prediction is **falsified**: measured $17.47 is outside
$[11.88, 14.29]$.

### Stop reasons / escalations

| | R2a | R2b |
|---|---:|---:|
| stop `completed` | 197 | 197 |
| stop `max_steps` | 3 | 3 |
| n_escalated entries | 0 | 65 |
| escalate turn hist | — | t0:37, t1:14, t2:6, t3:7, t4:1 |

## Phase timers (R2a, 732 turns)

| | t_other (s) | t_tool_exec (s) |
|---|---:|---:|
| mean | 0.0180 | 0.000288 |
| median | 0.000951 | 0.000247 |
| p95 | 0.0796 | 0.000597 |
| max | 0.0973 | 0.00486 |
| entry0 turn0 | 0.0943 | — |

**Finding:** the X-2 ~4.8 s/turn uncovered remainder is **gone**. R2a
`t_other` is tens of milliseconds (entry0 turn0 = 0.094 s). Phase timers now
close the wall budget as
`t_template_build + t_tokenize + t_generate + t_tool_exec + t_other`;
X-2 lacked those additive phases, so wall−(prefill+decode) looked like ~4.8 s
of mystery.

## Observability census (R2a)

Host-observable classes at zero cost from the sealed ledger. Priority:
max_steps → no-emit → else host-clear.

| class | n | frac/200 | first observable turn |
|---|---:|---:|---|
| **A** no parseable tool call | 65 | 0.325 | t0:37, t1:14, t2:6, t3:7, t4:1 |
| **B** looped to max_steps | 3 | 0.015 | t1:1, t3:2 (`_2`, `_15`, `_34`) |
| **C** tool call raised | 0 | 0 | no `tool_error` field on sealed turns |
| host-clear (emit OK, not max_steps) | 132 | 0.660 | — |
| **D** SILENT (tools clean, task fail) | **UNAVAILABLE** | — | needs BFCL score |

Class D is the only failure a router cannot see. Its share cannot be measured
from this sealed tree; future seals must persist `score` /
`model_result_decoded`.

## Cloud rescue rate (R2b)

| | |
|---|---|
| n_escalated | 65 |
| n_rescued (operational: finished all turns) | 65 |
| **rescue rate (operational)** | **1.000** |
| cloud baseline completion (n=20 report) | 0.65 |
| BFCL quality rescue | UNAVAILABLE |

Operational rescue ≫ 0.65 means the cloud **finished remaining turns** after
every local emission failure. That is **not** a BFCL trajectory statement;
quality independence vs correlation remains open until scores are sealed.

## Cost-model diagnosis (R2b)

| | |
|---|---|
| measured $ | 17.4679 |
| predicted $ | 13.0812 [11.8752, 14.2871] |
| n_escalated pred → meas | 45 → 65 |
| mean ctx at escalate | 3616 |
| mean n_cloud_turns after escalate | 3.108 |
| mean $ / escalated entry | 0.2687 |

Fits (n=65 escalated entries):

| model | a | b | R² |
|---|---:|---:|---:|
| $ ~ a + b·context_at_escalation | 0.248 | 5.67e-6 | **0.001** |
| $ ~ a + b·n_cloud_turns | 0.00674 | 0.0843 | **0.642** |

**Context-at-escalation does not explain the miss** (R²≈0). The miss is
escalation count (65 vs 45) plus dollars tracking **remaining cloud turns**
(R²≈0.64), matching the original turns-remaining structure but with a higher
escalate rate (ledger emission failures = 65, not the W-3 empty_turn count of
45).

### Corrected model (spec only — do not change `fdr_replay` yet)

```
n_escalated = count(entries with a turn where emitted_parseable_tool_call=false)
              # measured 65 on R2a/R2b local int4; W-3 empty_turn=45 undercounts
              # turn-level emission failures that still produce a non-empty decode

usd_entry ≈ 0.00674 + 0.0843 × n_cloud_turns_remaining_at_escalate
usd_total = sum usd_entry over escalated entries

# Do NOT use context_at_escalation as the primary regressor (R²≈0 on R2b).
# Re-fit a,b on the sealed R2b escalations before the next prediction seal.
```

## R2c

Policy `full_signal_bounceback` implemented in `tools/run_h1_hybrid.py`.
Fixture test: `tests/test_h1_hybrid.py::test_r2c_full_signal_bounceback_each_trigger_once`.
Prediction filed in `derived/d1_replay/H1_PREDICTIONS.md` (section R2c) before
any live R2c run. Live OpenVINO seal of R2c is refused until turn-by-turn
generation with context injection exists (full-entry precompute cannot bounce).
