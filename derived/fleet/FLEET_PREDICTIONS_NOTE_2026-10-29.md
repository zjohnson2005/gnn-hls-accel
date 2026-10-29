# FLEET_PREDICTIONS.json: stale prefill constant (note, no rescoring)

Filed 2026-10-29 17:06 EDT (Task BT, COST-1 registration step 5). Wording-fix class; logged in
docs/PLAN_LOCK_2026-10-23.md (red-flag/log section).

- derived/fleet/FLEET_PREDICTIONS.json uses a = 96,768 B/token ("a_B_per_token"). The current BR constant
  (docs/registrations/BR_HYB1_2026-10-26.md) is a = 87,520 B/token.
- The JSON's bytes are left unchanged: sha256
  b1563eb81c7de9b711376a94368ee5230dca80f4a0eb482240bcc4ed3c7033e9 (pinned in AUDIT_LOG.md line 3639).
- The registered FLEET predictions stand as filed and are scored as filed. Nothing is recomputed or rescored
  by this note.
- Per BR_HYB1's inheritance rule, current values enter only through the params file hashed at the Nov 22 data
  freeze; that file must use a = 87,520.
- Flag, not changed: the JSON's budget_xps_GiB 3.412 vs B_BR 3.267 GB (3,267,086,560 B). Open question for
  Zach.
