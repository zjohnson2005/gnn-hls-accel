# Physics of the data path: local LLM agent inference on Intel Panther Lake (Xe3) unified-memory iGPUs

> Correction 2026-10-20 (Task AX): measured on XPS run 39c1c131 (arm A local_only, DEMO1_BASE_30, 118 local turns), a local turn generates a median of 91 tokens (p90 157), not 130-255.

Scope: Qwen3-4B INT4 under OpenVINO GenAI on (a) Core Ultra 5 325 laptop (16 GB) and (b) Arc B390 mini PC (64 GB). All "derived" numbers below are ESTIMATES computed by the researcher from the team's own measurements plus cited specs; they are labeled as such. Researched through Oct 2026.

Note on access: arXiv 2605.10380 ("Agent-X: Full Pipeline Acceleration of On-device AI Agents") could not be read (the fetch proxy rate-limited it), so its contents are not reflected here.

## 1. Hardware specs (Panther Lake / Core Ultra 300, Core Ultra 5 325, Arc B390)

### Takeaway
The Core Ultra 5 325 does NOT have an Arc B390. It has a 4-Xe3-core "Intel Graphics" iGPU and Notebookcheck lists its memory as LPDDR5X-7467 on a 128-bit bus, which gives about 119.5 GB/s theoretical peak. That calculation is the defensible source for "~120 GB/s", and it applies only to the 325 with LPDDR5X-7467. The B390 has 12 Xe3 cores and 16 MB of L2, and is usually paired with LPDDR5X-9600 (about 153.6 GB/s theoretical on 128 bits). No source fetched gives an official per-GPU XMX TOPS figure.

### Cited Findings
- Core Ultra 5 325: 8 cores (4 Cougar Cove P-cores up to 4.5 GHz + 4 Darkmont LP E-cores up to 3.4 GHz). iGPU is "Intel Graphics 4 Xe3" at 2450 MHz. Memory up to 96 GB LPDDR5X-7467 or 128 GB DDR5-6400. Power is 25 W base (PL1), 55 W max turbo (PL2), 15 W minimum assured. NPU is 50 TOPS INT8. Caches: L2 16 MB, L3 12 MB — [Notebookcheck: Core Ultra 5 325](https://www.notebookcheck.net/Intel-Core-Ultra-5-325-Processor-Benchmarks-and-Specs.1196417.0.html)
- Wikipedia's SKU table lists the Core Ultra 5 325 with "Intel Graphics, 4 Xe cores" and NPU **47 TOPS (int8)**. That conflicts with Notebookcheck's 50 TOPS for the same SKU, and Wikipedia's table cells are misaligned, so treat NPU TOPS for the 325 as 47–50 — [Wikipedia: Panther Lake](https://en.wikipedia.org/wiki/Panther_Lake_(microprocessor)); [Notebookcheck](https://www.notebookcheck.net/Intel-Core-Ultra-5-325-Processor-Benchmarks-and-Specs.1196417.0.html)
- Panther Lake platform memory support: LPDDR5X-9600 and DDR5-7200, 2 channels, up to 128 GB. NPU 5 is "up to 50 TOPS (int8)", about the same as the previous generation's NPU but in a smaller block. Arc B390 = 12 Xe cores, up to 2.5 GHz (Core Ultra X9 388H). Arc B370 = 10 Xe cores. Smaller tiles have up to 4 Xe cores and are branded "Intel Graphics" — [Wikipedia: Panther Lake](https://en.wikipedia.org/wiki/Panther_Lake_(microprocessor))
- Branding rule: the B390/B370 names apply only with memory of at least LPDDR5X-7467. Otherwise the iGPU is labeled plain "Intel Graphics" — [Wikipedia](https://en.wikipedia.org/wiki/Panther_Lake_(microprocessor)); [3DTested](https://www.3dtested.com/pc-components/cpus/intel-mandates-at-least-7-467-mt-s-ram-speed-for-panther-lake-slower-memory-will-relabel-the-arc-b370-and-b390-igpus-as-generic-intel-graphics-in-task-manager)
- Xe3 microarchitecture (Chips and Cheese, ITT 2025):
  - Each Xe core keeps "the same 8 512 bit Vector Engines and 8 2048 bit Matrix Engines" as Xe2.
  - A render slice holds up to 6 Xe cores (up from 4).
  - L1/SLM grows from 192 KB to 256 KB.
  - The 12-Xe GPU has 16 MB of L2 (vs 8 MB), which cuts SoC fabric traffic "by up to 36%".
  - The compute tile has "the 8MB Memory Side Cache alongside the 128b memory bus".
  - The NPU shrinks about 40% vs Lunar Lake and gains FP8 support.
  — [Chips and Cheese: Panther Lake's Reveal at ITT 2025](https://old.chipsandcheese.com/2025/10/14/panther-lakes-reveal-at-itt-2025/)
- Arc B390 test system (Core Ultra X9 388H) used 32 GB LPDDR5X-9600 with 16 MB L2 and a 2.5 GHz max GPU clock:
  - Full GPU performance draws about 38–40 W for the GT cores, roughly 52 W package.
  - Time Spy Graphics at package limits of 20/28/35/45 W scored 4,567 / 5,600 / 6,321 / 6,830. At 20 W the score is about 33% below 45 W.
  - Notebookcheck does not state XMX TOPS, TFLOPS or bandwidth.
  — [Notebookcheck: Arc B390 analysis](https://www.notebookcheck.net/Intel-Panther-Lake-Arc-B390-performance-and-efficiency-analysis-Intel-s-new-iGPU-trades-blows-with-the-Nvidia-GeForce-RTX-4050.1212582.0.html)
- Intel's official infographic claims "Up to 180 platform TOPS" with no per-component split. It gives no GPU TOPS, memory speed or Xe-core count — [Intel ITT Panther Lake infographic (PDF)](https://download.intel.com/newsroom/2025/client-computing/itt-panther-lake-Infographic.pdf)
- GMKtec EVO-T2 is a Panther Lake mini PC with an 80 W TDP, an Arc B390 and "up to 128 GB of ultra-fast LPDDR5x" (headline only; the exact speed was not verified) — [Notebookcheck: GMKtec EVO-T2](https://www.notebookcheck.net/GMKtec-previews-EVO-T2-as-first-Intel-Panther-Lake-mini-PC-with-80-W-TDP-Arc-B390-iGPU-and-up-to-128-GB-of-ultra-fast-LPDDR5x-RAM.1167272.0.html)

### Inferences
- **Theoretical bandwidth (DERIVED = MT/s × 128 bit / 8, using Chips and Cheese's 128b bus):**

  | Memory | Theoretical bandwidth |
  |---|---|
  | LPDDR5X-7467 | 119.5 GB/s |
  | LPDDR5X-8533 | 136.5 GB/s |
  | LPDDR5X-9600 | 153.6 GB/s |

  "~120 GB/s" is therefore defensible only as a derived theoretical peak for the Core Ultra 5 325 if the XPS ships LPDDR5X-7467. The team should confirm the actual DIMM speed, e.g. via CPU-Z/HWiNFO.
- **XMX throughput (ESTIMATE, not sourced this session):**
  - Basis: Chips and Cheese says Xe3 keeps Xe2's 8×2048-bit matrix engines per Xe core. If Xe2's commonly quoted rate of about 2048 FP16 FLOP/clk (4096 INT8 ops/clk) per Xe core carries over, then:
    - 4-Xe3 at 2.45 GHz ≈ 20 TFLOPS FP16 / 40 TOPS INT8 (dense).
    - B390 (12 Xe at 2.5 GHz) ≈ 61 TFLOPS FP16 / 123 TOPS INT8.
  - The 123 TOPS figure lines up with the widely repeated "~120 GPU TOPS" in the 180-platform-TOPS claim, but no fetched source confirms per-GPU TOPS. Cite these only as estimates.
- **Machine balance (ESTIMATE):**
  - Core Ultra 5 325 GPU: about 20 TFLOPS / 119.5 GB/s ≈ 170 FLOP/byte.
  - B390: about 61 TFLOPS / 153.6 GB/s ≈ 400 FLOP/byte.

### Gaps
- No official Intel ARK page or product brief was fetched for the Core Ultra 5 325 or for B390 XMX TOPS. The 47 vs 50 NPU TOPS conflict for the 325 is unresolved.
- The exact memory speed in the team's XPS and T2 units was not verified. The XPS may not use LPDDR5X-7467.
- No third-party measured memory bandwidth for Panther Lake was found (e.g., a Chips and Cheese GPU bandwidth microbenchmark).
- Whether the 8 MB memory-side cache helps LLM decode was not established. It almost certainly cannot hold 2.3 GB of weights.

## 2. Roofline reasoning: decode bandwidth, KV precision, prefill attention

### Takeaway
Our numbers fit a simple bandwidth model well. At 25–27 tok/s with about 3.5k context (u8 KV), decode pulls an implied ~62–75 GB/s of effective bandwidth, roughly 52–62% of the 119.5 GB/s peak. The same model predicts about 21 tok/s at 12k against 19.85 measured. KV precision barely matters at 3.5k (f16 is about 9% slower than u8) but matters a lot at 30k (f16 is about 33% slower). In prefill FLOPs, attention overtakes the linear layers per token at about 12.3k context and in cumulative cost at about 24.6k. On the slower 4-Xe GPU, that puts the attention wall right at the SLO boundary.

### Cited Findings
- Roofline framework for LLM inference (decode is memory-bound, prefill compute-bound) — [LLM Inference Unveiled: Survey and Roofline Model Insights (arXiv 2402.16363)](https://arxiv.org/html/2402.16363v5)
- Intel's own AI-PC low-bit kernel paper puts AI-PC bandwidth "on the order of 100 GB/s". It says its kernels "achieve the attainable memory bandwidth" and run at "close to peak roofline" on CPUs, and that on Xe2 GEMMs it reaches "compute throughput close to the ideal int2×int8 DPAS throughput". It reports a 1.5× speedup on Arc B580 over 2-bit inference on A100 and up to 7× over 16-bit inference. It gives no per-iGPU tok/s or bandwidth-utilization figures — [Pushing the Envelope of LLM Inference on AI-PC and Intel GPUs (arXiv 2508.06753)](https://arxiv.org/html/2508.06753v2)
- In multi-turn agent prefill, cached tokens still cost attention work: with C cached and U uncached tokens, the work grows roughly with U(C+U) — [From LLM Inference to Agentic Workloads (arXiv 2608.15127)](https://arxiv.org/html/2608.15127v1)

### Inferences (all DERIVED estimates)

**Bytes read per token.** KV per token = 36 × 8 × 128 × 2 (K,V) × bytes per element:

| KV precision | Per token | At 3.5k | At 12k | At 30k |
|---|---|---|---|---|
| f16 | 147,456 B | 0.52 GB | 1.77 GB | 4.42 GB |
| u8 | 73,728 B | 0.26 GB | 0.89 GB | 2.21 GB |
| u4 | 36,864 B | 0.13 GB | 0.44 GB | 1.11 GB |

**Implied effective decode bandwidth.** BW_eff = tok/s × (weight bytes + ctx × KV bytes).
- At 25–27 tok/s, 3.5k context, weights 2.2–2.5 GB:
  - u8 KV: 61.5–74.5 GB/s, central value ~68 GB/s (26 tok/s, 2.35 GB). That is about 57% of 119.5 GB/s.
  - f16 KV: 68–81 GB/s.
- Validation: holding ~67.8 GB/s fixed, u8 predicts 21.0 tok/s at 12k vs **19.85 measured** (5% gap). The gap is plausibly attention compute and softmax overhead.
- Holding BW fixed instead under an f16 assumption predicts about 18 tok/s at 12k (9% under). The u8 assumption fits slightly better. The team should confirm which KV precision the "default" run used.

**Predicted decode tok/s at fixed BW_eff ≈ 67.8 GB/s, weights 2.35 GB:**

| Context | f16 | u8 | u4 | f16 vs u8 |
|---|---|---|---|---|
| 3.5k | 23.7 | 26.0 | 27.4 | −9% |
| 12k | 16.5 | 21.0 | 24.3 | −21% |
| 30k | 10.0 | 14.9 | 19.6 | −33% |

The gain from u8 to u4 is +5% at 3.5k and +32% at 30k. These are upper bounds, since dequant cost and attention-kernel inefficiency are ignored.

**Weight-precision cross-check.**
- INT8 weights (~4.0–4.4 GB) would be about 1.8× the bytes of INT4, but measured decode is only 1.3–1.67× slower.
- So INT4 decode is not sitting perfectly on the bandwidth roofline. At about 1.5× slower, INT8 implies roughly 74 GB/s effective vs about 68 GB/s for INT4.
- That points to INT4 dequant and kernel overhead. The 4-Xe GPU is not purely bandwidth-limited at INT4, so faster memory alone would give somewhat less than proportional gains.

**B390 vs XPS.**
- Decode: 34.5 / 26 ≈ 1.33×. Bandwidth (9600 vs 7467): 1.29×. Decode tracks memory bandwidth, not the 3× Xe-core count, which is consistent with bandwidth-bound decode. This assumes T2 runs LPDDR5X-9600 at similar context.
- Prefill: 18.5k vs 10k tokens in the same 10 s TTFT.

**Prefill FLOPs, Qwen3-4B.** Inputs: hidden 2560, intermediate 9728, from the public model config (not re-fetched this session).
- Linear layers ≈ 7.27 GFLOP/token.
- Causal attention (QKᵀ + AV, 32 query heads × 128 dims) ≈ 2.95×10⁵ × N² FLOPs for an N-token prefill.
- Attention share of prefill FLOPs:

  | Context | Attention share |
  |---|---|
  | 3.5k | 12% |
  | 10k | 29% |
  | 12k | 33% |
  | 18.5k | 43% |
  | 30k | 55% |

- Marginal attention cost per token equals the linear cost at **~12.3k context**. Cumulative attention equals linear at **~24.6k**.
- Attention kernels (softmax, masking, KV reads) usually run at lower utilization than GEMMs, so the wall-time crossover probably comes earlier than these FLOP crossovers.

**Effective prefill compute.**
- XPS: 10k tokens in 10 s ≈ 102 TFLOP / 10 s ≈ **10 TFLOPS effective**. That is about 50% of the estimated 20 TFLOPS FP16 peak, or 25% of 40 TOPS INT8.
- B390: 18.5k tokens in 10 s ≈ 235 TFLOP / 10 s ≈ **23.5 TFLOPS effective**, 2.3× the XPS.
- Prefill scales sub-linearly with the 3× Xe count, likely because of the larger attention share at 18.5k and power/clock limits.

**Why the KV-precision effect flips between phases.**
- f16 KV measured 15–27% faster in prefill at depth, likely because it avoids quantize/dequantize work in compute-bound attention.
- u8/u4 saves bytes in bandwidth-bound decode.
- See Q5 for the crossover.

### Gaps
- No published LLM roofline or characterization specifically for Panther Lake or Lunar Lake/Meteor Lake iGPUs with measured bandwidth utilization was found within budget. Intel's AI-PC paper (2508.06753) is qualitative on iGPU numbers.
- No Apple M-series or AMD Strix Halo measured tok/s-vs-bandwidth study from a primary source was fetched. Only SEO benchmark aggregator pages surfaced, and they were not used.
- The Qwen3-4B hidden/intermediate sizes used in the FLOP math come from the public config.json and were not re-verified this session.

## 3. Agentic workload shape

### Takeaway
Agent turns have huge raw input:output ratios (54–560× in Claude Code-driven agent traces). But with prefix caching, the new input per output token is only 1.5–7.3×. LLM time is then 91–98.6% decode, even on H100s. Our 67–90% decode share (no or partial prefix reuse, slower iGPU prefill) agrees directionally. The levers that follow are aggressive prefix caching and controlling output length (thinking tokens and verbose prose).

### Cited Findings
- 2605.26297 setup: Claude Code agents on ADE-Bench, DABStep, GAIA, SWE-bench Pro and Terminal-Bench 2.0. Models are Qwen3.6-27B and Gemma4-31B, served by vLLM on 2×H100. Findings:
  - **Raw input:output ratio mean 53.9×–559.8×.**
  - **Append-to-output ratio (new input per output token) mean 1.5×–7.3×**, with medians often below 1.5×.
  - **Decode is 91.0–98.6% of LLM time; prefill is 1.4–9.0%.**
  - Theoretical cache-hit ratio is 87.9–99.3%; empirical 84.6–99.5% (no eviction).
  - Thinking tokens are 29–68% of output in thinking modes.
  - Tool-call tokens are 70–98% of output in Instant modes.
  - Agents average 12–62 turns per task. LLM inference is 71–98% of runtime; tools are 2–29%.
  - Failed runs carry more context (Terminal Bench Qwen: 79.2K vs 44.4K mean).
  — [Agentic AI Workload Characteristics (arXiv 2605.26297)](https://arxiv.org/html/2605.26297v1)
- 2608.15127 findings:
  - Claude Code-style agents (static system prompt, append-only history) reach "cache hit rates of up to 99%". DeepResearch-style agents that restructure context see prefix reuse "drop to 1% or lower".
  - In ReAct loops (Mini-SWE, Codex), input "scales quadratically with the turn count".
  - In Mini-SWE, decode latency tracks output length, and prefill latency tracks the newly appended uncached observation.
  - In WebAgent, richer observations raise per-step input 4.8× and push LLM time from 46.9% to 61.6% of latency.
  - The authors call prefix caching "an absolute necessity rather than an optional optimization".
  — [From LLM Inference to Agentic Workloads (arXiv 2608.15127)](https://arxiv.org/html/2608.15127v1)
- Other agent-workload characterizations surfaced but were not read in full: [TraceLab: coding agent workloads (arXiv 2606.30560)](https://arxiv.org/html/2606.30560v1); [Agentic Coding in the Wild: GitHub Copilot (arXiv 2608.00101)](https://arxiv.org/html/2608.00101v1); [Stateful Inference for Multi-Agent Tool Calling (arXiv 2605.26289)](https://arxiv.org/html/2605.26289v1)

### Inferences
- Our workload has about 3.5k input (median step-0 prompt 3,412) and a median of 91 output tokens per turn (p90 157), a raw ratio of about 38× (run 39c1c131; the 130–255 and 14–27× first written here were not measured). That is far lower than the H100 traces because our contexts are short. With prefix reuse, new input per turn is probably a few hundred tokens (tool result plus user message), so the append-to-output ratio would sit in the same 1.5–7× band.
- The literature's "agentic = prefill-heavy" framing holds in raw token counts. It does not hold in time once prefix caching works. On a bandwidth-starved iGPU decoding at about 26 tok/s, decode dominance is stronger still. Each output token costs about 38 ms; each prefilled token costs about 1 ms at ~1,000 tok/s cold.
- One output token costs roughly as much wall time as about 35–40 prefill tokens on the XPS (DERIVED: 1000 / 26).

### Gaps
- No BFCL or tau-bench trace-level prefill/decode time split was found within budget.
- No agent characterization on an iGPU or edge device was read; Agent-X (2605.10380) was rate-limited.

## 4. Levers grounded in physics

### Takeaway
Ranked by expected payoff on this hardware (DERIVED):
1. Cut output tokens (decode is about 38 ms/token).
2. Prefix reuse (turns about 3–13 s cold prefill into about 0.3–0.4 s deltas).
3. Lower-precision KV once context grows past about 10k.
4. Speculative or prompt-lookup decoding (about 1.3–1.4× measured on Lunar Lake with a draft model).
5. Power and thermal headroom (up to about 33% GPU throughput loss at 20 W vs 45 W on B390).

### Cited Findings
- (b) Speculative decoding on an Intel iGPU, OpenVINO GenAI: Qwen3-8B INT4 target on a Core Ultra 7 268V (Arc 140V iGPU, 32 GB, OpenVINO 2025.2), run in a smolagents agent. A Qwen3-0.6B INT8 draft gave **~1.3× average speedup**. A depth-pruned draft (6 of 28 layers removed, fine-tuned) gave **~1.4×**. Acceptance rates and absolute tok/s were not reported — [Hugging Face/Intel: Accelerating Qwen3-8B Agent on Core Ultra](https://huggingface.co/blog/intel-qwen3-agent)
- (d) Prefix caching reaches up to 99% hit rates for append-only agents, but cached tokens still cost U(C+U) attention work — [arXiv 2608.15127](https://arxiv.org/html/2608.15127v1)
- (e) Observation size drives prefill: richer observations raised per-step input 4.8× and pushed LLM latency from 46.9% to 61.6% — [arXiv 2608.15127](https://arxiv.org/html/2608.15127v1)
- (a) Output composition: thinking is 29–68% of output tokens in thinking mode — [arXiv 2605.26297](https://arxiv.org/html/2605.26297v1)
- (f) Thermal/sustained load, as reported in 2603.23640:
  - **Correction:** the paper does NOT report a 41.5% drop. It reports **37.3% (Warm, 25.31 vs 40.35 tok/s peak)** and **44.1% (sustained Hot, 22.56 tok/s)** on an **iPhone 16 Pro**, running Qwen2.5-1.5B 4-bit.
  - Galaxy S24 Ultra: the GPU was floored to 231 MHz at iteration 6, at 78.3 °C.
  - An RTX 4050 laptop at about 34 W showed no throttling.
  - **No Intel iGPU or laptop SoC iGPU was tested**, so the thin-laptop claim cannot be transferred directly.
  — [LLM Inference at the Edge: … Under Sustained Load (arXiv 2603.23640)](https://arxiv.org/html/2603.23640v1)
- (f) On Panther Lake, B390 GPU performance falls with package power: Time Spy 4,567 at 20 W vs 6,830 at 45 W (−33%). Full GPU load draws about 38–40 W GT / ~52 W package — [Notebookcheck B390](https://www.notebookcheck.net/Intel-Panther-Lake-Arc-B390-performance-and-efficiency-analysis-Intel-s-new-iGPU-trades-blows-with-the-Nvidia-GeForce-RTX-4050.1212582.0.html)
- (f) Core Ultra 5 325 sustains 25 W PL1 / 55 W PL2 / 15 W min — [Notebookcheck 325](https://www.notebookcheck.net/Intel-Core-Ultra-5-325-Processor-Benchmarks-and-Specs.1196417.0.html). The EVO-T2 mini PC is configured for 80 W — [Notebookcheck EVO-T2](https://www.notebookcheck.net/GMKtec-previews-EVO-T2-as-first-Intel-Panther-Lake-mini-PC-with-80-W-TDP-Arc-B390-iGPU-and-up-to-128-GB-of-ultra-fast-LPDDR5x-RAM.1167272.0.html)
- (g) Shared fabric and memory: the 16 MB GPU L2 reduces SoC fabric traffic by up to 36%. CPU, GPU and NPU share one 128-bit memory bus through an 8 MB memory-side cache — [Chips and Cheese](https://old.chipsandcheese.com/2025/10/14/panther-lakes-reveal-at-itt-2025/)

### Inferences (DERIVED)
- **(a) Output tokens.**
  - At about 26 tok/s, a 200-token turn spends about 7.7 s in decode; trimming to about 60 tokens (bare tool-call JSON) saves about 5.4 s per turn.
  - Decode energy and time scale with N_out × (weights + KV) bytes.
  - Disabling Qwen3 thinking (/no_think), stopping on the tool-call close tag and using max_new_tokens caps are the highest-leverage knobs. They also shrink future context, and with it KV and prefill.
- **(b) Speculative / prompt-lookup decoding.**
  - Decode arithmetic intensity at INT4 is about 4 FLOP/byte vs a machine balance of about 170 (XPS) or about 400 (B390) FLOP/byte. Verifying k drafted tokens costs about k× FLOPs at nearly the same bytes, so the compute is almost free.
  - Prompt-lookup (n-gram) decoding needs no draft model. It fits agent turns that copy file paths, JSON keys and earlier tool-output snippets.
  - Expected gain is about 1.3–1.4× per the Lunar Lake draft-model result. On the 16 GB laptop, a draft model costs extra memory (about 0.6 GB for a 0.6B INT8 model).
  - The INT8-vs-INT4 evidence that the 4-Xe GPU carries non-bandwidth overhead suggests gains may be smaller on the 325 than on the B390.
- **(c) KV precision.** u8 vs f16 saves about 9% decode at 3.5k, about 21% at 12k and about 33% at 30k. f16 gains 15–27% prefill. See the crossover in Q5.
- **(d) Prefix reuse.** FLOPs for a 300-token delta over cached context C vs cold prefill:

  | Cached context C | Delta FLOPs | Cold FLOPs | Reduction | Delta time at ~10 TFLOPS |
  |---|---|---|---|---|
  | 3.5k | 2.8 TFLOP | 31.9 TFLOP | 11× | ~0.3 s |
  | 12k | 4.3 TFLOP | 134 TFLOP | 31× | ~0.4 s |
  | 30k | 7.5 TFLOP | 491 TFLOP | 65× | ~0.75 s |

  This is the main way to escape the 10 s TTFT SLO at depth. It needs byte-stable prompts: a static system prompt, append-only history, no reordering and no timestamps at the top.
- **(e) Observation masking/truncation.** Shrinks U (prefill) and C (KV bytes read per decode token and attention FLOPs) at once.
  - Example: holding context at 12k instead of 30k with u8 KV raises predicted decode from about 14.9 to about 21 tok/s.
  - Masking edits break the prefix cache from the edit point onward, so mask in a way that preserves the prefix, e.g. truncate only the newest observation before it is appended.
- **(f) Power.** On a thin laptop, decode is bandwidth-bound and may be less power-sensitive than prefill. Prefill is compute-bound and should track GPU clocks and power, as Time Spy does.
  - Recommend measuring tok/s and TTFT across Windows power modes (Best performance vs Balanced) and after 10+ minutes of sustained agent runs.
- **(g) Unified-memory contention.** CPU-side work (tokenization, tool execution such as pip/grep/compilers, browser) shares the same 119.5–153.6 GB/s bus. Bandwidth-heavy tool steps that overlap decode should cut decode tok/s roughly in proportion to the bandwidth they consume.
  - On the 16 GB laptop, the OS and apps also compete for capacity: weights 2.4 GB + f16 KV at 30k ≈ 4.4 GB.

### Gaps
- No published measurement of CPU/GPU memory-bandwidth contention during LLM decode on Intel unified-memory SoCs was found.
- No measured thermal-throttling study of LLM inference on Panther Lake or Lunar Lake laptops was found. The 41.5% figure cited in the brief does not appear in 2603.23640.
- No source was fetched for OpenVINO GenAI prompt-lookup decoding speedups on an Intel iGPU. The feature exists in OpenVINO GenAI per its docs, but no measured numbers were verified this session.

## 5. Crossover analyses (KV precision, speculative decoding, GPU vs NPU vs CPU)

### Takeaway
No published crossover analysis specific to Intel iGPUs was found. A first-principles crossover from our own numbers: f16 KV wins only when a turn's uncached prefill is large relative to its output tokens (cold or cache-miss turns). With prefix reuse, u8/u4 KV wins at every depth, and by more as context grows. GPU beats CPU in both phases (17× prefill, 3.2× decode, measured). No NPU phase data was found.

### Cited Findings
- Speculative decoding on a Lunar Lake iGPU gives 1.3–1.4× with a draft model (Qwen3-8B target). No acceptance or crossover analysis is given — [HF/Intel blog](https://huggingface.co/blog/intel-qwen3-agent)
- 2603.23640 tested no CPU-only or iGPU configuration, so it reports no CPU/GPU/NPU crossover — [arXiv 2603.23640](https://arxiv.org/html/2603.23640v1)
- Panther Lake NPU 5 is about 50 TOPS INT8, roughly the same as the previous-generation NPU — [Wikipedia](https://en.wikipedia.org/wiki/Panther_Lake_(microprocessor))

### Inferences (DERIVED estimates)

**KV crossover per turn.**
- f16 wins if s × T_prefill(U) > N_out × L·KVH·D·2 × ctx / BW_eff, where s is the 0.15–0.27 prefill saving and the right-hand side is the extra f16 decode bytes.
- Cold 3.5k turn, 200 output tokens:
  - f16 saves about 0.5–0.9 s of TTFT (3.5 s × 15–27%).
  - f16 costs about 0.8 s more decode (200/23.7 − 200/26.0).
  - Result: **roughly break-even**.
- Cold 12k turn: f16 saves about 2–3.5 s of TTFT and costs about 2.6 s more decode. Break-even again, but f16 helps meet the TTFT SLO.
- With prefix reuse (U ≈ 300): f16's prefill saving is about 0.05–0.1 s while its decode penalty is 0.8–2.6 s. **u8/u4 wins clearly.**
- Rule:
  - Use f16 KV only if prefix caching is unavailable or misses often and TTFT is the binding SLO.
  - Otherwise use u8. Consider u4 past about 20k context, if accuracy holds.

**Speculative decoding crossover.** It helps when (draft latency + verify latency) / expected accepted tokens < target per-token latency.
- On bandwidth-bound decode, verifying k tokens costs about the same as one token until k × 4 FLOP/byte nears machine balance, i.e. k up to tens of tokens.
- The risk is mostly the draft's own bandwidth cost (a 0.6B INT8 draft is about 25% of the INT4 target's bytes) and memory capacity on 16 GB.

**GPU vs NPU vs CPU by phase.**
- Measured: the GPU dominates CPU (17× prefill, 3.2× decode).
- Decode on any engine is capped by the same shared bus. The NPU's potential advantage is power, not decode speed. NPU prefill vs GPU prefill was not measured or sourced.

### Gaps
- No published f16-vs-quantized-KV crossover analysis was found for Intel iGPUs or OpenVINO.
- No published NPU-vs-iGPU phase comparison was found for Panther Lake.
- No speculative-decoding acceptance-rate data for Qwen3-4B tool-calling outputs was found.
- These crossovers should be validated empirically with the team's harness (TTFT and tok/s per KV precision, with and without prefix caching).
