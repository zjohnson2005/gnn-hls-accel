# Asks for Rithwik, Mon Oct 26 2026 (Zach sends)

Hi Rithwik - the 16 GB XPS showed that a larger GPU share gives LESS context (u4 22,750 / 21,250 /
17,750 tokens at 50 / 57 / 74%), and one non-weight budget (~3.27 GB) explains 14 configurations
within +-5%. To show this is not one runtime on one vendor, we would like time on three machines
this week and next. Each item is one page: what to run, what to keep, how long. Everything is
registered before it runs (docs/registrations/BR_XRT_2026-10-26.md); nothing here touches the T2S.
Model for all items: Qwen/Qwen3-4B-GGUF Q4_K_M, revision bc640142, sha256 7485fe6f...fdf5
(2,497,280,256 B), so results line up with ours. llama.cpp: tag b11559 (or tell us the build you use).

## E3 + E4: RTX 4070 laptop (second vendor, discrete VRAM). About 2-3 h.
Setup that matters: on Windows set NVIDIA Control Panel > Manage 3D settings > Program settings >
llama-server.exe (and python.exe for vLLM) > "CUDA - Sysmem Fallback Policy" = "Prefer No Sysmem
Fallback". Otherwise allocations spill into shared RAM and "max context" becomes a slowdown instead of
an out-of-memory error. Linux avoids this.
- E3 (llama.cpp, CUDA build b11559), flash attention OFF, the test of the 1/(k + 4 x n_head x ubatch)
  form. For ubatch in 128, 512, 2048 and KV f16: find the largest -c that loads AND prefills:
  `llama-server -m Qwen3-4B-Q4_K_M.gguf -c N -ub UB -b 2048 -ctk f16 -ctv f16 -fa off -ngl 99 --fit off -np 1 --cache-ram 0 --no-warmup`
  then POST /completion with a prompt of N - 64 tokens, n_predict 1. Bisect N at 1,024. Repeat once
  with -fa on at ubatch 512 (f16 and q4_0; q4_0 needs -fa on).
  Prediction (registered): FA-off ceiling proportional to 1/(k + 4 x 32 x ubatch) bytes.
  If easier: our tool tools/xrt_llamacpp.py (`boundary` mode) automates this and writes one JSON
  row per trial (Python 3.11, standard library only).
- E4 (vLLM, any recent version you have): Qwen/Qwen3-4B (bf16 or AWQ), gpu_memory_utilization 0.85,
  max_num_batched_tokens in 256, 512, 1024, 2048, 4096, 8192 (one start each). Keep the startup log
  line "# GPU blocks: X" / "KV cache size: Y tokens". About 1 min per point.
- Keep: full server logs (the "compute buffer size", "KV buffer size", "model buffer size" lines),
  nvidia-smi before each run, driver version, Windows/Linux version, the Sysmem Fallback setting.

## E5: Strix Halo GPU-share sweep (third vendor, unified memory). About 3-4 h.
- 3 to 6 GPU-share points. Linux: ttm.pages_limit (with a small BIOS carve-out). Windows: the VGM
  setting (AMD Software), one reboot per point. Record the OS-reported GPU memory at each point.
- At each point: llama.cpp b11559 Vulkan (and ROCm if you have it), KV f16 and q4_0, -fa on,
  ubatch 512, the same boundary search as E3 (largest -c that loads and prefills N - 64 tokens).
  Use a context range large enough that memory, not the 40,960 window, binds; if needed a larger
  model (tell us which, and its sha256) - we will register it before you run.
- Prediction (registered): ceiling linear in the GPU share with slope 1/k (R^2 >= 0.98). Any drop at
  a high share would generalize our inversion.
- Keep: the share setting per point (screenshot or command), server logs, rocm-smi / vulkaninfo
  summary, driver versions. Watch for llama.cpp's UMA heuristics silently shrinking -c (issue
  #18159): we pass --fit off and record the loaded n_ctx.

## Optional: 64 GB box time (only if E5 slips). About 2 h.
Same E2-style boundary on the 64 GB Panther Lake box at its default share, f16 and q4_0. It adds
capacity, not a vendor; only with your OK.

## Logistics
- Logs: a zip per machine to our shared folder; we never need remote access.
- Timing: E3/E4 by Sun Nov 1 if possible, E5 first three points by Sun Nov 8 (Gate B), the rest by
  Nov 15. Gate A (Wed Nov 4) decides whether the inversion becomes a section.
- Nothing here asks for changes to your queue watchdog or files.
