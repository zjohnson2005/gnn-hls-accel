# Fail-turn analysis (d482c621-4292-4281-b6a1-8635e5eeb6da)

Pre-registration `a7af15efb78d5403180700082e01e48fe65db926`. Checker 2025.12.17 matches the seal. Per-turn verdicts were not sealed; prefixes were rescored offline.

Disagreements versus sealed entry scores: 0.

## Q1 / Q2

| question | n | meeting | rate |
|---|---:|---:|---:|
| Q1 bounceback escalated MISMATCH, first fail local and after last bounce | 37 | 19 | 0.5135135135135135 |
| Q2 emission escalated MISMATCH, first fail cloud-served | 20 | 9 | 0.45 |

## Q3 entries escalated under both policies

n=57.

| emission \ bounceback | PASS | non-PASS |
|---|---:|---:|
| PASS | 9 | 20 |
| non-PASS | 2 | 26 |

## 2d. Bucket transitions (cell = escalated/not under the second policy)

### slo_escalate->emission_escalate

| row \ col | PASS | MISMATCH | EMPTY | EXEC_RESP |
|---|---:|---:|---:|---:|
| PASS | 0/17 | 1/3 | 0/0 | 0/0 |
| MISMATCH | 3/0 | 11/83 | 0/0 | 0/1 |
| EMPTY | 25/0 | 8/5 | 3/0 | 2/3 |
| EXEC_RESP | 1/0 | 0/2 | 0/0 | 5/27 |

### slo_escalate->full_signal_bounceback

| row \ col | PASS | MISMATCH | EMPTY | EXEC_RESP |
|---|---:|---:|---:|---:|
| PASS | 1/15 | 2/3 | 0/0 | 0/0 |
| MISMATCH | 3/0 | 11/83 | 0/0 | 1/0 |
| EMPTY | 10/0 | 22/4 | 1/0 | 7/2 |
| EXEC_RESP | 1/0 | 2/1 | 0/0 | 5/26 |

## 2e. Empty-turn first failures

| policy | entry_id | escalated | empty turn | first escalation | served_by | vs first escalation |
|---|---|---|---:|---:|---|---|
| slo_escalate | multi_turn_base_103 | False | 1 | None | local | no_mark |
| slo_escalate | multi_turn_base_105 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_107 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_108 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_11 | False | 1 | None | local | no_mark |
| slo_escalate | multi_turn_base_113 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_115 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_120 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_125 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_129 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_13 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_130 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_131 | False | 2 | None | local | no_mark |
| slo_escalate | multi_turn_base_132 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_137 | False | 3 | None | local | no_mark |
| slo_escalate | multi_turn_base_138 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_142 | False | 1 | None | local | no_mark |
| slo_escalate | multi_turn_base_143 | False | 1 | None | local | no_mark |
| slo_escalate | multi_turn_base_145 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_148 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_158 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_159 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_162 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_17 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_176 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_187 | False | 2 | None | local | no_mark |
| slo_escalate | multi_turn_base_188 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_194 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_20 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_39 | False | 1 | None | local | no_mark |
| slo_escalate | multi_turn_base_47 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_52 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_55 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_56 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_57 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_61 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_62 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_67 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_71 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_72 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_91 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_92 | False | 1 | None | local | no_mark |
| slo_escalate | multi_turn_base_94 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_97 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_98 | False | 0 | None | local | no_mark |
| slo_escalate | multi_turn_base_99 | False | 0 | None | local | no_mark |
| emission_escalate | multi_turn_base_142 | True | 1 | 1 | cloud | on |
| emission_escalate | multi_turn_base_159 | True | 1 | 0 | cloud | after |
| emission_escalate | multi_turn_base_188 | True | 2 | 0 | cloud | after |
| full_signal_bounceback | multi_turn_base_142 | True | 1 | 1 | cloud | on |

## 2f. Emission outcome by escalated-turn count

| n_escalated_turns | PASS | MISMATCH | EMPTY | EXEC_RESP |
|---:|---:|---:|---:|---:|
| 1 | 2 | 8 | 0 | 3 |
| 2 | 5 | 3 | 0 | 2 |
| 3 | 8 | 2 | 1 | 0 |
| 4 | 5 | 3 | 1 | 2 |
| 5 | 7 | 4 | 0 | 0 |
| 6 | 2 | 0 | 1 | 0 |

Not escalated (0): PASS 17, MISMATCH 93, EMPTY 0, EXEC_RESP 31.

## Verdicts

| prediction | predicted | measured | verdict |
|---|---|---|---|
| Q1 | >= 70% local and after last bounce | 19/37 = 0.5135135135135135 | MISS |
| Q2 | >= 70% cloud-served first failure | 9/20 = 0.45 | MISS |
| Q3 | (emission PASS, bounceback non-PASS) >= 3 x reverse | 20 : 2 | HIT |
| Q4 | exploratory, no prediction | 50 empty-turn first failures | EXPLORATORY |
| KILL | KILL H-GRAN if Q1 < 50% | Q1 rate 0.5135135135135135 | NOT_FIRED |

KILL H-GRAN: False.
