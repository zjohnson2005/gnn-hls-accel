# DEMO-2 pilot P0a: true-default readback on the XPS (run_id 597f40a9-98b1-4f58-b5f6-48ffabe08446)

Host XPS (aipc-c1), 2026-10-16 ET, run by Zach by hand during Task AU
(tools/kv_compiled_readback.ps1 -Mode all; pilots step 4). Copied unchanged
from ~/seam_closeout_1013/xps/p0_readback_20261016.txt (file mtime 15:32 ET);
sha256 34060c8f0edf79d4984f11667b16d9877db910c8422f52f30c8e6e202c8f790e. openvino 2026.2.1-21919, openvino_genai 2026.2.1.0-3123,
Qwen3-4B-int4-ov (INT4_SYM, group 128), device "Intel(R) Graphics (iGPU)".

Arm A validity checks (docs/amendments/DEMO2_PILOTS_2026-10-16.md, P0):
- backend PA ("Model: LLM with Paged Attention"); no "Falling back to SDPA"
  line (sdpa_fallback_warning false). PASS.
- compiled KV_CACHE_PRECISION i8 in GenAI's own compile at
  OPENVINO_LOG_LEVEL=3 (pa_property_dump_seen true). PASS.
- IR rt_info runtime_options present, KV_CACHE_PRECISION absent: no
  override. PASS.
- verdict_true_default: valid, no reasons.
- runner smoke with -RequireTrueDefault (pilots step 5, = P0b): NOT RUN
  (launch_h1 -PolicyCapUsd bug, fixed in Task AV). P0 is complete on the
  XPS only after P0b.

Also read:
- Core compile, no property: key_cache and value_cache int8 on all 72 ports
  (36 + 36). u8 request: int8 on 72 ports (u8 maps to i8, as the source
  read said). u4: uint8_t ports with compiled property uint4_t (packed).
  f16: float16.
- GenAI latency scheduler: max_num_batched_tokens 18446744073709551615,
  cache_size 0, dynamic_split_fuse true, use_cache_eviction false,
  enable_prefix_caching true; matches the 2026.2.1 source read
  (PREFIX-CACHE-AUDIT (a)). Struct defaults SchedulerConfig(): 256 /
  prefix caching false / split-fuse true.
- The u8 KV lines in the log tail are from a CPU-compiled model in the
  same pipeline (its EXECUTION_DEVICES is CPU), not the GPU LLM.
- Load 4.39 s (child), core compiles 3.93-4.62 s; one load each, not a
  timing measurement.
