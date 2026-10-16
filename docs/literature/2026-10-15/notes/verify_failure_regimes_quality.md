# Verify failure regimes and quality findings for local LLM inference (sweep 5)

Note on method: About 24 tool calls. The Ollama FAQ (docs.ollama.com/faq) could not be fetched because the fetch tool's provenance rule blocked it. The Ollama context-length doc page was fetched instead. Several claims rest on one secondary source, and each is flagged.

## A. Failure regimes under memory pressure (silent truncation / unified spill / discrete OOM)

### Takeaway
A1 (context-managed runtimes truncate silently) is **corroborated for Ollama** and only **partially corroborated for llama.cpp**: current llama-server builds return HTTP 400 rather than shifting context. A2 (unified memory spills and pays latency) is **partially corroborated** for Apple, but the failure is a system-wide slowdown or hang, not a clean "latency only" result. The Intel iGPU CL_OUT_OF_RESOURCES result has a documented cause: Intel's roughly 4 GB single-allocation limit on pre-Xe2 hardware. That is a per-buffer limit, not a total-memory one, so it does not have to contradict A2 if the paper words it carefully. A3 (discrete GPU raises an explicit error) is **corroborated for vLLM**, which fails fast at startup, and **contradicted/qualified for Ollama**, which offloads layers to CPU instead of erroring.

### Cited Findings
**A1: silent truncation (Ollama), corroborates**
- No response field, header or `finish_reason` reports truncation on any Ollama endpoint. Whole-message dropping is logged only at DEBUG (`truncating native chat messages which exceed context length`, needs `OLLAMA_DEBUG=1`). Token-level shifting is logged at WARN as `truncating input prompt`. The source read tag v0.33.1. — [Particula Tech blog (secondary, source-code reading)](https://particula.tech/blog/ollama-num-ctx-silent-prompt-truncation)
- The official Ollama context-length page says nothing about truncation or what happens when input exceeds the window. It only warns that a larger context "will increase the amount of memory required." — [Ollama docs: Context length](https://docs.ollama.com/context-length)

**A1: llama.cpp context shift, partial / contradicts for current builds**
- llama.cpp issue #17284, "Server Fails with HTTP 400 (Context Size Exceeded) Instead of Truncating Chat History": older builds (e.g., b6721) truncated without an error, and current builds (e.g., b7062) return HTTP 400. Users say context shift was removed in PR #16391 without a deprecation notice. One user saw generation stop mid-sentence with no error, followed by a 400 on the next request. — [llama.cpp issue #17284](https://github.com/ggml-org/llama.cpp/issues/17284)
- ggerganov, as quoted in that thread: "context truncation is the job of the client, not the server". He said any reintroduced truncation option "can be off by default". A commenter says the docs list `--no-context-shift` as the default. — [llama.cpp issue #17284](https://github.com/ggml-org/llama.cpp/issues/17284)
- Commenters describe context shift as lossy: it "literally truncates the content," can drop system prompts and break chat templates. — [llama.cpp issue #17284](https://github.com/ggml-org/llama.cpp/issues/17284)

**A1: "confident, categorical wrong answers with no hedging"**
- No external source directly measured hedging or abstention after silent truncation. See Gaps.

**A2: unified-memory spill (Apple), partial**
- A model that fits at an empty prompt can end up "in swap forty turns later" as the context grows. Symptoms are memory-pressure red, UI stutter, and tok/s collapsing "partway through a long reply". If you raise the GPU wired limit too far, you don't get "a polite error"; you get "a machine that stops redrawing." — [LocalAIMaster: Mac memory pressure (secondary)](https://localaimaster.com/blog/mac-memory-pressure-local-llm)
- llama.cpp on Metal warns, without failing: "warning: current allocated size is greater than the recommended max working set size." The often-quoted "75% of RAM" GPU cap could not be confirmed from a first-party source. Read `recommendedMaxWorkingSetSize` per machine instead. — [LocalAIMaster (secondary)](https://localaimaster.com/blog/mac-memory-pressure-local-llm)
- Status: corroborates "output intact, pays latency" on Apple. It also adds a failure mode the claim does not mention: over-commit can stall the whole system.

**A2 vs. Intel CL_OUT_OF_RESOURCES: explains the anomaly**
- Intel compute-runtime issue #627, "Too low 4GB allocation limit on Intel Arc GPUs (CL_DEVICE_MAX_MEM_ALLOC_SIZE)": the single-buffer limit is about 4 GB (3.86 GB on A750). Larger buffers fail with error -61 (`CL_INVALID_BUFFER_SIZE`). The workaround is `CL_MEM_ALLOW_UNRESTRICTED_SIZE_INTEL` plus the build option `-cl-intel-greater-than-4GB-buffer-required`, which has a performance cost. Intel (MichalMrozek): "We have no plans to change the defaults on older Hardware". Large buffers are the default only on Xe2+ and PVC. — [intel/compute-runtime #627](https://github.com/intel/compute-runtime/issues/627)
- Caveat: that thread is about discrete Arc and error -61, not CL_OUT_OF_RESOURCES (-5) on an iGPU. The same per-allocation and 32-bit-offset limits apply to Gen9–Xe-LP iGPUs, so this is a likely cause, not a confirmed one.

**A3: discrete-VRAM explicit error, partial**
- vLLM fails fast at startup: "ValueError: To serve at least one request with the models's max seq len (10485760), (240.00 GiB KV cache is needed, which is larger than the available KV cache memory (88.38 GiB)." There is an RFC for `--max-model-len auto`. — [vLLM issue #19407](https://github.com/vllm-project/vllm/issues/19407)
- Ollama does not error by default. It offloads to CPU. The official doc tells users to check the PROCESSOR column in `ollama ps` and to "avoid offloading the model to CPU" for best performance. That means CPU or GPU split is the normal response to VRAM shortage. — [Ollama docs: Context length](https://docs.ollama.com/context-length)
- In a small BFCL quantization study, Qwen3-1.7B at fp16 "ran out of CUDA memory" on a 4 GB laptop GPU under llama.cpp. This is anecdotal support that llama.cpp with full GPU offload errors explicitly on NVIDIA. — [DEV Community: Does quantization break tool calling?](https://dev.to/happynood/does-quantization-break-tool-calling-i-measured-it-on-a-4gb-laptop-gpu-bfcl-3-seeds-bootstrap-185l)

### Inferences
- The three-regime taxonomy holds better as a "runtime policy × memory architecture" grid than as a hardware-only split. On the same NVIDIA GPU, Ollama silently spills to CPU (latency regime), llama.cpp with a fixed `-ngl` errors, and vLLM refuses to start.
- The Intel iGPU CL_OUT_OF_RESOURCES fits as a fourth sub-case: unified memory does not prevent explicit failures when the driver caps per-allocation size or the GPU-visible budget. The paper should say unified memory removes the capacity cliff but not driver-imposed allocation cliffs.
- For llama.cpp, the claim needs a build number. Silent shift applies to older builds or `--context-shift`; current llama-server gives an explicit 400.

### Gaps
- No peer-reviewed or vendor source measured answer confidence or hedging after silent context truncation. The "confident categorical wrong answer" claim rests on our own data.
- No first-party Apple documentation was found on GPU wired-memory defaults or swap/compression behaviour for Metal LLM workloads.
- No source specifically on CL_OUT_OF_RESOURCES for llama.cpp's OpenCL or SYCL backend on Intel iGPUs. llama.cpp issue #5441 showed up in search but was not fetched.
- No primary source (Ollama code or docs) was fetched for Ollama's layer-offload algorithm.

## B. Ollama default context length, history, silence, configuration

### Takeaway
**Partially contradicts "4096 default."** Current Ollama uses a VRAM-tiered default: 4k below 24 GiB, 32k for 24–48 GiB, 256k at 48 GiB or more. History is 2048 → 4096 (April 2025) → VRAM-tiered (February 2026). For hosts under 24 GiB of VRAM, including iGPU and CPU-only, the effective default is still 4096, so our measurement is valid for our hardware if the paper states the version and VRAM tier.

### Cited Findings
- Official wording: "Ollama defaults to the following context lengths based on VRAM: < 24 GiB VRAM: 4k context; 24-48 GiB VRAM: 32k context; >= 48 GiB VRAM: 256k context". "Tasks which require large context like web search, agents, and coding tools should be set to at least 64000 tokens." — [Ollama docs: Context length](https://docs.ollama.com/context-length)
- History, from a source-code reading (secondary): commit `424f6486` (2025-04-22) raised the fallback from 2048 to 4096. Commit `0334ffa6` (2026-02-02) added VRAM tiering: 262144 at 47 GiB or more, 32768 at 23 GiB or more, otherwise 4096, including CPU-only. The source says the FAQ "still states 4096" and calls it stale. — [Particula Tech](https://particula.tech/blog/ollama-num-ctx-silent-prompt-truncation)
- Small discrepancy: the docs say 24/48 GiB thresholds, while the code reading says 23/47 GiB. These are probably rounding or headroom in code, but should be cited as "about 24/48 GiB". — [Ollama docs](https://docs.ollama.com/context-length); [Particula Tech](https://particula.tech/blog/ollama-num-ctx-silent-prompt-truncation)
- Ways to raise it, in rising precedence:
  - `OLLAMA_CONTEXT_LENGTH` on the server; unset or 0 triggers VRAM tiering.
  - Modelfile `PARAMETER num_ctx` plus `ollama create`, which also works via `/v1`.
  - CLI `/set parameter num_ctx`.
  - Native API `options.num_ctx` on `/api/chat` or `/api/generate`, which has the highest precedence.
  - In the OpenAI-compatible `/v1` request body, `num_ctx` is silently discarded.
  - Verify with the CONTEXT column of `ollama ps`. — [Particula Tech](https://particula.tech/blog/ollama-num-ctx-silent-prompt-truncation); env var and `ollama ps` confirmed by [Ollama docs](https://docs.ollama.com/context-length)
- What caps it: memory. "Ensure you have enough VRAM available to increase the context length". Past VRAM, Ollama offloads to CPU (PROCESSOR column). — [Ollama docs](https://docs.ollama.com/context-length)
- Silence: see A1. No API-level signal; DEBUG- or WARN-level logs only. — [Particula Tech](https://particula.tech/blog/ollama-num-ctx-silent-prompt-truncation)

### Inferences
- Any paper statement should read something like: "Ollama ≥ v0.x (Feb 2026+) on hosts with < 24 GiB VRAM defaults to 4096 tokens." Pre-April-2025 releases default to 2048. Workstation GPUs with 24 GB or more get 32k by default, which would hide the failure regime.
- The `/v1` silent discard of `num_ctx` is a second silent-failure path worth mentioning: clients using the OpenAI SDK cannot raise context per request.

### Gaps
- The exact Ollama release tag that first shipped commit `0334ffa6` was not confirmed from Ollama release notes.
- The Ollama FAQ page could not be fetched to confirm the "stale 4096" wording.

## C. Retention: positional truncation vs. semantic/observation pruning

### Takeaway
**Partially corroborates the direction.** Published work shows tool observations dominate agent context and can be masked or compressed with no loss of correctness. No source reproduces the specific "21% needed vs. 44–76% retained" or "4.7× usable context" figures; those remain our own contribution.

### Cited Findings
- "Observation tokens make up around 84% of an average SWE-agent turn". This comes from a preliminary SWE-bench Lite-50 subset. — [Lindenbauer et al., "The Complexity Trap", arXiv 2508.21433v3 (JetBrains/TUM; NeurIPS 2025 DL4Code workshop)](https://arxiv.org/html/2508.21433v3)
- Observation masking (rolling window M = 10) roughly halves cost compared with the raw agent and matches LLM summarization on SWE-bench Verified. Cost vs. raw agent and solve rate (masking vs. summary):

  | Model | Masking cost | Solve rate, masking vs. summary |
  |---|---|---|
  | Qwen3-Coder-480B | -52.7% | 54.8% vs. 53.8% |
  | Gemini 2.5 Flash | -56.1% | 35.6% vs. 36.0% |
  | Qwen3-32B | -50.9% | 15.0% vs. 16.0% |

  A hybrid approach cuts cost by a further 7% vs. masking and 11% vs. summary. — [arXiv 2508.21433v3](https://arxiv.org/html/2508.21433v3)
- ACON (Kang et al., Microsoft): "reduces peak token usage by 26-54%" while improving task success over compression baselines on AppWorld, OfficeBench and Multi-objective QA. A compressor distilled into smaller LMs gives "up to a 46% performance gain" for small-model agents, attributed to reduced context distraction. arXiv 2510.00615 (v2 2025-10-17); listed at ICLR 2026, ICML 2026 and PMLR v306. — [arXiv 2510.00615](https://arxiv.org/abs/2510.00615v2); [PMLR v306](https://proceedings.mlr.press/v306/kang26b.html)

### Inferences
- Our ~4.7× usable-context gain from semantic retention is the same order as the published results: about 2× cost reduction from masking alone, and up to about 2.2× peak-token reduction (54%) from ACON. Ours is larger because it is measured at a fixed small window on memory-capped devices, which is a different metric. Present it as consistent with, not replicated by, prior work.
- The 46% small-model gain in ACON supports the idea that removing irrelevant tool output can improve, not just preserve, small-model correctness.

### Gaps
- LLMLingua, LLMLingua-2 and "Tool Attention" were not fetched in this sweep; no numbers were collected for them.
- No source quantifies how much of a tool artifact a task actually needs (our ~21%) or how much positional truncation keeps.

## D. Quality: Qwen3-4B BFCL v4 multi-turn, INT4 vs. INT8 tool-call parse failures, KV-cache quantization

### Takeaway
**Partial.** The public BFCL v4 multi-turn score for Qwen3-4B-Instruct-2507 (FC) is 22.1%, about twice our 10–11.5%, so our pipeline (quantization, context cap, prompt format) costs roughly 10 points. That should be disclosed, not treated as a contradiction. "INT4 equal completion but more unparseable calls" is **corroborated in kind** by 2026 work: aggregate scores hide quantization damage while specific failure modes, such as missed calls and hallucinated tool names, increase. One study found no missed-call increase for Qwen3-4B at NF4 on single-turn BFCL, which partly contradicts us at that size. KV-cache quantization to 2-bit with per-channel keys (KIVI) is nearly lossless on LongBench. Naive 2-bit is not.

### Cited Findings
**BFCL v4 baseline**
- Qwen3-4B-Instruct-2507 (FC) on BFCL v4:

  | Category | Score |
  |---|---|
  | Overall | 35.7% (rank 51 of 98) |
  | Multi-turn | 22.1% |
  | Non-live AST | 87.9% |
  | Live | 76.4% |
  | Web search | 3.0% |
  | Memory | 17.6% |

  Multi-turn sub-scores (V3-labelled): Base 26.5, Miss Func 21.0, Miss Param 15.5, Long Context 25.5. The aggregator pulls from Gorilla's `data_overall.csv` and `data_multi_turn.csv`, with no collection date given. Secondary aggregator. — [BenchmarkList: Qwen3-4B-Instruct-2507](https://benchmarklist.com/models/qwen3-4b-instruct-2507/)

**Quantization and tool calling**
- Roshaan, Aaliyan & Bin Zubair, "Compression Breaks Discipline: Quantization Increases Missed Tool Calls in Small Language Models, but Not Mid-Size Ones" (NeurIPS 2026 SLM-Agents workshop). Setup: BFCL single-turn, 600 generations, FP16 vs. NF4, greedy decoding. — [NeurIPS 2026 poster](https://neurips.cc/virtual/2026/171153)
  - Qwen3-1.7B missed required calls: 6.0% → 17.3% (Δ 11.3 pp, McNemar p = 0.0001).
  - Qwen3-4B: 7.3% → 7.3%, no change, with nominally higher accuracy.
  - Size interaction: p = 0.006.
  - 13 of 26 NF4 misses were correct under FP16.
  - Conclusion: damage is "lost tool-calling discipline rather than lost knowledge."
- Jang, Yang, Lim & Park, "Flat Score, Amplified Failures…" (arXiv 2607.27275, 2026-07-31). Setup: 16/8/4-bit weights, two families × dense/MoE × telecom/retail, 456 episodes per cell. — [DevelopersDigest summary (secondary; PDF text not machine-readable)](https://www.developersdigest.tech/papers/flat-score-amplified-failures-quantized-llm-agents)
  - No aggregate score change survives correction; equivalence is bounded at ±7.5 points.
  - Quantization amplifies failures the model already had by up to 2.5× (+17.6 points per task), e.g., tool-name hallucination.
  - A 10-error budget hides this; a 2-error budget reveals a 17-point gap.
- DEV Community study (2026, llama.cpp GGUF, 3 seeds, bootstrap CI). — [DEV Community (non-peer-reviewed)](https://dev.to/happynood/does-quantization-break-tool-calling-i-measured-it-on-a-4gb-laptop-gpu-bfcl-3-seeds-bootstrap-185l)
  - Qwen3-1.7B: Q4_K_M vs. Q8_0 shows no significant drop on BFCL simple and irrelevance (FCR 0.844 vs. 0.842).
  - Qwen3-0.6B at Q4_K_M: small significant drops in AC and FCR.
  - Llama-3.2-1B on parallel/ToolACE: syntax-valid rate falls from 0.572 (fp16) to 0.338 (Q4_K_M).
  - Unparseable-call counts were not recorded.

**KV-cache quantization and long context**
- KIVI (Liu et al., ICML 2024), 2-bit per-channel K / per-token V, LongBench average 16-bit → 2-bit: Llama2-7B 44.52 → 44.27; Mistral-7B 46.58 → 45.85; Llama-3-8B-Instruct 45.21 → 44.37. Needle-in-a-haystack is shown only as heatmaps, with retrieval said to be retained. Peak memory falls about 2.6×, throughput rises 2.35–3.47×. — [KIVI, arXiv 2402.02750](https://arxiv.org/pdf/2402.02750)
- Naive per-token 2-bit KV quantization collapses. On Llama-2-7B: CoQA 63.88 → 39.88, GSM8K 13.50 → 0.83. On the same naive scheme, "4 bits" is described as accurate. — [KIVI](https://arxiv.org/pdf/2402.02750)

### Inferences
- Our INT4 "same completion, 4.6× more no-parse entries (32 vs. 7)" matches the pattern in Jang et al. and Roshaan et al.: aggregate metrics stay flat while format and discipline failures grow. It goes against Roshaan et al.'s single-turn null result for Qwen3-4B. Plausible reasons: multi-turn BFCL and longer contexts stress format adherence more, and INT4 schemes differ (NF4 vs. GGUF Q4/AWQ/GPTQ). The paper should name the INT4 scheme.
- Our 10–11.5% multi-turn vs. the public 22.1% (FC, likely BF16 with full context) suggests about 10 points are lost to the local configuration. The paper should cite the leaderboard number as the upper reference.
- KV quantization at 8-bit, or 4-bit with per-channel keys, is unlikely to explain our quality loss. Naive 2-bit would.

### Gaps
- KVQuant (Hooper et al.) and llama.cpp `--cache-type-k q4_0/q8_0` long-context recall numbers were not fetched.
- No published source reports INT4 vs. INT8 unparseable tool-call counts on BFCL multi-turn for Qwen3-4B specifically.
- The BFCL v4 numbers came from a secondary aggregator. The official gorilla.cs.berkeley.edu leaderboard was not fetched, and the snapshot date and version are unknown.
- Full text of arXiv 2607.27275 was not machine-readable; model names and failure breakdown are unconfirmed.
