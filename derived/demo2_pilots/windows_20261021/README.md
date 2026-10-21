# T2S hang window 2026-10-21 12:09 PM ET (Task BA script; closed out in Task BB)

- t2s_1209_hang/: the window's own records (steps, cells, run_ids, drivers,
  uptime, Windows Update pause, pull/pin, py-spy fetch, park-tool hash,
  hand-back), byte copies.
- scripts/run_window_t2s_hang.sh.as_run_20261021_1209: the script as it ran
  (sha256 0142317b...). It was replaced in Task BB by the P11-B version.

Cells:
- p11_l1_repro 9b4cdefb: completed.
- p11_l2_runner 8af10211: per-turn watchdog at 600 s while progressing.

The script then stopped by design: step 5 had no variant set. The T2S was
rebooted (back in 72 s), and the hand-back check found PYTHON_COUNT=0 and a
clean tree.
