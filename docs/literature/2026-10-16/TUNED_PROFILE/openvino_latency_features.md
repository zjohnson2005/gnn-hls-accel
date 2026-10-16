# OpenVINO GenAI / GPU-plugin features for a stronger "tuned" Qwen3-4B INT4 agent profile on Xe3 iGPU (2026.2.x, with 2026.1/2026.3 deltas)

**Method.** Most claims come from reading source at release tags. I cloned these tags in this session:

- openvino.genai `2026.2.1.0` (commit 7dea045), `2026.3.1.0` (56d9685) and `2026.1.2.0` (adc69c5).
- openvino `2026.2.1` (ede283a), sparse checkout of `src/plugins/intel_gpu`, `src/inference` and `docs`.
- The 2026.3.1 release-notes `.rst`, plus the 2026.3.1 and master copies of the GPU `execution_config.cpp`.

Line numbers refer to those tags. The GitHub REST API was not reachable (no linked account), so I could not search issues or PRs systematically; issues below come from web search only. HuggingFace raw files were blocked by the proxy, so I took the Qwen3 chat template from the copy embedded in GenAI's test data.

**Base URLs.**
- G = https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/
- G3 = https://github.com/openvinotoolkit/openvino.genai/blob/2026.3.1.0/
- O = https://github.com/openvinotoolkit/openvino/blob/2026.2.1/
- RN = https://github.com/openvinotoolkit/openvino/blob/2026.3.1/docs/articles_en/about-openvino/release-notes-openvino.rst (line numbers below are from the 2026.3.1 file, which contains the 2026.3, 2026.2, 2026.1 and 2026.0 sections: 2026.3 = L19-308, 2026.2 = L309-537, 2026.1 = L538-704, 2026.0 = L705+)

**Back-of-envelope model facts (used in the inferences below).**
- Qwen3-4B has 36 layers, 32 Q heads and 8 KV heads, and 32,768 native context (131,072 with YaRN) — [Qwen3-4B model card](https://huggingface.co/Qwen/Qwen3-4B).
- head_dim = 128 is from my prior knowledge of the HF config. I could not verify it this session because the config.json fetch was blocked.
- KV per token is therefore 36 × 8 × 128 × 2 = 73,728 values:
  - f16: about 144 KiB/token (10k tokens ≈ 1.4 GiB; 32k ≈ 4.5 GiB)
  - i8: about 72 KiB/token plus scales (32k ≈ 2.3 GiB)
  - u4: about 36 KiB/token plus scales (32k ≈ 1.1 GiB)

---

## 1. Sparse attention for prefill (TriShape, XAttention), KV-cache eviction/compression (SnapKV/H2O/KVCrush/Adaptive R-KV), KV-cache rotation

### Takeaway
All of these exist in 2026.2.1 as `SchedulerConfig` fields (`use_sparse_attention` + `SparseAttentionConfig`, `use_cache_eviction` + `CacheEvictionConfig`) and run on GPU. None is a good fit for the measured agent workload (median about 3.5k input tokens, mostly prefix-cache hits, decode-dominated turns), for three reasons:

- **XAttention.** It is a Xe2/Xe3, CM-kernel-only preview. It forces a 256-token KV block, supports only f16/i8 KV, and is disabled under speculative decoding. Its own paper reports about 52% attention density at 4k tokens, so there is little to skip at agent-scale prompts.
- **TriShape.** It only sparsifies across scheduler chunks, so with the default unlimited `max_num_batched_tokens` (one chunk per prompt) it does nothing.
- **Cache eviction.** It does not speed up prefill and does not bound the prompt's KV. On GPU it also turns on attention-score outputs, which (per source) disables the XMX micro-SDPA prefill kernel.

The candidate worth an A/B is XAttention for cold, long (10k+ token) prompts only. Treat it as a TTFT-at-depth lever with an accuracy check, not as a default.

### Cited Findings

**API and availability (2026.2.1)**
- `enum class SparseAttentionMode { TRISHAPE, XATTENTION }`. `SparseAttentionConfig` fields and defaults:
  - `num_last_dense_tokens_in_prefill = 100`
  - `num_retained_start_tokens_in_cache = 128`
  - `num_retained_recent_tokens_in_cache = 1920`
  - `xattention_threshold = 0.8`
  - `xattention_block_size = 64`
  - `xattention_stride = 8`, documented as: "if full (dense) attention takes M time … the importance score calculation would be taking `M / xattention_stride` time as overhead."
  — [G src/cpp/include/openvino/genai/sparse_attention.hpp L12-83](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/sparse_attention.hpp#L12-L83)
- Enablement per the docs: "set `.use_sparse_attention` field to `True` in the `openvino_genai.SchedulerConfig`"; e.g. `SchedulerConfig(use_sparse_attention=True, sparse_attention_config=SparseAttentionConfig(mode=SparseAttentionMode.XATTENTION))`. — [G site/docs/concepts/optimization-techniques/sparse-attention-prefill.md L18-59](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/site/docs/concepts/optimization-techniques/sparse-attention-prefill.md)
- The same doc says sparse prefill does **not** lower memory: "do not lead to decreased maximum and average memory consumption … but they do lead to the decreased total generation and first token latency times". — same doc L8-13
- **TriShape works across scheduler chunks.** "the full prefill stage for each sequence may take several time steps … The prompt processing occurs as usual until at least two KV cache blocks have been completely filled". The skipper is applied only when `m_apply_sparse_attention_mask = m_config.use_sparse_attention && mode == TRISHAPE` (scheduler.hpp L320-326). — [sparse-attention-prefill.md L28-45](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/site/docs/concepts/optimization-techniques/sparse-attention-prefill.md); [G scheduler.hpp L320-330](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/scheduler.hpp#L320-L330)
- **XAttention threshold scheduling.** `_schedule_xattention_threshold` returns 0.0 (dense) for decode and for a chunk where `num_processed_tokens_after_this_chunk < prompt_len && (prompt_len - …) < num_last_dense_tokens_in_prefill`. Otherwise it returns `xattention_threshold`. — [G scheduler.hpp L667-685](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/scheduler.hpp#L667-L685)

**XAttention on the GPU plugin (2026.2.1)**
- **Hardware and compiler gate.** XAttention throws if unsupported: "[GPU] XAttention is not supported by your current GPU architecture or IGC version. Please either disable XAttention … or switch to a GPU with Xe2/Xe3 architecture and ensure the latest IGC is installed." The checks are `info.supports_immad` (XMX) and `check_cm_jit_support` (IGC CM front end; warning text: "ensure clangFEWrapper for CM is available (check CM_FE_DIR or LD_LIBRARY_PATH on Linux)"). — [O src/plugins/intel_gpu/src/plugin/transformations_pipeline.cpp L694-741](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/plugin/transformations_pipeline.cpp#L694-L741)
- **Separate KV layout.** "KVCache layout with XAttention - k: [num_blocks, num_kv_heads, block_size(256), head_size]". With BY_TOKEN key mode the KV precision is forced to i8 (L743-772). `block_size = 16; block_size_xattn = 256`. GenAI detects this and sets `gpu_block_size_xattn = 256`. — [O transformations_pipeline.cpp L743-772](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/plugin/transformations_pipeline.cpp#L743-L772); [O include/intel_gpu/primitives/paged_attention.hpp L47-48](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/include/intel_gpu/primitives/paged_attention.hpp#L47-L48); [G kv_cache_manager.hpp L96-110](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/cache/kv_cache_manager.hpp#L96-L110)
- **The CM PagedAttention kernel is used only with XAttention, and it accepts only f16 Q and f16/i8 KV cache** (`supported_kv_types = { f16, i8 }`). It requires `kv_head_size % 16 == 0` and `supports_immad`. Comment: "CM optimized for systolic-array architectures". — [O src/plugins/intel_gpu/src/graph/impls/cm/paged_attention.hpp L24-82](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/graph/impls/cm/paged_attention.hpp#L24-L82)
- **The GPU ignores GenAI's default `xattention_block_size=64`.** `get_xattn_block_size` returns 128 on pre-Xe2 hardware; on Xe2+ it accepts only 128 or 256 and otherwise uses 256: `(xattn_block_size == 128 || == 256) ? xattn_block_size : block_size_256`. — [O impls/cm/paged_attention.cpp L278-304](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/graph/impls/cm/paged_attention.cpp#L278-L304)
- **Bypass rule.** XAttention estimation is skipped when threshold ≥ 1.0 (if bypass is allowed) or when `q_len < STRIDE`. — [O impls/cm/paged_attention_gen.cpp L112-123](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/graph/impls/cm/paged_attention_gen.cpp#L112-L123)
- **Speculative decoding disables XAttention.** `bool allow_xattention = false;` in `SpeculativeDecodingImpl::init_speculative_models`. — [G speculative_decoding/continuous_batching/fast_draft_strategy.cpp L38](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/speculative_decoding/continuous_batching/fast_draft_strategy.cpp#L29-L50)

**Release-note history (XAttention)**
- 2026.0: "Preview support for XAttention on Intel's Xe2/Xe3 architecture to improve TTFT performance." (RN L748; also L741 for GenAI)
- 2026.1: "XAttention … now initially supported on Intel's Xe1 architecture … (Xe2/3 is already supported). Performance has been improved for low threshold scenarios." (RN L591). CPU: "XAttention now maintains proper accuracy when enabled, resolving previous accuracy issues." (RN L581)
- 2026.2: "Enabled by-channel INT8 KV cache quantization by default for GPU XAttention (sparse attention), delivering improved accuracy" (RN L360); "Preview: Enhanced XAttention accuracy on CPUs and GPUs through by-channel INT8 KV-cache quantization" (RN L330)

— [RN](https://github.com/openvinotoolkit/openvino/blob/2026.3.1/docs/articles_en/about-openvino/release-notes-openvino.rst); [OpenVINO 2026.2 blog (Medium)](https://medium.com/openvino-toolkit/openvino-2026-2-more-models-gpu-optimizations-and-enhanced-agentic-support-b962b0c8e898), which says XAttention keeps its "core advantage of reduced time-to-first-token latency" but gives **no TTFT numbers**.

**XAttention paper: magnitude and density**
- "up to 13.5× acceleration in attention computation", reported "at 256K tokens".
- Density at stride 8 is 52.16% at 4k, 43.77% at 8k and 27.49% at 16k (Table 5).

— [XAttention, arXiv 2503.16428](https://arxiv.org/html/2503.16428v1)

**Cache eviction (2026.2.1)**
- `CacheEvictionConfig` defaults: `m_start_size = 32`, `m_recent_size = 128`, `m_max_cache_size = 672`, `aggregation_mode = NORM_SUM`, `apply_rotation = false`, `snapkv_window_size = 8`. The SnapKV window is described as "following the SnapKV article approach … Setting this to 0 disables the SnapKV score aggregation". `ADAPTIVE_RKV` and `KVCrushConfig` are also available. — [G src/cpp/include/openvino/genai/cache_eviction.hpp L15-224](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/cache_eviction.hpp)
- The eviction doc says:
  - "No eviction is done during prefill stage, therefore no speedups would be achieved during the prefill using cache eviction alone and the reduction in maximum KV cache consumption … is limited from below by the amount of KV cache blocks occupied by the full prompt."
  - Gains appear "only … during the generation stage and [are] most noticeable for longer generation lengths."
  - Rotation limitation: "only targeted for the regular, linear LLaMa-like RoPE … may degrade accuracy on models that use other RoPE schemes."
  - It shows KVCrush/SnapKV LongBench accuracy tables, but no latency tables.

  — [G site/docs/concepts/optimization-techniques/kvcache-eviction-algorithm.md L9-79](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/site/docs/concepts/optimization-techniques/kvcache-eviction-algorithm.md)
- **What eviction switches on.** With `use_cache_eviction`, GenAI builds the ModelRunner with `collect_attention_scores = true` and `is_aggregate_attention_scores = true`, and rotation inputs if `apply_rotation`. — [G continuous_batching/pipeline_impl.cpp L66-85, L194-226](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/pipeline_impl.cpp#L66-L226)
- **The GPU plugin marks `has_score_aggregation` only when the PA op has more than one output** (i.e. when the scores output exists). `supports_micro_sdpa()` then returns false: `if (desc->has_scores_output() || desc->has_score_aggregation) { return false; }`. — [O plugin/ops/paged_attention.cpp L91-94](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/plugin/ops/paged_attention.cpp#L91-L94); [O impls/ocl_v2/sdpa/paged_attention_opt.cpp L1351-1394](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/graph/impls/ocl_v2/sdpa/paged_attention_opt.cpp#L1351-L1394)
- **Prefix caching interplay.** I found no assertion or warning in 2026.2.1 GenAI that forbids combining `use_cache_eviction` with `enable_prefix_caching` (grep of `src/cpp/src` for both terms together found nothing). — [G continuous_batching/](https://github.com/openvinotoolkit/openvino.genai/tree/2026.2.1.0/src/cpp/src/continuous_batching)

**2026.3 deltas**
- `sparse_attention.hpp` and `cache_eviction.hpp` are unchanged between 2026.2.1.0 and 2026.3.1.0 (diff empty). — [G3 sparse_attention.hpp](https://github.com/openvinotoolkit/openvino.genai/blob/2026.3.1.0/src/cpp/include/openvino/genai/sparse_attention.hpp)
- 2026.3 CPU notes add "Enabled Adaptive R-KV support". — RN L85

### Inferences
- **TriShape is a no-op under the runtime default.** With `max_num_batched_tokens = SIZE_MAX` the whole prompt is one scheduler step, so the "two filled blocks before sparsifying" condition never occurs across chunks. To get any TriShape effect you must chunk prefill, which itself adds per-chunk overhead on an iGPU. TriShape also retains only start + recent (128 + 1920) tokens for most of the body, a real accuracy risk for tool-use prompts that reference early tool schemas. **Not recommended.**
- **XAttention can act within a single chunk** (the CM kernel estimates blocks inside the multi-token stage). Its likely payoff is limited to cold prefills of about 10k+ tokens:
  - At 4k, about half the attention blocks are still needed (paper Table 5).
  - At 3.5-12k on a 4B model, attention is a minority of prefill FLOPs next to the QKV/MLP GEMMs.
  - The agent's warm turns prefill only a few hundred new tokens after a prefix-cache hit.
  - For the dense-tail threshold logic, single-chunk prefill means `num_processed_after_this_chunk == prompt_len`, so the dense-tail branch is never taken and the threshold applies to the whole prompt. Accuracy may then differ from the documented "dense tail" behavior. This needs verification.
- **XAttention costs and conflicts:**
  - The 256-token KV block (vs 16) coarsens cache allocation, though GenAI does restore partial blocks for prefix caching.
  - It cannot be combined with u4 KV (CM kernel accepts only f16/i8), which matters on 2026.3 where u4 becomes the auto default for INT4-weight PA models.
  - It cannot be combined with speculative decoding.
- **Cache eviction is counter-productive for latency here.** It does not reduce prefill (and so not TTFT) or the prompt's KV footprint. On GPU it enables score outputs, which disables the XMX micro-SDPA prefill path, so prefill likely gets slower. Decode savings are minimal at about 3.5k context with 130-255 generated tokens, because decode on a 4B INT4 model is dominated by streaming the weights, not attention over 3.5k tokens. Its only clear use is capping KV memory for very long generations.

### Gaps
- No primary-source TTFT numbers for OpenVINO XAttention on Xe2/Xe3 at any context length. Release notes and the blog are qualitative, and the openvino.genai GitHub issues/PR search was unavailable.
- Not verified empirically:
  - whether XAttention on 2026.2.1 needs CM front-end libraries absent from standard Windows/Linux driver installs on Panther Lake;
  - whether the "single chunk ⇒ no dense tail" reading is correct.
- No source on how prefix-cache restoration behaves when eviction has removed blocks of a cached prefix (correctness or hit-rate implications).

---

## 2. Dynamic quantization of activations (DYNAMIC_QUANTIZATION_GROUP_SIZE) and INFERENCE_PRECISION_HINT on GPU

### Takeaway
On XMX GPUs (Xe2/Xe3) the GPU plugin already enables per-token INT8 dynamic quantization of FullyConnected activations by default (`group_size = UINT64_MAX` = per-token). It only applies when the token batch exceeds 64, so it affects prefill (TTFT) and not single-token decode. `INFERENCE_PRECISION_HINT` defaults to f16 on GPU. The runtime default is therefore already the "fast" setting:

- Setting `DYNAMIC_QUANTIZATION_GROUP_SIZE=0` is the documented way to disable it, for accuracy A/B only.
- `EXECUTION_MODE_HINT=ACCURACY` or `INFERENCE_PRECISION_HINT=f32` would slow inference.

There is no lever here that beats the default for latency.

### Cited Findings
- **Options and defaults in the GPU config:**
  - `inference_precision` default `ov::element::f16`, valid values `{ f16, f32, dynamic }`
  - `dynamic_quantization_group_size` default 0 (unfinalized)
  - `dynamic_quantization_group_size_max` default UINT64_MAX
  - internal `asym_dynamic_quantization` false
  - internal `dynamic_quantization_threshold` 64: "Apply dynamic quantization only when batch size is larger than this value in OneDNN"
  - internal `use_onednn` false (finalized to true on immad)

  — [O include/intel_gpu/runtime/options.inl L11, L30-31, L53, L57-60](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/include/intel_gpu/runtime/options.inl#L11-L60)
- **Finalization.** `if (!is_set_by_user(ov::intel_gpu::use_onednn) && info.supports_immad) { m_use_onednn = true; }` … `if (!is_set_by_user(ov::hint::dynamic_quantization_group_size) && get_dynamic_quantization_group_size() == 0) { if (info.supports_immad) m_dynamic_quantization_group_size = std::numeric_limits<uint64_t>::max(); else m_dynamic_quantization_group_size = 32; }`. Model rt_info `runtime_options/DYNAMIC_QUANTIZATION_GROUP_SIZE` can override (L173-174). — [O src/runtime/execution_config.cpp L173-174, L337-349](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L337-L349)
- **The pass runs only on XMX with oneDNN:** `if (device_info.supports_immad && config.get_use_onednn()) { … DynamicQuantizeFullyConnected … }`.
  - For i8/u8 weights on Xe2+ the group becomes 128 (`use_gs128_for_int8_per_token = arch >= xe2 && group_dyn_quan_allowed`). For 4-bit weights per-token stays (ShouldUseGs128 applies only to `is_wei_i8u8` or linear-attention models).
  - It is skipped for f32 inputs and rank > 3.

  — [O transformations_pipeline.cpp L1591-1690](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/plugin/transformations_pipeline.cpp#L1591-L1690); [O dynamic_quantize_fully_connected.hpp L15-17](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/plugin/transformations/dynamic_quantize_fully_connected.hpp)
- **Group size 0 disables it:** `if (adj_group_size != UINT64_MAX && (adj_group_size == 0 || …)) return false;`. Group sizes < 32 are also rejected. — [O dynamic_quantize_fully_connected.cpp L82-91](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/plugin/transformations/dynamic_quantize_fully_connected.cpp#L82-L91)
- **Batch threshold at runtime:** `if (node.get_program().get_config().get_dynamic_quantization_threshold() >= input_batch)` skips dyn-quant. — [O src/graph/dynamic_quantize.cpp L36](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/graph/dynamic_quantize.cpp#L36)
- **Official doc wording:**
  - "**Dynamic quantization** … improves inference latency and throughput of LLMs, though it may cause insignificant deviation in generation accuracy … Larger group sizes lead to faster inference but lower accuracy."
  - "On Intel CPU and Intel GPU, dynamic quantization is enabled **by default** … For Intel GPU with XMX support, the only supported group size is ``innermost axis`` and it is turned on **by default**."
  - "To disable … **(Primary Option)** Set ``DYNAMIC_QUANTIZATION_GROUP_SIZE`` to the ``0`` value", or switch to ACCURACY mode.

  — [O docs/articles_en/openvino-workflow-generative/inference-with-optimum-intel.rst L226-276](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/docs/articles_en/openvino-workflow-generative/inference-with-optimum-intel.rst#L226-L276)
- **ACCURACY mode** keeps the model's precision, and "Dynamic Quantization is disabled in this mode." — [O precision-control.rst L38-46](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/docs/articles_en/openvino-workflow/running-inference/optimize-inference/precision-control.rst)
- **GenAI does not set any of these properties itself.** A grep of `src/cpp/src` at 2026.2.1.0 for DYNAMIC_QUANTIZATION / KV_CACHE_PRECISION / INFERENCE_PRECISION finds only image-generation and GGUF code. — [G src/cpp/src](https://github.com/openvinotoolkit/openvino.genai/tree/2026.2.1.0/src/cpp/src)
- **Versions.** 2026.3.1 and master keep the same immad default (`m_dynamic_quantization_group_size = UINT64_MAX` at execution_config.cpp L351 in 2026.3.1 and L371 on master). — [openvino 2026.3.1 execution_config.cpp](https://github.com/openvinotoolkit/openvino/blob/2026.3.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp)

### Inferences
- In the measured runs, prefill already used INT8 activations × INT4 weights on XMX via oneDNN. Single-token decode (and 6-token speculative verification) is below the 64-token threshold, so it ran f16 activations with INT4 weight decompression. Neither knob offers a further latency gain.
- If an accuracy audit is needed, an A/B with `DYNAMIC_QUANTIZATION_GROUP_SIZE=0` isolates the dyn-quant contribution to TTFT. Expect slower prefill. I found no published magnitude.

### Gaps
- No published OpenVINO measurement of TTFT or accuracy with dyn-quant on vs off for Xe2/Xe3. The docs claim "insignificant deviation" without numbers.

---

## 3. Speculative decoding (draft model, EAGLE-3) and prompt-lookup decoding in the CB pipeline on GPU

### Takeaway
2026.2.1 supports three draft methods on GPU through the continuous-batching (PA) backend, all under the latency-oriented SchedulerConfig with prefix caching on:

- **(a) Classic draft model:** `draft_model(path, device)` plus `num_assistant_tokens` (default 5) or `assistant_confidence_threshold`.
- **(b) EAGLE-3:** `draft_model(..., eagle3_mode=True)`; needs an EAGLE-3 head trained for the target; greedy-only streaming; Top-K/tree sampling arrives in 2026.3.
- **(c) Prompt-lookup decoding:** `prompt_lookup=True` plus `num_assistant_tokens` and `max_ngram_size`.

Published Intel iGPU data shows modest gains for classic drafts: Qwen3-8B with a Qwen3-0.6B draft was 1.3× (1.4× with a pruned draft) on Lunar Lake. A user-reported Qwen3-14B run got 1.35× with a CPU draft (NAT=3) and a slowdown with an NPU draft. Gains for a 4B target will be smaller, since the 0.6B draft is roughly 15% of the target's cost.

Prompt lookup is draft-free and copies n-gram continuations from prompt + generated text, so it targets exactly the tool-call/argument copying spans. Two caveats:

- Candidates are padded to `num_assistant_tokens` even when no match is found, so every step verifies K+1 tokens.
- I found no published OpenVINO numbers for it.

### Cited Findings

**Dispatch and enablement**
- **CB dispatch:**
  - `if (is_prompt_lookup_enabled) { OPENVINO_ASSERT(draft_model_descr.model == nullptr, "Speculative decoding and prompt lookup decoding are mutually exclusive"); m_impl = std::make_shared<PromptLookupImpl>(…) }`
  - `else if (draft … && eagle_rt_info.eagle3_mode) { m_impl = std::make_shared<Eagle3DecodingImpl>(…) }`
  - `else if (draft …) { m_impl = std::make_shared<SpeculativeDecodingImpl>(…) }`

  — [G src/cpp/src/continuous_batching/pipeline.cpp L54-95](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/pipeline.cpp#L54-L95)
- **Draft model or `prompt_lookup=true` forces the PA/CB path** in LLMPipeline ("explicitly requires PA"). On non-x86/ARM it throws "Speculative decoding requires PagedAttention operation support on non-NPU devices". The stateful (SDPA) speculative path asserts: "Stateful FastDraft and Stateful Eagle3 Speculative Decoding require NPU". — [G utils.cpp L815-851](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L815-L851); [G llm/pipeline.cpp L164-183](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/llm/pipeline.cpp#L164-L183)
- **Draft scheduler.**
  - If the draft's SchedulerConfig is default, the main config is reused and `cache_size` is split proportionally to KV hidden sizes ("split KV cache to 2 caches for main and draft models").
  - Otherwise `dynamic_split_fuse` and `max_num_batched_tokens` are copied from main.
  - Tokenizers must match ("Tokenizers for draft and main models are different!").
  - XAttention is disabled (`allow_xattention = false`).

  — [G speculative_decoding/continuous_batching/fast_draft_strategy.cpp L29-120](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/speculative_decoding/continuous_batching/fast_draft_strategy.cpp#L29-L120)

**GenerationConfig fields**
- Fields: `assistant_confidence_threshold = 0.f; num_assistant_tokens = 0; max_ngram_size = 0;`.
- Doc: "ContinuousBatching backend for Speculative Decode uses `num_assistant_tokens` as is … If `num_assistant_tokens` is not set, it defaults to `5`". `default_num_assistant_tokens = 5`.
- `is_prompt_lookup()` is `max_ngram_size > 0 && num_assistant_tokens > 0`. The two assistant parameters are mutually exclusive.

— [G generation_config.hpp L618-623, L676-678](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/generation_config.hpp#L618-L678); [G generation_config.cpp L268-277, L354-360](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/generation_config.cpp#L268-L360); [G speculative_decoding/continuous_batching/pipeline_impl.hpp L13](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/speculative_decoding/continuous_batching/pipeline_impl.hpp#L13)

**EAGLE-3**
- **Enablement.** The draft properties take `eagle3_mode` and an optional `hidden_layers_list`. The default layers are `{ 2, num_decoder_layers / 2, num_decoder_layers - 3 }`, read from the main model's config.json ("Eagle3 is expected to provide exactly three layers").
- **CB restrictions.** "Eagle3 only supports num_assistant_tokens (assistant_confidence_threshold must be 0.f)" and "Eagle3 streaming only supports batch size=1 with greedy".

— [G speculative_decoding/eagle3_model_transforms.cpp L26-72](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/speculative_decoding/eagle3_model_transforms.cpp#L26-L72); [G speculative_decoding/continuous_batching/eagle3_strategy.cpp L138-157](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/speculative_decoding/continuous_batching/eagle3_strategy.cpp#L138-L157)

**Prompt lookup**
- **Sample:** `LLMPipeline(model_dir, device, prompt_lookup=True)`; `config.num_assistant_tokens = 5`; `config.max_ngram_size = 3`. — [G samples/python/text_generation/prompt_lookup_decoding_lm.py](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/samples/python/text_generation/prompt_lookup_decoding_lm.py)
- **Algorithm:**
  - The search space is `full_input_ids = prompt + generated_tokens`.
  - It tries n-gram sizes from `max_ngram_size` down to 1 and returns the continuation after the **first (earliest)** match.
  - "Padding candidate tokens to maintain consistent shape … `candidates.push_back(PADDING_TOKEN_ID)`" up to `num_assistant_tokens`.

  — [G prompt_lookup/continuous_batching_for_prompt_lookup.cpp L22-81](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/prompt_lookup/continuous_batching_for_prompt_lookup.cpp#L22-L81)

**Benchmarks**
- **Intel/HF blog (Lunar Lake Core Ultra 7 268V, Arc 140V, 32 GB, OpenVINO 2025.2).** Qwen3-8B INT4 target with a Qwen3-0.6B INT8 draft on `device="GPU"`: "an average of 1.3× speedup over the baseline". A depth-pruned 6-layer-removed draft gives about 1.4×. The workload was a smolagents agent (web search + python-pptx). — [HF blog: Accelerating Qwen3-8B Agent on Intel Core Ultra](https://huggingface.co/blog/intel-qwen3-agent)
- **Community characterization (Lunar Lake 258V, Arc 140V, OpenVINO/GenAI 2026.1).** Qwen3-14B INT4 on GPU with a Qwen3-0.6B INT4 draft:
  - GPU-only baseline 12.2 tok/s.
  - CPU draft NAT=3: 16.5 tok/s (1.35×, acceptance 0.40). NAT=5: 14.7 tok/s (1.20×).
  - NPU draft: 0.55-0.74×.
  - Standalone 0.6B draft on GPU: 150 tok/s.
  - No GPU-draft speculative run was reported, and no maintainer replied.

  — [openvino Discussion #36484](https://github.com/openvinotoolkit/openvino/discussions/36484)
- **DFlash (block-parallel drafter conditioned on target hidden states) on Panther Lake Core Ultra X7 368H / Arc B390, OpenVINO 2026.3.0.** Dense Qwen3.5-9B: 2.8-3.4×. Qwen3.6-35B-A3B: 1.3-2.2×, with higher acceptance on HumanEval/GSM8K ("structured, predictable outputs"). Limits: "text-only inputs, one request at a time, and greedy sampling only. It does not yet support prefix caching". DFlash is not in a 2026.2/2026.3 GenAI release: "slated for upcoming OpenVINO.GenAI releases". — [HF blog: Accelerating Qwen3.6 on Core Ultra Series 3 with DFlash](https://huggingface.co/blog/ofirzaf/intel-dflash-ptl)

**Release-note history**
- 2026.0 section: "OpenVINO™ GenAI and OpenVINO™ Model Server introduces EAGLE-3 speculative decoding … on Intel CPUs and GPUs. Validated on Qwen3-8B model" (RN L719).
- 2026.3: "Extended the EAGLE-3 speculative decoding pipeline to LLMs and VLMs, enhancing continuous batching and adding Top-K sampling" (RN L225, L47); CPU "Enabled tree-mask support in PagedAttention for EAGLE-3 tree sampling" (RN L83); models "Qwen3-8B with EAGLE-3" (RN L36).
- 2026.1: "Extended prompt lookup decoding support to Vision-Language Models" (RN L668).

— [RN](https://github.com/openvinotoolkit/openvino/blob/2026.3.1/docs/articles_en/about-openvino/release-notes-openvino.rst)
- **2026.3 GenAI adds tree speculation fields** `branching_factor = 1; tree_depth = 0;` ("`total_draft_tokens = branching_factor^2 * (tree_depth - 1) + branching_factor`"), plus a Gemma4 MTP strategy (stateful). — [G3 generation_config.hpp L628-631, L695-696](https://github.com/openvinotoolkit/openvino.genai/blob/2026.3.1.0/src/cpp/include/openvino/genai/generation_config.hpp#L628-L696)

### Inferences
- **Why prompt lookup fits these agent turns.** Decode is 67-90% of generate time, and outputs re-emit spans present in the prompt (tool names, JSON keys, argument values, file paths, repeated schema fragments). Prompt lookup is the cheapest lever to try:
  - no extra model, memory or load time;
  - compatible with prefix caching (it is a CB impl over the same scheduler);
  - verification of K+1 = 4-6 tokens costs little more than one token on a bandwidth-bound iGPU (weights are read once per step).
- **Suggested starting point:** `num_assistant_tokens=3-5`, `max_ngram_size=3`.
- **Risks.** Because unmatched steps are padded rather than skipped, there is a per-step overhead when nothing matches (prose sections). Earliest-match selection may pick stale continuations in long histories. Measure accepted tokens per step with `SDPerModelsPerfMetrics`/`perf_metrics`.
- **Classic draft (Qwen3-0.6B) on the same iGPU is unlikely to pay off much for a 4B target.** The draft/target cost ratio is about 0.6/4 versus about 0.6/8-14 in the published 1.2-1.4× results. It also costs extra memory and load time, and both models' KV under prefix caching. Use it only if prompt lookup underperforms. A CPU draft (as in #36484) is an option because the CPU is idle in GPU-only runs.
- **EAGLE-3 requires a Qwen3-4B EAGLE-3 head converted to OpenVINO.** None was found in Intel/OpenVINO collections (Intel validates Qwen3-8B), and its gains are not established for 4B on iGPU.

### Gaps
- No published OpenVINO prompt-lookup speedups (CPU or GPU) for any model or task, including tool-calling.
- I did not find an OpenVINO-format EAGLE-3 draft for Qwen3-4B; HF search turned up none.
- I could not confirm whether `perf_metrics` reports per-step acceptance for prompt lookup in 2026.2.1.

---

## 4. Generation-config levers: stop strings/token IDs, max_new_tokens, structured output (XGrammar), Qwen3 chat template (`enable_thinking=false`) and prefix-cache reuse

### Takeaway
- **Stopping and length levers** exist and are cheap: `stop_strings` (with `include_stop_str_in_output=false` by default), `stop_token_ids`, `max_new_tokens` (default SIZE_MAX unless generation_config.json sets it).
- **Structured output** (`StructuredOutputConfig` with json_schema/regex/EBNF/`structural_tags_config`, via XGrammar) works in GenAI. It adds a per-request grammar compile (reported in `perf_metrics.get_grammar_compile_time()`), but I found no OpenVINO latency figures.
- **The most important finding is in the Qwen3 chat template.** With `enable_thinking=false` the generation prompt ends with `<|im_start|>assistant\n<think>\n\n</think>\n\n`. When that turn is re-rendered as history, the stock template drops the empty think block for assistant turns that have no reasoning content (unless the turn is the last message). The re-tokenized history therefore diverges from the cached KV right after `<|im_start|>assistant\n` of the previous turn. On the CB path, which re-templates the full history every turn, the prefix-cache hit ends there and the previous assistant output plus everything after it is re-prefilled.
- **Fix:** a custom chat template that always emits the empty `<think>\n\n</think>\n\n` for prior assistant turns (or one that never emits it), so that history and generation prompt match. This plausibly explains part of the warm-turn cost and is a "tuned" lever.

### Cited Findings

**GenerationConfig**
- Fields: `std::set<std::string> stop_strings; // Default setting in vLLM (and OpenAI API) is not to include stop string … bool include_stop_str_in_output = false; std::set<int64_t> stop_token_ids;`, `max_new_tokens = SIZE_MAX`, `max_length = SIZE_MAX`, `apply_chat_template = true`, `std::optional<StructuredOutputConfig> structured_output_config;`. — [G generation_config.hpp L569-690](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/generation_config.hpp#L569-L690)

**Structured output**
- Guide: "Compile the structured-output configuration (JSON Schema, regex, or EBNF grammar) into an internal grammar representation" (XGrammar). It supports `json_schema`, `regex`, `grammar`, `structural_tags_config` ("Trigger structured output during regular generation run" sample). `compound_grammar` and `StructuralTagsConfig` are deprecated. — [G site/docs/guides/structured-output.mdx L7-49, L124-128](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/site/docs/guides/structured-output.mdx)
- Implementation:
  - `m_grammar_compiler->CompileGrammar(grammar)` runs per config. Its time is recorded as `m_grammar_compile_times`; the compiler init time per backend is also recorded.
  - Perf metrics expose `get_grammar_compiler_init_times()` and `get_grammar_compile_time()` (ms).

  — [G sampling/structured_output/xgrammar_backend.cpp L27, L124-126](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/sampling/structured_output/xgrammar_backend.cpp#L124-L126); [G structured_output_controller.cpp L37-83](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/sampling/structured_output/structured_output_controller.cpp#L37-L83); [G perf_metrics.hpp L33-48, L99-153](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/perf_metrics.hpp)
- 2026.0 notes: "New parsers have been added to the LLMPipeline to extract structured outputs, reasoning steps, and tool calls from model responses." — RN L773

**Chat template**
- GenAI passes template variables through `ChatHistory.set_extra_context({"enable_thinking": ...})` ("Custom chat template variables (e.g. `enable_thinking` for models with extended reasoning like Qwen3)"). It also has `set_tools(...)`. — [G site/docs/guides/chat-scenario.mdx L190-216](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/site/docs/guides/chat-scenario.mdx); [G tokenizer_impl.cpp L795-824](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/tokenizer/tokenizer_impl.cpp#L795-L824)
- **The Qwen3 chat template (copy in GenAI test data):**
  - Generation prompt: `{%- if add_generation_prompt %}{{- '<|im_start|>assistant\n' }}{%- if enable_thinking is defined and enable_thinking is false %}{{- '<think>\n\n</think>\n\n' }}{%- endif %}{%- endif %}`
  - History assistant turns: `{%- if loop.index0 > ns.last_query_index %}{%- if loop.last or (not loop.last and reasoning_content) %}{{- '<|im_start|>' + message.role + '\n<think>\n' + reasoning_content.strip('\n') + '\n</think>\n\n' + content.lstrip('\n') }}{%- else %}{{- '<|im_start|>' + message.role + '\n' + content }}…{%- else %}{{- '<|im_start|>' + message.role + '\n' + content }}`
  - Reasoning extraction: `reasoning_content = content.split('</think>')[0]…; content = content.split('</think>')[-1].lstrip('\n')`
  - Tool calls render as `<tool_call>\n{"name": …, "arguments": …}\n</tool_call>`; tool results go in a `<|im_start|>user\n<tool_response>…` block.

  — [G tests/python_tests/data/tokenizer_configs.py L313](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/tests/python_tests/data/tokenizer_configs.py#L313)
- **Qwen model card:** `enable_thinking=False` is "a hard switch"; "When `enable_thinking=False`, the soft switches are not valid"; "the historical model output should only include the final output part." — [Qwen3-4B model card](https://huggingface.co/Qwen/Qwen3-4B)
- **HF chat-template deep dive:** "When set to false, the template inserts an empty `<think></think>` pair". For assistant replies before the latest real user turn "everything earlier is stripped out". It is silent on KV reuse. — [HF blog: The 4 Things Qwen-3's Chat Template Teaches Us](https://huggingface.co/blog/qwen-3-chat-template-deep-dive)
- **CB path re-encodes the full templated history each turn** (`apply_chat_template(histories[i], …)`); reuse relies solely on block-hash prefix caching. — [G continuous_batching/pipeline_base.cpp L97-106, L228-234](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/pipeline_base.cpp#L97-L106)
- **Prefix-cache restoration is token-exact by hash.** It restores full blocks via `sequence->get_hash(content_len, m_block_size)` and then a partially filled block token by token. — [G cache/block_manager.hpp L1304-1352](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/cache/block_manager.hpp#L1304-L1352)
- **2026.3:** "Improved `apply_chat_template` performance by caching compiled Minja templates, reducing TTFT during generation." This implies template compilation was a per-call TTFT cost in 2026.2. — RN L233

### Inferences
- **How the mismatch arises (my reading of the template; to be verified by tokenizing turn N's prompt + output against turn N+1's prompt).**
  - In an agent loop the sequence is user → assistant(tool_call) → tool → assistant…, and `last_query_index` points at the real user turn.
  - Every prior assistant turn after it has `reasoning_content == ''`, because the think block was in the prompt, not the output. It is not `loop.last`, so it renders as `<|im_start|>assistant\n` + content without `<think>\n\n</think>\n\n`.
  - The KV cache holds the version with the 4-6 think tokens, so reuse ends at the start of the previous assistant message. The previous output (about 130-255 tokens), the tool response and the new turn are all recomputed.
  - Appending the raw think block to the stored assistant content does not help, because the template strips it via `split('</think>')`.
- **Fixes, in order of preference.**
  - (a) Supply a modified chat template (tokenizer `chat_template` override or IR rt_info) that renders prior assistant turns with the same empty think block.
  - (b) Bypass templating: manage token IDs directly (generate from pre-tokenized input that appends exactly the generated tokens).
  - (c) Accept the loss. It is bounded to about one assistant output plus the tool result per turn.
- **Cheap decode levers.** `max_new_tokens` (e.g. 256-384) caps runaway turns and also caps the initial dynamic KV allocation (`min(2×prompt, prompt+max_new_tokens)`). Qwen3's tool calls end with `</tool_call><|im_end|>`, so a `</tool_call>` stop string saves only about 1 token; the real decode lever is generating less prose (prompting) or prompt lookup.
- **Structured output is a correctness lever, not a latency lever.** Use `structural_tags_config` triggered at `<tool_call>` so free text is unconstrained. Measure `grammar_compile_time` per request, since the grammar is compiled per request.

### Gaps
- No OpenVINO-published per-token mask cost or grammar-compile latency for XGrammar on any device.
- I did not verify by tokenization that the history/prompt divergence occurs in practice for the user's exact message handling (e.g., whether their harness stores raw text with or without the think block, or uses `tool_calls` fields).
- Whether optimum-intel-exported Qwen3 IRs embed exactly this template version was not checked; the HF raw tokenizer_config fetch was blocked.

---

## 5. KV-cache precision on GPU (f16 / i8 / u4; separate K/V precisions; group sizes; by-channel)

### Takeaway
On GPU there is a single `KV_CACHE_PRECISION` for both K and V. `KEY_CACHE_PRECISION`, `VALUE_CACHE_PRECISION` and `*_GROUP_SIZE` are CPU-plugin properties; the GPU plugin's option list has none of them.

Key quantization defaults to BY_CHANNEL with a fixed group of 16 and value to BY_TOKEN. The internal `KEY_CACHE_QUANT_MODE` can switch the key to BY_TOKEN, but u4 + BY_TOKEN keys asserts on PA and disables micro-SDPA.

Defaults on PA: i8 in 2026.1/2026.2, u4 auto for 4-bit-weight models in 2026.3. For latency, the user's own measurements favor **f16 KV** (prefill 15-27% faster at depth; warm turn-2 at 12k 0.64 s vs 1.00 s for u8). f16 also keeps the micro-SDPA prefill path and XAttention-compatible types. The cost is about 2× i8 memory, roughly 4.5 GiB at 32k tokens for Qwen3-4B, which fits in 16 GB alongside about 2.5 GB of INT4 weights.

The recommended latency setting is `KV_CACHE_PRECISION=f16`, with `cache_size` preallocated (see Q6).

### Cited Findings
- **GPU options.** `kv_cache_precision` default `ov::element::dynamic`; `key_cache_quant_mode` default `BY_CHANNEL`; `value_cache_quant_mode` default `BY_TOKEN`. No key/value-precision or group-size options exist in the GPU option list (2026.2.1 and master). — [O options.inl L32, L39-40](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/include/intel_gpu/runtime/options.inl#L32-L40); [openvino master options.inl](https://github.com/openvinotoolkit/openvino/blob/master/src/plugins/intel_gpu/include/intel_gpu/runtime/options.inl)
- **The CPU plugin has separate `key_cache_precision`, `value_cache_precision`, `key_cache_group_size` and `value_cache_group_size`.** — [O src/plugins/intel_cpu/src/config.cpp L350-400](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_cpu/src/config.cpp#L350-L400)
- **The property is internal:** `key_cache_quant_mode{"KEY_CACHE_QUANT_MODE"}` in `ov::internal`. — [O src/inference/dev_api/openvino/runtime/internal_properties.hpp L166](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/inference/dev_api/openvino/runtime/internal_properties.hpp#L166)
- **The GPU PA KV layout config:**
  - `keyCacheQuantBychannel = (key_cache_quant_mode == BY_CHANNEL)`
  - `keyCacheGroupSize = BY_CHANNEL ? 16 : 0`
  - `valueCacheQuantBychannel = false; valueCacheGroupSize = 0;`
  - Key and value precision are both taken from `kv_cache_precision`.

  — [O transformations_pipeline.cpp L752-772](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/plugin/transformations_pipeline.cpp#L752-L772)
- **Normalization:** u8 → i8 ("plugin is supposed to work with INT8 internally"), i4 → u4. — [O execution_config.cpp L353-361](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L353-L361)
- **Default finalization:**
  - 2026.2.x: `bool auto_enable_4bit_kv = false;` → PA gets i8.
  - 2026.3.1: auto u4 for PA + 4-bit weights + non-BY_TOKEN key.
  - 2026.1.2: no u4 branch.

  This is consistent with the prior source review in this project. — [O execution_config.cpp L250-298](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L250-L298); [openvino 2026.3.1 execution_config.cpp L268-300](https://github.com/openvinotoolkit/openvino/blob/2026.3.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L268-L300)
- **Micro-SDPA (XMX flash-attention prefill) eligibility in PA.**
  - It requires `supports_immad`, arch ≥ xe_hpg and microkernel support; equal K/V head size ≤ 256; no scores output; no alibi.
  - "Disable micro SDPA for INT4 BY_TOKEN due to accuracy issues": `if (is_i4_u4(kv_cache_dt) && !desc->is_key_by_channel) return false;`
  - The PA kernel has distinct `IS_KV_COMPRESSED` code paths (dequantization inside the kernels).

  — [O impls/ocl_v2/sdpa/paged_attention_opt.cpp L50-60, L292-298, L1351-1394](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/graph/impls/ocl_v2/sdpa/paged_attention_opt.cpp#L1351-L1394)
- **Official doc wording:**
  - "KV-cache can be quantized into the following precisions: ``u8``, ``u4``, ``bf16``, ``f16`` … Keys and Values precisions can be configured independently using ``KEY_CACHE_PRECISION`` and ``VALUE_CACHE_PRECISION``."
  - "Default … U8 Keys: channel-wise quantization, group_size = 32 (CPU) / 16 (GPU); U8 Values: token-wise".
  - Note: "for KV-cache quantization, GPU ignores the DYNAMIC_QUANTIZATION_GROUP_SIZE property, using ``group_size = head_size``."

  — [O inference-with-optimum-intel.rst L278-301](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/docs/articles_en/openvino-workflow-generative/inference-with-optimum-intel.rst#L278-L301). **Conflict:** the doc's "independently configurable K/V precision" is true for CPU, but the 2026.2.1 GPU plugin exposes only `KV_CACHE_PRECISION` (source above).
- **Release notes, 2026.2:** "INT4 KV-cache compression is enabled for GPUs, with substantial memory reduction when KV cache size is significant, such as with large input prompts exceeding 32K tokens." (RN L327, L361). In the 2026.2.x source this is opt-in (`KV_CACHE_PRECISION=u4`); it became the automatic default only in 2026.3. — [RN](https://github.com/openvinotoolkit/openvino/blob/2026.3.1/docs/articles_en/about-openvino/release-notes-openvino.rst)
- **Known issue (2026.2):** "Gemma 4 INT8/INT4 weight compressed models require explicitly setting KV cache group size to 64 to preserve accuracy". This shows KV-quant accuracy is model-sensitive; it is not reported for Qwen3. — RN L494-503

### Inferences
- **For a latency-tuned profile on 2026.2.1, `KV_CACHE_PRECISION=f16` is the defensible choice.** The user's own data shows f16 prefill is 15-27% faster at depth and warm turn-2 at 12k is 36% faster than u8. Source supports the mechanism: the compressed-KV kernels add dequantization (`IS_KV_COMPRESSED`), while f16 avoids it. f16 also avoids any quantization accuracy question.
- **Memory headroom (estimate).** Qwen3-4B f16 KV at 32k native context is about 4.5 GiB, versus about 2.3 GiB for i8. With about 2.3-2.6 GB of INT4 weights plus runtime overhead on a 16 GB LPDDR5X system shared with the OS, f16 at 32k is feasible but tight. At the agent's realistic 4-16k it is about 0.6-2.3 GiB.
- **When u4 is worth it.** Use it only if the context-held objective (e.g. 64k-128k with YaRN, or concurrent sessions) dominates. Keep keys BY_CHANNEL (the default) to retain micro-SDPA eligibility.
- **On 2026.3 the default changes to u4**, so a 2026.3 "default" baseline would be both slower at prefill (per the user's u4 data) and smaller in memory. Pin the version or set the precision explicitly when comparing.

### Gaps
- No Intel-published per-precision prefill/decode benchmark or accuracy table for GPU KV f16/i8/u4 on Qwen3.
- Whether i8/u4 decode is faster than f16 at long context (less KV bandwidth) on Xe3 is untested in public sources. The user's data shows decode at about 3.5k context, where KV traffic is small.

---

## 6. `max_num_batched_tokens` / split-fuse chunk size, `cache_size` preallocation, `GPU_ENABLE_LARGE_ALLOCATIONS`, model caching (`CACHE_DIR`)

### Takeaway
- **Chunking.** For single-user TTFT, keep the runtime default `max_num_batched_tokens = unlimited` (one-shot prefill). Smaller chunks only add per-step overhead, and TriShape (the one feature that needs chunks) is not recommended.
- **`cache_size` (the real tuning gain).** With `cache_size=0` the GPU KV cache is allocated dynamically, starting at `min(2×prompt, prompt+max_new_tokens)` tokens. It then grows in 256-token steps; each step allocates new tensors for every layer and copies the old cache into them. Under prefix caching it never shrinks. Setting `SchedulerConfig.cache_size` (GB) preallocates once and removes growth reallocations and copies from the critical path. This requires passing a full SchedulerConfig, which replaces the latency defaults, so set `max_num_batched_tokens` to SIZE_MAX and `enable_prefix_caching=True` explicitly.
- **`GPU_ENABLE_LARGE_ALLOCATIONS`** (default false) only matters if a single cache tensor exceeds the device max-alloc size. Per-layer K and V tensors for a 4B model at 32k context are about 60-65 MiB each, so it is irrelevant here.
- **`CACHE_DIR`.** Set it for load time: it writes GPU `.cl_cache` blobs, and 2026.2 added parallel blob loading and faster GenAI GPU load with cache blobs.

### Cited Findings
- **Default latency SchedulerConfig** (`max_num_batched_tokens = SIZE_MAX // don't limit total batch size`, `enable_prefix_caching = true`); a user-supplied SchedulerConfig fully replaces it (no merge). Bare-struct defaults are 256 tokens and prefix caching false. — [G utils.cpp L794-813](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L794-L813); [G scheduler_config.hpp L18-86](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/scheduler_config.hpp#L18-L86)
- **Header comment on 256:** "TODO: benchmark this value and understand a required value to ensure inference is not memory bound". — [G scheduler_config.hpp L20-23](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/scheduler_config.hpp#L20-L23)
- **Dynamic growth:**
  - `m_kv_blocks_initial_multiplier = 2`; `m_cache_growth_num_tokens = 256 // Number of tokens by which KV-cache is increased`.
  - `_initialize_cache` uses `prompt_len * 2` capped by `prompt_len + max_new_tokens`.
  - On GPU `_try_increase_cache` checks `utils::get_available_gpu_memory` and grows by 256 tokens, or by fewer if memory is short.

  — [G continuous_batching/scheduler.hpp L29-33, L536-596](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/scheduler.hpp#L536-L596)
- **Each growth reallocates and copies** (`KVCacheManager::allocate_cache_if_needed`): for each decoder layer it calls `m_context.create_tensor(...)` for new K and V tensors, then `// copy current cache data … dst_key_roi.copy_from(m_key_cache[decoder_layer_id]); dst_value_roi.copy_from(...)`. — [G cache/kv_cache_manager.hpp L159-200](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/cache/kv_cache_manager.hpp#L159-L200)
- **The cache is cleared only when prefix caching is off and the cache is dynamic:** `if (!scheduler_config.enable_prefix_caching && scheduler_config.cache_size == 0 && scheduler_config.num_kv_blocks == 0) { m_scheduler->clear_cache(); }`. — [G continuous_batching/pipeline_impl.cpp L645-650](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/pipeline_impl.cpp#L640-L650)
- **GPU available-memory estimate** for KV sizing: used `cl_mem + usm_device` (+`usm_host` on integrated) × 1.1, then `min(total - used, device_max_alloc_mem_size * num_cache_tensors)`. — [G utils.cpp L950-983](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L950-L983)
- **`enable_large_allocations`** default false: "Allow buffer allocations that exceed the device max allocation size. Enabling this option may lead to performance degradation". The engine errors otherwise with "…or set ov::intel_gpu::hint::enable_large_allocations config property to true." — [O options.inl L23](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/include/intel_gpu/runtime/options.inl#L23); [O src/runtime/engine.cpp L300-314](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/runtime/engine.cpp#L300-L314)
- **Model caching docs:**
  - "a cached blob file: ``.cl_cache`` (GPU) … is automatically created inside the ``/path/to/cache/dir`` folder … the first ``compile_model`` operation takes slightly more time".
  - `CacheMode` `OPTIMIZE_SPEED` (default) vs `OPTIMIZE_SIZE` (weightless caching, "supported only by the GPU Plugin and IR model format").
  - GPU option: `cache_mode` default `OPTIMIZE_SPEED`.

  — [O model-caching-overview.rst L55-75, L143-170](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/docs/articles_en/openvino-workflow/running-inference/optimize-inference/optimizing-latency/model-caching-overview.rst); [O options.inl L8, L28](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/include/intel_gpu/runtime/options.inl#L8-L28)
- **Release notes, 2026.2:** "OpenVINO GenAI significantly reduces model loading times on GPU when using cache blobs — preventing bottlenecks for multi-stage AI pipelines, including agentic use cases" (RN L328); GPU: "Enabled parallel loading for model cache blobs, significantly reducing model load time" (RN L358). 2026.3: "Introduced compiled blob compatibility checks based on OpenVINO version, GPU device properties, and GPU driver" (RN L101). — [RN](https://github.com/openvinotoolkit/openvino/blob/2026.3.1/docs/articles_en/about-openvino/release-notes-openvino.rst)
- **GenAI's CB constructor sets `ov::cache_model_path = models_path`.** It passes remaining user properties (e.g. `CACHE_DIR`) to `compile_model`. — [G continuous_batching/pipeline.cpp L60-62](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/pipeline.cpp#L54-L62)

### Inferences
- **Tuned SchedulerConfig sketch (Python, 2026.2.1):** `sc = SchedulerConfig(); sc.max_num_batched_tokens = 2**64-1; sc.enable_prefix_caching = True; sc.dynamic_split_fuse = True; sc.cache_size = <GB>`.
  - For f16 KV at 32k tokens about 4.6 GB suffices; for i8 about 2.4 GB. Leave headroom for the OS on 16 GB.
  - Then pass `LLMPipeline(path, "GPU", scheduler_config=sc, KV_CACHE_PRECISION="f16", CACHE_DIR="...")`.
- **What preallocation buys.** It removes the 256-token growth steps; with f16 at 12k context each step copies about 1.7 GB of K+V. It also makes the memory footprint deterministic, which is the "context held" story. It does not change steady-state decode speed.
- **The cost is memory reserved up front.** That is acceptable for a single-agent appliance. Note: when cache_size is set, prefix-cache blocks are evicted LRU only when the pool is exhausted.
- **Chunk-size tuning is not a TTFT win for a single request.** It is a throughput/fairness lever for concurrent requests, and with an unlimited budget peak activation memory for a 10k prompt is still modest on a 4B model (inference; no OpenVINO measurement found).

### Gaps
- I did not measure the growth-copy cost on Xe3; its magnitude per growth event is an estimate.
- No public OpenVINO benchmark of `cache_size` preallocation vs dynamic allocation latency.
- Load-time savings from `CACHE_DIR` on Panther Lake are not quantified in release notes.

---

## 7. Intel guidance documents on LLM latency tuning for Intel GPUs / AI PCs

### Takeaway
I found no single Intel "LLM latency tuning on Intel GPU / AI PC" guide that prescribes settings for GenAI's LLMPipeline. The guidance is scattered:

- **OpenVINO docs:**
  - the "Enabling OpenVINO Runtime Optimizations" section (dynamic quantization defaults; KV-cache quantization);
  - the Precision Control guide (PERFORMANCE vs ACCURACY);
  - Model Caching Overview (CACHE_DIR/CacheMode);
  - the GPU device page (lists `dynamic_quantization_group_size` and `kv_cache_precision` as compile-time properties).
- **GenAI concept pages:** continuous batching, prefix caching, sparse prefill, KV eviction, speculative decoding (the last marked "work in progress").
- **Intel/HF blogs** with point measurements (Qwen3-8B agent speculative decoding on Lunar Lake; DFlash on Panther Lake).

None of them gives a recommended KV precision or SchedulerConfig for latency on iGPU. A tuned profile is therefore a project-specific composite, which should be stated explicitly in the write-up.

### Cited Findings
- **Runtime optimization section** (dynamic quantization "enabled **by default**" on GPU; XMX: per-token only; disable via `DYNAMIC_QUANTIZATION_GROUP_SIZE=0`; KV precisions u8/u4/bf16/f16; example `ov_config={"KV_CACHE_PRECISION": "u8", "DYNAMIC_QUANTIZATION_GROUP_SIZE": "32", "PERFORMANCE_HINT": "LATENCY"}`). — [O inference-with-optimum-intel.rst L226-301](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/docs/articles_en/openvino-workflow-generative/inference-with-optimum-intel.rst#L226-L301)
- **GPU device page:** lists `ov::hint::dynamic_quantization_group_size` and `ov::hint::kv_cache_precision` among properties that "must be set before calling ``ov::Core::compile_model()``". — [O gpu-device.rst L405-425](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/docs/articles_en/openvino-workflow/running-inference/inference-devices-and-modes/gpu-device.rst)
- **GenAI docs, speculative decoding:** "This page is a work in progress" (GenAI site). The OpenVINO docs example uses `SchedulerConfig(); cache_size = 2`, `num_assistant_tokens = 5`, comment `main_device = 'CPU'  # GPU can be used as well.` — [G site/docs/concepts/optimization-techniques/speculative-decoding.md](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/site/docs/concepts/optimization-techniques/speculative-decoding.md); [O inference-with-genai.rst L955-1002](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/docs/articles_en/openvino-workflow-generative/inference-with-genai.rst#L955-L1002)
- **GenAI docs, hybrid-attention page:** the LLMPipeline default "is optimized for local non-concurrent usage" (`max_num_batched_tokens` max, prefix caching true). — [G site/docs/concepts/optimization-techniques/hybrid-attention-models-cache.md](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/site/docs/concepts/optimization-techniques/hybrid-attention-models-cache.md)
- **Intel/HF agent blog (Lunar Lake):** Qwen3-8B INT4 + Qwen3-0.6B INT8 draft on GPU → 1.3× (pruned draft 1.4×). — [HF blog](https://huggingface.co/blog/intel-qwen3-agent)
- **Intel/HF DFlash blog (Panther Lake X7 368H, Arc B390, OpenVINO 2026.3.0):** 1.3-5.5× depending on model and task. Not yet in a GenAI release; no prefix caching. — [HF blog](https://huggingface.co/blog/ofirzaf/intel-dflash-ptl)
- **OpenVINO blog on GPU throughput techniques** (search result; not fetched/verified). — [blog.openvino.ai: Techniques for faster AI inference throughput with OpenVINO on Intel GPUs](https://blog.openvino.ai/blog-posts/techniques-for-faster-ai-inference-throughput-with-openvino-on-intel-gpus)
- **Release notes, 2026.1 section:** "Model inference performance has been optimized on Intel® Core™ Ultra Series 3 with 2 P-cores + 4 LPE-cores" (CPU plugin); "Preview: Experimental L0 backend support for Xe2+ GPUs" (GPU plugin). These are relevant to a Core Ultra 5 325 but are not a tuning guide. — RN L580, L589

### Inferences
- Defensible "tuned profile" levers for the write-up, each backed by a primary source above:
  1. `KV_CACHE_PRECISION=f16`: measured latency win; avoids dequant; micro-SDPA eligible.
  2. A full SchedulerConfig with unlimited `max_num_batched_tokens`, prefix caching on, and `cache_size` preallocated: no growth reallocation or copy.
  3. A chat template fixed so prior assistant turns tokenize identically to their generation prompt (`enable_thinking=false` empty think block): restores prefix-cache hits across tool turns.
  4. Prompt-lookup decoding (`prompt_lookup=True`, `num_assistant_tokens≈3-5`, `max_ngram_size≈3`): draft-free decode acceleration aimed at copied tool-call spans.
  5. `max_new_tokens` cap, and `CACHE_DIR` for load time.
- Leave dynamic quantization at its default (already on). Do not use cache eviction or TriShape. Treat XAttention as an optional, accuracy-checked lever for cold prefills of 10k+ tokens only.
- **Version caveat for the write-up.** On 2026.3 the default KV becomes u4 (slower prefill per the user's data), apply_chat_template gets cached Minja (lower per-turn TTFT), and EAGLE-3 gets Top-K/tree sampling. Baseline comparisons must pin the version.

### Gaps
- No Intel AI PC developer document with LLM latency settings specific to Panther Lake/Xe3 was found. The web search returned only generic benchmark pages, and docs.openvino.ai model-server pages returned navigation only.
- The OVMS "Efficient LLM Serving" and speculative-decoding demo pages could not be read (fetch returned navigation only), so OVMS-recommended defaults (e.g., `cache_size`, `kv_cache_precision`) are not captured here.
- GitHub issue search for Xe2/Xe3-specific bugs (XAttention, u4 KV, PA fallback, speculative decoding on GPU) was not possible without API access. Only openvino Discussion #36484 (Lunar Lake speculative decoding) was found via web search.
