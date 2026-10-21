# DEMO-2 pilot P0a: true-default readback on the T2S (record id 5e190568-868f-4f1d-b9c6-bfe59a1d9feb)

Host EVO-T2S (evo-t2), 2026-10-20 5:33-5:34 PM ET, step c of
~/seam_closeout_1013/xps/run_window_t2s.sh (tools\kv_compiled_readback.py --kv
all --mode all, spawned detached; uptime 551,078 s, UNCOLD). The tool writes
no run_id; the record id above was assigned at closeout (Task AZ), as for the
XPS record 597f40a9. kv_compiled_readback.json is the log copied unchanged
(it is pure JSON), sha256
520c953c66bf60f480f5d4b3ae68dc969049f4e2ba8e919b50171c8edd249957.
openvino 2026.2.1-21919, openvino_genai 2026.2.1.0-3123, device
"Intel(R) Arc(TM) B390 GPU (iGPU)", GPU driver 32.0.101.8509 (a_drivers.txt of
the same window).

Arm A validity checks (docs/amendments/DEMO2_PILOTS_2026-10-16.md, P0):
- GenAI's own compile (LLMPipeline(ir_dir, "GPU"), no properties,
  OPENVINO_LOG_LEVEL=3): backend PA, no "Falling back to SDPA" line, compiled
  KV_CACHE_PRECISION i8. PASS.
- IR rt_info runtime_options present, no KV_CACHE_PRECISION: no override. PASS.
- verdict_true_default valid. P0b (runner smoke) PASSED the same window:
  03632ad3-a6e4-480f-944b-854d8d3ceedd (seal MATCH). Arm A is valid on the T2S.

Also read: core compile default and u8 -> int8_t, u4 -> uint4_t, f16 ->
float16 (compiled property); latency scheduler in the GenAI log
(max_num_batched_tokens 18446744073709551615, prefix caching on); struct
defaults SchedulerConfig(): 256 / prefix caching false / split-fuse true.
