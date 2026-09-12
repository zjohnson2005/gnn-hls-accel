# Decode-verify remeasure — prepared commands

**Status:** `BLOCKED_ON_OPERATOR` (Cursor + Chrome resident on XPS; measurement must not fake `ssh_foreground`).

## Preconditions

1. Close Cursor and Chrome (and other contenders listed by `run_gpu_only_matrix.ps1`) on the XPS.
2. From the Mac, real SSH (so `SSH_CLIENT` / `SSH_CONNECTION` are set).
3. Script enforces `isolation.pre_run_settle_s=300` after the refuse check.

## Matrix

- arms: `{A, gpu_only}`
- N: `{12000, 20000}` only (do **not** re-run 36000)
- repeats: 3, interleaved + per-round shuffle
- path: smoke (`tools/smoke_gpu_exec.ps1 -N …`); `max_new_tokens=64` when `-N` set
- budget ~75 min (dominated by arm A prefill at n=20000)

## Launch (Mac → XPS SSH)

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_gpu_only_matrix.ps1 -LaunchContext ssh_foreground -Tag decode_verify_64 -NsList 12000,20000"
```

## Report after completion

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_gpu_only_matrix.ps1 -LaunchContext ssh_foreground -Tag decode_verify_64 -ReportOnly"
```

Artifacts land under `derived/gpu_smoke/` with prefix `decode_verify_64_`.
