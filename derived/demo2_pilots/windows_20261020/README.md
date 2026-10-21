# Window records, 2026-10-20 (closed out in Task AZ)

Copies of the Mac-side window folders (~/seam_closeout_1013/...), top-level
files only. The run dirs themselves are filed under derived/ (see
analysis/demo2_pilots/AZ/WINDOWS_20261020.md). All $0, all at commit 3aa9e27.

| folder | host | ET | what ran |
|---|---|---|---|
| xps_w2_1733 | XPS | 17:33-18:47 | drivers (Intel Graphics 32.0.101.8860, NPU 32.0.100.4778), reboot, P3 cell 0 a5d19dcc, arm A LONGCTX 15-30 15367c3a (123 skipped as hang) |
| xps_w3_p10_1930 | XPS | 19:30-20:17 | reboot (about 15 min to come back), P10 C1 027a07b7 HUNG at 123 turn 0 (600 s); post-hang reboot; XPS not back on ssh within 15 min: STOP (cells C2-C6, C0 not run) |
| t2s_1731 | T2S | 17:31 | STOP: the Rithwik-process check matched its own ssh PowerShell (pid 1236). Fixed outside the repo before 17:33 by excluding `$PID` |
| t2s_1733 | T2S | 17:33-19:39 | P0a (PASS), P0b 03632ad3, arm A BASE_30 b90f1d5b, LONGCTX 0-13 1a634610 / 15-29 daa6c026, u4 6c610aa6 / 3aa565da / 108d5f43, P4 16996cdb / 4d8e2fb1 / cc32619a, P9/P2 SKIPPED (uptime gate), e123 i8 bbdd1c0d HUNG (600 s): STOP |
| t2s_1952 | T2S | 19:52-20:35 | STEP_FROM=e REBOOT_OK=1: reboot, P9 63b2567a (cold, uptime 202 s), then it went on into step f: arm A BASE_30 09932887 (unplanned replicate), LONGCTX 0-13 launch cut off by the reboot from t2s_2024 (no run_id) |
| t2s_2024 | T2S | 20:24-21:11 | run_t2s_p9p2.sh (REBOOT_OK=1): waited for the python of t2s_1952, recopied P9 63b2567a (identical), then cold reboot before each of P2 i8 29209e26, u4 0a55c316, f16 aa01040d; hand-back check 0 python |

Two Mac scripts ran against the T2S at once (t2s_1952 and t2s_2024, 20:24-20:35
ET). t2s_2024 rebooted the T2S at 20:34:08 while t2s_1952 was opening a LONGCTX
launch. 09932887 had exited at 20:33:38 and is seal MATCH; the cut-off launch
left no run dir.

scripts/: the four window scripts as run (`*.as_run`) and as fixed in Task AZ
(driver summary line), with SHA256SUMS. `run_window_t2s.sh.as_run` already has
the `$PID` exclusion (edited outside the repo before 17:33 ET); the pre-edit
text was not kept. `run_t2s_p9p2.sh` was written 2026-10-20 about 7:55 PM ET
outside the repo (P9 + P2 only, cold, REBOOT_OK=1).
