# Artifact audit (Phase 2)

Written to accompany cost-side waterfall results. Outcome labels are
inherited from public / upstream evaluators; this audit reports how
sensitive the waterfall is to LLM-judge rows and to truncation.

## Corpus composition

| scaffold | n | swebench_exact | llm_judge | synthetic | trunc_rate | parse_fail_rate | censored_rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| mini_swe_agent | 15 | 15 | 0 | 0 | 0.067 | 0.133 | 0.067 |

## Waterfall with LLM-judge trajectories excluded

| scaffold | n_full | n_excl | unreachable_full | unreachable_excl | realizable_share_full | realizable_share_excl |
|---|---:|---:|---:|---:|---:|---:|
| mini_swe_agent | 15 | 15 | 0.6893 | 0.6893 | 0.3107 | 0.3107 |

Published work: judge scoring diverges from exact-match by 10–24pp on knowledge tasks; truncation affected up to 65% of responses in some settings — both can inflate apparent headroom.

## Flags

- F4 UNMEASURED
- invariance bias UNMEASURED
