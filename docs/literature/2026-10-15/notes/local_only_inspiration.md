# Sweep 6: LOCAL-ONLY on-device/edge LLM inference work that treats configuration as a variable (inspiration, not competitors)

Scope note for the report writer: every paper below is LOCAL-ONLY (on-device / edge execution, no cloud routing) unless explicitly flagged. One exception is flagged in Q2 (Khatib et al. 2609.08307), which adds a near-edge server and a GPT-4o reference and so sits at the boundary of the hybrid space. It should be cross-checked against the competitor sweeps. Window: 2024 through October 2026. Searches were run on 2026-10-15.

## Q1. Which local-only papers sweep configuration knobs on consumer devices (quantization, KV precision, CPU/GPU/NPU placement, context length, batch, memory policy)?

### Takeaway
Many local-only measurement papers sweep model size × weight quantization × framework × backend (CPU/GPU/NPU) × context length on phones, AI PCs and Jetsons. Their common finding is that the best backend and precision depend on the stage (prefill vs decode), the context length and the framework. No single knob setting dominates. KV-cache precision and session residency (prefix caching) are rarely swept in these characterization papers. They show up mostly as point techniques.

### Cited Findings
- **MELTing point (Laskaridis et al., arXiv 2403.12844, v4 July 2024; LOCAL-ONLY).** Devices: Galaxy S23, Pixel 6a, iPhone 14 Pro, iPhone SE, Jetson Orin AGX and Orin Nano. Swept knobs: models from TinyLlama-1.1B to Llama-2-13B, 3/4-bit quantization (plus AWQ/GPTQ for accuracy), MLC-LLM vs llama.cpp, CPU vs GPU, a grid over context size, max generated length and batch size, and Jetson power modes (50/30/15 W; 15/7 W). Measurement used a Monsoon power monitor (up to 5 kHz) and a thermal camera. — [arXiv 2403.12844](https://arxiv.org/html/2403.12844v4)
  - "4-bit models averaged 24.77% higher throughput than 3-bit variants". Models of 3B or fewer parameters were unusable at 3-bit (hallucinating or repeating the prompt). iPhones had 78.93% higher MLC-LLM generation throughput than OpenCL Android. Zephyr-3B used about 0.16–0.21 mWh/token. — [arXiv 2403.12844](https://arxiv.org/html/2403.12844v4)
  - Quote: "Quantization drastically reduces memory requirements and renders execution viable, but at a non-negligible accuracy cost." — [arXiv 2403.12844](https://arxiv.org/html/2403.12844v4)
- **"Is Your NPU Ready for LLMs?" (Cai et al., Tsinghua/BJTU, arXiv 2607.05475, July 6 2026; LOCAL-ONLY).** Four Snapdragon phones (SM8650/8750/8850, 16 GB). Swept knobs: backend (CPU/GPU/NPU), five frameworks (llama.cpp, MNN, MLC-LLM, MLLM, GENIE), W4 vs W4A16, context length from 16 to 4096, and scheduling knobs (RPC polling interval, NPU sleep latency, CPU affinity, DVFS). — [arXiv 2607.05475](https://arxiv.org/html/2607.05475v1)
  - GENIE NPU prefill reached 1463.7 tok/s vs 115.1 tok/s for llama.cpp, but decode was about 23 tok/s for both. NPU decode cost about 3.2×10⁵ µJ/token vs about 9.7×10⁴ for llama.cpp CPU. Decode throughput fell 23.8% (Llama 1B) and 20.0% (Qwen 1.5B) going from 16 to 4096 context. W4A16 gave 2.16–2.63× throughput and 53.5–66.9% less energy, but perplexity rose 30.36% on Llama-3.2-1B vs 1.04% on 3B. Tuning RPC polling cut energy 30.9–37.8%, and NPU sleep latency cut it 44.6–50.9%. — [arXiv 2607.05475](https://arxiv.org/html/2607.05475v1)
  - Quotes: "NPUs excel at compute-bound prefilling, while CPUs outperform all other backends in memory-bound decoding." and "static-graph NPU execution requires a large context window to be preallocated in advance." — [arXiv 2607.05475](https://arxiv.org/html/2607.05475v1)
- **"When NPUs Are Not Always Faster" (Li, Qi, Chen, Leiden, arXiv 2605.27435, ~May 2026; LOCAL-ONLY).** Snapdragon 8 Gen 3 phone, llama.cpp with the Hexagon backend. Swept knobs: CPU vs NPU offload depth (ngl), prefill vs decode, prompt length (~321/641/1281), and four models from 3B to 8B at Q4_0. — [arXiv 2605.27435](https://arxiv.org/html/2605.27435v1)
  - The NPU is 1.27–1.62× slower than the 6-core CPU on prefill MUL_MAT. It is 1.55–1.67× faster on decode MUL_MAT, but only 1.05–1.20× faster end-to-end in decode. Full NPU offload raised battery drain by 22%/32%/51% at the three prompt lengths. Quote: "increasing NPU offloading leads to higher energy consumption (up to 51%)". — [arXiv 2605.27435](https://arxiv.org/html/2605.27435v1)
  - Conflict to note: 2607.05475 finds the NPU wins prefill and the CPU wins decode, while 2605.27435 finds the CPU wins prefill and the NPU wins MUL_MAT in decode. The difference is framework-dependent (GENIE/MNN vs llama.cpp Hexagon backend), so placement conclusions are runtime-specific. — [2607.05475](https://arxiv.org/html/2607.05475v1); [2605.27435](https://arxiv.org/html/2605.27435v1)
- **HeteroInfer / "Characterizing Mobile SoC for Accelerating Heterogeneous LLM Inference" (Chen et al., SJTU, SOSP '25, arXiv 2501.14794; LOCAL-ONLY).** Characterizes CPU, GPU and NPU on the Snapdragon 8 Gen 3. Quote: "no single processor can saturate the SoC's memory bandwidth during LLM decoding". GPU alone reaches 43.3 GB/s, GPU+NPU together 59.5 GB/s (theoretical peak 68 GB/s). The resulting engine gives 1.34–6.02× end-to-end speedup, uses 55% less energy than GPU-only, and slows decode by 17.7% under gaming interference. — [arXiv 2501.14794](https://arxiv.org/html/2501.14794v2)
- **Sustainability Is Not Linear (Ehsani, Giamattei, Malavolta, Pietrantuono, arXiv 2603.26603, 2026; LOCAL-ONLY).** Galaxy S25 Ultra, CPU-only llama.cpp, 8 models from 0.5B to 9B including the MoE OLMoE-1B-7B, Q4_K_M vs IQ4_XS, 30 repetitions per condition. Quote: "the architecture of the model, not its quantization scheme, is the decisive factor". 8B/9B models exceed 10 s end-to-end latency. A Gemma-2-9B run exceeds 300 J vs about 50 J for Qwen2-0.5B. — [arXiv 2603.26603](https://arxiv.org/html/2603.26603v2)
- **lm-Meter (Wang et al., Georgia State + Toyota, SEC '25, arXiv 2510.06126; LOCAL-ONLY).** Pixel 8 Pro, 7 and 6. Swept knobs: model families and sizes, 4-bit vs FP16, and CPU governors (Performance/Conservative/Powersave). Phase- and kernel-level online profiler. Scaling Pythia from 70M to 1.4B raised prefill latency per token 158× but decode latency per token only 10×. GPU idle exceeds 21% of a decode step. Quote: "prefill emerges as the dominant throughput bottleneck in on-device LLM inference". — [arXiv 2510.06126](https://arxiv.org/pdf/2510.06126)
- **Agent.xpu (Wei et al., Peking University, arXiv 2506.24045, 2025; LOCAL-ONLY, agentic).** Intel Core Ultra (CPU/iGPU/NPU shared memory), Llama-3.2-3B W8A16 on OpenVINO. Mixes proactive (background) and reactive (user) agent requests. Placement knobs: prefill chunks on the NPU, decode and attention on the iGPU, "elastic" kernels assigned at runtime, chunk size set by profiling, three memory-pressure tiers (thresholds 0.4/0.7). Reports about 4.6× lower reactive latency than llama.cpp CPU and 1.6–6.8× higher sustained proactive rate. Quote: "NPUs excel at static, pre-compiled computation graphs but struggle with the variable sequence lengths". — [arXiv 2506.24045](https://arxiv.org/html/2506.24045v2)
- **Adaptive KV-cache precision (Boroujeni et al., Clemson, arXiv 2604.04722, Apr 2026; LOCAL-ONLY).** Per-token KV precision chosen from {2,4,8,16} bits by a small MLP over token entropy, rarity, attention variance and confidence. On SmolLM-360M/HellaSwag it gives 17.75% lower ms/token than static KV quantization and +7.60 accuracy points, within 0.30 points of FP16. Hardware is not named in the excerpt read. — [arXiv 2604.04722](https://arxiv.org/html/2604.04722v1)
- **MLPerf Client v1.0 (MLCommons, July 30 2025; LOCAL-ONLY benchmark).** Models: Llama 2 7B Chat, Llama 3.1 8B Instruct, Phi 3.5 Mini, and Phi 4 Reasoning 14B (experimental). Experimental long-context summarization at about 4k and 8k tokens. Acceleration paths: AMD NPU+GPU (Ryzen AI / ORT), Intel NPU+GPU (OpenVINO), NVIDIA GPU (DirectML, llama.cpp CUDA), Qualcomm NPU+CPU hybrid (Genie/QAIRT), Apple GPU (MLX, llama.cpp Metal). The page fetched did not list metrics or memory requirements. — [HPCwire / MLCommons release](https://www.hpcwire.com/aiwire/2025/07/30/mlcommons-releases-mlperf-client-v1-0-a-new-standard-for-ai-pc-and-client-llm-benchmarking/); vendor tuning example: [AMD Ryzen AI MLPerf Client article](https://www.amd.com/en/developer/resources/technical-articles/2025/unlocking-peak-ai-performance-with-mlperf-client-on-ryzen-ai-.html)

### Inferences
- Across 2607.05475, 2605.27435, 2501.14794 and Agent.xpu, placement is stage-dependent (prefill vs decode) and framework-dependent. A hybrid study that fixes one local backend is therefore measuring one arbitrary point. This directly supports the "hidden variable" claim, using local-only evidence.
- Context length changes local decode cost (about 20–24% drop from 16 to 4096 tokens on NPUs) and NPU static-graph preallocation. Context and retention policy therefore change the local-side cost curve that any router compares against cloud.
- KV-cache precision and session residency are under-studied as swept variables in local characterization work. This is an open gap the hybrid study can occupy.

### Gaps
- No local-only characterization paper found that sweeps prefix-cache / session residency (keeping a KV cache resident across agent turns) as a first-class variable on phones or AI PCs. Agent.xpu touches memory pressure, but not cross-turn KV retention.
- MLPerf Client v1.0's exact metrics (TTFT/TPS definitions) and memory requirements were not in the page fetched. Check the MLCommons documentation directly.
- Not fetched: llm.npu (Xu et al., ASPLOS '25) — [PDF](https://xumengwei.github.io/files/ASPLOS25-NPU.pdf), [arXiv 2407.05858](https://arxiv.org/html/2407.05858v2). It is a known NPU-prefill system, but its numbers were not verified in this sweep.
- Intel, Qualcomm and Apple developer docs were not mined for configuration guidance due to the tool budget.

## Q2. Which local-only works report multi-objective trade-offs or Pareto fronts (latency, memory, energy, accuracy)?

### Takeaway
Explicit Pareto analysis exists, but it is mostly descriptive: plots over measured grids, not optimization. lm-Meter (accuracy–latency frontiers plus a "Harmonic Quantization" score), Sustainability Is Not Linear (a speed–quality Pareto) and Khatib et al. (an accuracy–latency front with injected network delay) are the clearest templates. The Khatib paper is borderline-hybrid.

### Cited Findings
- **lm-Meter (SEC '25; LOCAL-ONLY).** Plots accuracy-vs-latency Pareto frontiers (Figs. 6–8) and proposes the Harmonic Quantization (HQ) score, "the harmonic mean of normalized accuracy and latency ratios". HQ averages for Pythia: 0.982 (ARC-Easy), 1.243 (ARC-Challenge), 1.260 (GSM8K). On ARC-Easy, Pythia-1B/410M/160M/70M lose 9/15/27/34% accuracy vs 1.4B, while decode speeds up 0.6×/2.2×/5.1×/10.4×. — [arXiv 2510.06126](https://arxiv.org/pdf/2510.06126)
- **Sustainability Is Not Linear (2026; LOCAL-ONLY).** Speed and quality form a strict Pareto trade-off (Fig. 9c). The MoE model breaks the monotone size–cost trend: OLMoE-1B-7B is second in generation speed and energy despite 7B total parameters, but all experts must stay in RAM. Qwen2.5-7B beats Llama-3.1-8B in quality at lower energy. — [arXiv 2603.26603](https://arxiv.org/html/2603.26603v2)
- **Khatib, Symeonides, Trihinas, Pallis, Dikaiakos, "A Measurement Study of LLM Inference Trade-offs Across Edge Continuum Hardware" (arXiv 2609.08307, Sep 8 2026). NOT strictly local-only:** Jetson AGX Orin on-device, plus a near-edge Xeon+T4 server, plus GPT-4o as a cloud accuracy and latency reference. Swept knobs: model (1B–7B), F16/Q5_K_M/Q4_K_M, placement (Orin GPU / server CPU / server GPU). Batch and context are not varied. Almost every point on the accuracy–latency front comes from the server GPU. CPU-only trials are all dominated. Adding hypothetical 30 ms and 60 ms per-token delivery overheads to server setups shifts the front and makes the Orin more competitive. Quotes: "CPU-only execution can be deprioritized when latency is the primary objective." and "the best deployment depends on the accuracy-delay trade-off." — [arXiv 2609.08307](https://arxiv.org/html/2609.08307v1)
- **MELTing point (LOCAL-ONLY).** Reports throughput, energy per token, accuracy and thermal behavior jointly. The iPhone 14 Pro sustained 13.8 W with peaks above 18 W and reached a surface temperature of 47.9 °C. "No single quantization scheme won across all tasks." — [arXiv 2403.12844](https://arxiv.org/html/2403.12844v4)
- **2607.05475 (LOCAL-ONLY)** reports the joint throughput / energy / perplexity cost of W4A16: large speed and energy gains with a 30.36% perplexity rise on 1B vs 1.04% on 3B. This is a model-size-dependent quantization penalty. — [arXiv 2607.05475](https://arxiv.org/html/2607.05475v1)

### Inferences
- Khatib et al.'s trick of adding a per-token network-delay term to remote configurations and watching the Pareto front move is the most directly borrowable method. In the hybrid study, the "cloud side" can be modeled as a family of RTT and token-delivery-overhead offsets, while the local configuration is swept. That shows which local configurations ever reach the joint front.
- An HQ-style scalar (harmonic mean of normalized quality and latency, or energy) could serve as a single routing-utility metric to compare configurations. Report full fronts alongside it.
- The small-model quantization penalty (1B degrades much more than 3B) means weight precision interacts with model size. Sweep them jointly, not independently.

### Gaps
- No local-only paper found that reports a full multi-objective front including memory footprint and energy and quality across KV-precision × context-length grids.
- Khatib et al. has no venue listed and no peer review confirmed. Its server energy is a partial lower bound.

## Q3. Which local-only works do automated configuration search or autotuning for on-device LLMs, and with what methods?

### Takeaway
Autotuning for on-device LLMs is emerging (2025–2026). The common pattern is offline profiling, then a learned or regression performance/power model, then runtime filtering by a QoE constraint, then choosing the most energy-efficient feasible configuration. Methods are random forests, LSTM-based search, MPC and profiling-derived roofline/turning points. Bayesian optimization was not found in a verified on-device LLM paper in this sweep.

### Cited Findings
- **EnerInfer (Zou et al., TUM / Huawei / SJTU, arXiv 2606.23001, June 22 2026; listed for ACM SIGOPS ATC; LOCAL-ONLY).** Tunes NPU and DDR frequency levels during decode only (prefill runs at max). Random-forest regressors predict peak throughput, a frequency-scaling factor, and NPU+memory power from six model hyperparameters. Configurations missing the throughput QoE are filtered out, and a ranking-driven feedback loop picks the most efficient remaining one. A linear thermal predictor triggers MPC to keep shell temperature under about 42 °C. Up to 65% (phone), 12% (laptop) and 24% (board) energy-efficiency gains with no QoE violation. Throughput prediction MAPE: 2.3–4.2%. Power MAPE: 1.5–2.2%. Quotes: "Existing systems primarily optimize for decoding speed, implicitly assuming that faster execution is always preferable." and "The most energy-efficient NPU/DDR setting varies with the model, inference engine, platform, and runtime conditions". — [arXiv 2606.23001](https://arxiv.org/html/2606.23001v1)
- **CLONE (Tian et al., University of Macau, arXiv 2506.02847, June 2025; LOCAL-ONLY edge).** Jetson Orin NX/Nano plus a 28 nm accelerator. Jointly searches device-specific layer pruning (encoder–evaluator–decoder with LSTM, gradient search, beam decoding), LoRA routing, and per-token DVFS through a learned controller that uses an output-length predictor. Up to 11.92× faster inference and 7.36× energy savings. Notes that Llama-7B needs about 14 GB in FP16 vs 4–12 GB RAM on typical edge devices. — [arXiv 2506.02847](https://arxiv.org/html/2506.02847v1)
- **Agent.xpu (LOCAL-ONLY).** Offline roofline profiling of GEMM/MHA on NPU and iGPU. Each kernel is annotated with time, bandwidth, footprint and estimated power. Chunk size is chosen at the "turning point where the kernel just saturates the NPU or iGPU". — [arXiv 2506.24045](https://arxiv.org/html/2506.24045v2)
- **2607.05475 (LOCAL-ONLY)** gives hand-tuned recommended settings (RPC polling 20 µs, NPU sleep latency 65535 µs, CPU pinned to lowest frequency during NPU runs). It proposes phase- and model-aware NPU DVFS, with a projected (not measured) energy saving of up to 54.8%. — [arXiv 2607.05475](https://arxiv.org/html/2607.05475v1)
- **LaTune: "Lightweight and Adaptive Configuration Tuning for LLM Inference on Edge Devices"** (ACM DOI 10.1145/3774904.3792382) and **llm-tuna: "Hyperparameter Optimization for LLM Inference"** (ACM DOI 10.1145/3774904.3792953) appear in search results. Their content could not be fetched (ACM returned an error), so their methods are unverified. — [LaTune (ACM)](https://dl.acm.org/doi/10.1145/3774904.3792382); [llm-tuna (ACM)](https://dl.acm.org/doi/10.1145/3774904.3792953)
- **GPU Goldmines: Tunable WebGPU Kernels for Edge LLM Inference** (arXiv 2610.17321, Oct 2026) appeared in search as kernel-level autotuning for edge browsers. It was not read. — [arXiv 2610.17321](https://arxiv.org/html/2610.17321)

### Inferences
- EnerInfer's pipeline (predict per configuration, filter by QoE, pick the most efficient) maps cleanly onto hybrid routing. Extend the configuration table with "cloud" rows (latency = RTT + queue + server TPOT; device energy = radio energy). The router then becomes a constrained configuration selector over {local configurations} ∪ {cloud}.
- EnerInfer's premise that "many scenarios do not require maximum throughput" supports evaluating hybrid policies on QoE-satisficing energy rather than raw latency.
- Low-MAPE random-forest predictors from a few model hyperparameters suggest a cheap surrogate model can replace exhaustive sweeps of the hybrid configuration space.

### Gaps
- LaTune and llm-tuna abstracts could not be retrieved. Verify whether either uses Bayesian optimization or tunes KV/quantization knobs.
- No verified on-device LLM paper using Bayesian optimization was found within this tool budget.

## Q4. How do local-only works characterize failure behavior at memory limits?

### Takeaway
Memory-limit failure is reported mostly anecdotally (OOM kills, reboots, unresponsiveness during model load) or as throughput collapse under mmap paging. Offloading systems (LLM in a flash, PowerInfer-2, FlexInfer) turn the hard cliff into a storage-bandwidth-bound slope. Few papers systematically sweep the memory budget. FlexInfer is the main exception.

### Cited Findings
- **MELTing point (LOCAL-ONLY).** Out-of-memory errors killed applications at arbitrary times, especially on lower-RAM phones. Some runs failed from OOM or took longer than an hour per conversation. Model loading (Zephyr-3B 4-bit, 2.41 ± 0.09 s) often made the device unresponsive. Quote: "device restarts, which for undefined reasons caused Denial of Service (DoS) by rebooting the device". — [arXiv 2403.12844](https://arxiv.org/html/2403.12844v4)
- **FlexInfer (Du et al., CityU HK / MBZUAI, arXiv 2503.03777, Mar 2025; LOCAL-ONLY, CPU).** Sweeps the available memory budget with cgroups (Table 1: about 5–35 GB) for Llama2-7B up to Llama2-70B. Under llama.cpp mmap: "almost every access to the model weight triggers IO operations". Throughput was 0.08–0.67 tok/s, and 70B stayed around 0.5 tok/s from 5 to 25 GB. FlexInfer (async prefetch, balanced memory locking, budget-aware tensor preservation) gives 4.2–12.5× over mmap. It favors keeping FFN tensors resident when memory is ample and attention tensors when it is tight. — [arXiv 2503.03777](https://arxiv.org/html/2503.03777v1)
  - Internal inconsistency: the Table 1 caption gives a full-memory 70B throughput of 31.14 tok/s, while the Fig. 4(d) label shows 1.3 tok/s. Unreconciled in the paper. — [arXiv 2503.03777](https://arxiv.org/html/2503.03777v1)
- **LLM in a flash (Alizadeh et al., Apple, arXiv 2312.11514, rev. July 2024; LOCAL-ONLY).** Quote: "enable running models up to twice the size of the available DRAM, with up to 4x and 20x increase in inference speed" vs naive loading on CPU/GPU. Uses windowing (reusing recently activated neurons) and row-column bundling. — [arXiv 2312.11514](https://arxiv.org/html/2312.11514v3)
- **PowerInfer-2 (Xue et al., SJTU, arXiv 2406.06282, June 2024; LOCAL-ONLY).** Runs LLMs exceeding device memory using neuron-cluster scheduling (dense clusters on NPU, sparse on CPU) and a segmented neuron cache. "Up to a 27.8x speed increase", and "the first system to serve a 47B LLM on a smartphone, achieving 11.68 tokens/s". — [arXiv 2406.06282](https://arxiv.org/abs/2406.06282v1)
- **Sustainability Is Not Linear (LOCAL-ONLY).** All 0.5B–9B models ran on a Galaxy S25 Ultra without OOM, so in this case the limit showed up as latency (>10 s for 8B/9B) and energy rather than a crash. IQ4_XS significantly reduced peak memory vs Q4_K_M. — [arXiv 2603.26603](https://arxiv.org/html/2603.26603v2)
- **2607.05475 (LOCAL-ONLY).** The NPU static-graph memory constraint (preallocating a large context window) raises per-step decode cost. This is a memory-policy cost that persists even below OOM. — [arXiv 2607.05475](https://arxiv.org/html/2607.05475v1)
- **HeteroInfer (LOCAL-ONLY).** Gaming co-run interference slowed decode by 17.7%. Contention for shared memory bandwidth is a soft failure mode. — [arXiv 2501.14794](https://arxiv.org/html/2501.14794v2)

### Inferences
- Local failure at memory limits comes in three regimes that a hybrid study should label explicitly: (1) hard failure (OOM kill or reboot), (2) a paging/offload cliff (throughput collapses by about 10×), and (3) soft degradation from preallocation or bandwidth contention. Each implies a different routing response: a must-offload trigger, a cost-model discontinuity, or gradual cost inflation.
- FlexInfer's cgroup-based memory-budget sweep is a cheap, reproducible way to emulate "device RAM" as a continuous variable on a single host. It is directly borrowable for sweeping device memory in the hybrid study.
- Session residency (keeping KV and weights resident across agent turns) competes with app memory under OS pressure. MELTing point's arbitrary OOM kills suggest residency should be modeled as probabilistic eviction, not a guarantee.

### Gaps
- No local-only paper found that systematically measures KV-cache growth to OOM over long multi-turn agent sessions on phones (where the failure point falls as a function of context and KV precision).
- No measured data found on OS-level LLM eviction (Android low-memory killer, iOS jetsam) frequency vs model footprint.

## Q5. Which local-only works give provisioning guidance (how much memory or which device a model needs)?

### Takeaway
Guidance is coarse and empirical. Roughly: more than 6 GB RAM for chat LLMs on phones (2024); about 3B or smaller for interactive use on a 2025 flagship phone; 7–8B models exceed 10 s on CPU-only phones. Choose by measured Pareto fronts, not parameter count. No paper gives a principled memory-sizing model that includes KV, context and residency.

### Cited Findings
- MELTing point: "high-end mobile devices with more than 6GB of memory can run a chat LLM at a reasonable rate", with significant battery drain and QoE impact. — [arXiv 2403.12844](https://arxiv.org/html/2403.12844v4)
- Sustainability Is Not Linear: models up to about 3B are acceptable for interactive use on a Galaxy S25 Ultra (CPU). 0.5B–1.5B for battery and responsiveness. About 3B (or OLMoE if RAM allows) for balanced use. Large dense models (e.g., Gemma-2-9B) only with ample RAM and cooling. Suggests thermal and battery-triggered fallback to a smaller model or shorter output. — [arXiv 2603.26603](https://arxiv.org/html/2603.26603v2)
- Khatib et al. (borderline-hybrid): "Choose configurations by Pareto analysis over measured results, not by model size". Parameter count and file size do not reliably predict accuracy or latency. — [arXiv 2609.08307](https://arxiv.org/html/2609.08307v1)
- CLONE: Llama-7B needs about 14 GB in FP16 vs 4–12 GB of RAM on typical edge devices. — [arXiv 2506.02847](https://arxiv.org/html/2506.02847v1)
- lm-Meter recommends task- and difficulty-aware model selection and suggests device-cloud offloading for hard tasks. It is a local-only paper pointing to the hybrid gap. — [arXiv 2510.06126](https://arxiv.org/pdf/2510.06126)
- The Sustainability paper cites Nguyen et al. as finding "remote fetching to be more energy-efficient for the client device in most scenarios". This is secondhand, so verify the primary source in the competitor sweep. — [arXiv 2603.26603](https://arxiv.org/html/2603.26603v2)

### Inferences
- A clear opportunity: none of these works gives a memory-provisioning curve that includes KV cache at the target context, KV precision, and residency across turns. The hybrid study could produce "minimum device RAM for X% local-handled agent turns" as a function of these knobs. That is a provisioning answer local-only papers do not give.
- Since several local-only papers point to cloud offload as the fallback (lm-Meter, the Sustainability paper), the hybrid study's framing ("local config determines when the cloud is needed") is consistent with gaps these authors themselves name.

### Gaps
- Vendor developer docs (Apple Foundation Models / Core ML, Qualcomm AI Hub, Intel OpenVINO, AMD Ryzen AI) were not checked for official memory-sizing guidance within this sweep.
- No 2026 phone or AI PC study found that gives RAM thresholds for 16 GB-class devices running 7–8B models with long agent contexts.

## Q6. Which concrete methods, metrics and experiments could the hybrid device-cloud study borrow?

### Takeaway
The highest-value borrowables:
- Khatib's network-delay-shifted Pareto front.
- EnerInfer's predict–filter–select configuration loop.
- FlexInfer's cgroup memory-budget sweep.
- Stage-aware (prefill vs decode) placement accounting from the NPU papers.
- MELTing point's device-farm protocol, including thermal and sustained-run effects.
- lm-Meter's low-overhead phase profiling.

### Cited Findings
- Network delay injected into the remote configurations' latency moves the accuracy–latency front — [arXiv 2609.08307](https://arxiv.org/html/2609.08307v1)
- Prediction-based configuration filtering by QoE, then energy-optimal selection, with low-MAPE random-forest surrogates — [arXiv 2606.23001](https://arxiv.org/html/2606.23001v1)
- cgroup/taskset memory and core caps to emulate constrained devices on one host — [arXiv 2503.03777](https://arxiv.org/html/2503.03777v1)
- The prefill and decode stages prefer different backends, and the answer flips by framework — [arXiv 2607.05475](https://arxiv.org/html/2607.05475v1); [arXiv 2605.27435](https://arxiv.org/html/2605.27435v1)
- Sustained-run throughput drops (at the 20th and 32nd prompts on iPhone) and 47.9 °C surface temperature. Device-farm automation with a Monsoon power monitor — [arXiv 2403.12844](https://arxiv.org/html/2403.12844v4)
- MELTing point's own profiling cut decode throughput by more than 93% under Powersave, vs lm-Meter's 0.99%. Measurement overhead itself is a confounder — [arXiv 2510.06126](https://arxiv.org/pdf/2510.06126)
- Mixed proactive/reactive agent workloads on a shared SoC with memory-pressure tiers — [arXiv 2506.24045](https://arxiv.org/html/2506.24045v2)
- Host CPU accounts for up to 30% of system energy during NPU inference. Count whole-SoC energy, not just the accelerator — [arXiv 2607.05475](https://arxiv.org/html/2607.05475v1)

### Inferences
- **Experiment idea A (front shift):** For each local configuration (placement × weight bits × KV bits × context), measure the local point. Add cloud points at several RTT and TPOT offsets. Report which local configurations are ever on the joint front and the crossover RTT at which routing flips. This shows hardware configuration as a hidden variable: the crossover RTT moves with the local configuration.
- **Experiment idea B (stage split across boundary):** The local-only papers show prefill and decode prefer different engines. In the hybrid setting, test "cloud prefill + local decode" vs "local prefill + cloud decode" as further placements, since the stage preference already exists locally.
- **Experiment idea C (memory budget sweep):** Use cgroups to sweep device RAM (e.g., 4/6/8/12/16 GB) and record the fraction of agent turns that must go to the cloud because of OOM or paging-cliff regimes. This gives a provisioning curve.
- **Experiment idea D (sustained/thermal):** Run long agent sessions (more than 30 turns) to capture DVFS and thermal drift, which shifts the routing decision over time.
- **Metric idea:** Report energy per *successful* agent turn (quality-gated), whole-SoC plus radio energy, and an HQ-style harmonic score alongside full Pareto plots.

### Gaps
- No local-only paper found that measures radio/network energy for the device side of offload. The hybrid study must source this elsewhere.
- No local-only paper found that evaluates prefix-cache reuse across agent turns as a swept variable. This remains a novel axis for the hybrid study.
