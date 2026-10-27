# SEAM XRT queue job E5: Strix Halo evo-x2 (llama.cpp Vulkan)

Prepared Mon Oct 26 2026 (Task BS). Registered before any run:
docs/registrations/BS_XRT_RUNBOOKS_2026-10-26.md (E5a predictions; E5b keeps P-XRT-8 of
docs/registrations/BR_XRT_2026-10-26.md). It runs as one job in your queue; we never access the machine.
Your logs are the record; we seal them by sha256 when they arrive.

**E5a (default GPU share; the only part we ask for now).** No setting is changed. Four cells, KV f16 and
q4_0, flash attention on, ubatch 512, bisection at 1,024 tokens, one repeat at the edge:

| Cell | What holds | Search range |
|---|---|---|
| E5_L_f16, E5_L_q4_0 | the server LOADS at -c n (KV and compute buffers are allocated at load) | 4,096 (8,192 for q4_0) - 4,194,304 |
| E5_P_f16, E5_P_q4_0 | it loads AND prefills n - 64 tokens | 4,096 (8,192) - 131,072 |

L cells find the memory boundary even far above the model window, in seconds per trial. P cells stop at
131,072 because above that the model window and the prefill time bind, not memory.

**E5b (3+ share points) ONLY if you say share changes are OK.** It needs a VGM/BIOS change and a reboot
per point, which we do not ask for now. The script refuses E5b unless E5B_SHARE_OK=1 and E5B_SHARE_GB
(the share you set, in GB) are both given. One job per share point.

## What the queue must provide
- Windows 10/11, Windows PowerShell 5.1 (built in). No admin, no Python, no WSL/Docker.
- Network for the first job (downloads below), or pre-place the three files (sha256 still checked).
- About 3 GB free on C:. Everything goes in C:\seam_xrt\ (bin, models, logs, out, zips); nothing else.
- **No other GPU job at the same time** (the job refuses to start if another llama-server runs, and
  each L trial briefly allocates up to all GPU-visible memory).
- Timeout: 6 h for the job (expected 2-4 h; at most 54 trials, the job prints its budget first).
  Per-trial timeout 3,600 s (SEAM_TRIAL_TIMEOUT_S).
- Any working directory. Exit code 0 = all cells finished; 1 = refused or aborted (reason in the log).

## Job command
`powershell -NoProfile -ExecutionPolicy Bypass -File <folder>\run.ps1`, then the same with collect.ps1.

Environment (all optional for E5a):

| Variable | Meaning |
|---|---|
| E5_PART | a (default) or b |
| E5B_SHARE_OK / E5B_SHARE_GB | required for b: 1, and the GPU share in GB set for that point |
| E5_ROCM | 1 = also run the same cells with the b11559 HIP build (only if ROCm/HIP already works here) |
| SEAM_RUN_ID / SEAM_NEW_RUN | resume a given run / force a new one (default: resume the last unfinished) |
| SEAM_TRIAL_TIMEOUT_S, SEAM_OPERATOR | per-trial timeout (3600), operator name |

Downloads (size + sha256 checked before use; any mismatch deletes the file and exits 1):
- llama-b11559-bin-win-vulkan-x64.zip, 32,084,119 B, sha256 bf2fb2a7...66dc
- Qwen3-4B-Q4_K_M.gguf (Qwen/Qwen3-4B-GGUF rev bc640142), 2,497,280,256 B, sha256 7485fe6f...fdf5
- only with E5_ROCM=1: llama-b11559-bin-win-rocm-10.0-x64.zip, 257,958,782 B, sha256 5511af01...f9ab

## Per trial
`llama-server -m Qwen3-4B-Q4_K_M.gguf -c N -b 2048 -ub 512 -ctk KV -ctv KV -fa on -ngl 99 --fit off
-np 1 --cache-ram 0 --no-warmup --host 127.0.0.1 --port 8092` (one fresh server per trial). P cells then
POST /completion with exactly N - 64 prompt tokens, n_predict 1; a trial holds on HTTP 200, no error,
all prompt tokens processed. `--fit off` stops llama.cpp's UMA heuristics from shrinking -c
(issue #18159); the loaded n_ctx is in each log.

## After the job
collect.ps1 writes C:\seam_xrt\seam_xrt_evo-x2_<date>.zip (logs, out, a system record: OS build, GPU
driver, GPU memory as the driver and Vulkan report it, dxdiag Dedicated/Shared memory, llama.cpp
version, sha256 manifest) and prints its sha256. Please send the zip, the sha256 and a screenshot of the
GPU memory / VGM setting (AMD Software > Performance > Tuning, or the BIOS page) as it was for the run.

Questions: Zach. Thank you!
