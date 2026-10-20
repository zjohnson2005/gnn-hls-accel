# 841b84e4: P6 arm A local_only on DEMO1_LONGCTX_30, UNSEALED partial (hang)

run_id 841b84e4-0eb8-436d-89f6-c5b558848991. XPS (aipc-c1), clean tree at
eddc760e, launched 2026-10-19 5:18 PM ET (uptime 3,206 s), worker start
5:19 PM ET. Command (evidence/p6_longctx30_launch.txt): `--interleaved
--interleaved-policy local_only --policy-cap local_only=0 --placement gpu_only
--residency RESIDENT --kv default --require-true-default --mem-telemetry
--gpu-mem-counters --debug-raw-text`, entries DEMO1_LONGCTX_30 (sha256
7a71fa6a...). No -CacheDir. $0 (local only).

This directory is NOT sealed (no .sealed; the worker never finished). It is a
byte copy of what the run wrote, committed as a record. It is not a
measurement of 30 entries and is not cited as one.

## What completed
- 14 of 30 entries, the first 14 in pin order: 59, 100, 101, 104, 106, 107,
  112, 114, 115, 116, 117, 118, 120, 121 (multi_turn_long_context_<n>).
- 57 local turns in local_turn_telemetry.jsonl. Every load read back PA and
  compiled KV i8 (15 loads by entry 121); true-default verdict valid.
- Local pass 1/14 (policies/local_only/summary.json).
- Largest step-0 prompt 43,961 tokens (entry 117, turn 5); lowest available
  memory seen during a turn 767.6 MB (entry 101, turn 0). Both entries completed.

## Where it stopped
- Last telemetry row: entry 121 turn 3 (prompt 9,094 tokens), written
  2026-10-19 6:14:03 PM ET (= policies/local_only/summary.json finished_utc
  22:14:03Z).
- Last write to the worker log: 6:14:08 PM ET. The tail
  (evidence/longctx_stall.txt) is the compiled-property dump of a pipeline
  load (KV_CACHE_PRECISION i8, CACHE_DIR empty, ending "[XAttention]:
  DISABLED on GPU device."). seam/genai_runtime.capture_native_output echoes
  that dump to the log only after the load returns, so the load for the next
  entry had finished.
- Next entry in pin order: multi_turn_long_context_123. No turn of 123 was
  written. The stall is therefore between the end of that load and the end of
  turn 0 of entry 123.

## The stop
- 9:20 PM ET: the window script stopped waiting (python still running after
  4 h; evidence/steps.txt).
- 9:31 PM ET: Zach stopped the worker (Stop-Process); afterwards no python
  process was left (evidence/longctx_kill.txt).

## Evidence copied in (evidence/, as captured, CRLF kept)
- longctx_status.txt (about 9:13 PM ET): worker PID 17776, CPU 9,162.0 s.
- longctx_stall.txt (about 9:29 PM ET): telemetry line count 57 and last row,
  available memory 3,019 MB, worker CPU 9,886.9 s, working set 7,391 MB,
  commit 10,992 MB, log last write 18:14:08, log tail.
- longctx_kill.txt (9:31 PM ET): GPU 3D utilization 0 (6 x 5 s samples),
  22 pages/s, pagefile 18%, worker CPU 9,985.6 s, WS 7,392 MB; python_left=0.
- p6_longctx30_launch.txt, steps.txt, run_ids.txt (window record).
- Not on the Mac (open): the full worker log and the launch evidence dir
  derived/h1_hybrid/_launches/841b84e4-.../ (plan.json lists its 3 files and
  their sha256).

The analysis is in analysis/demo2_pilots/AW_20261019/LONGCTX_HANG_841b84e4.md.
