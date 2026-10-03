# T2S watchdog gate

The T2S (evo-t2) is shared with Rithwik's APU queue. His scheduled task
`APU-QueueWatchdog` writes `C:\apu\ovn\watchdog.log`. SEAM only reads the log
(`tools/t2s_queue_watchdog.py`). It never edits his task or files.

## Log format

One entry per line: `[<UTC ISO time>] {json}`. Older fixtures put the time in a
`utc` field and have no prefix; both formats parse.

Entries are classified by `action`:

| class | entries | launch gate | in a cell window |
|---|---|---|---|
| idle | `empty_flag`, `paused` | last non-digest entry must be idle | ignored |
| neutral | no `action`, has `digest` (results-digest job) | skipped | ignored |
| busy | any other entry (`none` with a running job, `launched`, `crashed_requeued`, ...) | refuses | marks the cell FOREIGN_ACTIVITY, excluded from sealed results |

The launch gate also refuses if any python or llama-server process is running.

## Rule change 2026-10-03: `paused` counts as idle

Before: only `empty_flag` was idle.

After: `empty_flag` or `paused`.

Reason: `paused` is set by the queue owner by hand and stops the queue from
launching anything. That is a stronger idle guarantee than `empty_flag`, which
only says the queue was empty at that tick and can still launch at the next one.
Run 52fab50c (T2S 4B-int4 GPU u8, 2026-09-29) was voided under `empty_flag`:
the queue launched `t2s_q0_token_calibration` 2 s after the cell started.

Digest lines, which the watchdog added later, carry no `action`. Before this
change they were treated as the last entry and refused every launch. They now
count as neither idle nor busy.

## Bug fixed in the same commit: bracketed timestamps

`parse_log_line` stored the `[...]` prefix with its brackets as `utc`.
`parse_utc` then raised, and `entry_utc` returned None, so `evidence_lines`
dropped every line in the live format. The foreign-activity check could not
flag anything on this format. Runs on the T2S whose evidence came from the
live log must be re-scanned with the fixed parser (results in
`docs/HANDOFF_2026-10-03.md`; any finding goes to `derived/VOIDS/`).
