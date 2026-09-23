# Pre-registration: transition analysis d482c621

run_id: `d482c621-4292-4281-b6a1-8635e5eeb6da`

Filed before any transition count in this directory.

Hypothesis H-GRAN: a one-turn bounce unsticks the local model but control
returns and the local model finishes in the wrong state; session-level
escalation converts rescued entries into passes.
P1. slo->bounceback: OTHER->MISMATCH >= 2 x OTHER->PASS.
P2. slo->emission:   OTHER->PASS > OTHER->MISMATCH.
P3. >= 30% of bounceback-escalated entries have >= 2 bounces.
P4. Under each policy, >= half of regressions (slo PASS -> policy non-PASS)
    are on entries that policy did NOT escalate.
P5. < 25% of the 91 always-MISMATCH entries were escalated under emission.
KILL: if P1 fails, or if the OTHER-row flows are mostly on non-escalated
entries, H-GRAN is rejected as the explanation.
