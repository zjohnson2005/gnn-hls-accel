# Known hybrid device-cloud LLM execution papers vs. SEAM claims (sweep 1: fixed list of 20)

Scope note: 20 arXiv IDs were checked (all resolved, all real, dates through Aug 2026). Rating scale per sub-claim: 0 = unrelated, 1 = adjacent (same vocabulary, different setting or not tested), 2 = partial overlap (makes a similar claim in a different setting or tests it weakly), 3 = pre-empts the claim. Claim keys: C1 config-caused escalations / cloud bill; C2 config moves cost/quality more than routing policy; C3 routing-policy rank reversal across device configs; C4 config change substitutes for buying hardware/memory; P2a joint provisioning + routing; P2b predictive routing / silent local failure.

Retrieval caveats: arXiv API and some arXiv URLs were blocked by the fetch proxy; HW-Router was read from its abstract page only (PDF returned no text); 2509.24050 was read from its abstract page only (HTML blocked); 2605.30102 was read from abstract + HTML v1. Some arXiv HTML renderings lacked dates, so dates come from abstract pages or arXiv stamps where available.

## Paper-by-paper classification (hybrid vs local-only vs datacenter; fixed vs varied device knobs)

### Takeaway
Of the 20 papers, only 8 are device+cloud hybrids (2502.11007 TMO, 2509.24050, PAAC, IslandRun [conceptual, no experiments], HybridFlow, ConfigSpec, HERA, "When Cloud Agents Meet Device Agents" [device simulated on A100]); 7 are local-only (Hydra, Agent-X, 2603.23640, 2508.06753, Agent.xpu, HeRo, QEIL v2) and 4 are datacenter/cloud-only (HW-Router, RouterWise, 2607.18253, AgentServeSim) plus MALBO (cloud-API-only). Every hybrid paper except ConfigSpec holds the device configuration fixed (one GPU, one model, no quantization/KV/residency/context sweeps), and none runs on a real consumer AI PC.

### Cited Findings

**Datacenter / cloud-only (NOT hybrid)**
- **HW-Router: Hardware-Aware Routing for Scalable Multi-LLM Serving** (2608.14575). Ahasan Kabir, Jiaqi Xue, Mengxin Zheng, Qian Lou (UCF). arXiv v1 dated 10 Jun 2026, cs.NI, no venue listed. Datacenter, multi-LLM across heterogeneous GPUs. Adds real-time hardware signals (queue lengths, KV-cache usage, GPU utilization, recent TTFT/TPOT) to routing via a lightweight latency predictor. Reports lower E2E latency, higher SLO attainment vs. CARROT and IRT, about 200 µs routing overhead, no quality loss. Its premise is that existing routers estimate cost from "static model properties" and ignore hardware state. — [arXiv abs](https://arxiv.org/abs/2608.14575). Ratings: C1 0, C2 1, C3 1, C4 0, P2a 0, P2b 1 (predictive latency, not failure).
- **RouterWise** (2604.10907). Hossein Hosseini Kasnavieh, Gholamreza Haffari, Chris Leckie, Adel N. Toosi (Melbourne/Monash). The search index lists it as "RouterWise: Joint Resource Allocation and Routing for Latency-Aware Multi-Model LLM Serving"; the PDF fetched is titled "RouterWise: Deployment-Aware Prompt Routing for Multi-Model LLMs" (title differs between index and PDF, likely different versions). No venue stated. Datacenter: 4 or 8 A100 80GB, vLLM, 3 models (Mistral-7B, WizardLM-13B, Yi-34B). Varies tensor parallelism {1,2,4}, GPU thread % (10–100% via MPS), shard placement, co-location. Quantization and KV cache are not varied. It **jointly optimizes deployment setup (outer loop) and routing under a latency SLO (inner loop, dual-price rule)**. Quotes: "latency is not a fixed property of a model: it depends on how the model is deployed"; "achievable routing quality varies by up to 87% across deployment configurations on the same GPU cluster" (score span 0.30–0.56); "the optimal model for a prompt depends not only on the prompt itself, but on the deployment environment." About 700 retained setups (3 models) and about 17,000 (4 models). At λ=80, τ=500 ms, average TTFT is 600 ms vs. FrugalGPT 24,200 ms and RouteLLM 7,800 ms at matched score. Cost is NOT measured. The per-prompt rank-flip claim is asserted in the intro but not directly tested. — [arXiv PDF](https://arxiv.org/pdf/2604.10907). Ratings: C1 0, C2 2 (datacenter analog: deployment config moves achievable quality by 87%), C3 2 (states the optimal routing depends on deployment environment, but does not test it and is not device-side), C4 1, **P2a 2 (closest prior art for "provisioning and routing are one decision", but within a fixed cluster, not BOM/memory purchase, not hybrid)**, P2b 0.
- **Beyond Accuracy and Cost: Latency-Aware LLM Query Routing for Dynamic Workloads** (2607.18253). Shivam Patel, Akaash R. Parthasarathy, Ankur Mallick, Gauri Joshi (CMU; Microsoft). arXiv v1, page header 13 May 2026, cs.AI, no venue. Datacenter serving (vLLM/Sarathi-Serve; Fig. 2 uses Qwen3-0.6B on one H100). Varies offered load, latency emphasis, and arrival process. Not hardware configuration. Claims up to 40% improvement in accuracy–cost utility with latency comparable to load balancing; the TTFT estimator has under 5% MAPE. Escalation is attributed to query difficulty. The fetched excerpt was truncated before results. — [arXiv HTML](https://arxiv.org/html/2607.18253). Ratings: all 0–1 (C3 1: load-dependence of routing).
- **AgentServeSim: A Hardware-aware Simulator for Multi-Turn LLM Agent Serving** (2606.09613). Rakibul Hasan Rajib, Mengxin Zheng, Qian Lou (UCF). arXiv v2, 18 Jun 2026, cs.CL. Datacenter simulator (RTX 3090 / H100 / B200; Llama-3.1-8B/70B; HBM/DRAM/CXL tiers). Session residency and prefix caching are central. Session-aware routing gives about 96.26% prefix hit rate vs. 92.6–93.0% for round-robin/least-loaded and is 1.2–5.1 s faster on p95 JCT. At prefix reuse η=0.9, InferCept's mean JCT is about 3.3× lower than Autellix's (538.3 s vs. 1,751.4 s); at η=0.1 the gap is about 1.8×. Quote: "Multi-instance routing is not merely a load-balancing problem; it is a cache-locality problem." Most sweeps use one hardware config, there is no provisioning analysis, and rank flips across hardware are not shown. — [arXiv HTML](https://arxiv.org/html/2606.09613). Ratings: C1 0, C2 1, C3 1 (the size of a policy's advantage depends on workload reuse), C4 0, P2a 1, P2b 0.
- **MALBO** (2511.11788). Listed as "MALBO: Optimizing LLM-Based Multi-Agent Teams via Multi-Objective Bayesian Optimization"; the HTML is a Master's thesis "MALBO: Multi-Agent LLM Bayesian Optimization" by Antonio Sabbatella (Univ. Milano-Bicocca, AY 2024-25). Cloud-API-only multi-agent model assignment (accuracy vs. API cost). No device or hardware knobs. More than 45% average cost cut in the BO phase, and up to 65.8% cost reduction for heterogeneous vs. homogeneous teams. — [arXiv abs](https://arxiv.org/abs/2511.11788), [HTML](https://arxiv.org/html/2511.11788). Ratings: all 0 (methodological analog only: multi-objective search over a configuration space rather than a default).

**Local-only (NOT hybrid)**
- **Hydra: Phase-Aware Workload Characterization of LLM Inference across Edge SoC Generations, Backends, and Quantization Levels** (2608.25053). Amir Taherin et al. (Northeastern; Glasgow; W&M). Submitted 25 Aug 2026, accepted IEEE IISWC 2026. **Local-only** Jetson AGX Xavier/Orin/Thor, batch-1. Sweep: 3 SoCs × 13 models × 5 formats (HF bf16; llama.cpp F16/Q8_0/Q6_K/Q4_K_M) = 195 cells (190 loaded), about 107k records. KV reuse is on and not varied; placement is GPU-only. Q4_K_M mean ΔPPL +0.36 vs. F16; worst accuracy drop about 2.4 pts. Input 1k to 5k raises TTFT 5.0–5.7×. Quote: "edge LLM performance is not determined by parameter count or hardware generation alone." No cloud, routing, or provisioning. — [arXiv HTML](https://arxiv.org/html/2608.25053). Ratings: C4 1 (local analog), others 0.
- **Agent-X: Full Pipeline Acceleration of On-device AI Agents** (2605.10380). Jinha Chung, Byeongjun Shin, Jiin Kim, Minsoo Rhu (KAIST). Submitted 11 May 2026, no venue. **Local-only** (Mac mini M4 Pro, 64 GB, MLX, TinyAgent-7B). Knobs: tool-example count, KV cache budget (SSD-stored clusters), draft models. 1.61× E2E speedup, prefill 1.97×, decode 1.73×. — [arXiv HTML](https://arxiv.org/html/2605.10380). Ratings: all 0 (the KV-cache reuse idea is adjacent to session residency).
- **LLM Inference at the Edge: Mobile, NPU, and GPU Performance Efficiency Trade-offs Under Sustained Load** (2603.23640). Pranay Tummalapalli et al. (Conscious Engines). arXiv v2, 7 Jun 2026, cs.DC. **Local-only**. 4 platforms, one model (Qwen2.5-1.5B, 4-bit), 20 iterations each. iPhone 16 Pro drops from 40.49 to about 23.67 tok/s (−41.5%) under sustained load. [CORRECTED 2026-10-16: the paper reports 37.3% (Warm, 25.31 vs 40.35 tok/s) and 44.1% (sustained Hot, 22.56 tok/s) on an iPhone 16 Pro, Qwen2.5-1.5B 4-bit; not 41.5%, and not Intel. docs/literature/2026-10-16/TUNED_PROFILE/physics_data_path.md section 4.] Quote: "thermal management supersedes peak compute as the primary constraint." — [arXiv HTML](https://arxiv.org/html/2603.23640). Ratings: all 0 (supports the SEAM thermal warm-up guardrail).
- **Pushing the Envelope of LLM Inference with Ultra-Low-Bit Quantized Models** (2508.06753). Evangelos Georganas, Dhiraj Kalamkar, Alexander Heinecke, Pradeep Dubey (Intel). **The task brief labelled this "AI-PC hybrid", but it is local-only.** It has no cloud, offload, or routing. It targets Intel client CPUs (Core Ultra 285K/255H, Lunar Lake 258V) and Xe2 GPUs (Arc 140V iGPU, Arc B70 discrete), int2/ternary vs. BF16. A 2B model reaches 542 tok/s on BMG vs. 405 on RTX PRO 6000 and 300 on A100. LNL CPU reaches 88 tok/s. LNL-GPU 5.34 tok/J. — [arXiv HTML](https://arxiv.org/html/2508.06753). Ratings: C4 1 (weight precision lets client hardware beat datacenter GPUs on a small model, a local analog of "config substitutes for hardware"), others 0.
- **Agent.xpu: Efficient Scheduling of Agentic LLM Workloads on Heterogeneous SoC** (2506.24045). Xinming Wei et al. (PKU/HKU). arXiv v2, 6 Jan 2026, no venue. **Local-only** ("fully on-device concurrent serving"). Runs on an **Intel Core Ultra 5 125H (NPU + Arc iGPU), 64 GB**, W8A16, Llama-3.2-3B/3.1-8B, with an OpenVINO iGPU baseline. Placement is NPU/iGPU per op. Reactive latency is 91–97% lower vs. OpenVINO iGPU, and energy per token is 26.8% lower. Cloud is mentioned only as background ("selectively routed to cloud LLMs"). — [arXiv PDF](https://arxiv.org/pdf/2506.24045). Ratings: all 0 on hybrid claims (closest hardware platform to SEAM).
- **HeRo: Adaptive Orchestration of Agentic RAG on Heterogeneous Mobile SoC** (2603.01661). Maoliang Li et al. (PKU). **Local-only** LLM inference (Snapdragon 8 Gen 3/Gen 4, CPU/GPU/NPU placement, INT8). Up to 10.94× latency reduction vs. GPU-only. — [arXiv PDF](https://arxiv.org/pdf/2603.01661). Ratings: all 0.
- **QEIL v2: Roofline-Derived Pareto-Optimal Edge Intelligence via First-Principles Energy Modeling and Multi-Objective Orchestration** (2602.06057). Satyam Kumar, Saurabh Jha. No venue or date stated. **Local-only** heterogeneous edge (Core Ultra 9 285HX + NPU + RTX PRO 5000 + Intel iGPU), with layer placement across devices. Its reported IPW figures are inconsistent with its own definition (75.7/63.8 ≈ 1.19, not the 0.9749 it reports). — [arXiv HTML](https://arxiv.org/html/2602.06057). Ratings: all 0–1 (placement-as-knob analog, local).

**True device+cloud hybrids**
- **Device-Cloud Collaborative LLM Inference with Multi-Modal, Multi-Task, Multi-Turn Conversations** (TMO, 2502.11007). Liangqi Yuan, Dong-Jun Han, Shiqiang Wang, Christopher G. Brinton (Purdue/Yonsei/Exeter). Extends a MobiHoc 2025 paper (Best Paper runner-up). **Hybrid** (Phi-3-mini on device, GPT-4o cloud, RL router). **It varies the device platform (8 platforms in Table IV, Raspberry Pi-4B to iPhone 15 Pro; default Jetson TX2) and reports NO significant effect:** "Performance variations across different devices do not significantly impact the operation of the TMO system" (Sec. VI-F). The on-device model, quantization, KV, and memory are not varied. Cloud cost (Eq. 14) is device-independent. Per-device offload rate is not reported. On-device quality gaps are simulated by adjusting dataset scores. RC-A2C costs 13.71e-3 USD vs. 25.14e-3 cloud-only, with score 1.06 vs. 1.04. — [arXiv HTML](https://arxiv.org/html/2502.11007). Ratings: C1 0, **C2 1 (apparent counter-evidence)**, C3 1 (claims TMO is best on all devices, so no reversal, but per-baseline ranks are not shown), C4 0, P2a 0, P2b 0.
- **Bridging On-Device and Cloud LLMs for Collaborative Reasoning: A Unified Methodology for Local Routing and Post-Training** (2509.24050). Wenzhi Fang, Dong-Jun Han, Liangqi Yuan, Evan Chen, Christopher Brinton. Submitted 28 Sep 2025, v4 23 May 2026, cs.LG, no venue. **Hybrid**: the on-device LLM learns via RL post-training (hierarchical rewards, group-level policy gradient, adaptive prompt filtering) when to offload. It addresses "policy collapse" into always-local or always-cloud. On-device-scale LLaMA/Qwen. Device hardware configuration is not described as varied. — [arXiv abs](https://arxiv.org/abs/2509.24050). Ratings: C1 0, C2 0, C3 0, C4 0, P2a 0, P2b 1 (local self-assessment for offload; the full text was not readable, so its treatment of confident-wrong local answers is unverified).
- **PAAC: Privacy-Aware Agentic Device-Cloud Collaboration** (2605.08646). Liangqi Yuan, Wenzhi Fang, Shiqiang Wang, Christopher G. Brinton. **Hybrid** agent; the device model is **Qwen3-4B-Instruct (same model as SEAM) but served by vLLM on an A100**; the cloud is Gemini 3 Flash. Device config is not varied, and no router is evaluated. The on-device sanitizer "fails to adhere to the prescribed structured output format." Termination is reactive: "Unilateral termination is therefore unreliable in either direction." Accuracy +15–36% and leakage reduced 2–6× vs. device-cloud baselines. — [arXiv PDF](https://arxiv.org/pdf/2605.08646). Ratings: C1 0, C2 0, C3 0, C4 0, P2a 0, P2b 1.
- **IslandRun: Privacy-Aware Multi-Objective Orchestration for Distributed AI Inference** (2512.00595). Bala Siva Sai Akhil Malepati (sole author). arXiv preprint. **Hybrid but conceptual**: "This paper presents a theoretical framework without empirical evaluation on real workloads." Device tiers are illustrative (M2 Max 32 GB / Llama-3-13B; iPhone 15 / 7B). Capacity-triggered fallback uses hysteresis (fall back below 70%, return above 80%). No provisioning. — [arXiv HTML](https://arxiv.org/html/2512.00595v1). Ratings: all 0–1 (P2b 1: resource-reactive fallback; mentions local OOM in ablation).
- **HybridFlow: Resource-Adaptive Subtask Routing for Efficient Edge-Cloud LLM Inference** (2512.22137). Jiangwen Dong, Jiayu Li, Tianhang Zheng, Wanyu Lin. **ICML 2026 (PMLR 306)**. **Hybrid**. The edge is fixed: Llama3.2-3B on one RTX 3090; the cloud is GPT-4.1. Despite "resource-adaptive" in the title, edge resources and quantization are not varied. It motivates with "fluctuating network latency, dynamic API budgets, and varying edge load" but does not test them. One swapped model pair (Qwen2.5-7B / DeepSeek-V3) on GPQA keeps HybridFlow first (53% vs. DoT 49%, HybridLLM 47%). Average accuracy 55.34% vs. cloud-only CoT 58.99%; average API cost 0.0088 vs. 0.0269. Routing is predictive (MLP utility estimate plus budget-adaptive threshold); silent local failure is not addressed. — [arXiv HTML](https://arxiv.org/html/2512.22137). Ratings: C1 0, C2 0, C3 1, C4 0, P2a 0, P2b 1.
- **ConfigSpec: Profiling-Based Configuration Selection for Distributed Edge–Cloud Speculative LLM Serving** (2604.09722). Xiangchen Li (Virginia Tech) et al. **TDIS '26 workshop (Edinburgh, Apr 27–30 2026), DOI 10.1145/3802513.3803483**. **Hybrid** (edge draft + cloud verifier). **The only paper in this list that varies device-side configuration in a hybrid system**: 3 edge devices (RPi 4B, RPi 5, Jetson AGX Orin) × 8 draft models (Llama-3.2-1B..3.1-8B; Qwen3-0.6B..8B) × quantization Q4_K_M–Q8_0 × speculative length K=2–10 × 2 cloud targets (Llama-3.1-70B, Qwen3-32B). The best config flips with objective and device: goodput favors the smallest Q4 draft at device-dependent K* (K=2 on RPi 4B, about 6 on RPi 5, 8–10 on Jetson); cost favors the largest (8B) draft at K=2 on every device; energy favors the smallest at K=2. Quotes: "goodput is maximised by the smallest, fastest draft model at device-dependent speculative lengths"; "no single fixed configuration can simultaneously optimise throughput, cost, and energy". Cloud cost efficiency spans about 19.4% (Llama) and 24.9% (Qwen) between largest and smallest drafts. On RPi 5, moving from the cost-optimal to the goodput-optimal draft gives 2.9× goodput and 7.8× better energy at a 46% cost-efficiency loss. **Quality is not measured** (speculative decoding is lossless; acceptance rate is the proxy). There is no routing, provisioning, or escalation. The paper has internal numeric inconsistencies (e.g., Jetson goodput 6.5 vs. 7.65 tok/s). — [arXiv HTML](https://arxiv.org/html/2604.09722). Ratings: **C1 2** (device config moves cloud verification cost, but there are no escalations; cost moves via acceptance rate), C2 1 (no routing policy to compare against), C3 1 (config rank reversal across devices and objectives, not router rank reversal), C4 1, P2a 0, P2b 0. **It also pre-empts the SEAM/ERN hypothesis "no configuration wins on all objectives" in the hybrid speculative-decoding setting (rating 2–3 for that sub-hypothesis).**
- **HERA: Hybrid Edge-cloud Resource Allocation for Cost-Efficient AI Agents** (2504.00434). Shiyi Liu, Haiying Shen, Shuai Che, Mahdi Ghandi, Mingqin Li. Submitted 1 Apr 2025, cs.LG, no venue listed. **Hybrid** agent with subtask-level SLM/LLM selection (the system is called AIMS in the abstract). The edge is fixed: one RTX 4090, llama.cpp. Model pairs are Mistral-7B/GPT-4 and Llama-3.1-8B/Claude 3.5. Quantization, memory, and hardware are not varied. Across model pairs, SLM share changes from −4.65% to +8.20% and cost from −29.31% to +20.45%; cost-effectiveness "depends on the specific task and model pair combination." LLM use is attributed to subtask position and difficulty. It cuts cost 19–30% vs. all-LLM; 45.67% of subtasks go to the SLM; accuracy is up to 9.1% higher than HybridLLM. Routing is predictive with 35–46% incorrect assignments vs. Oracle (not framed as silent failure). — [arXiv abs](https://arxiv.org/abs/2504.00434), [PDF](https://arxiv.org/pdf/2504.00434v1). Ratings: C1 1, C2 0, C3 1, C4 0, P2a 0, P2b 1.
- **When Cloud Agents Meet Device Agents: Lessons from Hybrid Multi-Agent Systems** (2605.30102). Corrado Rainone, Davide Belli, Bence Major, Arash Behboodi. Submitted 28 May 2026; **AIWILD workshop at ICML 2026**. **Hybrid**, but **not deployed on real devices**: Qwen3 4B/8B/14B/32B executors run on an A100 with vLLM; edge energy is modeled (App. A.1); the cloud supervisor is GPT-4o. Varied: executor size, verification interval, architecture (PEVR vs. EVA), and role placement. Hardware, quantization (except fp8 for 32B), and KV precision are fixed. Lessons: "no 'free lunch' MAS architecture" (the architecture ranking flips across benchmarks, not device configs); more frontier compute does not reliably help; "Executor size correlates positively with performance in all cases"; energy is cut up to 3× via executor context resets. Monolithic edge agents hit **out-of-context errors in about 20% of runs at 80 turns**. Verifier false negatives ("the Supervisor fails to intervene despite eventual failure") are 5.3–14.8%. Cloud cost is controlled by "a single verification parameter". Role swap: GPT-4o executor + Qwen-32B supervisor gives the same 0.25 success as GPT-4o alone at $0.67 vs. $0.37. — [arXiv abs](https://arxiv.org/abs/2605.30102), [HTML v1](https://arxiv.org/html/2605.30102v1). Ratings: C1 1, C2 1, C3 1 (task-dependent reversal, not device-dependent), C4 0, P2a 0, P2b 1–2 (closest to measuring undetected failures, but these are supervisor misses, not local silent context drop).

### Inferences
- The brief's grouping "known HYBRID papers" overstates the hybrid count. 12 of 20 are not device+cloud hybrids, and 2508.06753 in particular is a local-only Intel quantization-kernel paper, not an AI-PC hybrid paper.
- No paper in this list runs a hybrid system on a real consumer AI PC (Intel unified memory) or uses OpenVINO GenAI in a hybrid loop. The hybrid papers use datacenter GPUs as the "device" (PAAC A100, 2605.30102 A100, HERA RTX 4090, HybridFlow RTX 3090) or embedded boards (ConfigSpec, TMO).

### Gaps
- HW-Router full text was not readable (the PDF returned no text), so its exact numbers and per-hardware ranking results are unverified.
- 2509.24050 full text was blocked, so its offload ratios and any discussion of confident-wrong local answers are unverified.
- 2607.18253 results section was truncated, so whether router rankings flip with load is unverified.
- MALBO's model pool section was truncated; the absence of local models is only likely, not confirmed.

## Which papers vary device configuration within a hybrid system, and how many configs/knobs?

### Takeaway
Only ConfigSpec varies device-side configuration knobs (device × draft model × quantization × speculative length × cloud target, 5 knobs) inside a hybrid loop. TMO varies only the device platform (8 platforms, same model), and 2605.30102 varies only executor model size (4 tiers). None varies placement (CPU/GPU/NPU), KV precision, session residency, or context window in a hybrid system.

### Cited Findings
- ConfigSpec has 3 devices × 8 drafts × Q4_K_M–Q8_0 × K 2–10 × 2 targets, enumerating all feasible triples per target-device pair (no total count stated). — [ConfigSpec](https://arxiv.org/html/2604.09722)
- TMO uses 8 hardware platforms with a fixed on-device model and no quantization/KV/memory sweep. — [TMO](https://arxiv.org/html/2502.11007)
- 2605.30102 varies executor size (Qwen3 4B/8B/14B/32B) and verification interval, with hardware not varied and energy modeled. — [When Cloud Agents Meet Device Agents](https://arxiv.org/html/2605.30102v1)
- HERA (RTX 4090), HybridFlow (RTX 3090), and PAAC (A100) each use one fixed edge hardware/model; only model pairs are swapped. — [HERA](https://arxiv.org/pdf/2504.00434v1); [HybridFlow](https://arxiv.org/html/2512.22137); [PAAC](https://arxiv.org/pdf/2605.08646)
- The local-only papers do vary the SEAM knobs, but without cloud: Hydra varies 3 SoCs × 13 models × 5 formats; Agent.xpu does NPU/iGPU placement on a Core Ultra 125H; HeRo does CPU/GPU/NPU placement; QEIL v2 does layer placement across CPU/NPU/iGPU/dGPU. — [Hydra](https://arxiv.org/html/2608.25053); [Agent.xpu](https://arxiv.org/pdf/2506.24045); [HeRo](https://arxiv.org/pdf/2603.01661); [QEIL v2](https://arxiv.org/html/2602.06057)

### Inferences
- The SEAM gap holds for this list. The knobs SEAM varies are characterized only in local-only work, and the hybrid work holds them fixed. The 6-axis SEAM sweep (placement, residency, KV precision, weight precision, context window, model tier) inside a hybrid loop has no match here.
- ConfigSpec is the paper SEAM must cite and differentiate from. Its setting is speculative decoding: quality is fixed by construction, there are no escalations or routing, and it runs on Raspberry Pi/Jetson. SEAM's configurations change quality and feasibility, and therefore escalation.

### Gaps
- None for this question within the 20 papers.

## Do any attribute cloud spend or escalations to device configuration?

### Takeaway
No paper attributes escalations to device configuration (SEAM C1 is unclaimed). ConfigSpec shows device-side draft configuration moves cloud verification cost (about 19–25% cost-efficiency spread), which is the nearest analog. TMO explicitly reports that device platform variation does not significantly affect its hybrid system, which reviewers could raise as counter-evidence.

### Cited Findings
- ConfigSpec: cost-efficiency spans about 19.4% (Llama) and 24.9% (Qwen) between largest and smallest drafts, driven by acceptance rate; on RPi 5 the goodput-optimal draft costs 46% in cost efficiency vs. the cost-optimal one. — [ConfigSpec](https://arxiv.org/html/2604.09722)
- TMO: "Performance variations across different devices do not significantly impact the operation of the TMO system"; its cloud cost equation does not depend on the device. — [TMO](https://arxiv.org/html/2502.11007)
- HERA attributes LLM use to subtask position and difficulty ("necessitates LLM usage for all systems" for late-stage complexity); across model pairs cost changes from −29.31% to +20.45%, attributed to "the specific task and model pair combination." — [HERA](https://arxiv.org/pdf/2504.00434v1)
- 2605.30102: cloud cost is controlled by "a single verification parameter"; device-side choices affect it only indirectly through supervisor calls and restarts. — [When Cloud Agents Meet Device Agents](https://arxiv.org/html/2605.30102v1)
- 2607.18253 frames routing to larger, pricier models as driven by query difficulty. — [2607.18253](https://arxiv.org/html/2607.18253)
- RouterWise attributes quality and latency variation to "how compute and memory are distributed across models" (datacenter; cost not measured). — [RouterWise](https://arxiv.org/pdf/2604.10907)

### Inferences
- TMO's null result does not contradict SEAM. TMO varies only compute speed and price of a fixed model on boards, with quality gaps simulated. Hardware speed changes only a normalized latency/cost term in the reward, so it cannot move escalations through feasibility or quality. SEAM's knobs (KV precision, context window, residency, model tier) change whether the local step succeeds. Pre-empting this distinction in the paper ("platform speed ≠ configuration") is advisable.
- The difficulty-centric attribution in HERA and 2607.18253 is the default framing that SEAM C1 challenges.

### Gaps
- TMO's per-device offload-rate figures are only in Fig. 6 (not in text), so it is unknown whether offload rate shifted while the reward did not.

## Do any show router rankings changing with device/configuration?

### Takeaway
No paper demonstrates routing-policy rank reversal across device configurations (SEAM C3 is unclaimed). RouterWise asserts the analogous principle for datacenter deployments without directly testing per-prompt flips. ConfigSpec shows configuration (not router) rank reversal across devices. 2605.30102 shows architecture rank reversal across tasks. HybridFlow and TMO report their method stays best across the alternatives they tried.

### Cited Findings
- RouterWise: "the optimal model for a prompt depends not only on the prompt itself, but on the deployment environment"; "achievable routing quality varies by up to 87% across deployment configurations on the same GPU cluster." — [RouterWise](https://arxiv.org/pdf/2604.10907)
- ConfigSpec: goodput-optimal K* is device-dependent (K=2 RPi 4B, about 6 RPi 5, 8–10 Jetson), and "no single fixed configuration can simultaneously optimise throughput, cost, and energy." — [ConfigSpec](https://arxiv.org/html/2604.09722)
- 2605.30102: PEVR wins on AppWorld while EVA wins on HotpotQA/FanOutQA ("no 'free lunch' MAS architecture"); this is not tested across executor size. — [When Cloud Agents Meet Device Agents](https://arxiv.org/html/2605.30102v1)
- HybridFlow: on the swapped Qwen2.5-7B/DeepSeek-V3 pair HybridFlow stays first (53% vs. 49% vs. 47%). — [HybridFlow](https://arxiv.org/html/2512.22137)
- TMO claims best across all 8 device platforms; per-baseline rankings per device are not reported. — [TMO](https://arxiv.org/html/2502.11007)
- HW-Router: existing routers estimate cost from "static model properties" and ignore hardware state (datacenter). — [HW-Router](https://arxiv.org/abs/2608.14575)
- AgentServeSim: a scheduler's JCT advantage shrinks from about 3.3× to about 1.8× as prefix reuse drops from η=0.9 to 0.1 (workload, not hardware). — [AgentServeSim](https://arxiv.org/html/2606.09613)

### Inferences
- The closest conceptual precedent for C3 is RouterWise (datacenter, untested). SEAM can position C3 as the first empirical demonstration on the device side of a hybrid.
- The evidence from HybridFlow and TMO that their method stays best is weak (one alternative pair; ranks not shown). It does not contradict rank reversal among simpler policies such as threshold, cascade, and always-local.

### Gaps
- HW-Router results on ranking stability vs. CARROT/IRT under different hardware states were not readable.

## Do any jointly optimize provisioning (hardware/memory) and routing?

### Takeaway
Only RouterWise jointly optimizes deployment configuration and routing, in a fixed A100 cluster (outer-loop setup search plus inner-loop SLO-constrained routing). No hybrid paper treats device memory/hardware provisioning (BOM) and routing as one decision, so SEAM paper 2's provisioning claim is open in the hybrid setting. RouterWise must be cited as the datacenter precedent.

### Cited Findings
- RouterWise searches feasible deployment setups (TP, GPU thread %, co-location) in an outer loop and solves score-maximizing routing under a latency SLO in an inner loop (Eq. 5). It retains about 700 setups (3 models) and about 17,000 (4 models). — [RouterWise](https://arxiv.org/pdf/2604.10907)
- HERA's title says "Resource Allocation", but it allocates subtasks between SLM and LLM, not hardware. — [HERA](https://arxiv.org/abs/2504.00434)
- IslandRun covers per-request routing only; provisioning is not modeled. — [IslandRun](https://arxiv.org/html/2512.00595v1)
- AgentServeSim says simulation can explore configurations "beyond available clusters" but gives no provisioning analysis. — [AgentServeSim](https://arxiv.org/html/2606.09613)
- 2605.30102 notes typical DRAM is 4–8 GB on mobile and 8–32 GB on laptops (context for provisioning) but does not optimize it. — [When Cloud Agents Meet Device Agents](https://arxiv.org/html/2605.30102v1)

### Inferences
- The paper-2 contribution should be framed as "joint provisioning and routing for hybrid device-cloud with a cloud price and a device BOM," not as "joint resource allocation and routing" in general, which RouterWise already claims for datacenters.

### Gaps
- None further within this list.

## Do any address silent/unobservable local failure in routing?

### Takeaway
No paper addresses silent local failure (confident wrong answers from context drop) as a routing problem, or proposes routing from a measured feasibility/failure-regime boundary. Adjacent material: 2605.30102 measures supervisor false negatives (5.3–14.8%) and 20% out-of-context errors in monolithic edge agents; PAAC notes reactive termination is unreliable; several routers are predictive but predict quality from query features, not from a device-feasibility model.

### Cited Findings
- 2605.30102: verifier false negatives, where "the Supervisor fails to intervene despite eventual failure", are 5.3% (AppWorld plan-based), 6.0% (AppWorld query-based), 8.4% (FanOutQA plan-based), and 14.8% (FanOutQA query-based). Monolithic edge agents hit out-of-context errors in about 20% of runs at 80 turns. — [When Cloud Agents Meet Device Agents](https://arxiv.org/html/2605.30102v1)
- PAAC: "Unilateral termination is therefore unreliable in either direction"; the on-device model "fails to adhere to the prescribed structured output format." — [PAAC](https://arxiv.org/pdf/2605.08646)
- HERA: predictive estimators make 35–46% incorrect assignments vs. Oracle, not framed as silent failures. — [HERA](https://arxiv.org/pdf/2504.00434v1)
- HybridFlow: predictive MLP utility plus budget-adaptive threshold; it does not address local crashes or silent degradation. — [HybridFlow](https://arxiv.org/html/2512.22137)
- IslandRun: capacity-reactive fallback (below 70% / above 80% hysteresis); it notes local OOM when TIDE is removed, and is conceptual only. — [IslandRun](https://arxiv.org/html/2512.00595v1)
- 2509.24050: the local model learns when to offload via RL, guarding against "policy collapse" into always-local or always-cloud. Its handling of confidently wrong local answers is unverified. — [2509.24050](https://arxiv.org/abs/2509.24050)
- HW-Router and 2607.18253 are predictive on latency (hardware state, TTFT estimator under 5% MAPE), not on failure. — [HW-Router](https://arxiv.org/abs/2608.14575); [2607.18253](https://arxiv.org/html/2607.18253)

### Inferences
- The 20% out-of-context rate in 2605.30102 corroborates the SEAM finding that context limits cause local failure in long multi-turn agents. Its context-reset mechanism (3× energy cut) is a retention-like knob, relevant to the ISPASS paper's retention axis, and should be cited.
- The P2b claim (predictive routing from a measured feasibility boundary because some local failures are silent) is unclaimed in this list.

### Gaps
- Whether 2509.24050's RL offload policy is evaluated on confident-wrong local answers could not be checked (full text blocked).

## Numbers that corroborate or contradict SEAM measurements

### Takeaway
There is no direct numeric contradiction: none of these papers measures Qwen3-4B on Intel AI PCs with BFCL in a hybrid loop. The main framing-level tensions are TMO's device-insensitivity result and Hydra's small int4 quality cost. The main corroboration is ConfigSpec's "no single configuration wins".

### Cited Findings
- Hydra: Q4_K_M vs. F16 mean ΔPPL is +0.36, worst-case accuracy drop about 2.4 points; the authors describe the quality cost as small. If SEAM finds large int4 vs. int8 BFCL multi-turn differences, the explanation is the gap between perplexity/short-benchmark evaluation and agentic multi-turn evaluation. — [Hydra](https://arxiv.org/html/2608.25053)
- Hydra: input 1k to 5k raises TTFT 5.0–5.7× on Jetson. This is consistent with SEAM's latency binding at about 9,750 tokens under a 10 s TTFT SLO (different hardware; a qualitative match only). — [Hydra](https://arxiv.org/html/2608.25053)
- 2508.06753: Lunar Lake 258V CPU 88 tok/s (2B, int2); Arc 140V iGPU 5.34 tok/J. These are useful Intel client reference points for the precision knob. — [2508.06753](https://arxiv.org/html/2508.06753)
- Agent.xpu: Core Ultra 5 125H with W8A16 on NPU+iGPU cuts reactive latency 91–97% vs. OpenVINO iGPU. This corroborates that placement is a large lever on Intel unified-memory SoCs. — [Agent.xpu](https://arxiv.org/pdf/2506.24045)
- ConfigSpec: "no single fixed configuration can simultaneously optimise throughput, cost, and energy". This corroborates the SEAM/ERN hypothesis that no configuration wins on all objectives, in a hybrid setting. — [ConfigSpec](https://arxiv.org/html/2604.09722)
- 2603.23640: an iPhone loses 41.5% throughput under sustained load [CORRECTED 2026-10-16: 37.3% Warm and 44.1% sustained Hot, iPhone 16 Pro; not 41.5%, not Intel]. This supports SEAM's 60-second thermal warm-up guardrail. — [2603.23640](https://arxiv.org/html/2603.23640)
- RouterWise: an 87% quality spread across deployment configs (datacenter) is the same order as SEAM's placement result of 0 to full SLO compliance. — [RouterWise](https://arxiv.org/pdf/2604.10907)

### Inferences
- Possibly relevant new papers surfaced incidentally in search (NOT in this sweep's list, not read; candidates for sweep 2): "Empowering Edge Agents: A Systematic Analysis of Edge-Cloud Collaboration in LLM Agent Execution" (arXiv 2610.17816, Oct 2026) and "Should SLMs Be in the Driver's Seat? A Study of Local Models as Interpreters in Cloud-Written Agent Programs" (2610.14209). Both are hybrid and recent, and fetches were rate-limited (HTTP 429). Also seen: "EdgeAgent: Orchestrating On-Device LLM inference for End-User Multi-Agent Systems on CPU-GPU Unified Memory Architectures" (2610.03394), "JOVE: Joint Execution and Verification for Resource-Aware LLM Task Graphs" (2610.03296), and "INAR-VL: Input-Aware Routing for Edge–Cloud Vision–Language Inference" (2605.18853). Search-result listing: [2610.17816](https://arxiv.org/html/2610.17816), [2610.14209](https://arxiv.org/html/2610.14209), [2610.03394](https://arxiv.org/html/2610.03394v1).

### Gaps
- 2610.17816 and 2610.14209 could not be read (rate-limited), and they may be the closest competitors overall. They need checking in a follow-up sweep.

## Summary closeness matrix (0–3)

| Paper | Type | C1 | C2 | C3 | C4 | P2a | P2b |
|---|---|---|---|---|---|---|---|
| HW-Router 2608.14575 | Datacenter | 0 | 1 | 1 | 0 | 0 | 1 |
| RouterWise 2604.10907 | Datacenter | 0 | 2 | 2 | 1 | 2 | 0 |
| 2607.18253 latency-aware routing | Datacenter | 0 | 0 | 1 | 0 | 0 | 0 |
| TMO 2502.11007 | Hybrid | 0 | 1 (counter) | 1 | 0 | 0 | 0 |
| 2509.24050 local routing + post-training | Hybrid | 0 | 0 | 0 | 0 | 0 | 1 |
| Hydra 2608.25053 | Local-only | 0 | 0 | 0 | 1 | 0 | 0 |
| Agent-X 2605.10380 | Local-only | 0 | 0 | 0 | 0 | 0 | 0 |
| 2603.23640 edge sustained load | Local-only | 0 | 0 | 0 | 0 | 0 | 0 |
| 2508.06753 ultra-low-bit (Intel) | Local-only (not hybrid) | 0 | 0 | 0 | 1 | 0 | 0 |
| PAAC 2605.08646 | Hybrid | 0 | 0 | 0 | 0 | 0 | 1 |
| IslandRun 2512.00595 | Hybrid (conceptual) | 0 | 0 | 0 | 0 | 0 | 1 |
| HybridFlow 2512.22137 | Hybrid | 0 | 0 | 1 | 0 | 0 | 1 |
| ConfigSpec 2604.09722 | Hybrid | 2 | 1 | 1 | 1 | 0 | 0 |
| HERA 2504.00434 | Hybrid | 1 | 0 | 1 | 0 | 0 | 1 |
| Agent.xpu 2506.24045 | Local-only | 0 | 0 | 0 | 0 | 0 | 0 |
| HeRo 2603.01661 | Local-only | 0 | 0 | 0 | 0 | 0 | 0 |
| QEIL v2 2602.06057 | Local-only | 0 | 0 | 0 | 1 | 0 | 0 |
| MALBO 2511.11788 | Cloud-API only | 0 | 0 | 0 | 0 | 0 | 0 |
| AgentServeSim 2606.09613 | Datacenter sim | 0 | 1 | 1 | 0 | 1 | 0 |
| When Cloud Agents Meet Device Agents 2605.30102 | Hybrid (simulated device) | 1 | 1 | 1 | 0 | 0 | 1–2 |

No cell reaches 3: none of the 20 papers pre-empts any SEAM sub-claim. The highest-risk overlaps are ConfigSpec (hybrid configuration DSE, "no single configuration wins") and RouterWise (joint deployment and routing, "optimal routing depends on deployment environment", datacenter).
