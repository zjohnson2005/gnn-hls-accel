# Contamination-free reconcile — n=12000 only

**Status:** `BLOCKED_ON_OPERATOR` while Cursor/Chrome are resident on the XPS.

## What changed

- Inter-cell settle = `isolation.pre_run_settle_s` (300), not `recovery.settle_s` (20).
- Gate: `max−min free_physical_mb_start` across arms at same n ≤
  `isolation.settle_adequacy_max_free_mb_spread` (512 MB), pre-registered from
  matrix_partial_39a8a0f5 (~1698 MB observed spread). FAIL aborts the run.
- Smoke JSON now promotes `free_physical_mb_start` to the top level.

## Preconditions

1. Close Cursor and Chrome on the XPS.
2. Real SSH from the Mac (`SSH_CLIENT` / `SSH_CONNECTION` set).
3. Do **not** claim `ssh_foreground` from a local Cursor console.

## Launch

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_gpu_only_matrix.ps1 -LaunchContext ssh_foreground -Tag reconcile_n12000 -NsList 12000"
```

Budget ~45 min with 300 s inter-cell settles (6 cells + pre-run 300 s).

## Report only

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_gpu_only_matrix.ps1 -LaunchContext ssh_foreground -Tag reconcile_n12000 -NsList 12000 -ReportOnly"
```
