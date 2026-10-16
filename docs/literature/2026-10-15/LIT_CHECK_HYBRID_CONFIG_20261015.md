# Hybrid papers leave SEAM's configuration lever unclaimed

As of 15 October 2026, none of the 27 hybrid device-cloud papers examined pre-empts SEAM's central claim that hardware configuration is a hidden variable and the largest lever in hybrid execution. Every one of them holds placement, KV precision, weight precision, residency and context retention fixed. None runs on an Intel AI PC or OpenVINO, and none splits cloud spend into configuration-caused versus difficulty-caused escalation. The real risk is narrower and very recent. EC2-Bench (13 Oct), STEPGATE (Oct) and CARGO (Jul) already show that the winning routing or collaboration strategy flips, and its advantage collapses, as the **local model gets stronger**. That pre-empts the *model-size* slice of claims C2 and C3, so SEAM must claim reversal **with the model held fixed**. Three other neighbours each own one piece already. Microsoft's cloud-only "Whose Turn Is It?" and vLLM's SAAR have priced switch cost in closed form. RouterWise has claimed joint deployment and routing for datacenters. ConfigSpec has claimed "no single configuration wins" for hybrid speculative decoding. The counter-evidence (TMO's device-insensitivity result and EdgeWise's A100-vs-DGX-Spark parity) comes from devices that never hit a memory limit, so it does not threaten SEAM. On measurements, Intel's own tables match our iGPU decode and TTFT within about 10%. But three "defaults" in our write-up are wrong for our stack, two runtime behaviours (llama.cpp and Ollama) need restating, and the per-allocation explanation for the B390 crash does not fit Xe3 hardware.

## Twenty-seven hybrid papers, zero sweeps of SEAM's knobs

Seven literature sweeps checked about 60 papers and reports. Twenty-seven are true hybrid device/edge-cloud systems. The rest are datacenter routers, cloud-to-cloud routers, or local-only studies, and they are kept apart below. The hybrid papers mostly vary one thing on the device side: the **identity or size of the local model**. A few vary something else: edge device type (TMO, Edge-First, Splitwise), split point and bit-width (split computing), draft model and quantization inside speculative decoding (ConfigSpec), or runtime thermal state (HybridInfer). **None sweeps CPU/GPU/NPU placement, KV-cache precision, session residency or prefix caching inside a hybrid loop** ([known hybrids](https://arxiv.org/html/2604.09722); [October sweep](https://arxiv.org/html/2610.17816)). The hybrid papers also rarely use a real consumer device as the "device". PAAC and Rainone et al. run the device model on an A100 ([PAAC](https://arxiv.org/pdf/2605.08646); [Rainone et al.](https://arxiv.org/html/2605.30102v1)). HybridFlow uses an RTX 3090 ([HybridFlow](https://arxiv.org/html/2512.22137)). The SLM-interpreter paper uses a V100 ([2610.14209](https://arxiv.org/html/2610.14209)). EC2-Bench has no device at all and estimates edge compute as 2·N·T FLOPs ([EC2-Bench](https://arxiv.org/html/2610.17816)). Industry is no different. Perplexity and Intel's Computex 2026 hybrid orchestrator routes by data sensitivity and capability, and calls itself "chip agnostic", with no statement that memory or accelerator changes what runs locally ([Pulse 2.0](https://pulse2.com/perplexity-announces-first-hybrid-local-server-inference-orchestrator-for-personal-computer/)).

### Closeness matrix: hybrid papers versus SEAM claims

Scale: 0 = unrelated; 1 = adjacent (same vocabulary, untested, or different setting); 2 = makes a similar claim in a different setting or tests it weakly; 3 = pre-empts.

Column key:

| Code | Claim |
|---|---|
| C1 | Configuration-caused cloud spend / escalation |
| C2 | Configuration moves outcomes more than routing policy |
| C3 | Router rank reversal across device configurations |
| C4 | Configuration substitutes for a hardware or memory purchase |
| JPR | Joint provisioning and routing (paper 2) |
| PFR | Predictive, feasibility-aware routing under silent local failure (paper 2) |
| SWC | Priced switch cost (paper 2) |
| ISPASS | OL = operating limit, FR = failure regimes, RET = retention. This column was assigned during synthesis; the sweeps did not score it. |

| Hybrid paper | Device-side variation | C1 | C2 | C3 | C4 | JPR | PFR | SWC | ISPASS |
|---|---|---|---|---|---|---|---|---|---|
| [EC2-Bench 2610.17816](https://arxiv.org/html/2610.17816) | Edge model size (simulated, FLOPs) | 1 | 1–2 | **2** | 0 | 1 | 1 | 1 | 0 |
| [STEPGATE 2610.07816](https://arxiv.org/html/2610.07816) | Local model size; handoff context | 0 | 1 | **2** | 0 | 0 | 1 | 1 | RET 1 |
| [CARGO 2607.20481](https://arxiv.org/html/2607.20481v1) | Local model family/size (2×H100) | 0 | 1 | **2** | 0 | 0 | 1 | 0 | 0 |
| [ConfigSpec 2604.09722](https://arxiv.org/html/2604.09722) | Device × draft × quantization × spec length | **2** | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| [HybridInfer 2609.30270](https://arxiv.org/html/2609.30270) | Thermal state, one phone | **2** | 1 | 0 | 0 | 0 | 1 | 0 | FR 1 |
| [Edge-First 2505.16508](https://arxiv.org/pdf/2505.16508) | Device type, capacity tiers | **2** | 1 | 1 | 1 | 0 | 0 | 0 | OL 1 |
| [ECO-LLM 2507.09003](https://arxiv.org/html/2507.09003v1) | Pipeline config incl. quantization levels; one A6000 | 0 | **2** | 1 | 0 | 0 | 0 | 0 | RET 1 |
| [Rainone et al. 2605.30102](https://arxiv.org/html/2605.30102v1) | Executor size (A100, modelled energy) | 1 | 1 | 1 | 0 | 0 | 1–2 | 0 | FR 1, RET 1 |
| [HERA 2504.00434](https://arxiv.org/pdf/2504.00434v1) | Model pair; RTX 4090 | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 0 |
| [On-device agents 2511.03728](https://arxiv.org/html/2511.03728v1) | Context management; Galaxy S25 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | OL 1, RET 2 |
| [Splitwise 2512.23310](https://arxiv.org/html/2512.23310) | Split point, device type | 1 | 0 | 0 | 1 | 0 | 0 | 0 | OL 1 |
| [Adaptive split 2511.04002](https://arxiv.org/abs/2511.04002) (abstract) | Split, bits, sequence length, memory budget | 1 | 0 | 0 | 1 | 0 | 0 | 0 | OL 1 |
| [SLM interpreter 2610.14209](https://arxiv.org/html/2610.14209) | SLM size; V100 | 0 | 0 | 0 | 1 | 0 | 1 | 1 | RET 1 |
| [EdgeWise 2610.17560](https://arxiv.org/html/2610.17560) | Handoff context; A100 vs DGX Spark | 0 | 0 | 0 | 0 | 0 | 1 | 1 | RET 1 |
| [Minions 2502.15964](https://arxiv.org/html/2502.15964v1) | Local model; protocol | 0 | 0 | 0 | 0 | 0 | 1 | 1 | OL 1 |
| [Hera 2605.24598](https://arxiv.org/html/2605.24598) | None (step-level router) | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| [HybridFlow 2512.22137](https://arxiv.org/html/2512.22137) | One model-pair swap; RTX 3090 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 |
| [TMO 2502.11007](https://arxiv.org/html/2502.11007) | 8 platforms, fixed model | 0 | 1 (counter) | 1 | 0 | 0 | 0 | 0 | 0 |
| [RouterXBench 2602.11877](https://arxiv.org/html/2602.11877v1) | Model size (side analysis) | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| [CR2 2605.12001](https://arxiv.org/html/2605.12001) (device-to-edge) | Profiled edge pool | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| [Carbon-aware FC 2609.13559](https://arxiv.org/abs/2609.13559) (abstract) | Hardware tier as routing target | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| [Fang et al. 2509.24050](https://arxiv.org/html/2509.24050v4) | None | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| [PAAC 2605.08646](https://arxiv.org/pdf/2605.08646) | None (Qwen3-4B on A100) | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| [IslandRun 2512.00595](https://arxiv.org/html/2512.00595v1) (no experiments) | None | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| [Speculation at a Distance 2606.25091](https://arxiv.org/abs/2606.25091) (abstract) | RTT, server hosting | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| [QSV 2507.00605](https://arxiv.org/abs/2507.00605) (abstract) | Draft length, communication quantization | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| [SPADE 2608.13076](https://arxiv.org/html/2608.13076) | Single edge configuration | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

No hybrid cell reaches 3. The non-hybrid neighbours below matter as much, because reviewers will cite them anyway. Two of them reach 3 on switch cost in a cloud-only setting.

| Non-hybrid neighbour | Setting | Highest overlap |
|---|---|---|
| [Whose Turn Is It? 2610.19292](https://arxiv.org/html/2610.19292) | Cloud-to-cloud, Microsoft | SWC 3, C2 2, JPR 2 |
| [SAAR (vLLM blog)](https://vllm.ai/blog/2026-06-02-session-aware-agentic-routing) | Cloud multi-model serving | SWC 3 |
| [RouterWise 2604.10907](https://arxiv.org/pdf/2604.10907) | Datacenter A100 cluster | JPR 2, C2 2, C3 2 |
| [HW-Router 2608.14575](https://arxiv.org/html/2608.14575) | Datacenter H100 | C2 1, C3 1, PFR 1 |
| [AgentServeSim 2606.09613](https://arxiv.org/html/2606.09613) | Datacenter simulator | Residency, JPR 1 |
| [Loud/Quiet failures 2610.10062](https://arxiv.org/html/2610.10062) | Agent reliability, BFCL multi-turn | PFR mechanism 1–2 |
| [Hybrid LLM 2404.14618](https://arxiv.org/abs/2404.14618v1) | Model routing, ICLR 2024 | PFR 1 (pre-generation difficulty routing) |
| [Routing survey 2603.04445](https://arxiv.org/pdf/2603.04445) | TMLR survey | Contradicts "routers are reactive" |

A naming hazard needs care. **HERA** (2504.00434, Liu et al.) does subtask-level SLM/LLM allocation. **Hera** (2605.24598, Zhang et al.) does step-level device-cloud agent routing. They are different papers and must be cited separately.

## Five overlaps carry real reviewer risk

### Model-size rank reversal is already published, so SEAM must fix the model

The most dangerous overlap arrived this week. **EC2-Bench** (submitted 13 Oct 2026) compares four collaboration strategies across edge models from Qwen3.5-2B to Qwen3.7-Plus. It finds that the spread between best and worst strategy **collapses from 25.22 to 3.67 points** as edge capability rises. Externally routed strategies win with weak edges, and advisory strategies win with strong ones. At 2B, Per-step Routing reaches 39.97 completion against 15.86 for Delegation ([EC2-Bench](https://arxiv.org/html/2610.17816)). Under the same entropy router calibrated to about 15% cloud participation, cloud spend falls from **$12.80 at 2B to $5.29 at 27B** ([EC2-Bench](https://arxiv.org/html/2610.17816)). That is the model-size version of C1, though the paper never frames it as configuration-caused escalation.

**STEPGATE** runs on a BFCL-derived single-step and multi-turn set. It finds that at a 3B local model, learned routing gives 90.4%, against **90.8% for random escalation** and 88.5% for local-only, so random beats learned ([STEPGATE](https://arxiv.org/html/2610.07816)). **CARGO** reports that baseline router orderings are "task-dependent and less consistent across benchmark types and model families", and that the CoT-steps vs self-confidence ordering flips between Qwen2.5-3B and Phi-3 ([CARGO](https://arxiv.org/html/2607.20481v1)).

Together these three papers own the claim that *which* local model you deploy reorders routers and dwarfs routing gains. SEAM's distinct ground is **reversal and dominance driven by hardware configuration with Qwen3-4B held fixed**: placement, KV precision, weight precision, residency and retention. EC2-Bench's fixed 128K window with automatic compression also means the silent-truncation regime SEAM measures never arises there ([EC2-Bench](https://arxiv.org/html/2610.17816)). All three papers use a random-escalation-at-matched-rate baseline, or show it matters. SEAM's rank tables need one too.

### Switch cost is priced; the device-side asymmetry is not

Microsoft's "Whose Turn Is It?" prices switching between cloud models in closed form from prompt-cache prices. The breakeven number of calls is independent of context length (k\* = 1.25 for its downward pairs). An **upward switch costs about $4.9 per million context tokens, roughly 10× a downward one, and never pays back on input**. The paper concludes that switching should be "sticky" and context-length-aware ([Whose Turn](https://arxiv.org/html/2610.19292)). vLLM's SAAR already "prices a cached-input checkout delta". In 21,600 turns it cut switches from 9,709 to 2,011, with a 78.71% estimated cost reduction ([SAAR](https://vllm.ai/blog/2026-06-02-session-aware-agentic-routing)). **SEAM cannot claim to be first to price switch cost.**

What remains open is the hybrid asymmetry. Device-to-cloud escalation is exactly the "upward, never pays back" case, because the whole local context is re-sent as uncached cloud input. Cloud-to-device fallback costs local re-prefill time and energy, and that cost depends on placement, KV precision and residency. None of the hybrid papers models handoff cost. Hera's objective "does not penalize handoffs", and Fang et al., HybridInfer and Rainone et al. omit it too ([Hera](https://arxiv.org/html/2605.24598); [Fang et al.](https://arxiv.org/html/2509.24050v4); [HybridInfer](https://arxiv.org/html/2609.30270)). Whose Turn also notes that its baselines assume a warm cache. Cache expiry or a cold restart raises their cost, which mirrors SEAM's residency knob ([Whose Turn](https://arxiv.org/html/2610.19292)).

### RouterWise owns "joint deployment and routing" for datacenters

RouterWise searches deployment setups in an outer loop: tensor parallelism, GPU thread share and co-location, with about 700 setups retained for 3 models. It solves SLO-constrained routing in an inner loop. It reports that "achievable routing quality varies by up to 87% across deployment configurations on the same GPU cluster", and that the optimal model for a prompt depends on the deployment environment ([RouterWise](https://arxiv.org/pdf/2604.10907)). It does not measure cost, does not vary quantization or KV, and asserts per-prompt rank flips without testing them. Paper 2 must therefore claim **joint device provisioning (memory/BOM) and routing for hybrid device-cloud, priced against a cloud API**, not "joint resource allocation and routing". Whose Turn adds a cloud-only version of the same point. In two of its three pairs, simply picking the cheaper configuration (Luna alone, or Opus at low effort) **Pareto-dominates every routed policy**. The router itself ignores the pair ([Whose Turn](https://arxiv.org/html/2610.19292)).

### ConfigSpec and ECO-LLM already say "configuration matters" in hybrid settings

ConfigSpec is the only hybrid paper that sweeps device-side configuration: 3 edge devices × 8 draft models × Q4_K_M–Q8_0 × speculative length × 2 cloud targets. It concludes that "no single fixed configuration can simultaneously optimise throughput, cost, and energy". Cloud cost-efficiency spreads by about 19–25% across drafts ([ConfigSpec](https://arxiv.org/html/2604.09722)). It pre-empts SEAM's "no configuration wins on all objectives" in a hybrid setting. But speculative decoding is lossless, so quality, feasibility and escalation never move. SEAM's configurations change whether the local step succeeds, which is the mechanism behind C1.

ECO-LLM jointly searches query processing, retrieval, context processing, model and quantization level, and edge-versus-cloud placement. It claims to beat model-only routing (RouteLLM) with 90% accuracy versus GPT-4o's 74%, but on one RTX A6000 with hardware emulation left to future work ([ECO-LLM](https://arxiv.org/html/2507.09003v1)). It is the most direct precedent for "configuration over routing", for *application-pipeline* knobs. SEAM's knobs are device hardware and runtime, and that distinction has to be explicit.

### Device-state-driven offload exists qualitatively, and "hardware-aware routing" is taken

HybridInfer shows phone thermal state and long-prompt wedging driving offload. In its test, "22 of 40 long prompts wedge past a 240 s cap", and its learned router runs only 7% of queries on-device. It uses one device and lists cross-device transfer of learned thresholds as future work ([HybridInfer](https://arxiv.org/html/2609.30270)). Edge-First attributes cloud-redirected tokens to edge capacity limits ([Edge-First](https://arxiv.org/pdf/2505.16508)). Neither gives a counterfactual of the form "same task, different configuration, the cloud call disappears", which is SEAM's C1 accounting. Separately, HW-Router has claimed the term "hardware-aware routing" for datacenter serving. It explicitly assumes that "quality predictions remain hardware-independent" ([HW-Router](https://arxiv.org/html/2608.14575)). That is precisely the assumption SEAM's silent-truncation data overturns, so it is a useful contrast citation, and SEAM should use "configuration-aware" or "feasibility-aware" instead of that term.

## Counter-evidence exists, but it comes from unconstrained devices

Four results could be read as cutting against SEAM. Each has a principled answer that should go into the paper before reviewers raise it.

**TMO** varies 8 device platforms from Raspberry Pi to iPhone 15 Pro and reports that "performance variations across different devices do not significantly impact the operation of the TMO system" ([TMO](https://arxiv.org/html/2502.11007)). But TMO fixes the on-device model, simulates on-device quality gaps by adjusting dataset scores, and uses a cloud-cost term that does not depend on the device. Platform *speed* only rescales a latency term in its reward, so it cannot move feasibility or quality. **EdgeWise** (NVIDIA, 13 Oct) reports comparable Pass@3 on A100 and on a real DGX Spark ([EdgeWise](https://arxiv.org/html/2610.17560)). Both runs used BF16 weights with about 57 GiB reserved for KV, so neither was ever memory-constrained. SEAM's sentence should be: *platform speed is not configuration; SEAM's effects appear when memory, KV precision, weight precision, placement and residency bind.*

The SLM-interpreter paper reports that **no model under 5B parameters exceeds 5.9% on AppWorld** when it drives a ReAct loop ([2610.14209](https://arxiv.org/html/2610.14209)). A reviewer could use this against a Qwen3-4B local agent. BFCL v4 multi-turn is an easier tool-calling setting, but SEAM should state its local baseline explicitly. On quality, Hydra finds Q4_K_M costs only +0.36 mean ΔPPL versus F16 on Jetson ([Hydra](https://arxiv.org/html/2608.25053)). "Compression Breaks Discipline" finds **no increase in missed tool calls for Qwen3-4B at NF4** on single-turn BFCL, even though Qwen3-1.7B jumps from 6.0% to 17.3% ([NeurIPS 2026 poster](https://neurips.cc/virtual/2026/171153)). That partly contradicts our INT4 result (same completion, 32 vs 7 no-parse entries). Two reconciliations are plausible: multi-turn, long-context BFCL stresses format adherence more, and the INT4 schemes differ (NF4 vs OpenVINO INT4-MIXED). "Flat Score, Amplified Failures" supports our pattern: aggregate scores stay flat while existing failure modes grow up to 2.5× ([DevelopersDigest summary](https://www.developersdigest.tech/papers/flat-score-amplified-failures-quantized-llm-agents)).

Finally, the claim that existing routers are *reactive* is contradicted as written. The 2026 TMLR survey separates pre-generation routers (RouteLLM, Hybrid LLM) from post-generation cascades (FrugalGPT, AutoMix) ([survey](https://arxiv.org/pdf/2603.04445)). Hera describes existing device-cloud methods as making "a one-shot routing decision before inference begins" ([Hera](https://arxiv.org/html/2605.24598)). Uncertainty is also not useless for ordinary capability errors. Probe routers reach about 65–69 AUROC ([RouterXBench](https://arxiv.org/html/2602.11877v1)), and Hera finds device entropy is higher where device and cloud disagree. SEAM's "indistinguishable at runtime" therefore holds only for the **truncation-induced regime**, where the context the model would need in order to notice its own error is gone.

## Claim wording that has to change before submission

| Current claim | Required wording | Why |
|---|---|---|
| Configuration moves outcomes more than routing (C2) | "With the local model held fixed, **within-model hardware configuration** (placement, KV/weight precision, residency, retention) moves cost and quality more than routing policy" | Model-size dominance is already shown by EC2-Bench and STEPGATE; ECO-LLM shows it for pipeline knobs |
| Router rank reversal across device configurations (C3) | "Routing-policy behaviour and ranking are **not portable across placements and precision settings for the same model**", backed by our 0% vs 100% escalation of one latency-triggered policy on GPU vs CPU | EC2-Bench, STEPGATE and CARGO own model-driven reversal; HybridInfer names cross-device transfer as open ([HybridInfer](https://arxiv.org/html/2609.30270)) |
| Cloud spend is configuration-caused escalation (C1) | "We **quantify** the share of cloud spend that disappears under an alternative device configuration at fixed task difficulty" | Edge-First and HybridInfer already say device limits cause offload, qualitatively |
| No configuration wins on all objectives | Cite ConfigSpec as the hybrid speculative-decoding precedent; claim it for **quality- and feasibility-changing** configurations | [ConfigSpec](https://arxiv.org/html/2604.09722) |
| Joint provisioning + routing (paper 2) | "Joint **device memory/BOM provisioning** and routing for hybrid device-cloud with a priced cloud tier" | RouterWise holds the datacenter version |
| Existing routers decide escalation reactively | "Pre-generation routers predict capability from query text and **assume faithful execution**; post-generation routers react to outputs; **neither models a runtime/hardware feasibility boundary**" | Survey taxonomy, Hera, Hybrid LLM |
| Silent failures are indistinguishable at runtime | Restrict to the truncation-induced regime; add a probe/uncertainty baseline | Probe AUROC 65–69; Hera entropy signal |
| First to price switch cost | "First to price the **device-cloud switch asymmetry**: uncached full-context re-send upward, configuration-dependent re-prefill downward" | Whose Turn (k\* formula) and SAAR |
| "Hardware-aware routing" | "Configuration-aware" or "feasibility-aware routing" | HW-Router uses the term with the opposite quality assumption |
| Three failure regimes by memory architecture (ISPASS) | A **runtime policy × memory architecture** grid with named runtime versions | On the same NVIDIA GPU, Ollama spills to CPU, llama.cpp with fixed `-ngl` OOMs, and vLLM refuses to start ([Ollama docs](https://docs.ollama.com/context-length); [vLLM #19407](https://github.com/vllm-project/vllm/issues/19407)) |
| Unified memory spills and only pays latency | "Unified memory removes the capacity cliff but not **driver-imposed allocation cliffs**; over-commit can stall the whole system" | Apple over-commit gives "a machine that stops redrawing" ([LocalAIMaster](https://localaimaster.com/blog/mac-memory-pressure-local-llm)) |
| Retention gives 4.7× usable context | "Consistent with" observation masking (about 2× cost cut) and ACON (26–54% peak-token cut), measured at a fixed small window on memory-capped devices | [Complexity Trap](https://arxiv.org/html/2508.21433v3); [ACON](https://arxiv.org/abs/2510.00615v2) |
| Hybrid on consumer AI PCs | Keep, and make it explicit: no hybrid paper found runs on an Intel AI PC/OpenVINO with a frontier cloud API | All sweeps |

## External sources confirm the iGPU numbers but rewrite three defaults

The strongest corroboration comes from Intel. Its OpenVINO 2026.3 table for the Core Ultra 5 "330" lists Qwen3-4B INT4-MIXED at **17.6–18.1 tok/s decode and 775–815 ms TTFT at 1,024 input tokens**, which works out to about 1,260–1,320 tok/s of prefill ([Intel 5-330 CSV](https://github.com/openvinotoolkit/openvino/blob/master/docs/sphinx_setup/_static/benchmarks_files/llm_models_5-330.csv)). That is consistent with our 19.85 tok/s at 12k and with 10k tokens fitting inside a 10 s TTFT. Intel publishes no CPU column, though, so our **16.8× prefill and 3.18× decode CPU-to-iGPU ratios have no external confirmation**. The only independent Panther Lake comparison (llama.cpp, a MoE model on a 16-core 358H) finds about 6× prefill and 1.7× decode ([grigio.org](https://grigio.org/benchmarking-llama-cpp-backends-on-intel-panther-lake-vulkan-vs-sycl-vs-openvino-vs-cpu/)). That is not a like-for-like check. Our 325 has 8 threads and we measure at 12k depth. Present the ratios as specific to this SKU. Our INT8 decode being 1.3–1.5× slower than INT4 sits at or below Intel's **1.5–1.7×** at short context, as expected when KV reads dominate at depth ([Intel 7-368H CSV](https://github.com/openvinotoolkit/openvino/blob/master/docs/sphinx_setup/_static/benchmarks_files/llm_models_7-368H.csv)). Sustained-load throughput loss of 41.5% [CORRECTED 2026-10-16: 37.3% Warm and 44.1% sustained Hot; not 41.5%, not Intel] on an iPhone supports SEAM's 60-second thermal warm-up guardrail ([2603.23640](https://arxiv.org/html/2603.23640)).

The silent-failure premise also gets external support on SEAM's own benchmark. In fault-injected **BFCL multi-turn** runs, agents flagged 91.3% of loud faults but **only 58.8% of quiet ones**, and two fault-free runs reached the same end state only 63.3% of the time ([Loud/Quiet](https://arxiv.org/html/2610.10062)). The second number means SEAM must report run-to-run variance. Rainone et al. find **out-of-context errors in about 20% of monolithic on-device Qwen3 agent runs at 80 turns**, but those errors are loud, not silent ([Rainone et al.](https://arxiv.org/html/2605.30102v1)). KV quantization is unlikely to explain our quality loss: per-channel 2-bit KIVI keeps LongBench within about one point, and only naive 2-bit collapses ([KIVI](https://arxiv.org/pdf/2402.02750)).

| Item | Our statement | What the evidence says | Re-check |
|---|---|---|---|
| OpenVINO KV default on iGPU | Property reads "dynamic"; f16/u8/u4 treated as alternatives to a default | [CORRECTED 2026-10-16: wrong; 2026.2.1 hard-codes auto_enable_4bit_kv = false, so the PA default is i8; u4 is automatic only from 2026.3.x] At 2026.2.1 the GPU plugin resolves "dynamic" to **u4 for PagedAttention models with 4-bit weights**, and LLMPipeline defaults to PagedAttention ([execution_config.cpp](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp); [utils.cpp](https://github.com/openvinotoolkit/openvino.genai/blob/releases/2026/2/src/cpp/src/utils.cpp)) | Read the element type of the compiled model's `key_cache.*` input. If it is u4, the **26.5k limit is the default-config limit and f16 is the override**. |
| LLMPipeline prefix caching | Default false | The `SchedulerConfig` struct defaults to false with `max_num_batched_tokens = 256`, but **LLMPipeline substitutes a latency config with caching on and unlimited batch tokens** ([scheduler_config.hpp](https://github.com/openvinotoolkit/openvino.genai/blob/releases/2026/2/src/cpp/include/openvino/genai/scheduler_config.hpp)) | Re-run the 22.4 s vs 11 s append with an identical explicit `SchedulerConfig(enable_prefix_caching=True, max_num_batched_tokens=large)` for both cold and warm runs. 256-token chunking alone can explain about 2×. |
| Ollama default context | 4096 | VRAM-tiered since Feb 2026: <24 GiB gives 4k, 24–48 GiB gives 32k, ≥48 GiB gives 256k ([Ollama docs](https://docs.ollama.com/context-length)). Before Apr 2025 the default was 2048. `num_ctx` sent through `/v1` is silently discarded ([Particula](https://particula.tech/blog/ollama-num-ctx-silent-prompt-truncation)). | State the version and VRAM tier, record the CONTEXT column of `ollama ps`, and note that 24 GB+ GPUs hide the regime |
| llama.cpp | Context-managed, silent truncation | Current llama-server (b7062) returns **HTTP 400**. Context shift was removed in PR #16391; older builds (b6721) truncated silently ([llama.cpp #17284](https://github.com/ggml-org/llama.cpp/issues/17284)) | Name the build, or move llama-server into the explicit-error regime. Ollama remains the silent case ([Desbiens](https://yandesbiens.com/blog/contextpaw-silent-truncation/)). |
| NVIDIA discrete GPU | Explicit error | Ollama **offloads layers to CPU** (PROCESSOR column) rather than erroring; vLLM fails at startup ([Ollama docs](https://docs.ollama.com/context-length); [vLLM #19407](https://github.com/vllm-project/vllm/issues/19407)) | Restate by runtime |
| Intel per-allocation limit | Candidate cause of B390 CL_OUT_OF_RESOURCES | The ~4 GB single-buffer cap applies to **pre-Xe2** hardware; large allocations are default on Xe2+ ([compute-runtime #627](https://github.com/intel/compute-runtime/issues/627); [iGPU memory guide](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/openvino-workflow/running-inference/optimize-inference/managing-igpu-memory-usage.rst)). The B390 is Xe3, so **this cap probably does not apply**. Issue #36151 shows CL_OUT_OF_RESOURCES on a B390 that KV precision does not fix ([openvino #36151](https://github.com/openvinotoolkit/openvino/issues/36151)). | Re-run the 4k GPU generation with no NPU model loaded. Log `GPU_DEVICE_MAX_ALLOC_MEM_SIZE`, the driver version and the Shared GPU Memory Override. |
| BFCL Qwen3-4B | Our multi-turn score is 10–11.5% | Public FC score is **22.1% multi-turn** and 35.7% overall, from a secondary aggregator ([BenchmarkList](https://benchmarklist.com/models/qwen3-4b-instruct-2507/)) | Disclose the ~10-point configuration cost. Fetch the official leaderboard snapshot and run a BF16 full-context reference. |
| NPU MAX_PROMPT_LEN | 1024 gives 960 usable; 2048 gives 1984 | Docs define no "minus 64"; NPUW **rounds up** to multiples of 64 ([llm_compiled_model.cpp](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_npu/src/plugin/npuw/llm_compiled_model.cpp)) | Minimal repro with raw `input_ids` and no chat template |
| NPU ~2× after Windows Update | Unexplained | The NPU uses the **compiler-in-driver** by default, so a driver update changes the compiler ([release notes](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/about-openvino/release-notes-openvino.rst)) | Log the NPU driver version and clear `CACHE_DIR` blobs |
| f16 KV prefill 15–27% faster | Ours | Not quantified externally. Intel frames u4 KV as a memory feature for prompts over 32K; a Lunar Lake fleet paper reportedly found an INT8 KV hint slower than the default on Arc ([2608.19147](https://arxiv.org/html/2608.19147v1), extractor paraphrase) | Keep as a novel measurement |
| CPU working set 9.5–10.7 GB vs 5.1 GB | Ours | GenAI warns that CPU may promote KV to bf16 regardless of the hint ([utils.hpp](https://github.com/openvinotoolkit/openvino.genai/blob/master/src/cpp/src/utils.hpp)) | Read the CPU compiled model's KV port types |

## Local-only work supplies methods, not competition

These papers have no cloud tier and do not compete with SEAM. They show that the knobs SEAM varies matter locally, and they offer methods SEAM can borrow. Placement depends on both the stage and the framework. On Snapdragon, the NPU wins prefill (1463.7 vs 115.1 tok/s) while decode ties ([2607.05475](https://arxiv.org/html/2607.05475v1)). A llama.cpp Hexagon study finds the opposite for prefill ([2605.27435](https://arxiv.org/html/2605.27435v1)). That conflict is itself evidence that a hybrid study which fixes one local backend is measuring one arbitrary point. On Intel, Agent.xpu splits work across NPU and iGPU on a Core Ultra 5 125H and cuts reactive latency 91–97% versus an OpenVINO iGPU baseline ([Agent.xpu](https://arxiv.org/pdf/2506.24045)). Ultra-low-bit kernels let Intel client parts beat datacenter GPUs on a 2B model ([2508.06753](https://arxiv.org/html/2508.06753)). Note that this is a local-only paper, not an AI-PC hybrid paper as the sweep brief had labelled it. Hydra concludes that "edge LLM performance is not determined by parameter count or hardware generation alone" ([Hydra](https://arxiv.org/html/2608.25053)).

Five methods are directly borrowable. **Khatib et al.** add per-token network delay to remote configurations and watch the accuracy-latency front move ([2609.08307](https://arxiv.org/html/2609.08307v1)); the paper is borderline-hybrid, and in SEAM the same cloud RTT/TPOT offsets would show which local configurations ever reach the joint front. **EnerInfer** predicts per-configuration performance with random forests (2.3–4.2% MAPE), filters by QoE and picks the most efficient configuration ([EnerInfer](https://arxiv.org/html/2606.23001v1)), which is the template for a router framed as a constrained selector over {local configurations} ∪ {cloud}. **FlexInfer** sweeps memory budgets with cgroups from about 5 to 35 GB ([FlexInfer](https://arxiv.org/html/2503.03777v1)), so SEAM could produce a provisioning curve between its 16 GB and 64 GB endpoints the same way. **lm-Meter's** harmonic quality-latency score ([lm-Meter](https://arxiv.org/pdf/2510.06126)) could serve as a single summary metric next to full Pareto plots, and **MELTing point's** sustained-run and thermal protocol ([MELTing point](https://arxiv.org/html/2403.12844v4)) supports long-session drift experiments. Even local-only work rarely sweeps KV precision or cross-turn residency as variables. No paper found gives a memory-provisioning curve that includes KV at the target context, KV precision and residency.

## What stays unclaimed on 15 October 2026, and what to do next

Seven contributions appear open after this sweep. The first is a **quantified counterfactual decomposition** of hybrid cloud spend into configuration-caused versus difficulty-caused escalation. The second is **router or policy rank reversal across hardware configurations with the model held fixed**. The third is a **quality × cloud spend × device BOM** Pareto analysis, including configuration-versus-memory-purchase substitution, and the fourth is **joint device provisioning and routing** in a hybrid setting. The fifth is **routing on a measured runtime × hardware × context feasibility boundary**, backed by a measured rate at which silent truncation turns into well-formed wrong agent outputs; no peer-reviewed study measures this, and only practitioner blogs document Ollama's 200-OK truncation ([Desbiens](https://yandesbiens.com/blog/contextpaw-silent-truncation/)). The sixth is the **device-cloud switch-cost asymmetry** with configuration-dependent re-prefill, and the seventh is any hybrid study on an **Intel AI PC with OpenVINO and a frontier cloud API**. These are absences in a search, not proofs of absence. MLSys, MobiSys and MobiCom 2026 proceedings were not scanned title by title, and the October arXiv listings were covered by six searches. Three close hybrid papers appeared between 9 and 13 October alone, so the window is closing fast.

| # | Action | Protects |
|---|---|---|
| 1 | Run the rank-reversal experiment. Use Qwen3-4B fixed and at least 3 policies plus always-local, always-cloud and **random escalation at a matched rate**, across GPU/CPU placement and two KV precisions. Repeat runs and report rank confidence intervals. | C2, C3 |
| 2 | Compute counterfactual escalation accounting: the same task set across configurations, with cloud dollars split by whether an escalation disappears under a larger feasible window | C1 |
| 3 | Build the provisioning front: 16 GB vs 64 GB plus a cgroup memory sweep, with cloud RTT offsets, plotted as quality × cloud $ × BOM | C4, JPR |
| 4 | Extend the Whose Turn k\* formula with a configuration-dependent device re-prefill term, and measure re-sent tokens per escalation | SWC |
| 5 | Add an uncertainty/probe router baseline on truncated vs non-truncated runs | PFR |
| 6 | Re-label the KV default after reading the port types, and re-run the prefix-cache append with matched SchedulerConfigs | KV, residency measurements |
| 7 | Pin runtime versions: Ollama version and VRAM tier, llama.cpp build. Add llama-server's 400 and Ollama's CPU spill to the regime grid. | ISPASS regimes |
| 8 | Isolate the B390 failure (no NPU model loaded; log allocation size, driver and override); build the NPU 64-token repro; log the NPU driver across updates | ISPASS operating limit |
| 9 | Fetch the official BFCL leaderboard snapshot; run a BF16 full-context Qwen3-4B reference; name the INT4 scheme | Quality claims |
| 10 | Read the full texts not yet read: 2609.13559, 2511.04002, the HW-Router PDF, the Flat Score PDF, LaTune/llm-tuna, MTRouter, TRACE-ROUTER, and 2603.04428. Check every quote against the PDFs. Set a weekly arXiv watch on "edge-cloud agent" titles. | All novelty claims |

## Which sources were read only through abstracts or secondary summaries

Several citations in this report rest on partial reads and need full-text confirmation before they go into a paper. All arXiv quotes came from WebFetch or browser extraction of abstract or HTML pages, not PDFs.

| Source | How it was read |
|---|---|
| Carbon-aware function calling 2609.13559 | Abstract only |
| Adaptive split computing 2511.04002 | Abstract only |
| Quantize-Sample-and-Verify 2507.00605 | Abstract only |
| Speculation at a Distance 2606.25091 | Abstract only |
| EdgeAgent 2610.03394 | Abstract only |
| JOVE 2610.03296 | Abstract only |
| Apple Foundation Models report 2507.13575 | Abstract only |
| HW-Router 2608.14575 | Abstract page in sweep 1, partial HTML in sweep 3. The PDF returned no text. |
| Fang et al. 2509.24050 | Abstract only in sweep 1, HTML v4 in sweep 3. Sweeps disagree on the venue (none vs ICML 2026). |
| 2607.18253 | Truncated before its results |
| MALBO | Truncated |
| "Flat Score, Amplified Failures" 2607.27275 | DevelopersDigest summary only (PDF not machine-readable) |
| Cross-model KV transfer 2608.03893 | Emergent Mind summary |
| Compression Breaks Discipline | NeurIPS poster page |
| Qwen3-4B BFCL v4 scores | BenchmarkList aggregator, not the Gorilla leaderboard |
| Ollama default-context history, `/v1` discard, log levels | Particula Tech's reading of Ollama source |
| Apple unified-memory spill behaviour | LocalAIMaster blog |
| Ollama 200-OK truncation | Desbiens practitioner blog |
| Pipeline Shards 2608.19147 | KV-hint finding is an extractor paraphrase |
| LaTune, llm-tuna, MTRouter, Workload–Router–Pool, TRACE-ROUTER, Agentic Routing, Agent Memory Below the Prompt, FlexSpec, GPU Goldmines | Seen only as search results |
| RouteLLM, Lost in the Middle | Not re-read |
| Nguyen et al. on remote-fetch energy | Known only second-hand |

## Conclusion

The literature has converged on SEAM's intuition from the model side, not the hardware side. Three independent 2026 papers now show that local capability decides whether routing sophistication matters at all. That helps SEAM if it reframes hardware configuration as the thing that *sets* effective local capability for a fixed model. The same lens explains the apparent counter-evidence. TMO and EdgeWise found hardware irrelevant because they changed speed but never capacity. SEAM's distinctive evidence lives where capacity binds: the 16 GB, long-context, silent-truncation regime.

The measurement review changes more than it confirms. If the iGPU "default" was u4 KV with prefix caching on, SEAM's baseline was already a tuned configuration that nobody chose on purpose. That strengthens the hidden-variable thesis: even the authors' own defaults were hidden. The paper should lead with that example, but only after reading the compiled model's port types to confirm it. The next round of results should be organized around the fixed-model rank-reversal experiment, because it is the claim the October papers came closest to taking.
