# Pending: T2S 2026-09-21 watchdog coverage

Not a void. Not resolved. No sealed result is excluded by this note.
Awaiting Rithwik written confirmation of no T2S jobs 2026-09-21 16:30-19:00Z.

Sessions:

- `98bf5873-9ba2-451d-9471-41799df08a83` (unsealed, aborted), window
  2026-09-21T16:41:36Z to 2026-09-21T16:46:27Z
- `051d2681-4bb8-4f50-b9fc-b14441359ba6` (sealed), window
  2026-09-21T17:02:35Z to 2026-09-21T17:23:41Z
- `5c714535-9f36-4614-a594-698b6cd09296` (sealed), window
  2026-09-21T18:32:17Z to 2026-09-21T18:51:50Z

foreign-activity check: unchecked (watchdog.log starts 2026-09-29T03:38:39Z)

The copy at `C:\Users\zjohn\Projects\watchdog-t2s.log` (114390 bytes, copied
2026-10-03 14:08 ET) has no lines in the two sealed windows. Missing coverage
is not a clean window.

## C:\apu file times, 2026-09-21T00:00Z to 2026-09-22T06:00Z

Source: `C:\Users\zjohn\Projects\t2s_apu_0921.txt` (17 paths). Every path is a
file directly in `C:\apu`. There is no job or output subdirectory, and nothing
under `C:\apu\ovn`. No creation time and no last-write time falls on
2026-09-21. These files cannot bound a job during any of the three windows.
The day is not continuously covered.

`check_health.ps1` was created 2026-09-17T00:38:01Z and last written
2026-09-22T05:27:28Z. That interval covers all three windows. It is one script
rewritten later, not a job log, so the interval is not a job span.

The other 16 files are a 2026-09-22 cluster (measure, restart, and server
logs). Earliest creation is `measure_64k_bos.py` at 2026-09-22T04:58:15Z.
Latest write is `srv_err3.log` at 2026-09-22T06:24:49Z. That span starts about
10 hours after `5c714535` ended and does not overlap any of the three windows.
Each file's own creation-to-write is seconds long, except `srv_err3.log`
(2026-09-22T05:19:02Z to 2026-09-22T06:24:49Z), which also does not overlap.

## What the run records themselves show

Neither sealed summary has a queue process snapshot or a `foreign_queue`
field. The kill log in each tree is the SEAM `WorkloadsSessionHost` poll. It
does not list Rithwik's jobs.

- `5c714535`: `Qwen3-4B-int4-ov`, arm `gpu_only_f16`, `status` `complete`,
  recorded limit 18687. Five canaries, all `classification` `OK`,
  `drift_tripped` false. Canaries 0-2 are unscored (`gate_armed` false,
  drifts null). Canary 3 (2026-09-21T18:47:04Z): turn-1 relative drift
  0.00000511, turn-2 0.025952, thresholds 0.05 and 0.05. Canary 4
  (2026-09-21T18:51:50Z): turn-1 0.009336, turn-2 0.030008, same thresholds.
  Start kill `pids_found` empty, then 19 polls, each `n_found` 0 and
  `n_killed` 0.
- `051d2681`: `Qwen3-8B-int4-ov`, arm `gpu_only_f16`, `status` `complete`,
  recorded limit 16437. Five canaries, all `OK`, none tripped. Canaries 0-2
  unscored. Canary 3 (2026-09-21T17:18:39Z): turn-1 0.035239, turn-2 0.011134,
  thresholds 0.05 and 0.063076. Canary 4 (2026-09-21T17:23:41Z): turn-1
  0.021589, turn-2 0.020148, same thresholds. Start kill `pids_found` empty,
  then 21 polls, each `n_found` 0 and `n_killed` 0.

## Gate probes just before each session

Copied from the T2S untracked derived/_gate_probes/ files to
C:\Users\zjohn\Projects\. Filenames are US Pacific. None of the three files
contains a process list. There is no python snapshot, no queue job name, and
no other GPU user. Each file is platform_id evo-t2, all_passed true,
refusal_reasons empty. The gates are ac (mains-only, no battery), processor
AC 100/100 on the High performance scheme, available memory, uptime, and
onset (onset_s null, onset_status unknown).

- gates_20260921_094024.json is 2026-09-21T16:40:24Z, about one minute
  before 98bf5873. Available 60768 MB against floor 24000. Uptime 89.7 s
  against max 7200.
- gates_20260921_100128.json is 2026-09-21T17:01:28Z, about one minute
  before 051d2681. Available 60460 MB. Uptime 1353 s.
- gates_20260921_113129.json is 2026-09-21T18:31:29Z, about one minute
  before 5c714535. Available 60362 MB. Uptime 6754 s, still under 7200.

Available memory at the three gates is 60768, 60460, and 60362 MB. A large
co-resident model job would show far less. Rithwik's Vulkan budget wall is
47866 MiB. Uptime at the first gate is 89.7 s at 2026-09-21T16:40:24Z, so the
T2S rebooted about 16:39Z. Any foreign job had to start after that reboot.
