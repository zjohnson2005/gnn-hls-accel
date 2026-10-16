# Verify Intel AI PC / OpenVINO GenAI local-inference measurements (sweep 4)

Scope: external evidence for our Qwen3-4B / OpenVINO GenAI 2026.2.1 measurements on a Core Ultra 5 325 (Panther Lake, 4 Xe3 cores, 16 GB LPDDR5X) and an Arc B390 mini PC (64 GB). Sources are limited to October 2026 or earlier. Method notes: docs.openvino.ai pages render through JavaScript and WebFetch returned empty bodies, so the same documentation was read from its source in the openvinotoolkit GitHub repos (`docs/articles_en/...`). Source-code defaults were checked at the release tags that match our stack: openvino tag `2026.2.1` and openvino.genai branch `releases/2026/2`. Wherever a source comes from a different version, the finding says so.

Hardware context: Notebookcheck lists the Core Ultra 5 325 as "Panther Lake", a "mid-range 8-core (4+4) SoC" with 4 P-cores and 4 Darkmont LP E-cores (8 threads), "Intel Graphics 4 Xe3" (4 Xe3 cores, 2450 MHz), up to LPDDR5X-7467, NPU 5 at 50 TOPS INT8, and PL1 25 W / PL2 55 W. — [Notebookcheck: Core Ultra 5 325](https://www.notebookcheck.net/Intel-Core-Ultra-5-325-Processor-Benchmarks-and-Specs.1196417.0.html)

## Q1. iGPU vs CPU (prefill 16.8x, decode 3.18x / 19.85 vs 6.24 tok/s at 12k; 10k vs 468 tokens under a 10 s TTFT SLO; CPU working set 9.5-10.7 GB vs 5.1 GB)

### Takeaway
External sources agree on the direction and the shape of the result: prefill gains far more from the iGPU than decode does. Intel's own iGPU numbers for Qwen3-4B INT4 on a Core Ultra 5 "330" (the same low-end Panther Lake tier) match our iGPU decode rate and TTFT closely. No source gives an OpenVINO CPU-vs-iGPU Qwen3-4B comparison at 12k context, so the 16.8x / 3.18x ratios themselves are **not externally verified**. The one independent Panther Lake CPU-vs-iGPU comparison (llama.cpp, MoE model, bigger 16-core chip with 12 Xe3 cores) reports smaller ratios: about 6x prefill and 1.7x decode.

### Cited Findings
- **Intel official (iGPU only, OpenVINO 2026.3 data).** Intel's "Most Efficient Large Language Models for AI PC" page says: "The current data is as of OpenVINO 2026.3, 13 August 2026. The tables below list the key performance indicators for inference on built-in GPUs." It has tabs for 7-368H, 7-255H, 7-258V and 5-330, all at batch 1 and beam 1. — [Intel GenAI performance page (source rst)](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/about-openvino/performance-benchmarks/generative-ai-performance.rst); rendered at [docs.openvino.ai generative-ai-performance](https://docs.openvino.ai/2026/about-openvino/performance-benchmarks/generative-ai-performance.html)
- **Intel 5-330 table, Qwen3-4B INT4-MIXED.** At 1024 input tokens: 1st latency 775.1 / 814.6 ms, 2nd-token latency 55.4 / 56.9 ms (18.05 / 17.57 tok/s). At 32 input tokens: 49.2 / 50.8 ms (20.3 / 19.7 tok/s). — [llm_models_5-330.csv](https://github.com/openvinotoolkit/openvino/blob/master/docs/sphinx_setup/_static/benchmarks_files/llm_models_5-330.csv)
  - Our calculation: 1024 tokens / 0.775-0.815 s is about 1,260-1,320 prefill tok/s on the 5-330 iGPU. Our result that 10,000 tokens fit inside a 10 s TTFT (at least 1,000 tok/s averaged over a 10k prompt) fits this. Prefill rate is expected to fall as context deepens.
  - Our 19.85 tok/s iGPU decode at 12k context is slightly *higher* than Intel's 17.6-18.1 tok/s at 1k input on the 5-330. Possible causes are a different SKU or memory speed, or a different KV precision (our default probably resolved to u4; see Q2). The "330" tab was not mapped to an exact SKU: the platform PDF was not retrievable, and Notebookcheck's Panther Lake list shows a 325, 322, 332 and 335 but no 330. — [Notebookcheck](https://www.notebookcheck.net/Intel-Core-Ultra-5-325-Processor-Benchmarks-and-Specs.1196417.0.html)
- **Intel 7-368H (Panther Lake H) and 7-258V (Lunar Lake), Qwen3-4B INT4, 1024 input.** 368H: TTFT 170 / 175.9 ms, 24.2 / 24.8 ms per token (41.3 / 40.3 tok/s). 258V: TTFT 324.6 / 345.6 ms, 29.2 / 30.4 ms per token (34.2 / 32.9 tok/s). — [llm_models_7-368H.csv](https://github.com/openvinotoolkit/openvino/blob/master/docs/sphinx_setup/_static/benchmarks_files/llm_models_7-368H.csv); [llm_models_7-258V.csv](https://github.com/openvinotoolkit/openvino/blob/master/docs/sphinx_setup/_static/benchmarks_files/llm_models_7-258V.csv)
- **Intel publishes no CPU or NPU columns on this page.** It is iGPU-only ("built-in GPUs"), so Intel gives no official CPU-vs-iGPU ratio for Qwen3-4B. — [generative-ai-performance.rst](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/about-openvino/performance-benchmarks/generative-ai-performance.rst)
- **Independent Panther Lake CPU vs iGPU (llama.cpp, not OpenVINO).** Core Ultra X7 358H (16 cores, Arc B390 with 12 Xe3 cores, ~32 GiB LPDDR5), Qwen3.6-35B-A3B Q4_K_M, pp512/tg128. Vulkan 624.5 pp / 32.75 tg tok/s; SYCL 609.4 / 30.6; CPU 101.6 / 19.4. That is roughly 6x prefill and 1.6-1.7x decode for the iGPU over the CPU. The author says "Token generation is memory-bandwidth bound… on UMA the GPU and CPU share that bus." OpenVINO's llama.cpp backend *failed* on this MoE model ("failed to decode prompt batch, res = -3"). — [grigio.org Panther Lake llama.cpp backends](https://grigio.org/benchmarking-llama-cpp-backends-on-intel-panther-lake-vulkan-vs-sycl-vs-openvino-vs-cpu/)
- **Lunar Lake reference (OpenVINO GenAI 2026.1.0, Arc 140V iGPU).** Qwen3-8B INT4: 19.79 tok/s decode, 264.3 ms median TTFT. Qwen3-14B INT4: 11.13 tok/s. The author later notes the ~1,960 tok/s prefill figure was "prefix-cache-warm". Cold prefill was about 595-761 tok/s at 512 tokens for the 14B, and "cold prefill ≈28–36% faster" going from 2026.1.0 to 2026.2.1. — [openvino Discussion #36604](https://github.com/openvinotoolkit/openvino/discussions/36604)
- **Lunar Lake CPU vs iGPU, older stack (OpenVINO 2025.0, Llama-3.2-3B INT4, short prompt, 100 new tokens).** End-to-end time "iGPU (3.7sec) < CPU (5.6sec) < NPU (7.5sec)" on a Core Ultra 5 228V. — [openvino.genai #1882](https://github.com/openvinotoolkit/openvino.genai/issues/1882)
- **Lunar Lake 258V, OpenVINO 2026.1 via llama.cpp's OpenVINO backend.** Llama-3.1-8B Q4_K_M on OpenVINO CPU: 3.89 tok/s decode, 40.7 tok/s prefill (2k context). The OpenVINO GPU path "aborted on init"; Vulkan iGPU gave 5.7 decode / 172 prefill. — [elizaOS RFC #7633](https://github.com/elizaOS/eliza/issues/7633)

### Inferences
- Our iGPU absolute numbers (decode around 20 tok/s, at least 1,000 tok/s prefill out to 10k) agree with Intel's 5-330 iGPU table within about 10%. This is the strongest external corroboration we have for item 1, though it covers the iGPU side only.
- Our CPU-side ratios (16.8x prefill, 3.18x decode) are much larger than grigio's 6x / 1.7x. The chips differ in a way that predicts this: the 325's CPU has only 4P+4LP-E cores and 8 threads against the 358H's 16 cores, and our measurement is at 12k depth, where CPU attention cost dominates. The two results are not contradictory, but neither is a like-for-like check.
- The CPU working-set gap (9.5-10.7 GB vs 5.1 GB) could come from the CPU plugin choosing a higher-precision inference or KV type (CPU may "promote to bf16"; see the utils.hpp comment in Q2). This is a hypothesis we did not verify.

### Gaps
- No public OpenVINO CPU-vs-iGPU-vs-NPU benchmark for Qwen3-4B at 8-12k context on Panther Lake was found, from Intel, Phoronix, Notebookcheck, Tom's Hardware or Chips and Cheese.
- No external source reports process working-set memory for OpenVINO CPU vs GPU LLM inference.
- The "5-330" platform in Intel's table could not be tied to an exact SKU, memory speed or power mode, because benchmark_genai_platform_list.pdf was not retrievable.

## Q2. KV cache precision f16 / u8 / u4 (limits 15k / 20k / 26.5k; f16 prefill 15-27% faster; warm turn 0.64 / 1.00 / 0.95 s; default reads "dynamic"; prefix caching default false)

### Takeaway
The "dynamic" readback **is corroborated** and explained by the source code. The GPU plugin's `kv_cache_precision` option defaults to `ov::element::dynamic` and is resolved at compile time. [CORRECTED 2026-10-16: the next sentence is wrong. The 2026.2.1 source hard-codes auto_enable_4bit_kv = false, so the PA default is i8; u4 is automatic only from 2026.3.x. docs/literature/2026-10-16/DEMO2_CONTROL/openvino_defaults.md Q4.] **Important correction:** in 2026.2.1 the GPU plugin resolves "dynamic" to **u4** for PagedAttention models with 4-bit weights. LLMPipeline's default backend is PagedAttention, so the effective default for our INT4 Qwen3-4B on the iGPU was probably **u4**, not f16 or u8. Our f16 runs were therefore a non-default override. Intel confirms INT4 KV is new in 2026.2 and aimed at prompts above 32K. No external source quantifies the dequantization speed penalty we measured.

### Cited Findings
- **GPU option default.** At tag 2026.2.1, the GPU option is declared as `OV_CONFIG_RELEASE_OPTION(ov::hint, kv_cache_precision, ov::element::dynamic, "")`. This explains why reading the property back returns "dynamic". — [options.inl @2026.2.1](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/include/intel_gpu/runtime/options.inl)
- **Auto-resolution logic at 2026.2.1** ([execution_config.cpp @2026.2.1, ~L284-297](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp)):
  - "Enable 4-bit KV-cache compression for PA models with 4-bit compressed weights" sets `m_kv_cache_precision = ov::element::u4`.
  - Otherwise, "Enable KV-cache compression by default for: 1) Non-systolic platforms in case of SDPA-based models 2) For any platforms in case of PagedAttention-based model" sets `i8`.
  - Otherwise it uses the inference precision (f16).
- **Key/value quantization modes.** Key-cache quantization defaults to BY_CHANNEL and value-cache to BY_TOKEN. On current master, an explicitly set `u8` is remapped internally to `i8`. The remap was seen on master and not checked at the tag. — [execution_config.cpp (master)](https://github.com/openvinotoolkit/openvino/blob/master/src/plugins/intel_gpu/src/runtime/execution_config.cpp)
- **LLMPipeline uses PagedAttention by default.** `std::string attention_backend = PA_BACKEND;` (openvino.genai releases/2026/2, utils.cpp ~L857). LLMPipeline then builds a `ContinuousBatchingAdapter`, which compiles a PA model. — [utils.cpp @releases/2026/2](https://github.com/openvinotoolkit/openvino.genai/blob/releases/2026/2/src/cpp/src/utils.cpp); [pipeline.cpp](https://github.com/openvinotoolkit/openvino.genai/blob/releases/2026/2/src/cpp/src/llm/pipeline.cpp)
- **GenAI warns that the property can mislead.** utils.hpp: "Plugins may resolve the actual cache precision (e.g. CPU promoting to bf16 based on the resolved inference precision) independently of the ov::hint::kv_cache_precision property, so the precision must be read from the compiled model's cache input ports." — [utils.hpp (master)](https://github.com/openvinotoolkit/openvino.genai/blob/master/src/cpp/src/utils.hpp)
- **2026.2 release notes:**
  - "INT4 KV-cache compression is enabled for GPUs, with substantial memory reduction when KV cache size is significant, such as with large input prompts exceeding 32K tokens."
  - GPU plugin: "INT4 KV cache quantization has been enabled, reducing memory consumption…"
  - "Enabled by-channel INT8 KV cache quantization by default for GPU XAttention…"
  - NPU: "Reduced KV-cache memory consumption, reaching up to 2.5 GB saving for select models on longer contexts (8..12K)."
  - Source: [release-notes-openvino.rst (2026.2 – 28 May 2026 section)](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/about-openvino/release-notes-openvino.rst); rendered at [docs.openvino.ai release notes](https://docs.openvino.ai/2026/about-openvino/release-notes-openvino.html)
- **New Intel iGPU memory guide (added to master in Oct 2026, not present at tag 2026.2.1):**
  - "For the GPU plugin, supported KV-cache precision options include u8, u4, and f16."
  - "When KV_CACHE_PRECISION is not set, OpenVINO selects the effective KV-cache precision based on the model and device; there is no single version-neutral u8 or u4 default for every GPU configuration."
  - "To avoid KV-cache quantization, set KV_CACHE_PRECISION to f16."
  - "If OpenVINO would select u4, overriding it with u8 increases the KV-cache data precision and memory use relative to u4."
  - "When KV-cache quantization is enabled on GPU, get_state() and set_state() APIs are not supported."
  - The checklist recommends u4 "especially for long contexts above 32K tokens."
  - Source: [managing-igpu-memory-usage.rst](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/openvino-workflow/running-inference/optimize-inference/managing-igpu-memory-usage.rst)
- **CPU example readback.** A GenAI debug-logging example on a Xeon shows `KV_CACHE_PRECISION: f16` and `INFERENCE_PRECISION_HINT: bf16` for a CPU compiled model. — [debug-logging.mdx](https://github.com/openvinotoolkit/openvino.genai/blob/master/site/docs/guides/debug-logging.mdx)
- **Accuracy caveat from a field report.** In openvino #36151 (Qwen3.5 on an Arc iGPU), the reporter tried KV precision u4 and u8 as workarounds for a kernel crash, and neither changed the outcome. That issue is unrelated to speed. — [openvino #36151](https://github.com/openvinotoolkit/openvino/issues/36151)
- The SchedulerConfig default `enable_prefix_caching = false` is covered in Q4. It is corroborated for the struct, but LLMPipeline overrides it to true.

### Inferences
- If our "default" run was u4 (very likely for INT4 weights on 2026.2.1 with the PA backend), then the u4 row *is* the default configuration, and our 26,500-token resident limit is the default-config limit. Confirm by reading the compiled model's `key_cache.*` input element type, as utils.hpp recommends, rather than reading the property.
- The resident-limit ratios (u8/f16 = 1.33x and u4/f16 = 1.77x, rather than 2x and 4x) fit a fixed memory budget that has to hold the weights plus per-group scale/zero-point overhead. This is our arithmetic, not a published figure.
- Intel documents u4 KV as a memory feature for prompts above 32K and says nothing about speed. Our finding that f16 prefill is 15-27% faster than u8/u4 at depth is consistent with Intel's framing (memory saving, not speed), but no source quantifies it.

### Gaps
- No Intel or independent measurement of prefill/decode speed for f16 vs u8 vs u4 KV on Xe2/Xe3 iGPUs was found.
- No published accuracy evaluation of u4 KV (by-channel key) on Qwen3-4B was found. The release notes cite accuracy only for XAttention by-channel INT8.
- We did not check whether a user-set "u8" on 2026.2.1 maps to i8 before kernel selection; only master was inspected.

## Q3. INT8 vs INT4 weights (INT8 decodes 1.3-1.5x slower, about 1.76 GB more resident)

### Takeaway
**Corroborated in direction. Intel's own ratio is somewhat larger.** Intel's iGPU tables show Qwen3-4B INT8-CW decoding about 1.5-1.7x slower than INT4-MIXED on the 5-330, 7-368H and 7-258V. Our 1.3-1.5x is at or below Intel's range.

### Cited Findings
- **5-330, Qwen3-4B, 1024 input.** INT4-MIXED: 55.4 / 56.9 ms per token. INT8-CW: 86.3 ms (11.59 tok/s). That makes INT8 about 1.52-1.56x slower. At 32 input: INT4 49.2 / 50.8 ms vs INT8 81.5 ms, about 1.60-1.66x. INT8 TTFT at 1024: 954.6 ms vs INT4 775-815 ms. — [llm_models_5-330.csv](https://github.com/openvinotoolkit/openvino/blob/master/docs/sphinx_setup/_static/benchmarks_files/llm_models_5-330.csv)
- **7-368H, Qwen3-4B, 1024 input.** INT4 24.2 / 24.8 ms vs INT8 40.4 ms (about 1.63-1.67x). FP16 is 76.5 ms. — [llm_models_7-368H.csv](https://github.com/openvinotoolkit/openvino/blob/master/docs/sphinx_setup/_static/benchmarks_files/llm_models_7-368H.csv)
- **7-258V (Lunar Lake), Qwen3-4B, 1024 input.** INT4 29.2 / 30.4 ms vs INT8 48.9 ms (about 1.61-1.67x). FP16 is 90.3 ms. — [llm_models_7-258V.csv](https://github.com/openvinotoolkit/openvino/blob/master/docs/sphinx_setup/_static/benchmarks_files/llm_models_7-258V.csv)
- **Intel guidance.** "INT4 weight compression is usually the recommended first option for LLM deployments where model size is the primary memory pressure… INT8 weight compression… is useful for smaller LLMs or systems where enough RAM can be allocated." — [managing-igpu-memory-usage.rst](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/openvino-workflow/running-inference/optimize-inference/managing-igpu-memory-usage.rst)
- **Model load size.** A Qwen3.5-4B INT8 model "Loaded at about 5.19 GB" on an Arc iGPU (OpenVINO 2026.2.0). That is a different model, but it gives a rough scale for 4B INT8 resident size. — [openvino #36151](https://github.com/openvinotoolkit/openvino/issues/36151)

### Inferences
- Intel's numbers are from OpenVINO 2026.3 at short context (32 / 1024 tokens). At 12k context, KV-cache reads make up a larger share of each decode step and are the same for INT8 and INT4 weights. That would shrink the INT8/INT4 ratio, which may explain our lower 1.3x end.
- The ~1.76 GB extra resident memory is plausible for 4B parameters going from roughly 4.5 to 8 bits per weight (INT4-MIXED keeps some layers at INT8). This is our arithmetic; no direct external figure was found.

### Gaps
- Intel does not publish resident-memory figures per weight format for Qwen3-4B.

## Q4. Prefix caching and residency (session prefill up to 5.17x faster; appending ~8,500 tokens to a cached prefix took 22.4 s vs ~11 s cold)

### Takeaway
The claim "SchedulerConfig default enable_prefix_caching = false" is **true for the struct but misleading for LLMPipeline**. When no scheduler_config is passed, LLMPipeline substitutes a "latency-oriented" config with `enable_prefix_caching = true` **and an unlimited `max_num_batched_tokens`**. A user-constructed `SchedulerConfig()` instead carries `max_num_batched_tokens = 256`. This gives a concrete, testable explanation for the 22.4 s slow append. If the warm-path run passed an explicit SchedulerConfig (to turn prefix caching on) while the cold run used the default, the 8,500-token append was prefilled in 256-token chunks. No external report of this exact slowdown was found.

### Cited Findings
- **Struct defaults** (scheduler_config.hpp @releases/2026/2):
  - `std::size_t max_num_batched_tokens = 256;` with the comment "When ContinuousBatching is invoked from LLMPipeline (client scenario) by default max_num_batched_tokens is not limited."
  - `bool enable_prefix_caching = false;` with the comment "When ContinuousBatching is invoked from LLMPipeline (client scenario) by default prefix caching is turned on."
  - The comments also say "When turned on all previously calculated KV-caches are kept in memory for future usages… This results in more RAM usage."
  - Source: [scheduler_config.hpp @releases/2026/2](https://github.com/openvinotoolkit/openvino.genai/blob/releases/2026/2/src/cpp/include/openvino/genai/scheduler_config.hpp)
- **The override.** `get_latency_oriented_scheduler_config()` sets `max_num_batched_tokens = std::numeric_limits<size_t>::max(); // don't limit total batch size` and `enable_prefix_caching = true; // for better TTFT in chat scenarios` (utils.cpp ~L808 @releases/2026/2). LLMPipeline uses it as the fallback when the user passes no scheduler_config. — [utils.cpp @releases/2026/2](https://github.com/openvinotoolkit/openvino.genai/blob/releases/2026/2/src/cpp/src/utils.cpp); [llm/pipeline.cpp](https://github.com/openvinotoolkit/openvino.genai/blob/releases/2026/2/src/cpp/src/llm/pipeline.cpp)
- **Intel on batch-token limits.** "The default is already low, so reducing it is usually not the first optimization for long prompts. For low-concurrency or single-client long-context workloads, increasing this value can improve prompt processing and first-token latency." — [managing-igpu-memory-usage.rst](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/openvino-workflow/running-inference/optimize-inference/managing-igpu-memory-usage.rst)
- **Intel on prefix caching.** "Prefix caching can improve performance when OVMS requests repeat the same prompt prefix… Do not tune prefix caching as a primary memory-reduction setting." — [managing-igpu-memory-usage.rst](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/openvino-workflow/running-inference/optimize-inference/managing-igpu-memory-usage.rst)
- **GenAI concept page.** The page for prefix caching is a stub: "This page is a work in progress." — [prefix-caching.md](https://github.com/openvinotoolkit/openvino.genai/blob/master/site/docs/concepts/optimization-techniques/prefix-caching.md)
- **Field evidence of warm-vs-cold distortion.** On Lunar Lake (GenAI 2026.1.0), a reported ~1,960 tok/s Qwen3-14B prefill turned out to be "prefix-cache-warm". The cold harness gave about 595-761 tok/s at 512 tokens, so warm prefill looked roughly 2.6-3.3x faster. This is consistent in kind with our up-to-5.17x residency speedup. — [openvino Discussion #36604](https://github.com/openvinotoolkit/openvino/discussions/36604)
- **NPU has its own prefix caching.** NPUW has `NPUW_LLM_ENABLE_PREFIX_CACHING` with a block size tied to the prefill chunk size ("Prefix caching block size is adjusted to" the chunk size). — [llm_compiled_model.cpp (master)](https://github.com/openvinotoolkit/openvino/blob/master/src/plugins/intel_npu/src/plugin/npuw/llm_compiled_model.cpp)

### Inferences
- The 22.4 s vs 11 s anomaly needs a re-test. Run the append case with `SchedulerConfig(enable_prefix_caching=True, max_num_batched_tokens=<large>)`, and run the cold case with the identical config, before concluding that appending to a cached prefix is inherently slower.
- With 256-token chunks, the 8,500-token append takes about 33 scheduler iterations, each attending over a growing KV cache with all the per-step overhead. A 2x slowdown is plausible from that alone.

### Gaps
- No GitHub issue or benchmark was found that reports appending to a cached prefix being slower than a cold prefill in OpenVINO GenAI.
- The 5.17x residency speedup has no direct external counterpart beyond the anecdotal #36604 warm/cold gap.

## Q5. NPU (NPU 5) MAX_PROMPT_LEN (1024 gives 960 usable, 2048 gives 1984) and ~2x speedup after a Windows Update reboot

### Takeaway
Intel's docs define `MAX_PROMPT_LEN` (default 1024) as the prompt budget and `MIN_RESPONSE_LEN` (default 128) as the response budget. They do **not** document a "minus 64" usable-prompt behavior. The source shows NPUW **rounds both values up to multiples of 64**; it does not subtract 64. So our 960 / 1984 result is **not explained by any found doc or source** and stays an open empirical finding, possibly from chat-template or generation-token reservation. No external source reports NPU speed changing after a Windows Update. However, Intel confirms that the NPU compiles with the **compiler shipped in the driver** by default, so a driver update delivered through Windows Update can plausibly change NPU performance.

### Cited Findings
- **Intel NPU GenAI docs:**
  - "MAX_PROMPT_LEN -- defines the maximum number of tokens that the LLM pipeline can process for the input prompt (default: 1024), MIN_RESPONSE_LEN -- defines the minimum number of tokens that the LLM pipeline can generate in its response (default: 128). The maximum context size for an LLM on NPU is defined as the sum of these two values."
  - Example: "if the input prompt is just 30 tokens, the model can generate up to 1024 + 128 - 30 = 1122 tokens."
  - "OpenVINO 2025.3 has introduced dynamic input prompt support for NPU… NPUW_LLM_PREFILL_CHUNK_SIZE (default: 1024)… DYNAMIC (default since OpenVINO 2025.3)."
  - "In the GenAI LLM chat scenarios, the conversation history is accumulated in the context and may require a larger MAX_PROMPT_LEN."
  - Source: [inference-with-genai-on-npu.rst](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/openvino-workflow-generative/inference-with-genai/inference-with-genai-on-npu.rst); rendered at [docs.openvino.ai NPU with GenAI](https://docs.openvino.ai/2026/openvino-workflow-generative/inference-with-genai/inference-with-genai-on-npu.html)
- **GenAI defaults in code (releases/2026/2).** `MAX_PROMPT_LEN ... value_or(1024u)` and `MIN_RESPONSE_LEN ... value_or(128u)`. — [utils.cpp @releases/2026/2](https://github.com/openvinotoolkit/openvino.genai/blob/releases/2026/2/src/cpp/src/utils.cpp)
- **GenAI stateful-pipeline guard on NPU.** "Stateful LLM pipeline on NPU may only process prompts or hold chat history up to [m_max_prompt_len] tokens… Set the "MAX_PROMPT_LEN" config option to increase the limit." — [pipeline_stateful.cpp (master)](https://github.com/openvinotoolkit/openvino.genai/blob/master/src/cpp/src/llm/pipeline_stateful.cpp)
- **GenAI capacity helper.** It computes KV capacity as `max_prompt_len + min_response_len - max_generation_token_len` with `max_generation_token_len = 1u`. — [utils.cpp (master)](https://github.com/openvinotoolkit/openvino.genai/blob/master/src/cpp/src/utils.cpp)
- **NPUW at tag 2026.2.1.** `uint32_t max_prompt_len = align_to(m_cfg.get<NPUW_LLM_MAX_PROMPT_LEN>(), 64u);` and the same for MIN_RESPONSE_LEN (L751-752): the values are rounded *up* to 64. With chunked prefill, "max_prompt_len = align_to(max_prompt_len, chunk_size)" (master). — [llm_compiled_model.cpp @2026.2.1](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_npu/src/plugin/npuw/llm_compiled_model.cpp)
- **Default chunk size depends on the compiler version.** The 1024 chunk default is set explicitly only "for older compiler versions" (compiler < 7.22). — [llm_compiled_model.cpp (master)](https://github.com/openvinotoolkit/openvino/blob/master/src/plugins/intel_npu/src/plugin/npuw/llm_compiled_model.cpp)
- **Compiler location (2026.2 release notes).** "NPU compiler is now included in the OpenVINO™ distribution package as a separate library. This is a preview… By default, the NPU will continue using compiler-in-driver." — [release-notes-openvino.rst](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/about-openvino/release-notes-openvino.rst)
- **Known issue in 2026.3 (ID 191130).** "Qwen3 LLM fails to load on NPU. Qwen3 compilation fails for context sizes greater than 8K. As a workaround, switching compilation to CID mode through the compiler in the driver should resolve the problem." — [release-notes-openvino.rst (2026.3)](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/about-openvino/release-notes-openvino.rst)
- **NPU first-token cost is fixed.** An Intel maintainer in openvino.genai #1882: "NPU has a 1024-token compute budget for the 1st token, that's why it shows a longer time." Measured on Lunar Lake with 2025.0: NPU about 9.4 s vs CPU about 6.1 s for 100 tokens, Llama-3.2-3B. — [openvino.genai #1882](https://github.com/openvinotoolkit/openvino.genai/issues/1882)
- **Driver sensitivity.** Maintainers in #1882 asked which NPU driver was used (one commenter was on 32.0.100.3717). — [openvino.genai #1882](https://github.com/openvinotoolkit/openvino.genai/issues/1882)
- **NPU memory budget.** On a Lunar Lake 258V (OpenVINO 2026.1), Llama-3.1-8B "crashed mid-prompt after processing a 61-token prompt", which was attributed to the "NPU plugin per-graph budget". — [elizaOS RFC #7633](https://github.com/elizaOS/eliza/issues/7633)

### Inferences
- Since the NPU compiler comes from the driver by default, a Windows Update that installs a newer NPU driver changes both the compiler and the runtime. A roughly 2x speed change with the same IR and settings is therefore plausible. Record the NPU driver version before and after the update to attribute it. Also clear `CACHE_DIR` blobs, because a cached blob compiled by the old driver may be recompiled.
- The 64-token gap (1024 gives 960, 2048 gives 1984) is exactly one 64-token alignment unit. The only 64-specific constant found is the round-up alignment, so this alignment may be indirectly involved, along with chat-template tokens added by GenAI. This is unconfirmed.

### Gaps
- No documentation, issue or source line was found that states "usable prompt = MAX_PROMPT_LEN − 64". It needs a minimal repro, ideally a raw `input_ids` tensor with no chat template, and possibly a GitHub issue.
- No external report quantifies NPU 5 (Panther Lake) LLM performance with OpenVINO GenAI, and none reports a speed change after a Windows Update.

## Q6. Arc B390 iGPU: CL_OUT_OF_RESOURCES during a 4,000-token GPU generation with an NPU model also loaded, then a teardown crash (0xC0000409)

### Takeaway
**Partially corroborated.** CL_OUT_OF_RESOURCES (OpenCL error -5) on Intel iGPUs in OpenVINO 2026.x is a known, recurring failure, including on an Arc B390. Field reports tie it to model-architecture-specific kernels (Qwen3.5 hybrid attention), large hidden_dim × seq_len, and multi-device/pipeline-parallel setups rather than plain memory exhaustion. One report shows OVMS staying wedged after the error. No report specifically ties it to an NPU model being co-resident, and the 0xC0000409 teardown crash has no external match.

### Cited Findings
- **openvino #36151.** Core Ultra 9 275HX, Arc iGPU (Xe2), 32 GB, Windows 11, OpenVINO 2026.2.0, driver 32.0.101.8826.
  - Error: `[GPU] CL_OUT_OF_RESOURCES exception.` / `clWaitForEvents failed with -14`.
  - Qwen3.5-4B INT8 fails at about 1,400 characters, and the failure "scales with hidden_dim × seq_len".
  - Qwen3-4B INT8 (standard transformer) "works at all lengths".
  - None of these GPU properties helped: SDPA optimization, large allocations, KV precision u4/u8, f32.
  - A follow-up on an **Arc B390 (Xe3, 24 GB, OpenVINO 2026.5 dev)** hit `errcode -5` / "could not execute a primitive" on a ~31,448-token prompt with Qwen3.8-27B INT4. Switching KV to u8 did not help.
  - Another commenter found that `GPU_ENABLE_LARGE_ALLOCATIONS=True` causes `clWaitForEvents -14` on INT4 VLMs.
  - Source: [openvino #36151](https://github.com/openvinotoolkit/openvino/issues/36151)
- **Other CL_OUT_OF_RESOURCES issues (from search titles; bodies not read):**
  - "[GPU][Intel Arc B580][Gemma4] CL_OUT_OF_RESOURCES with OpenVINO 2026.2 nightly" — [openvino #35723](https://github.com/openvinotoolkit/openvino/issues/35723)
  - "OpenVINO 2026.2 CL_OUT_OF_RESOURCES, Qwen 3.6 MODEL_DISTRIBUTION_POLICY: PIPELINE_PARALLEL" — [openvino #36187](https://github.com/openvinotoolkit/openvino/issues/36187)
  - Same for 2026.4 with Qwen 3.8 — [openvino #37450](https://github.com/openvinotoolkit/openvino/issues/37450)
  - "Permanent LLMExecutor wedge after CL_OUT_OF_RESOURCES on discrete GPU: servable stays AVAILABLE but every request returns 400 until restart" — [model_server #4469](https://github.com/openvinotoolkit/model_server/issues/4469)
  - "[Bug]: GPU plugin can't finish correctly" — [openvino #25141](https://github.com/openvinotoolkit/openvino/issues/25141)
- **Intel iGPU memory guide** ([managing-igpu-memory-usage.rst](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/openvino-workflow/running-inference/optimize-inference/managing-igpu-memory-usage.rst)):
  - It lists symptoms including "GPU allocation errors where one buffer exceeds the device's maximum single-allocation size."
  - It exposes `GPU_DEVICE_TOTAL_MEM_SIZE` ("for iGPU, this reports host memory size") and `GPU_DEVICE_MAX_ALLOC_MEM_SIZE`.
  - "GPU_ENABLE_LARGE_ALLOCATIONS … On Xe2 and newer platforms, this option is enabled by default" (this covers Core Ultra Series 3 and Arc B-series).
  - "For integrated Intel® Arc™ GPUs on Windows 10 or 11 systems with more than 10 GB of system memory… shared memory allocation can be increased in Intel Graphics Software under Graphics > General > Shared GPU Memory Override."
- **Lunar Lake co-residency study (GenAI 2026.1.0 / OVMS 2026.2).** Shared GPU Memory override at 87% gives a 27.3 GiB iGPU window. The author says the default window "will not hold a resident 14B plus a second model". Under concurrent SDXL, a resident Qwen3-14B fell to about 1% throughput (19.8 to 0.22 tok/s), and the author attributes this to "execution-unit occupancy / compute scheduling", not bandwidth. No OOM or CL errors occurred, and NPU co-residency was not tested (NPU at 0 W). — [openvino Discussion #36604](https://github.com/openvinotoolkit/openvino/discussions/36604)
- **NPU and GPU share LPDDR.** The NPU plugin's per-graph memory budget was exceeded by an 8B model on Lunar Lake. That shows the NPU also draws on the shared pool, but it was not tested alongside a GPU workload. — [elizaOS RFC #7633](https://github.com/elizaOS/eliza/issues/7633)

### Inferences
- Our B390 failure has a likely contributing cause that #36151 rules out for its own case: with an NPU model loaded, the shared allocation window available to the GPU shrinks. But #36151 shows that CL_OUT_OF_RESOURCES on Xe2/Xe3 can also be a kernel or primitive failure that has nothing to do with total memory, and on a 64 GB machine at 4k tokens with a 4B model, plain exhaustion is unlikely. Re-run the same 4k GPU generation with no NPU model loaded, and log `GPU_DEVICE_MAX_ALLOC_MEM_SIZE`, the driver version and the Shared GPU Memory Override value, to tell the two apart.
- The teardown crash fits a pattern of the GPU plugin not shutting down cleanly after an OpenCL error (#25141 title; #4469 "permanent wedge"). The specific code 0xC0000409 is a Windows fail-fast / stack-buffer-overrun status (general Windows knowledge, not sourced here) and is unconfirmed for OpenVINO.

### Gaps
- No issue or doc reports CL_OUT_OF_RESOURCES caused specifically by GPU+NPU co-residency on Intel unified-memory SoCs.
- No issue matching a 0xC0000409 exit on OpenVINO teardown was found. The bodies of #25141, #35723, #36187, #37450 and #4469 were not read; only their titles were seen.
- No Phoronix, Chips and Cheese, Tom's Hardware or Notebookcheck coverage of OpenVINO GenAI on Panther Lake or the Arc B390 with these failure modes was found in this sweep.
