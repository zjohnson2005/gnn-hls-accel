# 027a07b7: P10-HANG123 cell C1 (prefix caching off), UNSEALED (watchdog hang)

run_id 027a07b7-b880-4567-a2d3-aa26522bdbe7. XPS (aipc-c1), clean tree at
3aa9e27, GPU driver 32.0.101.8860 (evidence/drivers.txt, read 19:31 ET before
the window reboot). Launched 2026-10-20 7:48:59 PM ET at uptime 1,044 s
(~/seam_closeout_1013/xps/run_window_w3.sh, W3_FROM=0). $0, local_only, entry
multi_turn_long_context_123 only.
- Cell C1 of docs/amendments/DEMO2_PILOT_P10_HANG123_2026-10-20.md: explicit
  SchedulerConfig {enable_prefix_caching false, max_num_batched_tokens
  18446744073709551615} with --sched-exploratory, KV default, compiled readback
  (plan.json runtime options). The worker log's GenAI dump shows
  `enable_prefix_caching: false` and `max_num_batched_tokens:
  18446744073709551615` on both loads, backend PA, no rt_info override: the
  intended single-field change.
- Turn 0 armed 23:49:58Z; the watchdog fired 23:59:58Z after 600.359 s (limit
  600 s), outcome hang, exit 86. py-spy --native dump: main thread in
  LLMPipeline::generate -> ... -> clEnqueueNDRangeKernel (OpenCL.dll) ->
  igdrcl64.dll, the same stall as 24c1abc0.
- P10 verdict for C1 (rule as registered): prefix caching off does NOT avoid
  the hang.
- After the hang the script rebooted the XPS (8:00:31 PM ET). It was not back
  on ssh within 15 min, so the script stopped. Cells C2-C6 and C0 were not run.
  Zach resumed window 3 at 9:14 PM ET (W3_FROM=1, from C2); that window is
  not part of this record.

Not sealed: the runner writes no .sealed on the hang path. interleaved_*/ is
a byte copy of what the run wrote (parked, copied to the Mac). evidence/:
launch evidence (3/3 match plan.json), launch/logtail/worker log, park
records, the window's steps, run_ids, cells, drivers, pull and py-spy check.
