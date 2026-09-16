# CAP-4 BLOCKED — host gates failed (no measurement spawned)

**Status:** `BLOCKED_ON_OPERATOR`  
**Recorded UTC:** 2026-09-16T01:14:45+00:00  
**Evidence:** `derived/cap4/_launch_dryrun_gates.txt` (DryRun of `tools/launch_cap4.ps1`)

## What is ready (pre-data)

| artifact | path |
|---|---|
| Pre-registration (md) | `derived/cap4/CAP4_PREDICTIONS.md` |
| Pre-registration (json) | `derived/cap4/CAP4_PREDICTIONS.json` (`status=pre_registered_before_measurement`, `registered_utc=2026-09-16T01:12:00+00:00`) |
| Worker | `tools/run_cap4_prefill_curve.py` (interleaved; reuses `measured_repeat` / ceiling child path) |
| Launcher | `tools/launch_cap4.ps1` (same five gates as C-1/C-2) |
| Sealer | `tools/seal_cap4.py` (derived_diagnostic + INF-5 `run_environment`) |

INF-5 is **not** re-done (`ec77526` already on main). New seals will stage `RunEnvironmentSession` (`session_design=interleaved`, `arm_order` recorded).

## Gate failures (live spawn refused)

| gate | observed | required |
|---|---|---|
| uptime | **16.92 h** since boot | < 2 h (CHOSEN/PROVISIONAL, same as C-2) |
| AC | ok (BatteryStatus=2) | on AC |
| power plan | Best Performance | Best Performance |
| Available MBytes | **~6602 MB** | ≥ 7000 |
| tier-1 | **Cursor ×16 (~2866 MiB), chrome ×18 (~1323 MiB), msedge ×5 (~162 MiB)** | none of Cursor/chrome/msedge/claude/vmmem |

Also: WorkloadsSessionHost was resident (6 processes) at DryRun start. On the live
path the launcher refused even earlier:

```
REFUSED -- WorkloadsSessionHost still resident after Stop-Process
(pids 2232,4240,6308,6340,17548,18292)
```

Evidence: `derived/cap4/_launch_live_refuse.txt`. WSH is respawning under the OpenVINO
workload package / OS; cold-boot bare session + the worker's 60 s watchdog is the
supported clear path (same as C-1/C-2).

## Why we stop (not improvise)

CAP-4 **merges MEM-CEIL**. Allocation-ceiling and Available-MB bookends are confounded by ~4 GB of tier-1 private working set and sub-floor free memory. Running anyway would be a silent protocol violation (SEAM: stop and report rather than improvise).

## Operator unblock

1. Cold-boot Platform A.
2. Bare SSH session (no Cursor / Chrome / Edge / Claude).
3. Confirm: Available MBytes ≥ 7000, Best Performance, AC, uptime < 2 h.
4. Launch:
   ```powershell
   powershell -NoProfile -File tools/launch_cap4.ps1
   ```
5. After `summary.json` status=complete:
   ```text
   .\.venv-seam\Scripts\python.exe tools\seal_cap4.py --session-id <uuid>
   ```

Do **not** pass `-DryRun` for measurement. Do **not** bypass tier-1 / Available gates for this experiment.
