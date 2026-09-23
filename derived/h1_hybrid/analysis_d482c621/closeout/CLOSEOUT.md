# D482 closeout (d482c621-4292-4281-b6a1-8635e5eeb6da)

started_utc `2026-09-23T14:56:10.766980+00:00`. Artifact tree `cd0c5e84c23c27cba6c97a3292fb197c3ce7ba798dd49ad56cf63e23ed40b1e1`.

The seal does not record a runner git SHA, dirty flag, or dirty-file list.

YES_UNRECORDED_LIST: sealed entry_quality has hybrid_pass, which is absent from the git commit that was HEAD at started_utc. The seal does not list dirty files. The uncommitted scoring diff on tools/run_h1_hybrid.py is the implementation that produces hybrid_pass.

## Buckets

First-failure buckets are the fail-turn rescore. Full-trajectory buckets are sealed hybrid_pass and hybrid_score_error_type. Each column sums to 200.

| policy | PASS | MISMATCH | EMPTY | EXEC_RESP | columns equal |
|---|---:|---:|---:|---:|---|
| slo_escalate first | 21 | 98 | 46 | 35 | True |
| slo_escalate full | 21 | 98 | 46 | 35 | True |
| emission_escalate first | 46 | 113 | 3 | 38 | True |
| emission_escalate full | 46 | 113 | 3 | 38 | True |
| full_signal_bounceback first | 30 | 128 | 1 | 41 | True |
| full_signal_bounceback full | 30 | 128 | 1 | 41 | True |

## Recovery

| policy | gross | regressions | net | USD | USD per net |
|---|---:|---:|---:|---:|---:|
| slo_escalate | 0 | 0 | 0 | 0.000000 |  |
| emission_escalate | 29 | 4 | 25 | 16.119519 | 0.644781 |
| full_signal_bounceback | 14 | 5 | 9 | 8.167050 | 0.907450 |

## McNemar

| left | right | b | c | p | p Holm |
|---|---|---:|---:|---:|---:|
| emission_escalate | slo_escalate | 29 | 4 | 1.09286e-05 | 3.27858e-05 |
| full_signal_bounceback | slo_escalate | 14 | 5 | 0.0635681 | 0.0635681 |
| emission_escalate | full_signal_bounceback | 21 | 5 | 0.00249392 | 0.00498784 |

## Divergence

Non-escalated bucket differs from slo: emission 14, bounceback 10. Controls: 20.

Prompt sha256 recorded: False. Classification counts: {'NOT_IN_SEAL': 44}.

TTFT verdict: **UNEXPLAINED**.

## R0 expected cloud USD

expected_usd = sum_k N_slo(k) * mean_usd(k). k is the user-turn index. N_slo(k) is the number of slo turns at that index (slo ran every turn locally). mean_usd(k) is the mean sealed cloud_usd of cloud turns at index k. Price check uses 3.0 USD/MTok in and 15.0 USD/MTok out on the same mean token depths.

Covered slo turns 732, uncovered 0, expected USD 64.823141. Price-list check 64.823141.

usd versus cloud_tokens_in r2 0.9956, slope 3.120183e-06. usd versus turn index r2 0.0044.

| turn | n cloud | mean tokens in | mean tokens out | mean USD |
|---:|---:|---:|---:|---:|
| 0 | 70 | 31094.7 | 455.3 | 0.100113 |
| 1 | 70 | 24217.8 | 387.5 | 0.078466 |
| 2 | 57 | 26092.2 | 319.1 | 0.083062 |
| 3 | 44 | 30745.8 | 369.0 | 0.097772 |
| 4 | 27 | 24757.8 | 324.1 | 0.079135 |
| 5 | 5 | 31061.2 | 269.0 | 0.097219 |
| 6 | 2 | 20612.0 | 102.0 | 0.063366 |

Cache token fields and per-call records: MISSING. cache_control set by the harness: False.
