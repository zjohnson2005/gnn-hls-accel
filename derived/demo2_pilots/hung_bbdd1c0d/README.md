# bbdd1c0d: arm A entry 123 alone on the T2S, UNSEALED (watchdog hang)

run_id bbdd1c0d-5c10-4dad-89c3-222576314a68. EVO-T2S (evo-t2), Arc B390, GPU
driver 32.0.101.8509, NPU 32.0.100.4512 (evidence/a_drivers.txt, read 5:33 PM
ET the same window). Clean tree at 3aa9e27. Launched 2026-10-20 7:27:55 PM ET
at uptime 557,920 s (UNCOLD_UPTIME deviation; launch_h1 -T2S), step h of
~/seam_closeout_1013/xps/run_window_t2s.sh. $0, local_only, arm A
(-RequireTrueDefault: compiled KV i8, backend PA, no rt_info override),
entry DEMO1_LONGCTX_30 index 14 = multi_turn_long_context_123, -TurnWatchdogS
600, no py-spy (not approved on the T2S).
- Turn 0 armed 23:28:45Z; the watchdog fired 23:38:46Z after 600.515 s,
  outcome hang, exit 86. Python stacks: main thread in
  bfcl_feasibility_probe._timed_generate (the native generate), as on the XPS.
  No native stack (no py-spy).
- The same stall on a second device, GPU and driver: 4 of 4 attempts at entry
  123 turn 0 have stalled (XPS 841b84e4, 24c1abc0, 027a07b7; T2S bbdd1c0d).
- The block stopped here (REBOOT_OK unset), so e123 u4 was not run. The T2S
  was rebooted cleanly at 7:52 PM ET by the next script (t2s_1952) and came
  back in about 90 s.

Not sealed (hang path). evidence/: launch evidence (3/3 match plan.json),
launch/logtail/worker log, park record, steps, run_ids, watchdog check,
drivers, uptime.
