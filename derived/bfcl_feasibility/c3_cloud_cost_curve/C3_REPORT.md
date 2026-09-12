# C-3 cloud cost curve

Generated: 2026-09-08T21:54:41.574649+00:00

## Escalation rule

Escalate at the first turn where local TTFT > 10 s, decode < 6 tok/s, or context > 10,000 (C-2). Once escalated, stay on cloud.

## Growth (not a mean)
median first-step-per-turn growth is 155.5 tokens, not ~1300; 1300 overstated per-turn growth by treating the 2598->7743 session span as if it were a single turn delta.
Pooled first-step-per-turn delta tokens: n=198 min=62.0 median=155.5 p90=229.90000000000015 max=780.0

## Cloud-only sanity
usd/entry=0.2704 (target ~0.27); usd/completed amortized=0.4159 (target ~0.42); completed=13/20

## Per configuration (SLO-driven T)

| config | n_esc | T median | $/session | $/completed |
|---|---:|---:|---:|---:|
| cpu-p_NON_RESIDENT | 20/20 | 0.0 | 0.2704 | 0.4159 |
| cpu-p_RESIDENT | 19/20 | 0.0 | 0.2546 | 0.3917 |
| gpu_only_NON_RESIDENT | 0/20 | None | 0.0000 | 0.0000 |
| gpu_only_RESIDENT | 0/20 | None | 0.0000 | 0.0000 |

## Forced-T cost curve (quadratic test)

| T | mean $/session | mean remaining turns |
|---:|---:|---:|
| 0 | 0.2704 | 3.50 |
| 1 | 0.1834 | 2.50 |
| 2 | 0.1112 | 1.50 |
| 3 | 0.0528 | 0.65 |
| 4 | 0.0136 | 0.20 |

## Quadratic claim

closer to linear in remaining cloud turns (fitted exponent 1.027); quadratic claim not supported
exponent vs remaining turns=1.026974487407871; R2=0.9974560988888902; linear cost-vs-T slope=-0.06441607499999999

## Spread ($/completed task, amortized)

Cheapest gpu_only_NON_RESIDENT: $0.0000; most expensive cpu-p_NON_RESIDENT: $0.4159; spread $0.4159

## Limits

- one_cloud_model_one_price: True
- curve_is_sonnet_shaped: True
- local_energy_w_estimate: [30, 45]
- local_energy_measured: False
- escalation_rule_is_one_policy_among_many: True
- curve_conditional_on_escalation_rule: True

Plot: `derived/bfcl_feasibility/c3_cloud_cost_curve/cost_vs_T.png`
