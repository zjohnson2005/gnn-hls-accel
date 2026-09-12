# Retired workers

`run_c2_ttft.py` -- retired 2026-09-08. C-2 folded into
`tools/run_c1_ceiling.py` via `--criterion ttft_slo`. Do not revive;
orchestration defects vs the proven C-1 watchdog path are recorded in the
dispatch that retired it (cwd=session_dir vs ROOT; soft refuse vs hard
SystemExit on watchdog death).
