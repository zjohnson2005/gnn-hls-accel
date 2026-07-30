# Hybrid Execution DSE — Topic Positioning and Collision Analysis

**Date:** July 29, 2026
**Context:** Sharc Lab (Georgia Tech). Successor to `orchestration_engine_research_brief`.
**Reading of the brief:** "hybrid execution" = agentic workloads split across a **client/edge device and a remote cloud model**, across an administrative and network boundary. Not CPU↔FPGA within one box. Everything below assumes that reading. If you actually meant the intra-node split, tell me — the positioning changes substantially, and it's a weaker lane.

---

## 1. Bottom line

Your instinct is right, but for a different reason than you think.

The hybrid-execution **runtime policy** space is already crowded and getting more crowded monthly. Do not build another router. You will lose.

The hybrid-execution **design-time** space is empty, and it is empty for a specific reason: it requires simultaneously modeling silicon, network, dollar cost, energy, *and task accuracy* — and nobody who owns the hardware tooling cares about accuracy, while nobody who cares about accuracy owns hardware tooling. Sharc Lab is one of maybe five labs on earth positioned to do both, because of OmniSim.

**Recommended primary bet:** a hardware-aware, accuracy-aware DSE framework for hybrid device↔cloud agentic execution, whose decision variables include **the local accelerator's configuration**, not just the routing policy. Working name: **SEAM**.

The reframing that makes it a paper instead of a tool demo: everyone else asks *"which model should handle this subtask?"* You ask **"what local silicon must exist for the optimal split to be reachable at all?"** That inverts the entire literature from a policy question into a hardware sizing question, which is your home turf.

---

## 2. The collision map

I searched hard. Here is who occupies what. This is the section to bring to your advisor.

| Work | Owns | Does **not** have |
|---|---|---|
| **When Cloud Agents Meet Device Agents** (Qualcomm AI Research, arXiv 2605.30102, May 2026, ICML AIWILD workshop) | The exact framing: hybrid device+cloud MAS, Pareto of accuracy/$/edge-energy. States the space is "complex and poorly understood" and handled by "ad hoc decisions." | No tool. No search algorithm. Two hand-adapted architectures. No silicon variables. **This is your motivating citation, not your competitor.** |
| **AgentServeSim** (UCF, arXiv 2606.09613, Jun 2026) | Hardware-aware simulator for multi-turn agent serving; program orchestrator, tool-gap model, KV residency across HBM/DRAM/CXL; 6% error; does a "hardware-aware DSE" section. | Datacenter-side only. No device, no network boundary, no $ cost, no energy, no accuracy. No search loop — it's a simulator you sweep by hand. **Closest collision. Read it in full this week.** |
| **LLMServingSim 2.0** (KAIST, arXiv 2602.23036) | Heterogeneous + disaggregated cluster serving, trace-driven, operator-level profiler, power. | Cluster scale only. Explicitly not edge devices. Request-level, not agent-program-level. |
| Vidur, TokenSim, LLMCompass, GenZ, APEX | Established simulator/DSE machinery for LLM serving hardware. | Stateless request pairs. No agent semantics, no device, no accuracy objective. |
| **HERA** (2504.00434), **HybridFlow** (2512.22137), **PAAC** (2605.08646), **PRISM**, **IslandRun** (2512.00595), **MSAO**, **EWSJF**, **ConfigSpec** (2604.09722) | Runtime routers/partitioners for edge↔cloud agent subtasks, some privacy-aware, some N-way. | All *runtime* policies on *fixed* hardware. None explores hardware. None is design-time. |
| **Agent.xpu** (2506.24045), **HeRo** (2603.01661) | On-SoC scheduling of agentic work across NPU/iGPU; HeRo explicitly handles the dynamic/partial DAG. | Fixed SoC. **Note: HeRo weakens the "dynamic graph has zero prior art" claim in your old brief. Drop that claim.** |
| **MALBO** (2511.11788) | Multi-objective Bayesian optimization over LLM agent team composition; Pareto of accuracy vs. inference cost. | Zero hardware. No latency, energy, or silicon. **Your search-algorithm neighbor — cite it, extend it to 5 objectives with hardware in the loop.** |
| **AgenTEE** (2604.18231), confidential-agentic survey (2605.03213) | Attested agent execution on edge devices (Arm CCA). | No DSE, no cost/perf exploration of the trust boundary. |
| **Asgar, Nguyen, Katti — Efficient and Scalable Agentic AI with Heterogeneous Systems** (arXiv 2507.19635, Jul 2025) | **Same shape as SEAM.** Cost-model-driven planning/optimization of agentic execution graphs across heterogeneous hardware; MLIR representation + compiler; dynamic placement; systems-level **TCO optimization**. Finding: old GPUs + new accelerators can match latest-gen homogeneous TCO. | Datacenter infrastructure only. Preliminary results, position-paper character. No accuracy, no privacy, no client device, no battery energy. **Sachin Katti is now Intel's CTO. Treat this as the most dangerous paper in the space.** |
| **Gimlet Labs** (Asgar, Azizi, Nguyen, Serrino; Stanford spinout; TechCrunch Mar 2026) | The commercial build of the above: "multi-silicon inference cloud," agent→compute-graph→fragments→heterogeneous placement, hardware-agnostic compiler, autonomous kernel gen. Claims 3–10× at equal power. Partners: NVIDIA, Intel, AMD. | Business model is an inference **cloud**. Client-device silicon is off-strategy for them. |
| **QEIL v2 / Inference-time Scaling Laws for Heterogeneous Computing** (arXiv 2602.06057) | Multi-objective Pareto over **energy + inference quality + latency** on heterogeneous **edge** devices; roofline/CMOS-physics-grounded models; Pareto-guided simulated annealing. | Edge-only — no cloud boundary. No agent semantics (WikiText/GSM8K/ARC, single-shot). Hardware is not a decision variable. No $ cost, no privacy. |
| **From LLM to Silicon: RL-Driven ASIC Architecture Exploration for On-Device AI Inference** (arXiv 2604.07526) | Jointly optimizes ASIC architecture + memory hierarchy + **workload partitioning**. Same co-optimization structure. | PPA objective only. Partitioning = operator placement across on-chip cores, not device↔cloud. No accuracy, no agents. |
| **Hardware-Algorithm Co-Optimization of Early-Exit NNs for Multi-Core Edge Accelerators** (arXiv 2512.04705) | Early-exit is the structural twin of cascade routing, co-optimized with hardware. | DNNs, not agents. **Expect the reviewer line: "this is early-exit co-design for LLMs."** Have an answer ready. |
| HW-NAS with accuracy surrogates; Neurosurgeon → DADS/Edgent/SPINN → DNN-partitioning-plus-resource-allocation | The **methodological precedent**: accuracy surrogates inside hardware DSE, and edge-cloud partitioning DSE. | DNN-era, single-shot, no agent semantics. Good news: your machinery is proven and respected, so reviewers won't call it unfounded. Bad news: **novelty is scope, not machinery.** Don't oversell. |
| Vendor TCO white papers (Lenovo 2026, etc.) | On-prem vs. cloud break-even economics, cost-per-Mtoken, NPU amortization. | Gray literature, spreadsheet-level, not workload-parametric. **Do not lead the paper with TCO — it reads as already known.** |
| AgenticOS @ ASPLOS 2026 (full program checked) | OS abstractions, sandboxing, prompt injection, serverless provisioning. | Nothing close to hardware DSE or sizing. Clean. |
| AgentDSE, gem5 Co-Pilot, A3D, ArchEval, CHIA, CUCo, ArchAgent | *Agents for DSE.* | Opposite direction. Not competitors — but reviewers will confuse your title with these. **Avoid "agentic DSE" in your title.** |
| Perplexity hybrid local–cloud orchestrator (Computex 2026); NVIDIA BlueField-4 DPU offload of the "serving-stack tax" | Industry is building the product and the hardware offload. | No published design methodology. **Validation that the market is real, and a clock on how long the window stays open.** |

**The empty cell (revised after red-team pass, July 29):** design-time, hardware-aware, accuracy-aware DSE across the **client-device↔cloud** boundary for **agentic** workloads, with **local silicon configuration as a decision variable**. Still open — but narrower than the first draft claimed.

**Two hard constraints that fall out of the red-team pass:**

1. **The datacenter version is closed.** Academically staked by Asgar/Nguyen/Katti and commercially built by Gimlet Labs. Do not frame any part of this as datacenter or cluster infrastructure — you will be compared to a funded startup with Intel's CTO as a co-author, and you will lose. **Client-side is now a hard requirement, not a preference.**
2. **The five-objective claim needs softening.** QEIL v2 already has three (quality, energy, latency). What nobody has is the *combination* of dollar cost + privacy + hardware-as-decision-variable + agent program semantics + the client/cloud trust boundary. Claim the combination and the scope. Do not claim the machinery.

**Window estimate, revised down:** Katti at Intel plus Gimlet's vendor partnerships means the internal industrial version of the client-side question is probably already being asked. Assume ~12 months, not 24.

---

## 3. The thing that kills your old brief (read this before you defend it)

Your brief's honest open question — "if subtasks take seconds, do microseconds of scheduling matter?" — now has a partial answer, and it is not in your favor.

Practitioner break-even analysis puts total routing overhead (prompt analysis + scoring + decision logic) at **under ~40 ms against 500–3000 ms model calls — under 5% of response time**. At request granularity, a routing accelerator is dead on arrival. Do not submit a paper whose thesis depends on that 5%.

But there is a real wedge inside it: **cascade and per-step routing overhead compounds with step count.** The same analysis shows cascade routers paying 1.0–1.47× the single-shot bill by N=10, with the gap growing linearly in N. Agentic workloads are heading to hundreds of steps with finer-grained routing.

So the defensible version of your hardware question is:

> **Routing amortization bound.** As a function of local accelerator throughput, network RTT, per-step decision cost, and step count, at what granularity does hybrid partitioning stop paying for itself?

That is a quantitative, closed-form-shaped result. It is citable. And critically: **it is publishable whichever way the number falls.** "Software routing suffices below granularity G; above G you need hardware" is a strong finding. "Software always suffices" is a strong negative result that kills a research direction — which is a real service and still a paper. This is how you stop being exposed to the failure mode that has been stalling you.

---

## 4. Primary recommendation — SEAM

**SEAM: Silicon-aware Exploration of Agentic Model partitioning**

### The claim structure

- **C1 — Characterization (the provocation).** The optimal device↔cloud split *flips* under modest changes in local silicon configuration. Therefore every fixed routing policy in the literature is implicitly overfit to one device. Show this with a sweep and you have invalidated an assumption held by ~10 recent papers. That is a strong opening.
- **C2 — Tool (the platform).** First DSE framework whose search space is the **product** of software partitioning policy × local accelerator configuration × network regime × privacy constraint. Five objectives: task accuracy, cloud $ cost, end-to-end latency/JCT, device energy, privacy leakage. Three of those five are alien to Timeloop/LLMCompass-class tooling; two are alien to MALBO-class tooling. Nobody has all five.
- **C3 — Result (the actionable output).** The routing amortization bound, plus a **silicon sizing rule**: given a workload and a target Pareto point, the minimum local accelerator configuration that reaches it. That is the sentence a Qualcomm or AMD architect screenshots.
- **C4 — Artifact (the moat).** Open-source tool + agentic trace suite + reference hardware configs. Tools and benchmarks are what get adopted; adoption is what compounds into a career.

### Why Sharc Lab specifically wins this

Every hybrid-execution paper models the device side analytically — roofline, TOPS, a latency table. **You can model it at RTL accuracy** through OmniSim (MICRO'26) and HLS. That gives you a defensible accuracy claim no competitor can match, and it makes the paper unmistakably a Sharc Lab paper rather than a systems paper that wandered in. It also aligns with FIFOAdvisor-style DSE methodology the lab already publishes.

Fold your old orchestration engine in as **one design point inside SEAM's search space**, not the thesis. If the accelerator wins, you get a bonus contribution and a follow-up FCCM/FPGA paper. If it loses, SEAM still lands. That hedge is the entire point.

### Naming alternatives
SEAM, SPLICE, FAULTLINE, RIFT. Avoid anything with "Agentic" + "DSE" adjacent — collides with AgentDSE/A3D in search.

---

## 5. Alternatives, ranked

**Alt A — "Silicon sizing for on-device agents" (safe, fast, smaller).**
Drop the framework framing. Answer one crisp question: what local NPU/FPGA configuration minimizes total cost of ownership for a given agentic workload at a fixed accuracy target? DAC/ASP-DAC-sized, high acceptance probability, low citation ceiling. **Use this as the fallback scope if the 14-week plan slips** — it's a subset of SEAM, so no wasted work.

**Alt B — The trust boundary as a hardware co-design axis (highest variance).**
DSE over {plaintext-local, TEE-local, cloud, TEE-cloud} where enclave and attestation overhead are modeled as real hardware cost and privacy leakage is a hard constraint. Highest novelty and the actual enterprise blocker, so the biggest commercial upside. Risks: needs security expertise you may not have, validation is hard, and you're reviewed by two communities that distrust each other. Consider this the **second paper**, or a SEAM extension axis.

**Alt C — Accelerate the gate, not the orchestrator (rescues the old brief).**
Instead of a general orchestration engine, build an HLS sub-microsecond routing/gating engine and publish the crossover analysis honestly. Cleaner target, defensible evaluation. Best deployed as the hardware design point inside SEAM (see above) and then as a standalone FCCM paper once the bound is established.

**What I would not do:** another learned router, another edge-cloud scheduler, or anything that claims dynamic-DAG scheduling is unexplored. Those lanes are closed.

---

## 6. Risks, stated plainly

| Risk | Severity | Mitigation |
|---|---|---|
| **Accuracy as a DSE objective is expensive to evaluate.** Real LLM evals per design point makes the search intractable. | **Highest.** This is the make-or-break. | Offline-profile accuracy per (subtask-type × model) once, fit a surrogate, validate on held-out tasks, report surrogate error as a first-class result. This risk *is* the novel technical contribution — own it, don't hide it. |
| 5-objective search is hard. | Medium | MOBO with qEHVI (BoTorch). MALBO proves 2 objectives works; extending to 5 with hardware in the loop is itself contributable. |
| Someone ships an overlapping tool in 4 months. | Medium-high, and rising | arXiv preprint by week 8. Ship code with the preprint. Do not wait for camera-ready. |
| AgentServeSim reviewers say "you're a delta on us." | Medium | Pre-empt in the intro: they have no device side, no network boundary, no cost, no energy, no accuracy, no search. Make the table in §2 a figure in the paper. |
| Validation credibility — reviewers will ask if the numbers are real. | Medium | Real hybrid deployment on one device (laptop NPU / Jetson / FPGA board) + one cloud API, plus OmniSim RTL cross-check for the device datapath. Report error bars against measured. |
| The routing amortization bound comes out saying software always wins. | Low as a threat | That is a publishable negative result and the reason to structure the paper as a tool + finding rather than an accelerator + speedup. |

---

## 7. Timeline — the window is real and short

| Venue | Deadline | Fit |
|---|---|---|
| **MLSys 2027** | **Oct 30, 2026** (~13 weeks) | Best fit for a tool + system finding. Primary target. |
| **DAC 2027** | Abstract Nov 11, paper **Nov 18, 2026** | Strong fit for the silicon sizing framing. Secondary target / same work reframed. |
| FCCM 2027 | ~Nov–Dec 2026 (confirm) | Home for Alt C once the bound exists. |
| ICCAD 2027 | ~Apr 2027 | Backup with a full extra quarter of results. |

Two real shots inside four months. Suggested shape:

- **Weeks 1–2:** Read AgentServeSim, Qualcomm 2605.30102, MALBO, HERA, HeRo in full. Write the one-page differentiation table. Take it to Callie. Kill or confirm.
- **Weeks 3–5:** Trace collection + workload characterization. Build the accuracy surrogate. This is the risky part — front-load it.
- **Weeks 6–8:** SEAM v0: simulator + MOBO loop, coarse hardware model. **arXiv preprint out at week 8.**
- **Weeks 9–11:** OmniSim/HLS device-side refinement. Real-hardware validation. The C1 flip experiment.
- **Weeks 12–13:** Routing amortization bound, write-up, MLSys submission.
- **Weeks 14–15:** DAC reframe and submission.

---

## 8. Career and commercial upside

- **The tool is the platform.** A named framework other people run is worth more to your career than three speedup papers. It gives you a talk, a GitHub graph, and an identity ("the hybrid execution DSE person") going into the job market.
- **It expands LightningSim's story.** LightningSim/OmniSim currently sells fast accurate simulation to FPGA engineers. SEAM is a flagship application that reframes it as infrastructure for AI systems architects — a much larger TAM. That is a conversation worth having with Callie explicitly, and it is where your financial upside actually lives.
- **The buyers are identifiable and already moving.** Qualcomm published the motivating paper. Perplexity shipped the orchestrator at Computex 2026. NVIDIA is offloading the coordination tax to BlueField-4. Every one of them needs to answer "how much local silicon?" and none of them has published a method. Silicon sizing methodology is exactly the kind of thing that gets licensed, consulted on, or hired around.
- **Revised after finding Gimlet Labs.** Someone already raised money on the datacenter-side version of this idea, with Intel's CTO as a co-author on the underlying paper. Read that two ways. Positive: the thesis is validated by people with better information than either of us, and the client-side half is not their business model. Negative: "found a competitor to Gimlet" is off the table, and you should stop thinking of the upside as equity. The realistic upside is *positioning* — being the person with the published, validated client-side methodology when Intel, Qualcomm, AMD, and every AI-PC OEM need to answer "how much local silicon?" That converts into internships, industrial funding for the lab, consulting, and a strong job market position. I'm not a financial advisor and these are judgments about a fast-moving market, not predictions.
- **Do not sit on it.** Industry attention started in earnest ~6 months ago and the commercial build-out is already underway. Assume the client-side gap closes in about a year.

---

## 9. Soundness audit — are these approaches actually good?

**What I read, precisely.** AgentServeSim: intro, §2, §4.2 (validation config), §5.1, §7 (limitations) in full text; not §3 internals or all twelve appendices. Asgar/Katti: abstract, §5 Preliminary Results, Tables 4–5; not the MLIR/compiler sections in depth. QEIL v2: abstract, intro gap list, experimental platform description, ablation table captions; not the full derivations. HERA, HybridFlow, PAAC, PRISM, IslandRun, HeRo: **abstracts only — not audited.** Treat claims about those as provisional.

### 9.1 AgentServeSim — good engineering, oversold fidelity, one fatal structural limit

Genuinely well-built: program-centric event simulation, four composable policy modules, validated against real vLLM on RTX 3090 / H100-SXM / B200 with Llama 8B and 70B, four real policy baselines (vLLM-FCFS, Autellix, InferCept, Continuum). This is a competent paper.

Three exploitable weaknesses:

1. **The 6% error claim is weaker than it reads.** From §4.2, verbatim: *"For each turn, we replay the captured prompt, generated-token count, and tool duration on both real and simulated sides, so JCT differences reflect serving-system behavior rather than agent-side nondeterminism."* Generated-token count and tool duration are **inputs, not predictions**. Decode time is token-count × TPOT, and their own appendix notes tool times dominate on SWE-Bench. So the dominant terms of JCT are handed to the simulator; what's actually predicted is queueing, batching interference, and KV hit/miss. Not circular, but the headline number oversells fidelity, and no one has called this out.
2. **Trace replay cannot model behavior change — and they admit it.** §7, verbatim: *"AgentServeSim does not model agent-side non-determinism (a different run of the same agent may make different tool calls); for predictive use cases we provide the generative tool-distribution mode, but its predictive validity is not the focus of this paper."* **This is fatal for hybrid execution.** Swapping a frontier cloud model for a local SLM changes output verbosity, retry count, which tools get called, number of turns, and whether the task succeeds at all. Every simulator in this space assumes agent behavior is invariant to the serving decision. For model routing that assumption is simply false.
3. **Profile-based operators cannot evaluate silicon that doesn't exist.** Operator latencies come from a vLLM layerwise profiler per (device, model) pair. So "configurations beyond available clusters" means interpolating memory capacity and bandwidth — not evaluating a new compute architecture. You cannot profile an NPU you haven't built.

Also: no accuracy modeling (impossible by construction under trace replay), no simulator-vs-simulator baseline, validation limited to two model sizes and three datacenter GPUs.

### 9.2 Asgar / Nguyen / Katti — a vision paper with a roofline spreadsheet

Reading §5 changes the threat assessment substantially. In their own words: *"These findings are preliminary, and comprehensive system validation is currently underway."* Specifically:

- Performance comes from *"empirical measurements when available and are augmented by theoretical roofline modeling."*
- *"All reported FLOP values assume dense computation, without accounting for sparsity."*
- *"we simulated a continuous workload scenario with unconstrained hardware availability"* — no queueing, no contention, no capacity limits.
- The hardware model is Table 5: six devices × {cost, memory, bandwidth, TFLOPs, $/hr}.
- One workload (a conversational voice agent), and they immediately place all non-LLM components on CPU and state *"the following focuses on exploring optimizations on the LLM component"* — so the agentic structure is discarded and it reduces to LLM serving hardware selection.

**Verdict: the paper that worried me most is technically thin.** It is dangerous for *positioning* — Intel's CTO, a funded startup, a staked claim — not because the science is settled. Avoid the datacenter because the credit and the commercial lane are taken, not because there's a strong result to beat.

### 9.3 QEIL v2 — real measurements, wrong workload, dishonest "edge"

Important: QEIL v2 explicitly frames itself as extending Asgar et al. to consumer edge hardware, and its own gap list names *"Intel CPU + Intel NPU + NVIDIA GPU"* heterogeneity. **So your lane already has traffic.** But the execution is weak:

- Their "edge platform" is a Core Ultra 9 285HX with an **NVIDIA RTX PRO 5000 Blackwell, 96.2 GB VRAM**. That is a workstation with a five-figure professional GPU. Calling it edge undermines the framing.
- Benchmarks are WikiText-103, GSM8K, ARC-Challenge — **single-shot QA, no tool calls, no multi-turn, no cloud boundary.** Not agentic in any sense.
- The key heterogeneity ablation uses **GPT-2, 125M parameters**.
- Eight-plus invented acronyms (DASI, CPQ, Phi, PGSAM, EAC, ARDE, CSVET, QEIL) and language like *"every coefficient traceable to semiconductor physics."* Presentation is outrunning substance.
- Self-cites v1 → v2 inside the same year and treats v1 as established prior work.
- Their own caveat: *"This variance analysis is performed on a single hardware platform."*
- Hardware is not a decision variable — they allocate across fixed devices. No dollar cost, no privacy.

Real strengths, to be fair: energy and latency from actual hardware counters, a reproducibility analysis with coefficient of variation, and IPW is borrowed from a legitimate source (Saad-Falcon et al. 2025) rather than invented.

**Verdict: beatable on workload realism, platform honesty, and scope.**

---

## 10. How we build the better tool — five concrete superiority claims

Ranked by strength. A is the flagship; it is also the hardest.

**A. Closed-loop, behavior-reactive simulation.** Every simulator in this space replays fixed agent behavior. Model the fact that the agent *re-decides* under a different configuration: token counts, turn counts, tool choices, and success rates all shift when a step moves from a frontier model to a local SLM. Build a **behavioral response model** by running real agents across configurations, then put it in the loop. Validate by predicting held-out configurations, and report error on turn count and task success — not just JCT. This is measurable superiority over AgentServeSim on its own metric, and it is the only way any hybrid-routing DSE result is trustworthy.

*Honest cost: this is why everyone replays traces. It's the hard part, and it's now the core scientific contribution rather than a side quest.*

**B. Evaluate silicon that cannot be profiled.** AgentServeSim needs a physical device to profile. Via HLS and OmniSim you can evaluate device-side accelerator configurations that don't exist, at RTL accuracy, and validate against a real FPGA over the EVO-T2's OCuLink port. No competitor can do this. Cleanest defensible claim in the set.

**C. Honest fidelity accounting.** Report prediction error decomposed by which terms were *given* versus *predicted*, under both replay and closed-loop conditions. This is a real methodological contribution and a polite, devastating critique of the 6%-style headline number. Cheap to do, and it makes you the credible one in the subfield.

**D. Real client hardware, honestly labeled.** Panther Lake, four on-die execution targets, measured RAPL energy, real cloud API dollar costs. Explicitly contrast with "edge" evaluations that include 96 GB professional GPUs.

**E. Accuracy in the loop on real agent benchmarks.** SWE-bench Verified, BFCL, real tool-use traces — not WikiText, and not GPT-2.

**What this means for the plan.** The project is harder than §7's timeline assumes, because A replaces "build a simulator" with "build a simulator plus a validated behavioral model." Two options: keep MLSys Oct 30 with A in reduced form (behavioral response model for token/turn counts only, success rate deferred), or target DAC Nov 18 / ICCAD April with A complete. Recommend deciding this after week 3, once you know how noisy the behavioral response actually is.

## Sources

- [When Cloud Agents Meet Device Agents: Lessons from Hybrid Multi-Agent Systems (arXiv 2605.30102)](https://arxiv.org/abs/2605.30102)
- [AgentServeSim: A Hardware-aware Simulator for Multi-Turn LLM Agent Serving (arXiv 2606.09613)](https://arxiv.org/html/2606.09613)
- [LLMServingSim 2.0 (arXiv 2602.23036)](https://arxiv.org/html/2602.23036v1)
- [Vidur: A Large-Scale Simulation Framework for LLM Inference (MLSys'24)](https://apanwariisc.github.io/publications/mlsys-2024-vidur/vidur_mlsys24.pdf)
- [TokenSim (arXiv 2503.08415)](https://arxiv.org/html/2503.08415v1)
- [LLMCompass (ISCA'24)](https://www.cl.cam.ac.uk/~ey204/teaching/ACS/R244_2024_2025/papers/LLMCOMPASS_ISCA_2024.pdf)
- [HERA: Hybrid Edge-cloud Resource Allocation for Cost-Efficient AI Agents (arXiv 2504.00434)](https://arxiv.org/abs/2504.00434)
- [HybridFlow (arXiv 2512.22137)](https://arxiv.org/html/2512.22137)
- [PAAC: Privacy-Aware Agentic Device-Cloud Collaboration (arXiv 2605.08646)](https://arxiv.org/abs/2605.08646)
- [IslandRun: Privacy-Aware Multi-Objective Orchestration (arXiv 2512.00595)](https://arxiv.org/html/2512.00595)
- [Agent.xpu: Efficient Scheduling of Agentic LLM Workloads on Heterogeneous SoC (arXiv 2506.24045)](https://arxiv.org/abs/2506.24045)
- [HeRo: Adaptive Orchestration of Agentic RAG on Heterogeneous Mobile SoC (arXiv 2603.01661)](https://arxiv.org/pdf/2603.01661)
- [MALBO: Optimizing LLM-Based Multi-Agent Teams via Multi-Objective Bayesian Optimization (arXiv 2511.11788)](https://arxiv.org/pdf/2511.11788)
- [Towards Understanding, Analyzing, and Optimizing Agentic AI Execution: A CPU-Centric Perspective (arXiv 2511.00739)](https://arxiv.org/abs/2511.00739)
- [AgenTEE: Confidential LLM Agent Execution on Edge Devices (arXiv 2604.18231)](https://arxiv.org/html/2604.18231v1)
- [When Agents Handle Secrets: Confidential Computing for Agentic AI (arXiv 2605.03213)](https://arxiv.org/html/2605.03213v1)
- [ConfigSpec: Distributed Edge–Cloud Speculative LLM Serving (arXiv 2604.09722)](https://arxiv.org/pdf/2604.09722)
- [Collaborative Inference and Learning between Edge SLMs and Cloud LLMs: A Survey (arXiv 2507.16731)](https://arxiv.org/pdf/2507.16731)
- [Benchmarking Compound AI Applications for Hardware-Software Co-Design (arXiv 2604.09593)](https://arxiv.org/html/2604.09593)
- [Sharc Lab @ Georgia Tech](https://sharclab.ece.gatech.edu/)
- [Perplexity AI hybrid local-cloud inference system, Computex 2026 (VentureBeat)](https://venturebeat.com/technology/perplexity-ai-unveils-hybrid-local-cloud-inference-system-at-computex-2026)
- [CPU-Free LLM Inference: BlueField-4 DPUs and the serving-stack tax (Spheron)](https://www.spheron.network/blog/cpu-free-llm-inference-bluefield4-dpu-smartnic-gpu-cloud-2026/)
- [Model Routing: Selection, A/B Testing, Cascades & Strategies — break-even analysis](https://mbrenndoerfer.com/writing/model-routing-selection-ab-testing-cascades-strategies)
- [MLSys 2027 deadlines](https://mlsys-deadlines.github.io/)
- [DAC 2027 important dates](https://www.getpaperpilot.com/deadlines/dac-2027.html)
