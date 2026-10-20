# 24c1abc0: arm A local_only on DEMO1_LONGCTX_30 entries 15-30, UNSEALED (watchdog hang)

run_id 24c1abc0-0613-4890-87b6-3da05350beda. XPS (aipc-c1), clean tree at
be82cb1. Launched 2026-10-20 3:26 PM ET (uptime 3,932 s); the worker started
3:27:21 PM ET.
- Command (evidence/p6_longctx_rest16_launch.txt): `--interleaved
  --interleaved-policy local_only --policy-cap local_only=0 --placement
  gpu_only --residency RESIDENT --kv default --entry-offset 14 --entry-count
  16 --require-true-default --mem-telemetry --gpu-mem-counters
  --debug-raw-text --turn-watchdog-s 1800 --hang-dump-py-spy
  C:\Users\zjohn\seam_tools\py-spy.exe`.
- Entries: DEMO1_LONGCTX_30 (sha256 7a71fa6a...), chunk 123 ... 148. No
  -CacheDir. $0.

The run is NOT sealed: the runner writes no .sealed on the hang path. This
directory is a byte copy of what the run wrote, parked on the XPS and copied
to the Mac. It is committed as the record of the hang.

## What happened
- Turn 0 of the first entry, multi_turn_long_context_123, was armed at
  19:27:26Z (3:27:26 PM ET).
- The watchdog fired at 19:57:27Z, after 1,800.453 s against a 1,800 s limit.
  It recorded outcome hang, ran py-spy (returncode 0), wrote checkpoints and
  ended the worker with exit code 86.
- Completed entries: 0 of 16. No local turn telemetry row was written.
- The log tail (evidence/p6_longctx_rest16_logtail.txt) shows the startup
  load dump, `CELL_START ... entry=multi_turn_long_context_123`, the
  per-entry load dump, then TURN_WATCHDOG_HANG. Its 99-line load dump is
  byte-identical to the entry-123 dump in 841b84e4.

## Files
- interleaved_24c1abc0-.../: plan.json, summary.json and checkpoint.json
  (status aborted_hang), plus hang_events.json.
  - hang_stacks_multi_turn_long_context_123_t0.txt: Python faulthandler
    stacks.
  - hang_dump_multi_turn_long_context_123_t0.txt: py-spy dump --native.
  - policies/local_only/ holds the checkpoint, the summary, entry_quality
    (123, outcome hang) and an empty turn ledger.
- evidence/launch_24c1abc0-.../: the launch evidence dir. All 3 files match
  plan.json git.launch_evidence by bytes and sha256.
- evidence/: the window-1 record:
  - steps.txt, run_ids.txt, pyspy.txt (py-spy 0.4.2, exe sha256
    6E83AB09..., pip freeze unchanged), park_*.txt;
  - the launch output and log tails of all three window-1 launches
    (1f3a261a and 162a9b5c are sealed under derived/h1_hybrid/).

The full worker log was not copied to the Mac (only the 120-line tail). It
is on the XPS at derived\h1_hybrid\_launches\h1_interleaved_20261020_152709.log (gitignored, not parked);
the window-2 script copies it to the Mac before the reboot.

Analysis: analysis/demo2_pilots/AY/GPU_HANG_ENTRY123.md.
The hang record used by `--skip-hang-record`:
interleaved_24c1abc0-0613-4890-87b6-3da05350beda/hang_events.json.
