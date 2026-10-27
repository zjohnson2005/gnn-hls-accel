# SEAM XRT runbook E3: RTX 4070 laptop (llama.cpp CUDA)

Prepared Mon Oct 26 2026 (Task BS). Registered before any run: docs/registrations/BR_XRT_2026-10-26.md
(P-XRT-7) and docs/registrations/BS_XRT_RUNBOOKS_2026-10-26.md. You run it; we never access the machine.
Your logs and screenshots are the record; we seal them by sha256 when they arrive.

**What it measures.** The largest context (-c) that loads AND prefills n - 64 tokens on the RTX 4070,
for 5 settings. One fresh llama-server per trial, bisection at 1,024 tokens, one repeat at the edge.

| Cell | Flash attention | ubatch | KV cache | Search range |
|---|---|---|---|---|
| E3_fa0_ub128_f16 | off | 128 | f16 | 4,096 - 65,536 |
| E3_fa0_ub512_f16 | off | 512 | f16 | 4,096 - 65,536 |
| E3_fa0_ub2048_f16 | off | 2048 | f16 | 4,096 - 65,536 |
| E3_fa1_ub512_f16 | on | 512 | f16 | 4,096 - 65,536 |
| E3_fa1_ub512_q4_0 | on | 512 | q4_0 | 8,192 - 196,608 |

**Time.** About 2-3 h in total: about 15-30 min of downloads (3.2 GB), then at most 52 trials of about
1-2 min each. The script prints its own budget before the first trial.

**Requirements.** Windows 10/11, NVIDIA driver 551.61 or newer (CUDA 12.4 build; the script stops
below 528.33 and asks below 551.61), about 6 GB free on C:. No admin, no Python, no installs.
Everything goes in C:\seam_xrt\ (bin, models, logs, out, zips); nothing else is touched.

## Steps
1. Unzip this folder anywhere (e.g. Downloads\seam_rtx4070). Close games, video players and other GPU
   apps. Plug in the charger.
2. Open PowerShell in that folder and run:
   `powershell -ExecutionPolicy Bypass -File .\run.ps1`
3. The script prints the driver requirement, then downloads and checks (size + sha256; it stops on any
   mismatch):
   - llama-b11559-bin-win-cuda-12.4-x64.zip, 265,207,128 B, sha256 4a885b80...ecd7
   - cudart-llama-bin-win-cuda-12.4-x64.zip, 391,443,627 B, sha256 8c79a9b2...e1d6
   - Qwen3-4B-Q4_K_M.gguf (Qwen/Qwen3-4B-GGUF rev bc640142), 2,497,280,256 B, sha256 7485fe6f...fdf5
4. **Sysmem Fallback (required).** The script stops and shows the path of
   C:\seam_xrt\bin\b11559-cuda-12.4\llama-server.exe. In NVIDIA Control Panel > Manage 3D settings >
   Program settings > Add, browse to that exe and set "CUDA - Sysmem Fallback Policy" =
   "Prefer No Sysmem Fallback", then Apply. Take a screenshot of that setting and save it in the run
   folder the script prints (C:\seam_xrt\out\<run_id>\). Type CONFIRMED. Without this setting, VRAM
   overflow silently spills into system RAM and the limit becomes a slowdown, not an error.
5. Let it run. Do not use the GPU meanwhile. Each trial prints one line
   (`TRIAL <cell> bisect n=<ctx> status=hold|fail_load|fail_prefill|timeout`).
   A warning "CUDA buffers > VRAM" means Sysmem Fallback is probably still on: stop (Ctrl+C), fix the
   setting, and run step 2 again.
6. When it prints RUN_DONE, run:
   `powershell -ExecutionPolicy Bypass -File .\collect.ps1`
   It writes C:\seam_xrt\seam_xrt_rtx4070_<date>.zip and prints its sha256.
7. Send Zach the zip, the sha256 line and the screenshot.

**Interrupted?** Run step 2 again: it resumes the unfinished run (trials already done are replayed from
C:\seam_xrt\out\<run_id>\trials.jsonl, not re-run). `-NewRun` starts over.

## What the server is started with (one per trial)
`llama-server -m Qwen3-4B-Q4_K_M.gguf -c N -b max(UB,2048) -ub UB -ctk KV -ctv KV -fa on|off -ngl 99
--fit off -np 1 --cache-ram 0 --no-warmup --host 127.0.0.1 --port 8091`, then POST /completion with
exactly N - 64 prompt tokens, n_predict 1. A trial holds if the reply is HTTP 200 with no error and
all N - 64 prompt tokens were processed. `--fit off` stops llama.cpp from choosing the context itself.

## What the zip contains
- out\<run_id>\trials.jsonl: one JSON line per trial (status, buffer sizes per device from the log,
  free MiB per device, prefill time, errors) and one cell_done line per cell.
- out\<run_id>\server_logs\: the full server log of every trial.
- nvidia-smi snapshots (start of run and before each cell), llama.cpp version, device list, the
  Sysmem Fallback confirmation, run_meta.json (operator, machine, script sha256).
- out\system_rtx4070_<date>\: OS build, GPU driver, GPU memory as the driver reports it, dxdiag
  display memory, and a sha256 manifest of every file.

Questions: Zach. Thank you!
