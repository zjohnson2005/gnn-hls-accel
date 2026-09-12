# Close-out: ceiling_a A/A_prime PARTIAL (force-killed, censored)

- **session_id:** `ad7b9288-42e6-42e8-be3e-ad1a1b1abc4c`
- **status:** PARTIAL, force-killed. Not COMPLETE. Orchestrator stopped after n=40000 ladder r0 timeouts for A and A_prime; round 1 was ordered then the process did not continue. Do not read highest_pass as a bracketed memory ceiling.
- **arm A run_id:** `b5ce21e5-9f29-46f4-8319-f74adcdeb628` (in_progress until promote)
- **arm A_prime run_id:** `64e525e7-37df-4a7a-91e5-21419acf5dd2` (in_progress until promote)
- **verdict run_id (reserved):** `404dc3d0-1760-41a8-b9c5-d0d439b1a1fe`
- **seal:** `derived/ceiling_a/sealed_ad7b9288-42e6-42e8-be3e-ad1a1b1abc4c`
- **launch log:** `derived/ceiling_a/_launches/ceiling_a_20260806_190044.log`

## Ceiling (CENSORED — lower bound)

| arm | highest_pass | lowest_nonpass | label |
|---|---:|---|---|
| A | 36000 | null | CENSORED_LOWER_BOUND |
| A_prime | 36000 | null | CENSORED_LOWER_BOUND |

36000 is a **LOWER BOUND**, not a measured ceiling. The memory wall was never reached;
the run died on `generation.timeout_s=1800` at n=40000 r0 (both arms).

## Standby (4× `delta_n.modern_standby_inadmissible`)

Recorded in `standby_events.json` and launch-log excerpt.

- `A.n16000.ladder.r1` a0 (KP 506) + a1 (KP 507) discarded; admitted a2 (`attempt_used=2`) — **feeds prefill fit**
- `A_prime.n16000.ladder.r2` a0 discarded
- `A_prime.n20000.ladder.r0` a0 discarded

## Beyond-native context

Rungs above 32768 flagged (`beyond_native_context.json`): **36000**, **40000**.
Model: `max_position_embeddings=40960`, `rope_scaling=null`.

## Environment gap

`environment_gap.json`: **no** `environment_start` / `environment_peak` (run predates
available_mb capture and cleanliness gate). Host state unknown at that granularity.

## Mac backup

**Not required** — on-disk XPS artifacts are complete for this PARTIAL seal.

## Promote

```
.\.venv-seam\Scripts\python.exe tools\seal_ceiling_a_partial_session.py \
    --session-id ad7b9288-42e6-42e8-be3e-ad1a1b1abc4c \
    --promote-only --attempt-raw-promote --allow-dirty
```

Do not bypass isolation. Do not `--resume` this session.
