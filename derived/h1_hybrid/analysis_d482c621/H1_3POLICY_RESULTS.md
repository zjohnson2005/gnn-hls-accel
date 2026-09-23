# H1 3-policy results (d482c621-4292-4281-b6a1-8635e5eeb6da)

Every number below is from run_id `d482c621-4292-4281-b6a1-8635e5eeb6da`.

## Assertion

200 rows per policy: yes. Pass counts equal policy summaries: True. Pass counts equal summary/3: **FAIL**.

| policy | rows | hybrid_pass | local_pass | summary hybrid | summary local |
|---|---:|---:|---:|---:|---:|
| slo_escalate | 200 | 21 | 21 | 21 | 21 |
| emission_escalate | 200 | 46 | 17 | 46 | 17 |
| full_signal_bounceback | 200 | 30 | 15 | 30 | 15 |

## McNemar on hybrid_pass

b = left pass and right fail. c = left fail and right pass. p is the two-sided exact binomial test on the discordant pairs.

| left | right | b | c | p |
|---|---|---:|---:|---:|
| emission_escalate | slo_escalate | 29 | 4 | 1.09286e-05 |
| full_signal_bounceback | slo_escalate | 14 | 5 | 0.0635681 |
| emission_escalate | full_signal_bounceback | 21 | 5 | 0.00249392 |

## Cost frontier, 4B

| policy | pass rate | USD total | USD/entry | recovered vs slo | USD/recovered | escalated-turn fraction | cloud tokens / escalated turn |
|---|---:|---:|---:|---:|---:|---:|---:|
| slo_escalate | 21/200 = 0.105 | 0 | 0 | 0 |  | 0/732 = 0 |  |
| emission_escalate | 46/200 = 0.23 | 16.1195 | 0.0805976 | 29 | 0.555845 | 183/733 = 0.249659 | 27888.6 |
| full_signal_bounceback | 30/200 = 0.15 | 8.16705 | 0.0408353 | 14 | 0.583361 | 92/734 = 0.125341 | 28011.4 |

## SLO trigger audit

**SLO_INERT_ON_CONFIG**

Config: model `Qwen3-4B-int4-ov`, precision `int4`, placement `gpu_only`, residency `RESIDENT`, KV `u8`, platform `absent_from_seal`.

Turns 732. TTFT max 4.6939 s, median 0.299632 s, p99 4.41456 s. Min decode 18.402 tok/s. Turns violating ttft>10.0 or decode<6.0: 0. Escalations: 0.

## TTFT vs prompt tokens (local turns)

| policy | n | slope (s/token) | intercept (s) | r2 | mean TTFT (s) | mean prompt tokens |
|---|---:|---:|---:|---:|---:|---:|
| slo_escalate | 732 | 0.000126845 | 0.26184 | 0.0113593 | 0.753673 | 3877.44 |
| emission_escalate | 550 | 7.62143e-05 | -0.0980835 | 0.265352 | 0.200901 | 3922.95 |
| full_signal_bounceback | 642 | 5.53238e-05 | -0.0584157 | 0.22017 | 0.156827 | 3890.6 |

Policy effect after prompt length, slo as reference: **UNEXPLAINED**.

| term | estimate | 95% CI | excludes 0 |
|---|---:|---|---|
| prompt_tokens_centered | 8.86645e-05 | [5.56126e-05, 0.000121716] | True |
| emission_escalate | -0.556807 | [-0.628275, -0.485339] | True |
| full_signal_bounceback | -0.598013 | [-0.666481, -0.529545] | True |

Scatter points are in `H1_3POLICY_RESULTS.json` under `ttft_vs_prompt_tokens.scatter`.

## Census-D instance_state_mismatch

| policy | n | rate |
|---|---:|---:|
| slo_escalate | 98/200 | 0.49 |
| emission_escalate | 113/200 | 0.565 |
| full_signal_bounceback | 128/200 | 0.64 |

Entries with instance_state_mismatch under all three policies: 91.

## Predicted vs measured

`derived/h1_hybrid/H1_PREDICTIONS.md` is not in the tree. Re-anchored lines are `H1_3POLICY_PREDICTIONS.json`. Superseded H-1 lines are `derived/d1_replay/H1_PREDICTIONS.md`. R2B-8B is a different model and is not scored.

| source | arm | field | predicted | measured | verdict |
|---|---|---|---:|---:|---|
| derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json | R2a | completion | 0.06 | 0.105 | MISS |
| derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json | R2a | cloud_usd_total | 0 | 0 | HIT |
| derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json | R2a | emission | 0.685 | 0.685 | HIT |
| derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json | R2a | slo_fraction_local_turns | 1 | 1 | HIT |
| derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json | R2b | n_escalated | 63 | 59 | MISS |
| derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json | R2b | cloud_usd_total | 16.9304 | 16.1195 | MISS |
| derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json | R2b | completion_floor | 0.06 | 0.085 | MISS |
| derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json | R2b | completion_indep | 0.26475 | 0.23 | MISS |
| derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json | R2c | n_bounces | 66 | 92 | MISS |
| derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json | R2c | cloud_usd_total | 6.009 | 8.16705 | MISS |
| derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json | R2c | completion | 0.06 | 0.075 | MISS |
| derived/d1_replay/H1_PREDICTIONS.md | R2a | completion | 0.1 | 0.105 | MISS |
| derived/d1_replay/H1_PREDICTIONS.md | R2a | cloud_usd | 0 | 0 | HIT |
| derived/d1_replay/H1_PREDICTIONS.md | R2a | emission | 0.775 | 0.685 | MISS |
| derived/d1_replay/H1_PREDICTIONS.md | R2a | slo_frac_local | 1 | 1 | HIT |
| derived/d1_replay/H1_PREDICTIONS.md | R2b | cloud_usd | 13.0812 | 16.1195 | MISS |
| derived/d1_replay/H1_PREDICTIONS.md | R2b | n_escalated | 45 | 59 | MISS |
| derived/d1_replay/H1_PREDICTIONS.md | R2b | completion_floor | 0.1 | 0.085 | MISS |
| derived/d1_replay/H1_PREDICTIONS.md | R2b | completion_indep | 0.24625 | 0.23 | MISS |
| derived/h1_hybrid/R2B_8B_PREDICTIONS.json | R2b-8B | not_scored |  |  | NOT_THIS_EXPERIMENT |
