# New hybrid device-cloud LLM papers that vary device-side configuration (Sweep 2, 2025 to Oct 2026)

Scope notes: The sweep skipped the 20 papers already logged (HW-Router 2608.14575, RouterWise 2604.10907, 2607.18253, 2502.11007, 2509.24050, Hydra 2608.25053, Agent-X 2605.10380, 2603.23640, 2508.06753, PAAC 2605.08646, IslandRun 2512.00595, HybridFlow 2512.22137, ConfigSpec 2604.09722, HERA 2504.00434, Agent.xpu 2506.24045, HeRo 2603.01661, QEIL v2 2602.06057, MALBO 2511.11788, AgentServeSim 2606.09613, 2605.30102). 2509.24050 now shows a v4 on arXiv, but this sweep did not re-check its content. Each paper gets a closeness score from 0 to 3 for four SEAM sub-claims:
- **A, configuration-caused escalation:** cloud spend is attributed to device-side limits.
- **B, configuration beats routing:** configuration moves cost and quality more than routing policy does.
- **C, router rank reversal:** which router wins changes across configurations.
- **D, provisioning substitution:** configuration substitutes for buying hardware, or the paper jointly optimizes provisioning and routing, or builds a Pareto front over hardware BOM.

All quotes come from WebFetch extraction of the arXiv abstract or HTML pages. They should be checked against the PDF before they are cited in a paper.

## Which new hybrid papers vary device-side configuration knobs, and which outcomes do they report?

### Takeaway
About 14 new hybrid papers from 2025 to Oct 2026 turned up. Almost all of them hold device hardware fixed. The device-side knobs they do vary are mostly **local model size** (STEPGATE, CARGO, RouterXBench, CR2), **draft length or transmitted-token quantization** (edge-cloud speculative decoding), **split point, bit-width and memory budget** (split computing), **edge device type** (Splitwise, Edge-First), or **runtime device state** (HybridInfer's thermal headroom). None of them sweeps KV-cache precision, prefix-cache or session residency, or CPU/GPU/NPU placement in a hybrid setting. None runs on an x86 AI PC with a cloud tier. The two closest to SEAM are STEPGATE (2610.07816; BFCL, multi-turn, local model size sweep, a router-advantage collapse at 3B) and the Carbon-Aware Function-Calling router (2609.13559; per-tier hardware prediction for function calling).

### Cited Findings

#### Tier 1: closest to SEAM (hybrid, agentic or function-calling, with some device-side variation)

**1. Do I Need the Cloud? Uncertainty-Aware Step-Level Handoff for Small Language Model Agents (STEPGATE)**: Abolfazl Younesi (affiliation listed on the HTML page as Sharif University of Technology); arXiv 2610.07816 (October 2026 ID; exact date not shown on page)
- Setup: single-step BFCL-derived split (100 tasks, 52 test) plus a multi-turn set of 100 tasks in a sandboxed calendar, email, file and search environment. Local models are Qwen2.5-0.5B, 1.5B and 3B. The "strong" model is Qwen2.5-7B at 4-bit, which is not a frontier cloud model. No hardware is named, and the paper says energy measurements are "hardware-specific." — [arXiv 2610.07816](https://arxiv.org/html/2610.07816)
- Knobs varied: local model size, routing thresholds, extra local samples, one local retry, and **handoff context (full vs. minimized)**. No quantization, placement, or KV sweep. — [arXiv 2610.07816](https://arxiv.org/html/2610.07816)
- Outcomes for the 1.5B/7B pair: local-only gets 67.3% single-step and 48.0% multi-turn success. STEPGATE gets 82.7% at 30.8% cloud and 69.0% multi-turn at 30% cloud actions. Strong-only gets 92.3% and 82.0%. On latency, "STEPGATE's measured end-to-end latency is 0.777s versus 2.255s for strong-only". On remote tokens, "remote tokens are 134.5 versus 475.0". — [arXiv 2610.07816](https://arxiv.org/html/2610.07816)
- Router advantage collapses with local model size: at 3B, learned routing "yields diminishing returns for 3B (90.4% vs. an 88.5% local baseline and a 90.8% random escalation baseline)". In other words, random escalation beats the learned router at 3B. The STEPGATE vs. self-consistency multi-turn difference is not significant (p=0.629). — [arXiv 2610.07816](https://arxiv.org/html/2610.07816)
- Closeness: A=0 (escalations are not attributed to device limits), B=1, **C=2** (the winner flips between learned and random routing as local model size changes), D=0.

**2. Carbon-Aware Routing for Function Calling in Edge-Cloud LLM Systems**: Aikaterini Maria Panteleaki (with Paramanayakam, Tragoudas, Anagnostopoulos); arXiv 2609.13559, submitted 2026-09-11
- Three-tier edge-cloud system on "heterogeneous hardware." A k-NN predictor estimates per-query accuracy, delay and power on each edge tier, and these are combined with real-time grid carbon intensity to pick the lowest-emission tier that can complete the query. Uses "state-of-the-art function-calling benchmarks" (the abstract does not name BFCL). — [arXiv 2609.13559](https://arxiv.org/abs/2609.13559)
- Outcomes: "matches cloud-level accuracy" while "reducing operational carbon emissions by $4\times$ on average". The abstract does not report cost in dollars or the fraction of queries sent to cloud. — [arXiv 2609.13559](https://arxiv.org/abs/2609.13559)
- Knobs: the hardware tier is a routing target, not a swept device configuration. The abstract does not mention quantization, KV cache or context. — [arXiv 2609.13559](https://arxiv.org/abs/2609.13559)
- Closeness: A=0, B=0, C=0, D=1 (tiers are hardware-aware, but there is no provisioning sweep). Only the abstract page was read. The full text may hold per-tier hardware details.

**3. Efficient On-Device Agents via Adaptive Context Management**: Sanidhya Vijayvargiya (CMU, with Samsung Research America); arXiv 2511.03728 (Nov 2025 ID)
- Hybrid: the on-device agent answers directly, runs local tools, or delegates to a cloud LLM, which the paper calls a "hybrid on-device/cloud routing paradigm". — [arXiv 2511.03728](https://arxiv.org/html/2511.03728v1)
- Knobs: **context management** (State-Tracker compresses history into a Context State Object, compact tool schemas, just-in-time tool loading). Runs on CPU-based Galaxy S25 with 4-bit llama.cpp. Cuts initial prompt more than 6x and slows context growth 10–25x. — [arXiv 2511.03728](https://arxiv.org/html/2511.03728v1)
- Quotes: "limited memory capacity, which restricts usable context"; "a 10-fold reduction in the rate of context increase for typical, non-cloud conversations"; "This system incurs a modest overhead of an approximate 80MB memory increase and a 500ms latency per turn". — [arXiv 2511.03728](https://arxiv.org/html/2511.03728v1)
- Closeness: A=1 (memory limits on context are the stated motivation, but cloud delegation is not attributed to context overflow), B=0, C=0, D=1 (the context-retention knob relieves memory limits, which is close in spirit to configuration substituting for memory). The retention and context knob matches one of SEAM's knobs directly.

**4. HybridInfer: Thermal-Aware Reinforcement-Learning Tier Routing for On-Device, Edge, and Cloud LLM Inference**: Simran Koul (independent); arXiv 2609.30270 (page lists 14 Jul 2026)
- Q-learning router over on-device Llama 3.2 3B (q4f16_0, Galaxy S25+), edge Llama 3.1 8B plus RAG, and cloud GPT-4o. The router's state is **device thermal headroom** (5 bins) and query complexity. — [arXiv 2609.30270](https://arxiv.org/html/2609.30270)
- Device state drives offload: "a continuous always-on-device session crashes or wedges within a few queries"; "22 of 40 long prompts wedge past a 240 s cap"; "temperature is an aggravating stressor, not the sole cause". — [arXiv 2609.30270](https://arxiv.org/html/2609.30270)
- Outcomes on the matched 40-prompt subset: the learned router reaches BERTScore 0.8446 at $0.0017/query with 7% on-device. Cloud-only reaches 0.8496 at $0.0053/query. The thermal heuristic reaches 0.8373 with 37% on-device, and the complexity heuristic runs 50% on-device. On the locality bonus: "without it, the optimal policy degenerates to offloading every query". The paper notes "The study uses a single device model." — [arXiv 2609.30270](https://arxiv.org/html/2609.30270)
- Closeness: **A=2** (offload is explicitly driven by device state, with long-context wedging and thermal limits, although there is no quantitative decomposition), B=1, C=0, D=0.

#### Tier 2: hybrid routing or offloading with local-model or deployment variation

**5. Routing Without Training: Controllable-Ratio LLM Offloading via Reliability Gating (CARGO)**: Evan Chen (Purdue); arXiv 2607.20481, Jul 24 2026
- Local-cloud offloading to DeepSeek-R1. Local models: Llama-3.2-1B and 3B, Qwen2.5-1.5B, 3B and 7B, Phi-3-mini and Phi-3-medium, plus pretrained vs. RLHF versions. Hardware is not varied ("All experiments are conducted under 2 H100 GPUs."). No quantization. — [arXiv 2607.20481](https://arxiv.org/html/2607.20481v1)
- **Router rankings shift with the local model.** Baselines are "task-dependent and less consistent across benchmark types and model families", and "their performance varies across models and datasets". CoT-steps beats self-confidence on GSM8K with Qwen2.5-3B but trails it on some Phi-3 rows. For 1B and 1.5B models, training-free routing becomes much less effective. "Training-free signals can only exploit reliability structure that already exists in the local model". — [arXiv 2607.20481](https://arxiv.org/html/2607.20481v1)
- Closeness: A=0, B=1 (the local model sets an upper bound on routing gains), **C=2** (rank changes across local model family and size), D=0.

**6. Towards Fair and Comprehensive Evaluation of Routers in Collaborative LLM Systems (RouterXBench / ProbeDirichlet)**: Wanxing Wu (SUSTech); arXiv 2602.11877, Feb 12 2026
- Local-cloud router benchmark. Main pair is GPT-5 with Llama-3.1-8B. A side analysis covers Qwen2.5 at 0.5B, 3B and 7B. No hardware or quantization. "Our experiments focus on a single small-large model pair and report single-run results due to computational constraints". — [arXiv 2602.11877](https://arxiv.org/html/2602.11877v1)
- Rank sensitivity comes only from the threshold choice: "even minor shifts can lead to opposite conclusions about the Locally Adaptive Router". Cost is measured as large-model call rate. — [arXiv 2602.11877](https://arxiv.org/html/2602.11877v1)
- Closeness: A=0, B=0, C=1 (rank reversal under evaluation choices, not hardware), D=0. Useful as a citation that router conclusions are fragile.

**7. CR2: Cost-Aware Risk-Controlled Routing for Wireless Device-Edge LLM Inference**: Nan Xue (SJTU); arXiv 2605.12001 (2026)
- Device is Qwen3-1.7B on a Jetson AGX Orin profile. Edge pool is Qwen3-4B, 8B and 14B on RTX 4070 Ti, RTX 4090 and A40, each with profiled latency and power. Wireless state (channel, distance 30–150 m, bandwidth) sets deployment cost. — [arXiv 2605.12001](https://arxiv.org/html/2605.12001)
- Cuts normalized cost by up to 16.9% at matched accuracy. The residual gap is attributed to the router itself: "The residual gap is thus mainly driven by over-escalation at lower costs". Per-benchmark ranks shift: "Overall improvements thus reflect a stronger operating frontier rather than per-benchmark dominance". — [arXiv 2605.12001](https://arxiv.org/html/2605.12001)
- Closeness: A=0, B=0, C=1 (ranks shift per benchmark, not per device configuration), D=0. Device-to-edge rather than device-to-cloud, so it is adjacent to SEAM.

**8. ECO-LLM: Orchestration for Domain-specific Edge-Cloud Language Models**: Prasoon Patidar (CMU, with Microsoft Research co-authors); arXiv 2507.09003 (2025)
- Jointly searches a **configuration space**: query processing (CoT, step-back, LLMLingua), retrieval (chunk size, top-k, HyDE), context processing (CRAG, reranking), model (with context length and max tokens, and "various quantization levels"), and edge vs. cloud placement. — [arXiv 2507.09003](https://arxiv.org/html/2507.09003v1)
- Claims it beats model-only routing (RouteLLM) and GPT-4o: "ECO-LLM outperforms GPT-4o in terms of accuracy (90% vs. 74% on average)" while reducing "costs by 90% and latency by 55%". It frames the problem as "a joint optimization challenge". The headline numbers differ from those in Sec. 5.2, which reports 83% and 88% cost cuts. — [arXiv 2507.09003](https://arxiv.org/html/2507.09003v1)
- Hardware is not swept: edge models ran on one RTX A6000 ("This exceeds typical edge capabilities"), and hardware-aware emulation is left to future work. — [arXiv 2507.09003](https://arxiv.org/html/2507.09003v1)
- Closeness: A=0, **B=2** (whole-pipeline configuration beats model-routing alone, though the knobs are software and pipeline settings rather than hardware), C=1 (best path differs by domain: "The same path yields different latency-cost-accuracy tradeoffs for smart homes versus automotive assistants"), D=0.

**9. Edge-First Language Model Inference: Models, Metrics, and Tradeoffs**: SiYoung Jang (Nokia Bell Labs); IEEE ICDCS 2025; arXiv 2505.16508
- Hardware varied: Jetson AGX Orin, Jetson Orin Nano, a smartphone, plus simulated high-, medium- and low-capacity nodes. Qwen-2.5 from 0.5B to 72B. Cloud fallback when edge capacity is exceeded. — [arXiv 2505.16508](https://arxiv.org/pdf/2505.16508)
- "cloud fallback becomes essential due to limits in scalability or model capacity". Device-selection policy changes how many tokens are redirected to cloud: "*Weighted* significantly reduces tokens redirected to the cloud and associated costs". Cost per response is about 1.65¢ for GPT-4, 0.0041¢ for AGX/7B, and 0.0017¢ for Nano/3B (electricity only). Quality is 0.97, 0.91 and 0.80 respectively. — [arXiv 2505.16508](https://arxiv.org/pdf/2505.16508)
- Closeness: **A=2** (cloud tokens are explicitly attributed to edge capacity limits and load, the closest prior instance of capacity-caused escalation found), B=1, C=1 (the best device-selection policy differs between steady and bursty workloads), D=1. Caveat: the paper's PCR metric mixes directions and has a 332.35 vs. 332.25 inconsistency.

#### Tier 3: edge-cloud split or speculative execution (device-side knobs are bit-width, split point, device type, draft length)

**10. Splitwise: Collaborative Edge–Cloud Inference for LLMs via Lyapunov-Assisted DRL**: Abolfazl Younesi (U. Innsbruck); UCC '25 (Dec 2025); arXiv 2512.23310
- Head- and FFN-level partition between edge and cloud on Jetson Orin NX, Galaxy S23 and Raspberry Pi 5. Results: "reduces end-to-end latency by 1.4×–2.8×", "cuts energy consumption by up to 41%", and "reducing the required edge memory to 10 GB through effective computation offloading". Cloud cost is under $25 per million requests for 13B vs. more than $150 cloud-only. The fetched excerpt did not include per-device breakdowns. — [arXiv 2512.23310](https://arxiv.org/html/2512.23310)
- Closeness: A=1, B=0, C=0, D=1 (offload as a substitute for edge memory).

**11. Memory- and Latency-Constrained Inference of LLMs via Adaptive Split Computing**: Mingyu Sung; arXiv 2511.04002, Nov 6 2025
- Joint optimization over split point, mixed-precision quantization (OPSC; per-token adaptive bits, TAB-Q) and sequence length under a device memory budget. It "prevents out-of-memory failures by strategically partitioning models" and "achieves a 1.49 inference speedup". — [arXiv 2511.04002](https://arxiv.org/abs/2511.04002)
- Closeness: A=1, B=0, C=0, D=1 (the memory budget is an explicit constraint, but the abstract does not show how it shifts load to cloud).

**12. Quantize-Sample-and-Verify: LLM Acceleration via Adaptive Edge-Cloud Speculative Decoding**: Guangyi Zhang; arXiv 2507.00605 (v3 Jan 10 2026)
- Adapts **draft length and quantization precision** of the transmitted token information to channel conditions and semantic uncertainty. The quantized information is the transmitted token distribution, not the drafter's weights. It "provably preserves the output distribution of the cloud-based model". — [arXiv 2507.00605](https://arxiv.org/abs/2507.00605)
- Closeness: A=0, B=0, C=0, D=0 (the quantization is of the communication, not a device configuration).

**13. SPADE: Speculative Decoding for Precise and Low-Cost Distributed Edge–Cloud Inference**: Divya Jyoti Bajpai (IIT Bombay); arXiv 2608.13076, Aug 13 2026
- Single edge configuration: RTX 3080 12 GB with a Llama-3.2-1B drafter. About 77% fewer cloud target calls (133.25 down to 30.16 on Spec-Bench) with small quality dips (4.45 to 4.38). The paper acknowledges that "Model selection at the edge is governed by available resources such as GPU memory, CPU throughput, and system bandwidth" but does not measure this. — [arXiv 2608.13076](https://arxiv.org/html/2608.13076)
- Closeness: A=0, B=0, C=0, D=0.

**14. Speculation at a Distance: Where Edge-Cloud Speculative Decoding Actually Pays Off**: Yuan Lyu; arXiv 2606.25091 (v1 Jun 23, v2 Sep 5 2026)
- Analytic model: "DSD's per-request latency benefit is limited under WAN edge-cloud communication", and DSD "should therefore be evaluated primarily by multi-tenant capacity and server throughput." Whether collaboration pays off depends on RTT, drafting time t_d and whether the server can host both models. It is also infeasible against closed APIs without a verifier interface. — [arXiv 2606.25091](https://arxiv.org/abs/2606.25091)
- Closeness: A=0, B=1 (deployment conditions decide whether the hybrid technique wins at all), C=0, D=0. Relevant to SEAM because a Claude Sonnet cloud tier rules out distributed speculative decoding.

Also noted but not fetched in depth: FlexSpec (arXiv 2601.00644, edge-cloud speculative decoding with frozen drafts) — [arXiv 2601.00644](https://arxiv.org/abs/2601.00644); Latency-Optimal Adaptive Split Inference for Cloud-Edge-End (arXiv 2608.01148) — [arXiv 2608.01148](https://arxiv.org/abs/2608.01148).

#### Industry reports (hybrid; checked for configuration-dependence claims)
- **Perplexity and Intel hybrid orchestrator** (Computex, June 2 2026): routes between PC and cloud by data sensitivity and capability need. "A compact model runs locally to detect when sensitive data" is present, "while work requiring a frontier model's full capability routes to the server". The demo ran on Core Ultra Series 3. Srinivas calls it "chip agnostic". **No statement that local memory, NPU/GPU or chip generation changes what runs locally.** — [Pulse 2.0](https://pulse2.com/perplexity-announces-first-hybrid-local-server-inference-orchestrator-for-personal-computer/); [How2Shout](https://www.how2shout.com/news/perplexity-intel-hybrid-inference-orchestrator-computex-2026.html); [Decrypt](https://decrypt.co/369941/perplexity-hybrid-local-cloud-mode)
- **Apple Intelligence Foundation Language Models Tech Report 2025** (arXiv 2507.13575, Jul 2025): about 3B on-device model with KV-cache sharing and 2-bit QAT, plus a PT-MoE server model on Private Cloud Compute. The abstract describes no policy for the on-device vs. server split and no configuration knobs. — [arXiv 2507.13575](https://arxiv.org/abs/2507.13575v2)

#### Separate list: LOCAL-ONLY papers (not hybrid; context only)
- Measurement Study of LLM Inference Trade-offs Across Edge Continuum Hardware (Khatib, arXiv 2609.08307, Sep 2026). Varies Orin GPU, server CPU and server GPU; F16, Q5_K_M and Q4_K_M; and model families 1B–7B. GPT-4o is a reference only. "Model size alone is an insufficient deployment heuristic"; "CPU-only execution is consistently dominated in latency for our workload"; "the best deployment depends on the accuracy-delay trade-off". No monetary cost. — [arXiv 2609.08307](https://arxiv.org/html/2609.08307v1)
- Pre-Compiled Pipeline Shards for Distributed LLM Inference on Intel AI PC Fleets (Berenbaum, with an Intel co-author; arXiv 2608.19147, Aug 2026). Uses OpenVINO INT4 shards across Lunar Lake iGPUs and reports that the "INT8 KV cache hint ran slower than the default on Arc iGPU" (extractor paraphrase). Shard runs at 24.45 tok/s vs. 24.54 monolithic. No cloud fallback. Its Sec. 8.1 "When Is a Fleet Better Than Cloud?" was not in the fetched excerpt. Directly relevant to SEAM's OpenVINO and Arc KV-precision observations. — [arXiv 2608.19147](https://arxiv.org/html/2608.19147v1)
- TinyLLM: SLMs for agentic tasks on edge (Haque, arXiv 2511.22138, Nov 2025). Uses BFCL including multi-turn. Up to 65.74% overall and 55.62% multi-turn. "medium-sized models (1-3B parameters) significantly outperform ultra-compact models (<1B parameters)". Edge-only. — [arXiv 2511.22138](https://arxiv.org/abs/2511.22138)
- From Bits to Chips: HAQA hardware-aware quantization agent (Deng, arXiv 2601.03484, Jan 2026). Reports up to 2.3x speedup and adapts quantization per hardware platform. No cloud. — [arXiv 2601.03484](https://arxiv.org/abs/2601.03484v1)
- EnviroLLM (Allen, Georgia Tech; arXiv 2512.12004, Dec 2025). Local resource tracking; "model architecture dominates resource consumption independent of task-specific performance". — [arXiv 2512.12004](https://www.arxiv.org/pdf/2512.12004)
- Private LLM server for SMBs: Qwen3-30B on RTX 5090 (Khalil, arXiv 2512.23029, Dec 2025). On-prem vs. cloud baselines only. — [arXiv 2512.23029](https://www.arxiv.org/pdf/2512.23029)
- Agent Memory Below the Prompt: persistent Q4 KV cache for multi-agent edge inference (arXiv 2603.04428). Seen in search results only, not fetched. It is relevant to SEAM's KV-precision and residency knobs and is worth a check. — [arXiv 2603.04428](https://arxiv.org/html/2603.04428v1)

### Inferences
- The device-side knobs SEAM treats as first-class (KV-cache precision, weight precision, CPU/GPU/NPU placement, session residency and prefix caching, context retention) are, in the hybrid literature found, either held fixed or studied only in local-only papers. The hybrid papers vary local model size, network or wireless state, split point, or device thermal state instead.
- Agentic hybrid work on BFCL (STEPGATE) uses an open 7B model as the "cloud" and does not vary hardware, so SEAM's pairing of a real frontier API (Claude Sonnet) with a consumer AI PC seems still unoccupied.

### Gaps
- Exact submission date and venue for STEPGATE (2610.07816) and CR2 (2605.12001) were not visible on the pages fetched.
- The full text of 2609.13559 (Carbon-Aware Function Calling) was not read. Its per-tier hardware specs and benchmark names are unconfirmed.
- MobiSys 2026, MobiCom 2026, MLSys 2026 and ISCA/MICRO 2026 accepted-paper lists turned up in search but were not scanned title by title. A manual pass is recommended.
- No 2025–2026 Qualcomm, AMD or Microsoft hybrid-AI whitepaper with configuration-dependence claims was found in this sweep. Qualcomm's widely cited hybrid AI whitepaper is from 2023 and outside scope.

## Does any paper claim configuration matters more than routing policy, or show rank reversal of routers across configurations?

### Takeaway
No paper found claims that **hardware** configuration matters more than routing policy. Three papers come closest. ECO-LLM argues that joint pipeline-configuration search beats model-only routing (B=2, but for software and pipeline knobs). STEPGATE and CARGO both show router rankings flipping as the **local model** changes (C=2). The router-ranking-across-hardware result remains unclaimed.

### Cited Findings
- STEPGATE: at a 3B local model, learned routing "yields diminishing returns for 3B (90.4% vs. an 88.5% local baseline and a 90.8% random escalation baseline)". Random escalation edges out the learned router once the local model gets stronger. — [arXiv 2610.07816](https://arxiv.org/html/2610.07816)
- CARGO: baseline routers are "task-dependent and less consistent across benchmark types and model families". The CoT-steps vs. self-confidence ordering flips between Qwen2.5-3B and Phi-3. Routing becomes much less effective with 1B and 1.5B local models. — [arXiv 2607.20481](https://arxiv.org/html/2607.20481v1)
- RouterXBench: router conclusions flip with threshold choice: "even minor shifts can lead to opposite conclusions about the Locally Adaptive Router". — [arXiv 2602.11877](https://arxiv.org/html/2602.11877v1)
- CR2: "Overall improvements thus reflect a stronger operating frontier rather than per-benchmark dominance" (rankings change per benchmark). — [arXiv 2605.12001](https://arxiv.org/html/2605.12001)
- ECO-LLM: frames edge-cloud as "a joint optimization challenge" over pipeline configuration and placement. It beats RouteLLM and reports "costs by 90% and latency by 55%" lower. Hardware is fixed on one A6000. — [arXiv 2507.09003](https://arxiv.org/html/2507.09003v1)
- Speculation at a Distance: whether edge-cloud speculative decoding beats co-located or cloud-only decoding depends on RTT and the server's hosting capacity. "DSD's per-request latency benefit is limited under WAN edge-cloud communication". — [arXiv 2606.25091](https://arxiv.org/abs/2606.25091)

### Inferences
- STEPGATE and CARGO together suggest a pattern: as local capability rises, the margin from a sophisticated router shrinks or inverts. This matches SEAM's claim if hardware configuration (weight precision, context retention, model size that fits in memory) is what sets local capability. Neither paper ties this to hardware, which leaves SEAM's framing distinct.
- ECO-LLM is the most direct precedent for "configuration over routing," so SEAM should cite it and distinguish itself: ECO-LLM's configuration is the application pipeline, while SEAM's is device hardware and runtime.

### Gaps
- No paper compares routers across hardware platforms, precision settings or memory sizes. This may be a true absence or a search limit. Full-text grep of the 2026 MLSys and MobiSys proceedings was not done.

## Does any paper jointly choose hardware provisioning (memory size, accelerator) and routing policy, or compute a Pareto over quality, cloud spend and hardware BOM?

### Takeaway
No. The closest work treats device memory as a **constraint** that offloading relieves (Splitwise, adaptive split computing 2511.04002). Edge-First prices edge vs. cloud per response but uses electricity-only edge cost and no hardware BOM. The measurement study 2609.08307 builds accuracy-latency Pareto fronts across hardware, but it is local-only and has no cloud spend. No paper builds a Pareto front over quality, cloud spend and hardware BOM.

### Cited Findings
- Splitwise: "The 13B parameter model requires over 50 GB, exceeding the 8 GB limit of typical mobile devices". Offloading means "reducing the required edge memory to 10 GB through effective computation offloading". Cloud cost is under $25 vs. more than $150 per million requests cloud-only. — [arXiv 2512.23310](https://arxiv.org/html/2512.23310)
- Adaptive split computing jointly optimizes split point, quantization and sequence length "under memory and latency limits" and "prevents out-of-memory failures by strategically partitioning models". — [arXiv 2511.04002](https://arxiv.org/abs/2511.04002)
- Edge-First: cost per response is about 1.65¢ for GPT-4 vs. 0.0041¢ for Jetson AGX/7B and 0.0017¢ for Nano/3B, counting electricity only with no hardware amortization. — [arXiv 2505.16508](https://arxiv.org/pdf/2505.16508)
- Edge continuum measurement (local-only): every CPU-only trial falls off the accuracy-latency Pareto front, and "the best deployment depends on the accuracy-delay trade-off". It reports no monetary cost. — [arXiv 2609.08307](https://arxiv.org/html/2609.08307v1)
- CR2 profiles four GPU platforms (Orin, 4070 Ti, 4090, A40) but treats them as a fixed pool. The routing objective is normalized deployment cost, not provisioning. — [arXiv 2605.12001](https://arxiv.org/html/2605.12001)

### Inferences
- SEAM's claim that configuration can substitute for buying more memory (16 GB laptop vs. 64 GB mini PC) has partial precedent in the split-computing idea that offloading reduces required edge memory. The reverse direction, where device configuration reduces cloud spend at fixed hardware and is weighed against a hardware upgrade, has no precedent found.

### Gaps
- No TCO-style hybrid paper that amortizes device hardware against API spend was found. Grey-literature TCO blogs exist (e.g., Lenovo Press LP2368), but they compare on-prem vs. cloud, not hybrid, and were not examined.

## Does any paper attribute cloud cost to device-side limits (context overflow, latency SLO) vs task difficulty?

### Takeaway
Only qualitatively. Edge-First attributes cloud-redirected tokens to edge capacity and scalability limits. HybridInfer shows that device thermal and long-prompt wedging drive offloading. The context-management agent paper (2511.03728) motivates its work by memory-limited context. No paper decomposes cloud spend into configuration-caused vs. difficulty-caused escalation, which is SEAM's specific accounting.

### Cited Findings
- Edge-First: "cloud fallback becomes essential due to limits in scalability or model capacity". Device-selection policy changes cloud-redirected tokens: "*Weighted* significantly reduces tokens redirected to the cloud and associated costs". Under bursty load, Load-Aware gives the lowest redirection. — [arXiv 2505.16508](https://arxiv.org/pdf/2505.16508)
- HybridInfer: "22 of 40 long prompts wedge past a 240 s cap"; "temperature is an aggravating stressor, not the sole cause". The learned router runs only 7% on-device. There is no causal breakdown of offloading. — [arXiv 2609.30270](https://arxiv.org/html/2609.30270)
- Efficient On-Device Agents: "limited memory capacity, which restricts usable context". The hybrid mode delegates complex queries to cloud, and the paper reports a "10-fold reduction in the rate of context increase for typical, non-cloud conversations". — [arXiv 2511.03728](https://arxiv.org/html/2511.03728v1)
- CR2 attributes residual cost to the router's own over-escalation rather than to device limits: "The residual gap is thus mainly driven by over-escalation at lower costs". — [arXiv 2605.12001](https://arxiv.org/html/2605.12001)
- STEPGATE gates on uncertainty, schema, consistency, state and risk. Latency and energy appear only as objective terms, and there is no attribution of handoffs to device limits. — [arXiv 2610.07816](https://arxiv.org/html/2610.07816)

### Inferences
- SEAM's "configuration-caused escalation" metric, the cloud spend that would disappear under a different device configuration at equal task difficulty, appears to be novel as a quantified decomposition. Edge-First (capacity) and HybridInfer (thermal and long-prompt) are the best prior citations showing that device-side limits cause offload qualitatively.

### Gaps
- None of the fetched papers reports a counterfactual such as "same task, different device config, which changes the cloud call." Full texts of 2609.13559 and 2512.23310 might have per-device escalation tables. Those sections were not in the fetched excerpts.
