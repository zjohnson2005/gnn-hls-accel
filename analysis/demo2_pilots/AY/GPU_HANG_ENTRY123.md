# Entry 123 hang on the XPS GPU, now with a native stack (Task AY, 2026-10-20 ET)

Facts first. Interpretation is marked. Scope: one device (XPS aipc-c1, Xe3
iGPU "Intel(R) Graphics"), one driver, one runtime, one entry.

## 1. Runs
| | 841b84e4-0eb8-436d-89f6-c5b558848991 | 24c1abc0-0613-4890-87b6-3da05350beda |
|---|---|---|
| Date (ET) | 2026-10-19, launch 5:18 PM | 2026-10-20, launch 3:26 PM (uptime 3,932 s) |
| Commit | eddc760e, clean | be82cb1, clean |
| Entries before 123 in the worker | 14 (59 ... 121) | none (fresh worker, -EntryOffset 14) |
| Stop | no watchdog; stopped by hand after ~3 h 17 min | watchdog: turn 0 ran 1,800.453 s > 1,800 s, exit 86 |
| Record | derived/demo2_pilots/hung_841b84e4/ (UNSEALED) | derived/demo2_pilots/hung_24c1abc0/ (UNSEALED) |

Both: arm A local_only, gpu_only, RESIDENT, --kv default,
--require-true-default, no -CacheDir, greedy (do_sample false,
max_new_tokens 512). Both stopped at multi_turn_long_context_123 turn 0, after
the per-entry pipeline load returned. The 99-line load dump before the stall is
byte-identical in the two runs (PA, compiled KV_CACHE_PRECISION i8, CACHE_DIR
empty, DYNAMIC_QUANTIZATION_GROUP_SIZE 18446744073709551615; SchedulerConfig
max_num_batched_tokens 18446744073709551615, dynamic_split_fuse true,
enable_prefix_caching true, cache_size 0). Neither log has a WARN, error,
exception or fallback line.

24c1abc0 started fresh at 123. So nothing carried over from earlier entries in
the worker: no KV blocks, prefix cache, memory pressure or driver state from a
prior entry. This is a deterministic repeat on this device: 2 of 2 attempts.

## 2. Stacks (24c1abc0)
- Python (hang_stacks_*_t0.txt, faulthandler): the main thread is in
  tools/bfcl_feasibility_probe.py:1727 _timed_generate (pipe.generate). It was
  called from run_user_turn:2211, run_h1_hybrid run_turn:1828, and on up the
  stack to main.
- Native (hang_dump_*_t0.txt, py-spy 0.4.2 dump --native, exe sha256
  6E83AB09...C995). The main thread is "idle", innermost frame first:
  NtGdiDdDDIWaitForSynchronizationObjectFromCpu (win32u.dll) <- igdrcl64.dll
  (13 frames) <- clEnqueueNDRangeKernel (OpenCL.dll) <-
  openvino_intel_gpu_plugin.dll (14 frames) <- ov::IAsyncInferRequest::infer
  <- ov::InferRequest::infer <- ov::genai::ContinuousBatchingPipeline::step
  (x4) <- ContinuousBatchingPipeline::generate <- LLMPipeline::generate <-
  py_openvino_genai.pyd <- python311.dll.
- Symbol names without PDBs are the nearest exports and carry no meaning:
  clReleaseGlSharedEventINTEL, GTPin_Init, create_plugin_engine,
  ~LLMPipeline, finish_chat, get_tokenizer, ~CPUStreamsExecutor and similar.
  The module order (genai -> openvino -> GPU plugin -> OpenCL ICD -> Intel
  OpenCL driver -> win32u D3DKMT wait) is what the dump shows.
- Other threads: turn-watchdog (running py-spy), turn-mem sampler (waiting),
  two subprocess reader threads, and an idle executor worker.

## 3. Reading (interpretation)
Inside an OpenCL kernel enqueue, the CPU thread waits on a GPU sync object (a
D3DKMT wait). In 841b84e4 the GPU 3D engine was at 0% while the worker was
stuck (6 x 5 s samples, evidence/longctx_kill.txt), so the GPU was not busy
running work. The wait does not end and nothing reports an error or a
timeout. This is a GPU kernel or driver-level hang: a silent device stall.

What this does not show:
- the kernel, or whether the stall is in prefill or decode;
- which step of turn 0 it is in. Step 0's prompt is 2,189 tokens. On the
  gold path step 1 is 34,050 tokens (after get_stock_info returns 31,665
  tokens). The runner writes telemetry per turn, so a hung turn leaves no
  step record;
- whether another driver or device behaves the same. The T2S check is
  planned (run_window_t2s.sh, step f).

## 4. Pinned identifiers
- Entry: multi_turn_long_context_123, index 14 of DEMO1_LONGCTX_30 (sha256
  7a71fa6a...). Entry JSON, canonical (sort_keys, no spaces), sha256
  f78b6c221682e3fa42673d8b9ab536c490c6007016caf827c44414c8815659dc.
- Turn 0, step 0 prompt, reconstructed on the Mac. Same render path as the
  runner (MultiTurnAgentSession + render_bfcl_tools_style), pinned HF
  tokenizer and chat template (AW section 3), no model load:
  - 9,364 chars;
  - UTF-8 sha256 d3b347bc19c601c33c964762d5579cfc9a5ebb2020d286ecea583d11bcaa96a9;
  - 2,189 tokens;
  - token-id list (JSON) sha256 a260e28ca6df5c700d71b639826d1af8c3bbb4616c53c2a3b576d2fe322d567c.

  The XPS tokenizes with the OpenVINO tokenizer. Token equality with the HF
  count is NOT YET MEASURED on the host.
- Runtime (24c1abc0 plan.json):
  - openvino 2026.2.1-21919-ede283a88e3-releases/2026/2;
  - openvino_genai 2026.2.1.0-3123-7dea0459b2a;
  - Python 3.11.9;
  - model Qwen3-4B-int4-ov.
- GPU driver at the time of the hang: NOT RECORDED. Neither plan.json nor the
  gates file records it. The last recorded XPS iGPU driver is 32.0.101.8622
  (2026-02-19, oem32.inf), from the 2026-07-29 probe
  (analysis/aipc-c1/reprobe_af002_2026-07-29/drivers_probe.txt). The window-2
  script records it read-only before the reboot. Query, by hand:
  `ssh zjohn@100.101.81.6 'Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceClass -eq "DISPLAY" -or $_.DeviceName -match "NPU" } | Select-Object DeviceName,DriverVersion,DriverDate,InfName | Format-List'`

## 5. Failure regime: silent device stall under the shipped default config
Regimes recorded so far (PAPER_EVIDENCE_MAP I-8 and flag 3):
- explicit error: OpenCL CL_OUT_OF_RESOURCES on unified-memory Intel
  (c759d72f T2S B390 canary, 322b2f86, 2804d7fa);
- HTTP 400 on overflow (llama-server b7062);
- silent truncation (older llama.cpp b6721; Rithwik's context-managed side);
- CPU offload (Ollama on NVIDIA), and unified-memory paging spill with latency
  (83127e1b).

New regime, on this device, driver and entry:
- **Silent device stall under the shipped default configuration.** The call
  does not return, raises nothing, writes no log line, and the GPU sits idle.
  The true default (LLMPipeline(model, "GPU")) triggers it, which is the
  configuration a user gets. The prompt is short (2,189 tokens at step 0) and
  the memory reading was not low (3,019 MB available in 841b84e4).

What it means for routing (finding, not a general claim):
- The router sees no signal. No TTFT, decode rate, error code or token
  stream event arrives. A policy that escalates on a measured slow TTFT or on
  an error never fires, because the measurement never completes.
- Only a wall-clock deadline on the local call detects it. The native
  generate cannot be cancelled from Python, so recovery needs a process
  boundary: the worker records the hang and exits (our watchdog, exit 86).
- For Paper 2 ("failure is unobservable"): this is a third kind of
  unobservable failure beside silent wrong answers and silent truncation. It
  shows up only as missing output, and it needs a deadline plus process
  isolation in the routing design. The deadline must sit above the slowest
  healthy turn (469.4 s in 841b84e4) and below the user's tolerance.
- For ISPASS: the failure regime per run (I-10) needs a "stall" value next
  to error, OOR, spill and drop.
- Not claimed: anything beyond the XPS Xe3 iGPU, this driver, OpenVINO
  2026.2.1 and this entry. The P10-HANG123 matrix
  (docs/amendments/DEMO2_PILOT_P10_HANG123_2026-10-20.md) and the T2S check
  test which knobs and which device change it.

## 6. Effect on the pilots
- P6 for arm A LONGCTX_30 = 841b84e4 (14 entries) + 123 as a hang (24c1abc0)
  + the remaining 15 (window 2, `--skip-entries multi_turn_long_context_123
  --skip-hang-record <24c1abc0 hang_events.json>`). The hang counts as a local
  fail with outcome hang.
- Arm A's validity (P0) is unchanged. The hang is an entry-level outcome, not
  an invalid configuration.
