# Transition analysis (d482c621-4292-4281-b6a1-8635e5eeb6da)

Pre-registration commit `2f1b8047652e4388878076ebc09a8551d837e888`. Every count is from run_id `d482c621-4292-4281-b6a1-8635e5eeb6da`.

PASS = hybrid_pass. MISMATCH = hybrid error type contains instance_state_mismatch and not PASS. OTHER = everything else.

PASS intersect instance_state_mismatch is empty (n=0).

## Class counts

| policy | PASS | MISMATCH | OTHER |
|---|---:|---:|---:|
| slo_escalate | 21 | 98 | 81 |
| emission_escalate | 46 | 113 | 41 |
| full_signal_bounceback | 30 | 128 | 42 |

## OTHER failure buckets

### slo_escalate

| failure_bucket | n |
|---|---:|
| multi_turn:empty_turn_model_response | 46 |
| multi_turn:execution_response_mismatch | 35 |

### emission_escalate

| failure_bucket | n |
|---|---:|
| multi_turn:execution_response_mismatch | 38 |
| multi_turn:empty_turn_model_response | 3 |

### full_signal_bounceback

| failure_bucket | n |
|---|---:|
| multi_turn:execution_response_mismatch | 41 |
| multi_turn:empty_turn_model_response | 1 |

## 3a. Transition matrices

### slo_escalate->emission_escalate

| row \ col | PASS | MISMATCH | OTHER |
|---|---:|---:|---:|
| PASS | 17 | 4 | 0 |
| MISMATCH | 3 | 94 | 1 |
| OTHER | 26 | 15 | 40 |

### slo_escalate->full_signal_bounceback

| row \ col | PASS | MISMATCH | OTHER |
|---|---:|---:|---:|
| PASS | 16 | 5 | 0 |
| MISMATCH | 3 | 94 | 1 |
| OTHER | 11 | 29 | 41 |

### emission_escalate->full_signal_bounceback

| row \ col | PASS | MISMATCH | OTHER |
|---|---:|---:|---:|
| PASS | 25 | 15 | 6 |
| MISMATCH | 3 | 110 | 0 |
| OTHER | 2 | 3 | 36 |

## 3b. Split by escalation under the second policy

### slo_escalate->emission_escalate escalated under second (n=59)

| row \ col | PASS | MISMATCH | OTHER |
|---|---:|---:|---:|
| PASS | 0 | 1 | 0 |
| MISMATCH | 3 | 11 | 0 |
| OTHER | 26 | 8 | 10 |

### slo_escalate->emission_escalate not escalated under second (n=141)

| row \ col | PASS | MISMATCH | OTHER |
|---|---:|---:|---:|
| PASS | 17 | 3 | 0 |
| MISMATCH | 0 | 83 | 1 |
| OTHER | 0 | 7 | 30 |

### slo_escalate->full_signal_bounceback escalated under second (n=66)

| row \ col | PASS | MISMATCH | OTHER |
|---|---:|---:|---:|
| PASS | 1 | 2 | 0 |
| MISMATCH | 3 | 11 | 1 |
| OTHER | 11 | 24 | 13 |

### slo_escalate->full_signal_bounceback not escalated under second (n=134)

| row \ col | PASS | MISMATCH | OTHER |
|---|---:|---:|---:|
| PASS | 15 | 3 | 0 |
| MISMATCH | 0 | 83 | 0 |
| OTHER | 0 | 5 | 28 |

### emission_escalate->full_signal_bounceback escalated under second (n=66)

| row \ col | PASS | MISMATCH | OTHER |
|---|---:|---:|---:|
| PASS | 10 | 15 | 6 |
| MISMATCH | 3 | 20 | 0 |
| OTHER | 2 | 2 | 8 |

### emission_escalate->full_signal_bounceback not escalated under second (n=134)

| row \ col | PASS | MISMATCH | OTHER |
|---|---:|---:|---:|
| PASS | 15 | 0 | 0 |
| MISMATCH | 0 | 90 | 0 |
| OTHER | 0 | 1 | 28 |

## 3c. Escalation

- slo_escalate: 0 escalated entries. Escalated turns per entry: {}. First escalation turn: {}.
- emission_escalate: 59 escalated entries. Escalated turns per entry: {'1': 13, '2': 10, '3': 11, '4': 11, '5': 11, '6': 3}. First escalation turn: {'0': 32, '1': 15, '2': 5, '3': 4, '4': 3}.
- full_signal_bounceback: 66 escalated entries. Escalated turns per entry: {'1': 44, '2': 18, '3': 4}. First escalation turn: {'0': 38, '1': 14, '2': 7, '3': 5, '4': 2}.

Bounceback bounces per entry: {'0': 134, '1': 44, '2': 18, '3': 4}.
Entries where bounce count differs from escalated-turn count: 0.

| bounces | PASS | MISMATCH | OTHER |
|---:|---:|---:|---:|
| 0 | 15 | 91 | 28 |
| 1 | 8 | 26 | 10 |
| 2 | 5 | 9 | 4 |
| 3 | 2 | 2 | 0 |

## 3d. Regressions (slo PASS to policy non-PASS)

### emission_escalate (n=4)

| entry_id | escalated | n_escalated_turns | outcome |
|---|---|---:|---|
| multi_turn_base_135 | True | 1 | MISMATCH |
| multi_turn_base_179 | False | 0 | MISMATCH |
| multi_turn_base_21 | False | 0 | MISMATCH |
| multi_turn_base_88 | False | 0 | MISMATCH |

### full_signal_bounceback (n=5)

| entry_id | escalated | n_escalated_turns | outcome |
|---|---|---:|---|
| multi_turn_base_135 | True | 1 | MISMATCH |
| multi_turn_base_179 | False | 0 | MISMATCH |
| multi_turn_base_21 | False | 0 | MISMATCH |
| multi_turn_base_60 | True | 1 | MISMATCH |
| multi_turn_base_88 | False | 0 | MISMATCH |

## 3e. Always-MISMATCH

n=91. Escalated under emission: 10. Escalated under bounceback: 9.

## 4. Escalated payload

Sealed artifacts have no cloud request or response bodies. The only key matching a request hint is plan.json openvino kv_cache_precision.requested (value u8), which is the KV setting, not an API payload. Token counts were not decomposed.

## 5. Verdicts

KILL fired: False. H-GRAN: NOT_REJECTED.

OTHER-row flows are the slo OTHER -> {PASS, MISMATCH} cells on slo->bounceback and slo->emission. Mostly non-escalated means not-escalated count under the destination policy exceeds escalated count in that pooled set.

| prediction | predicted | measured | verdict |
|---|---|---|---|
| P1 | slo->bounceback OTHER->MISMATCH >= 2 x OTHER->PASS | 29 vs 2 x 11 | HIT |
| P2 | slo->emission OTHER->PASS > OTHER->MISMATCH | OTHER->PASS 26, OTHER->MISMATCH 15 | HIT |
| P3 | >= 30% of bounceback-escalated entries have >= 2 bounces | 22/66 = 0.3333333333333333 | HIT |
| P4 | under emission and bounceback, >= half of slo PASS -> non-PASS regressions are on entries that policy did not escalate | emission 3/4; bounceback 3/5 | HIT |
| P5 | < 25% of the 91 always-MISMATCH entries escalated under emission | 10/91 | HIT |
