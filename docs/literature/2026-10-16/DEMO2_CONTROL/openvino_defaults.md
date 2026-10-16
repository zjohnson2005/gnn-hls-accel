# OpenVINO GenAI 2026.2.x LLMPipeline default runtime behavior on Intel iGPU (Xe2/Xe3) and CPU

Method note: every claim below comes from reading the source at the exact release tags: openvino.genai tag `2026.2.1.0` (commit 7dea045, same commit as branch `releases/2026/2`), plus `2026.1.2.0` and `2026.3.1.0` for comparison, and openvino tag `2026.2.1` (commit ede283a, 9 Jun 2026), plus `2026.2.0`, `2026.1.2` and `2026.3.1`. Line numbers are for those tags. The GitHub API was not reachable from this session, so I could not do PR/blame archaeology. Web search turned up no relevant OpenVINO GitHub issues or benchmarks (details under Gaps).

Base URLs used below:
- GENAI = https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/
- OV = https://github.com/openvinotoolkit/openvino/blob/2026.2.1/

---

## Q1. What scheduler config and backend does LLMPipeline use when no SchedulerConfig is passed (GPU and CPU)? When does it fall back?

### Takeaway
With no `scheduler_config` and no `ATTENTION_BACKEND`, `LLMPipeline(path, "GPU" | "CPU")` on x86_64/ARM64 first tries the PagedAttention / continuous-batching backend (`ContinuousBatchingAdapter`) with the "latency-oriented" SchedulerConfig: `max_num_batched_tokens = SIZE_MAX` (unlimited), `enable_prefix_caching = true`, and every other field left at the struct default (`dynamic_split_fuse=true`, `cache_size=0`, `num_kv_blocks=0` so the cache is allocated dynamically, `use_cache_eviction=false`, `max_num_seqs=256`). It falls back to the stateful/SDPA backend only if PA initialization throws an `ov::Exception`, if the device is NPU, if `ATTENTION_BACKEND="SDPA"` is set, or on non-x86_64/ARM64 builds. Passing any `scheduler_config` forces the PA path and turns off that fallback. The user's struct is then used as-is: it is not merged with the latency defaults.

### Cited Findings
- **The backend defaults to PA.** `extract_attention_backend` starts from `std::string attention_backend = PA_BACKEND;`. It accepts only `"PA"` or `"SDPA"` from the `ATTENTION_BACKEND` property and asserts if a property that needs PA conflicts with `SDPA` (utils.cpp L855-874). — [utils.cpp L855-874](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L855-L874)
- **The latency-oriented config.** Quote (utils.cpp L808-813):
  ```cpp
  SchedulerConfig get_latency_oriented_scheduler_config() {
      SchedulerConfig default_config;
      default_config.max_num_batched_tokens = std::numeric_limits<size_t>::max(); // don't limit total batch size
      default_config.enable_prefix_caching = true; // for better TTFT in chat scenarios
      return default_config;
  }
  ```
  Only these two fields change. Everything else stays at the struct defaults (see Q2). — [utils.cpp L808-813](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L808-L813)
- **Constructor dispatch.** This is `LLMPipeline(models_path, tokenizer, device, properties)`, pipeline.cpp L214-244. The other constructors at L256+ and L304+ have the same structure:
  - `if (is_npu_requested)`: StatefulPipeline.
  - `else if (utils::explicitly_requires_paged_attention(user_properties))`: comment *"If CB is invoked explicitly, create CB adapter as is and re-throw in case if internal issues"*, then `extract_scheduler_config(properties, utils::get_latency_oriented_scheduler_config())`.
  - `else if (attention_backend == PA_BACKEND)`: inside `try { #if defined(OPENVINO_ARCH_X86_64) || defined(OPENVINO_ARCH_ARM64) m_pimpl = std::make_unique<ContinuousBatchingAdapter>(model, tokenizer, utils::get_latency_oriented_scheduler_config(), ...)` and `catch (const ov::Exception& exception) { log_paged_attention_fallback(exception); ...}`.
  - Finally, `if (m_pimpl == nullptr) { ... m_pimpl = std::make_unique<StatefulLLMPipeline>(...) }`.

  — [pipeline.cpp L214-244](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/llm/pipeline.cpp#L214-L244)
- **Fallback warning text.** `"Paged Attention backend initialization failed. Falling back to SDPA backend. Set ATTENTION_BACKEND=\"SDPA\" to skip Paged Attention initialization."` (pipeline.cpp L23-27). The real error is logged only at DEBUG. — [pipeline.cpp L23-27](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/llm/pipeline.cpp#L23-L27)
- **What counts as "explicitly requires PA".** Any of these does: a `scheduler_config` key in properties, `ATTENTION_BACKEND=="PA"`, a `draft_model` on a non-NPU device, or `prompt_lookup=true` (utils.cpp L815-844). — [utils.cpp L815-844](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L815-L844)
- **A user-supplied SchedulerConfig fully replaces the default.** In `extract_scheduler_config`, if the `scheduler_config` key exists then `scheduler_config = it->second.as<SchedulerConfig>();`. Only `else if (default_config.has_value())` uses the latency default (utils.cpp L794-806). Nothing is merged field by field. — [utils.cpp L794-806](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L794-L806)
- **The header comments confirm the client-scenario defaults.** scheduler_config.hpp L22: *"When ContinuousBatching is invoked from LLMPipeline (client scenario) by default max_num_batched_tokens is not limited."* L78: *"When ContinuousBatching is invoked from LLMPipeline (client scenario) by default prefix caching is turned on."* — [scheduler_config.hpp L22, L78](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/scheduler_config.hpp#L22-L79)
- **The official GenAI docs say the same thing.** *"`LLMPipeline` and `VLMPipeline` constructors that utilize Continuous Batching use a latency-oriented default scheduler configuration if the user does not pass a scheduler config in `properties`. It is optimized for local non-concurrent usage. That default changes two fields: `max_num_batched_tokens = std::numeric_limits<size_t>::max()`, `enable_prefix_caching = true`. `ContinuousBatchingPipeline` constructors do not assume that latency-oriented profile."* (site/docs/concepts/optimization-techniques/hybrid-attention-models-cache.md, around L70-82) — [hybrid-attention-models-cache.md](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/site/docs/concepts/optimization-techniques/hybrid-attention-models-cache.md)
- **The Python constructor docstring** says: *"Add {"scheduler_config": ov_genai.SchedulerConfig} to config properties to create continuous batching pipeline."* (py_llm_pipeline.cpp L151, L180). — [py_llm_pipeline.cpp L145-152](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/python/py_llm_pipeline.cpp#L145-L152)
- **KV cache sizing under the default.** With `cache_size=0` and `num_kv_blocks=0` the cache is allocated dynamically. Header L30: *"When both num_kv_blocks and cache_size are equal to zero dynamic cache allocation is turned on."*
  - Scheduler `_initialize_cache` sizes the initial target as `prompt_len * m_kv_blocks_initial_multiplier (=2)`, capped at `prompt_len + max_new_tokens`, then sets `m_dynamic_memory_allocation = true` (scheduler.hpp L530-558).
  - Growth happens in steps of `m_cache_growth_num_tokens = 256` (scheduler.hpp L31-33, L561-581).

  — [scheduler_config.hpp L30](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/scheduler_config.hpp#L30); [scheduler.hpp L29-33, L540-581](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/scheduler.hpp#L540-L581)
- **GPU-specific CB setup.** `ContinuousBatchingImpl::initialize_pipeline` compiles the PA-transformed model, then queries available memory: GPU uses `utils::get_available_gpu_memory`, CPU uses `get_available_cpu_memory`.
  - Partial preemption is disabled on GPU only when `!dynamic_split_fuse`. Comment: *"in case of executing a `vLLM-like` pipeline, it's better not to use partial eviction on the GPU"* (pipeline_impl.cpp L163-191).
  - Block size is fixed at `cpu_block_size = 32, gpu_block_size = 16` (kv_cache_manager.hpp, around L96).

  — [pipeline_impl.cpp L140-191](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/pipeline_impl.cpp#L140-L191); [kv_cache_manager.hpp](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/cache/kv_cache_manager.hpp)
- **Version comparison.** 2026.1.2.0 and 2026.3.1.0 have the same `get_latency_oriented_scheduler_config` (2026.1.2: utils.cpp L736-741; 2026.3.1: utils.cpp L866-871) and the same dispatch structure (2026.1.2: pipeline.cpp L211-221; 2026.3.1: pipeline.cpp L256-265). One difference: in 2026.1.2 the PA default path constructs the adapter from `models_path` instead of a pre-read model. — [2026.1.2.0 utils.cpp](https://github.com/openvinotoolkit/openvino.genai/blob/2026.1.2.0/src/cpp/src/utils.cpp#L736-L741); [2026.3.1.0 utils.cpp](https://github.com/openvinotoolkit/openvino.genai/blob/2026.3.1.0/src/cpp/src/utils.cpp#L866-L871)

### Inferences
- In 2026.2.1 the out-of-the-box control (`LLMPipeline(path, "GPU")`, no properties) runs on the PA/CB backend with prefix caching ON, unlimited batch tokens (so the whole prompt goes in one chunk), dynamic KV allocation, and no eviction. This holds on both GPU and x86 CPU, unless PA init fails. A PA failure is visible only as a WARN-level log line.
- Both the DEMO-2 "NON_RESIDENT" control (explicit bare `SchedulerConfig()` with `enable_prefix_caching=False`) and the "RESIDENT" tuned profile (no SchedulerConfig) end up on the PA backend. Two consequences:
  - The resident/non-resident label does not mean stateful vs PA.
  - The control silently loses the SDPA fallback, because explicit config means "re-throw".
- The control differs from the true default in two ways, not one:
  - (i) prefix caching is OFF;
  - (ii) `max_num_batched_tokens` is 256 instead of unlimited, which forces chunked prefill (see Q3).

  So the control is not the "runtime default configuration". It is the "ContinuousBatchingPipeline / bare-struct default".
- **Truthful default control:** `ov_genai.LLMPipeline(model_dir, "GPU")` with no `scheduler_config` and no KV properties.
- **Isolating prefix caching alone:** pass a SchedulerConfig with `max_num_batched_tokens` set to the max size_t (e.g. `2**64-1` on 64-bit, which pybind maps to size_t) and `enable_prefix_caching=False`. Leave other fields at default. (Inference: I did not run this.)

### Gaps
- I could not confirm empirically whether PA initialization succeeds for Qwen3-4B INT4 on Xe3 in 2026.2.1, or whether the pipeline silently falls back to SDPA. Verify at runtime: run with `OPENVINO_LOG_LEVEL` set at least to the WARNING level and look for "Falling back to SDPA backend", or for the "Model: LLM with Paged Attention" property dump (see Q4).

---

## Q2. Defaults of a bare `SchedulerConfig()` in 2026.2.x

### Takeaway
A bare `ov_genai.SchedulerConfig()` (Python `py::init<>()` maps directly to the C++ struct) has:

| Field | Default |
|---|---|
| `max_num_batched_tokens` | 256 |
| `num_kv_blocks` | 0 |
| `cache_size` | 0 (dynamic allocation) |
| `dynamic_split_fuse` | true |
| `use_cache_eviction` | false |
| `max_num_seqs` | 256 |
| `enable_prefix_caching` | false |
| `use_sparse_attention` | false |
| `cache_interval_multiplier` | unset (8 used for hybrid models) |

These values are the same in 2026.1.2 and 2026.3.1.

### Cited Findings
- scheduler_config.hpp at 2026.2.1.0:
  - L23 `std::size_t max_num_batched_tokens = 256;`, preceded by the comment *"TODO: benchmark this value and understand a required value to ensure inference is not memory bound"*
  - L26 `num_kv_blocks = 0;`
  - L31 `cache_size = 0;`
  - L48 `bool dynamic_split_fuse = true;`, with comment L45-47: *"whether to split prompt / generate to different scheduling phases. Allows to process prompt partially in case when batch size is limited. If dynamic_split_fuse is turned off any prompt that is longer than batch size will lead to error."*
  - L56 `use_cache_eviction = false;`
  - L70 `max_num_seqs = 256;`
  - L79 `bool enable_prefix_caching = false;`

  — [scheduler_config.hpp](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/scheduler_config.hpp#L18-L86)
- **Python binding:** `py::class_<SchedulerConfig>(m, "SchedulerConfig", ...) .def(py::init<>())` with `def_readwrite` for each field. No Python-side defaults are overridden (py_continuous_batching_pipeline.cpp around L437-450). — [py_continuous_batching_pipeline.cpp](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/python/py_continuous_batching_pipeline.cpp#L437-L450)
- **2026.1.2.0:** the same values at L18 (256), L31 (dsf true) and L62 (prefix false). **2026.3.1.0:** L23 (256), L51 (dsf true), L82 (prefix false). — [2026.1.2.0 header](https://github.com/openvinotoolkit/openvino.genai/blob/2026.1.2.0/src/cpp/include/openvino/genai/scheduler_config.hpp); [2026.3.1.0 header](https://github.com/openvinotoolkit/openvino.genai/blob/2026.3.1.0/src/cpp/include/openvino/genai/scheduler_config.hpp)
- **OpenVINO's own tool builds the same bare struct.** `tools/llm_bench` creates `openvino_genai.SchedulerConfig()` and only sets the fields the user supplies (llm_bench_utils/ov_utils.py L190-228). So llm_bench runs that pass a `cb_config` also inherit 256 / prefix-off unless those fields are overridden. — [ov_utils.py L190-228](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/tools/llm_bench/llm_bench_utils/ov_utils.py#L190-L228)
- **The official docs example uses a bare struct.** inference-with-genai.rst (speculative decoding) shows `scheduler_config = openvino_genai.SchedulerConfig(); scheduler_config.cache_size = 2` passed to `LLMPipeline(..., scheduler_config=scheduler_config, ...)` (OV docs, L987-993). — [inference-with-genai.rst](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/docs/articles_en/openvino-workflow-generative/inference-with-genai.rst)

### Inferences
- The prior literature note (a) is confirmed exactly by primary source.
- The DEMO-2 "NON_RESIDENT" control equals the bare-struct defaults with prefix caching explicitly false, which is already the default. Its effective config is therefore `max_num_batched_tokens=256`, `dynamic_split_fuse=true`, `enable_prefix_caching=false`, dynamic cache, no eviction.

### Gaps
- None for struct values.

---

## Q3. How does `max_num_batched_tokens=256` affect prefill of 4k-10k-token prompts? What is the known TTFT cost?

### Takeaway
With `dynamic_split_fuse=true` (the default), the scheduler admits at most `max_num_batched_tokens` prompt tokens per step. A single 4k-10k-token prompt is therefore prefilled in about 16-40 sequential model invocations of at most 256 tokens each, and the first token is sampled only after the last chunk. Under the LLMPipeline default (unlimited) the whole prompt is one step.

Separately, with prefix caching OFF the CB chat path re-templates and re-tokenizes the entire history every turn and recomputes all of it. TTFT then scales with total conversation length rather than new-turn length.

I found no published OpenVINO benchmark or GitHub issue that quantifies the TTFT penalty of 256-token chunking on Intel GPUs.

### Cited Findings
- **Dynamic split-fuse prompt scheduling** (scheduler.hpp L274-348):
  - `size_t num_tokens_in_megabatch = m_config.max_num_batched_tokens - scheduler_output.m_total_num_scheduled_tokens;`
  - `size_t num_scheduled_tokens = std::min(num_tokens_in_megabatch, num_available_tokens);`
  - Then `sequence_group->schedule_tokens(num_scheduled_tokens);`
  - Loop break: `if (scheduler_output.m_total_num_scheduled_tokens == m_config.max_num_batched_tokens) break;`
  - Comment L275-281: *"we need to balance multiple prompts (or parts of prompts) between available amount of tokens in megabatch ... we can slice prompt on chunks and schedule only portion of each prompt"*.

  — [scheduler.hpp L274-348](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/scheduler.hpp#L274-L348)
- **Step ordering.** `if (m_config.dynamic_split_fuse) { // deepspeed-mii case  _schedule_generate_phase_dynamic_split_fuse(...); _schedule_prompt_phase_dynamic_split_fuse(...); } else { // vLLM case ... _schedule_prompt_phase_vllm(...)}` (scheduler.hpp L103-119). In the vLLM path a prompt longer than the budget asserts: `"Sequence length (...) is longer than max number of tokens in batch (...)"` (L471). — [scheduler.hpp L103-119, L448-471](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/scheduler.hpp#L103-L119)
- **Chunking also bounds dynamic cache growth.** Within each scheduled chunk the cache grows via `_try_increase_cache` (scheduler.hpp L298-304, L561-581). With dynamic allocation that may add GPU allocations during prefill. — [scheduler.hpp L298-304](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/scheduler.hpp#L298-L304)
- **Chat history is re-encoded every turn on the CB path.**
  - In `IContinuousBatchingPipeline::generate` with chat mode, `m_history.push_back(user)` is followed by `std::string history = m_tokenizer.apply_chat_template(m_history, add_generation_prompt); input_ids.push_back(m_tokenizer.encode(history, ...).input_ids);` (pipeline_base.cpp L97-106).
  - The `ChatHistory` overload (used by the 2026.2 chat_sample) likewise templates the full history: `std::string templated_history = m_tokenizer.apply_chat_template(histories[i], add_generation_prompt);` (L228-234).
  - The only reuse mechanism is block-level prefix caching. `BlockManager` behaves differently under `m_enable_prefix_caching` (block_manager.hpp L541-568, L1261-1300).

  — [pipeline_base.cpp L97-106, L228-234](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/pipeline_base.cpp#L97-L106); [block_manager.hpp](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/cache/block_manager.hpp)
- **Contrast with the stateful SDPA path,** which keeps the KV in-model across turns and tracks `m_tokenized_chat_history` (pipeline_stateful.cpp L377-386, L501-503). — [pipeline_stateful.cpp](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/llm/pipeline_stateful.cpp#L377-L386)
- **The library's own rationale** for the defaults is the code comments `// don't limit total batch size` and `// for better TTFT in chat scenarios` (utils.cpp L810-811). — [utils.cpp L808-813](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L808-L813)
- **The 256 default is not tuned.** The header TODO says *"benchmark this value and understand a required value to ensure inference is not memory bound"*. — [scheduler_config.hpp L20-23](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/scheduler_config.hpp#L20-L23)
- **Web search** for OpenVINO-specific TTFT reports with small `max_num_batched_tokens` returned only vLLM forum threads on the general chunked-prefill trade-off, not OpenVINO measurements. — [vLLM forum: max-num-batched-tokens](https://discuss.vllm.ai/t/question-about-parameter-max-num-batched-tokens/2012)

### Inferences
- Chunk counts for a single-request prompt of N tokens: ceil(N/256) prefill iterations. That is 16 for 4k tokens, 32 for 8k, and 40 for 10k. Each iteration is a full model forward with host-side scheduling, sampling bookkeeping and an infer-request round-trip, and each attends over the growing KV. Expect higher TTFT than one-shot prefill on an iGPU, where per-launch overhead and small-GEMM inefficiency (256-row matmuls underutilize XMX compared with multi-thousand-row matmuls) are significant. The magnitude has to be measured; I found no published number.
- DEMO-2's NON_RESIDENT control therefore carries two TTFT penalties at once:
  - (a) every turn re-prefills the full history, because prefix caching is off;
  - (b) every prefill is chunked into 256-token pieces.

  A difference against the tuned profile cannot be attributed to "residency" alone.

### Gaps
- No primary-source benchmark or GitHub issue quantifying TTFT vs `max_num_batched_tokens` on Intel GPU/CPU was found. The GitHub issue search API was unavailable in this session. Recommend a direct A/B on the target hardware: default vs SchedulerConfig(max_num_batched_tokens=max, prefix=False) vs bare SchedulerConfig().

---

## Q4. Default KV-cache precision on GPU for INT4-weight LLMs in 2026.2.x. How does the "dynamic" readback relate to the compiled type, and how can the effective type be read?

### Takeaway
In OpenVINO 2026.2.0 and 2026.2.1 the GPU plugin's automatic u4 KV-cache selection for 4-bit-weight PA models is compiled out by a hard-coded `bool auto_enable_4bit_kv = false;`. With no user `KV_CACHE_PRECISION`, a PagedAttention (CB) model on GPU therefore gets **i8** KV cache (key by-channel, value by-token), not u4. The automatic u4 path is live only from 2026.3.x.

For a stateful/SDPA model on XMX-capable GPUs such as Xe2 and Xe3, the default is the inference precision (f16).

`ov::element::dynamic` is only the unfinalized option default. After compilation the compiled-model config holds the concrete type.

The 2026.2 release-note line "INT4 KV-cache compression is enabled for GPUs" conflicts with the 2026.2.x source. In 2026.2 it appears to mean opt-in support, not an automatic default.

### Cited Findings
- **The unfinalized default is `dynamic`:** `OV_CONFIG_RELEASE_OPTION(ov::hint, kv_cache_precision, ov::element::dynamic, "")` (options.inl L32). — [options.inl L32](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/include/intel_gpu/runtime/options.inl#L32)
- **2026.2.1 model-specific finalization** (execution_config.cpp L250-298):
  ```cpp
  bool auto_enable_4bit_kv = false;
  ...
  if (auto_enable_4bit_kv && !has_4bit_weights && has_4bit_matmul_weights(op)) { has_4bit_weights = true; }
  ...
  if (!is_set_by_user(ov::hint::kv_cache_precision) || get_kv_cache_precision() == ov::element::dynamic) {
      if (is_paged_attention_model && has_4bit_weights && m_key_cache_quant_mode != ov::internal::CacheQuantMode::BY_TOKEN) {
          // Enable 4-bit KV-cache compression for PA models with 4-bit compressed weights
          m_kv_cache_precision = ov::element::u4;
      } else if (is_paged_attention_model || !info.supports_immad || is_auxiliary_kv_update_model(model) ) {
          // Enable KV-cache compression by default for:
          // 1) Non-systolic platforms in case of SDPA-based models
          // 2) For any platforms in case of PagedAttention-based model
          m_kv_cache_precision = ov::element::i8;
      } else {
          m_kv_cache_precision = get_inference_precision();
      }
  }
  ```
  `auto_enable_4bit_kv` is never set to true anywhere in the 2026.2.1 intel_gpu tree (grep shows only L250 and L273). `has_4bit_weights` therefore stays false and PA models get i8. — [execution_config.cpp L250-298](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L250-L298)
- **2026.2.0 has the same `bool auto_enable_4bit_kv = false;`** at L246. — [2026.2.0 execution_config.cpp](https://github.com/openvinotoolkit/openvino/blob/2026.2.0/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L246)
- **2026.3.1 removes the guard.** The loop reads `if (!has_4bit_weights && has_4bit_matmul_weights(op)) { has_4bit_weights = true; }`, and `is_paged_attention_model && has_4bit_weights && key_quant_mode != BY_TOKEN` gives `m_kv_cache_precision = ov::element::u4` (L268-292). It also adds an `auxiliary_kv_cache_precision` rt_info override. — [2026.3.1 execution_config.cpp L268-300](https://github.com/openvinotoolkit/openvino/blob/2026.3.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L268-L300)
- **2026.1.2 has no u4 branch at all:** i8 for PA or non-immad, otherwise inference precision (L247-249). — [2026.1.2 execution_config.cpp](https://github.com/openvinotoolkit/openvino/blob/2026.1.2/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L240-L250)
- **Quant modes and type normalization.**
  - Key-cache quant mode defaults to `BY_CHANNEL` and value to `BY_TOKEN` (options.inl L39-40; execution_config.cpp L300-310).
  - A u8 request is normalized to i8, and i4 to u4: *"Replace UINT8 KV-cache compression data type with INT8, as plugin is supposed to work with INT8 internally"* (L356-363).
  - 4-bit PA KV with BY_TOKEN key mode asserts (L311-316).

  — [execution_config.cpp L300-363](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L300-L363)
- **Model rt_info can override the default.** `if (is_paged_attention_model || !info.supports_immad) { apply_rt_info_property(ov::hint::kv_cache_precision, rt_info); }` (L161-167). A `runtime_options/KV_CACHE_PRECISION` entry in `openvino_model.xml`, which some optimum-intel exports write, changes the PA default. — [execution_config.cpp L161-167](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L161-L167)
- **The readback is the finalized value.**
  - `Plugin::compile_model` calls `config.finalize(context.get(), transformed_model.get());` and then `std::make_shared<CompiledModel>(..., config)` (plugin.cpp L255-266).
  - `PluginConfig::finalize` calls `apply_model_specific_options(context, *model)` first, then re-applies user properties, then `finalize_impl` (plugin_config.cpp L102-121).
  - `CompiledModel::get_property` returns `m_config.get_property(name, OptionVisibility::RELEASE)`, with `KV_CACHE_PRECISION` listed as RO (compiled_model.cpp L278, L295).

  — [plugin.cpp L255-266](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/plugin/plugin.cpp#L255-L266); [plugin_config.cpp L102-121](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/inference/src/dev/plugin_config.cpp#L102-L121); [compiled_model.cpp L249-295](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/plugin/compiled_model.cpp#L249-L295)
- **GenAI reads the effective KV type from the compiled model's inputs.** In `KVCacheManager`, `auto cache_precision = input.get_element_type();` for inputs named `key_cache.*` / `value_cache.*`, which also sizes the blocks (kv_cache_manager.hpp L72-93). It applies u4 sub-byte handling where needed (L154, L219-230). — [kv_cache_manager.hpp L72-93](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/cache/kv_cache_manager.hpp#L72-L93)
- **GenAI can dump all compiled-model properties.**
  - `print_compiled_model_properties(compiled_model, "LLM with Paged Attention")` is called after compile (pipeline_impl.cpp L173).
  - It prints `Model: <title>` and every supported compiled property, but only if `env_setup_for_print_debug_info()` returns true, i.e. when `OPENVINO_LOG_LEVEL` is greater than `ov::log::Level::WARNING` (utils.cpp L594-614).

  — [utils.cpp L594-614](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L594-L614); [pipeline_impl.cpp L173](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/pipeline_impl.cpp#L173)
- **CPU default (for comparison):** `kvCachePrecision = keyCachePrecision = valueCachePrecision = ov::element::u8` under `#if defined(OPENVINO_ARCH_X86_64) || defined(OPENVINO_ARCH_ARM64)`, and f16 otherwise (config.h L76-84).
  - Model rt_info `runtime_options/KV_CACHE_PRECISION` overrides it if the property is not set explicitly (config.cpp L594-597).
  - `EXECUTION_MODE=ACCURACY` forces f32 KV (config.cpp L540-552).

  — [intel_cpu config.h L76-84](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_cpu/src/config.h#L76-L84); [intel_cpu config.cpp L526-552, L594-597](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_cpu/src/config.cpp#L526-L597)
- **Release notes, 2026.2 (28 May 2026), "What's New":** *"INT4 KV-cache compression is enabled for GPUs, with substantial memory reduction when KV cache size is significant, such as with large input prompts exceeding 32K tokens."* The GPU section adds: *"INT4 KV cache quantization has been enabled, reducing memory consumption for key-value cache storage during LLM inference."* The same lines sit under the 2026.2 section of the 2026.3.1 notes; the 2026.3 section, dated 4 Aug 2026, does not repeat them. — [release-notes-openvino.rst @2026.2.1 L42, L80](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/docs/articles_en/about-openvino/release-notes-openvino.rst); [release-notes-openvino.rst @2026.3.1](https://github.com/openvinotoolkit/openvino/blob/2026.3.1/docs/articles_en/about-openvino/release-notes-openvino.rst). This contradicts the 2026.2.0/2026.2.1 source, where automatic u4 is disabled ([execution_config.cpp L250](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L250)).

### Inferences
- Prior literature note (b), that "the default KV cache compiles to u4 in 2026.2", is **not supported by the 2026.2.x source**.
  - On 2026.2.1 GPU with the default PA backend and no KV property, the expected KV type is i8, unless the IR's rt_info sets one.
  - u4 becomes the automatic default for 4-bit-weight PA models only in 2026.3.x.
  - In 2026.2 "INT4 KV enabled" most plausibly means u4 is supported when requested, e.g. `KV_CACHE_PRECISION="u4"`. This is an inference: the PR text was not reachable.
- **Where a "dynamic" readback comes from.** The source says a compiled model reports the finalized concrete type. A "dynamic" readback most likely came from querying the plugin or core (`core.get_property("GPU", "KV_CACHE_PRECISION")`), which returns the unfinalized default, rather than the compiled model. It does not mean the compiled cache is dynamic or u4.
- **Reading the effective type in a GenAI run:** set `OPENVINO_LOG_LEVEL` to INFO or higher before constructing the pipeline and read `KV_CACHE_PRECISION` from the "Model: LLM with Paged Attention" dump. Cross-check against the bytes per block / KV memory in the perf metrics. In a standalone check, compile the PA-transformed model and inspect the `key_cache.*` input element types, which is what GenAI itself uses.
- **SDPA fallback case:** if the pipeline falls back to SDPA/stateful on Xe2/Xe3 (supports_immad), the default KV would be f16 (inference precision), not i8. Confirming which backend ran is therefore essential for interpreting KV memory.
- **Consequence for DEMO-2.** The tuned profile's "explicit KV precision" is only a real change relative to the control if it differs from i8 on 2026.2.1. On 2026.3.x the baseline would differ (u4).

### Gaps
- I did not determine whether Qwen3-4B INT4 IRs from current optimum-intel carry a `runtime_options/KV_CACHE_PRECISION` rt_info entry. Check `openvino_model.xml` for `<runtime_options>`.
- I could not retrieve the PR that introduced `auto_enable_4bit_kv = false` or explains the 2026.2 release-note wording (GitHub API unavailable). The exact `ov::log::Level` integer threshold for `OPENVINO_LOG_LEVEL` was not re-verified from source; use 3 or 4 to be safe.

---

## Q5. Is there a default context/window cap on GPU, or only max_position_embeddings / memory?

### Takeaway
On GPU and CPU (non-NPU) GenAI imposes no default prompt-length or context cap. `max_new_tokens` and `max_length` default to SIZE_MAX unless `generation_config.json` sets them. The PA backend grows the KV cache dynamically, bounded by device memory. The only hard prompt-length cap found in the LLM pipeline is NPU's `MAX_PROMPT_LEN`. I found no runtime check against `max_position_embeddings`.

### Cited Findings
- `size_t max_new_tokens = SIZE_MAX; size_t max_length = SIZE_MAX;` (generation_config.hpp L635-636). LLMPipeline loads `generation_config.json` if it exists (`utils::from_config_json_if_exists(models_path)`, pipeline.cpp L220). — [generation_config.hpp L635-636](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/generation_config.hpp#L635-L636)
- **NPU-only prompt cap:** `OPENVINO_ASSERT(data->get_size() <= m_max_prompt_len, ... "Set the \"MAX_PROMPT_LEN\" config option to increase the limit.")` (pipeline_stateful.cpp L348-367), with `m_max_prompt_len` read from `NPUW_LLM_MAX_PROMPT_LEN` (L26). — [pipeline_stateful.cpp L20-30, L345-367](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/llm/pipeline_stateful.cpp#L345-L367)
- **The GPU memory bound for dynamic KV** (`get_available_gpu_memory`, utils.cpp L950-983):
  - It sums `cl_mem` + `usm_device`, plus `usm_host` when `device_type == INTEGRATED`.
  - It multiplies that by a `used_memory_threshold = 1.1`.
  - It returns `std::min(total_device_memory - used_device_mem, max_alloc_memory_size * num_cache_tensors)`.

  — [utils.cpp L950-983](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L950-L983)
- **A fixed budget is only applied when requested.** If `cache_size > 0`, the budget is `cache_size` GiB and must be ≤ available memory (`"Requested cache size is larger than available memory size on the system."`) (cache_orchestrator.hpp L757-760). — [cache_orchestrator.hpp L747-800](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/cache/cache_orchestrator.hpp#L747-L800)
- A grep of `src/cpp/src/llm/*` and `continuous_batching/*` at 2026.2.1.0 for `max_position_embeddings` returned no matches.

### Inferences
- The effective bounds on the target machines are memory, via the 1.1x safety margin on used memory for integrated GPUs that share system RAM, and the model's trained context (`max_position_embeddings`, 40,960 for Qwen3-4B per its config). GenAI does not enforce the latter. Quality degrades past it, but nothing errors.

### Gaps
- I did not check whether the RoPE/positional subgraph in the IR constrains length at runtime (e.g. a precomputed sin/cos table size). Not found in GenAI source; it may be model/IR-specific.

---

## Q6. The officially recommended "default" way to build a chat pipeline in 2026.2. Do the docs recommend prefix caching for multi-turn chat?

### Takeaway
The official 2026.2 `chat_sample.py` builds `openvino_genai.LLMPipeline(args.model_dir, device)` with no properties and no SchedulerConfig, device default `"CPU"`. It runs multi-turn chat by passing a growing `ChatHistory` to `generate()`. The GenAI chat guide shows the same pattern. Neither tells users to enable prefix caching; that is unnecessary because the LLMPipeline latency default already turns it on "for better TTFT in chat scenarios".

### Cited Findings
- **chat_sample.py (2026.2.1.0):**
  - `parser.add_argument("device", nargs="?", default="CPU", ...)`
  - `pipe = openvino_genai.LLMPipeline(args.model_dir, device)`
  - `config.max_new_tokens = 100`
  - `chat_history = openvino_genai.ChatHistory()`, then a loop: `chat_history.append({"role": "user", ...}); decoded_results = pipe.generate(chat_history, config, streamer); chat_history.append({"role": "assistant", ...})`

  — [chat_sample.py](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/samples/python/text_generation/chat_sample.py)
- **The GenAI chat guide** says: *"For chat applications, OpenVINO GenAI provides special optimizations to maintain conversation context and improve performance using KV-cache."* Its example is `pipe = ov_genai.LLMPipeline(model_path, 'CPU')` with `ChatHistory`, and the guide has no prefix-caching or SchedulerConfig guidance (site/docs/guides/chat-scenario.mdx L8-48). — [chat-scenario.mdx](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/site/docs/guides/chat-scenario.mdx)
- **The prefix-caching concept page is a stub:** "# Prefix Caching > **Note:** This page is a work in progress." The continuous-batching page is also marked work in progress. — [prefix-caching.md](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/site/docs/concepts/optimization-techniques/prefix-caching.md); [continuous-batching.md](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/site/docs/concepts/optimization-techniques/continuous-batching.md)
- **The code-level rationale** is `default_config.enable_prefix_caching = true; // for better TTFT in chat scenarios` (utils.cpp L811). — [utils.cpp L811](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L811)

### Inferences
- The officially sanctioned default for a chat pipeline in 2026.2 is `LLMPipeline(model_dir, device)` with nothing else. On GPU that means PA/CB with prefix caching ON, unlimited batch tokens, dynamic KV, and i8 KV (2026.2.x). That is the configuration a "runtime default" control should reproduce.
- The DEMO-2 registered control (explicit bare SchedulerConfig, prefix off, which also implies 256-token chunking) is a deliberately degraded configuration. It is not the runtime default, and it should be labeled as such: for example "bare-SchedulerConfig / CB-struct default", or "no-prefix-cache, chunked-256". Otherwise the comparison overstates the tuned profile's gain relative to what a user gets out of the box.

### Gaps
- The docs.openvino.ai rendered 2026 pages were not fetched separately. The repo `site/docs` and OV `docs/articles_en` sources at the release tags were used instead, as the authoritative source of those pages.
