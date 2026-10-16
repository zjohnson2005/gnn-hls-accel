# October 2026 gap-closing sweep 7: hybrid device-cloud agent papers that earlier sweeps could not read

Retrieval note: WebFetch to arxiv.org returned HTTP 429 again (html, pdf, and one abs page), and direct curl to arXiv, Semantic Scholar, alphaXiv, Hugging Face and the Wayback Machine is blocked by the egress proxy (403). WebFetch got the abs pages of 2610.17816 and 2610.14209. All five full texts (2610.17816, 2610.14209, 2610.19292, plus the new find 2610.17560) and the abstracts of 2610.03394 and 2610.03296 were read in full through the user's Chrome (Claude in Chrome, arxiv.org/html and /abs pages). Statements below are close paraphrases of the papers' text. Numbers are copied exactly from the papers' tables and prose. Verbatim quotation is kept minimal because of copyright limits.

Scoring key (0 = no overlap, 1 = adjacent/motivational, 2 = partially makes the claim in a different setting, 3 = makes the claim). C1 = cloud bill is configuration-caused escalation. C2 = configuration moves cost/quality more than routing policy. C3 = router rank reversal depends on device configuration. C4 = configuration substitutes for more memory/hardware. JPR = provisioning and routing are one decision. PFR = predictive routing on a measured feasibility/failure boundary because local failures are silent. SWC = switch cost (context re-send) priced explicitly.

## Q1. arXiv 2610.17816, "Empowering Edge Agents: A Systematic Analysis of Edge-Cloud Collaboration in LLM Agent Execution" (EC2-Bench)

### Takeaway
This paper is hybrid in framing but not in hardware. The "edge" is a Qwen model of varying size with no named device, and edge compute is a FLOPs estimate (2·N·T). The only device-side knob is edge model size (Qwen3.5-2B/9B/27B, Qwen3.7-Plus). Its findings that matter for SEAM are two. First, the best collaboration strategy reverses with edge capability, a rank reversal driven by model size, not hardware configuration. Second, strategy differences shrink from 25.22 to 3.67 points as the edge model gets stronger, so edge capability moves quality more than strategy does. It partly preempts the model-size slice of C2/C3. It does not touch placement, precision, KV, residency or context-window knobs.

### Cited Findings
- Metadata: Huang, Liu, Ren, Yu, Yao, Yan, Xiao, Sun (Northeastern Univ. China, Tsinghua, China Mobile). Submitted 13 Oct 2026. 23 pages. Code at OpenBMB/EC2-Bench. — [arXiv abs](https://arxiv.org/abs/2610.17816)
- Setup: 128 executable digital-workspace tasks curated from six "Claw" benchmarks (Claw-Eval, WildClawBench, QwenClawBench, LiveClawBench, PinchBench, ClawBench), run in the OpenClaw runtime inside E2B sandboxes. The context window is 128K, each model interaction is capped at 32K, and OpenClaw's automatic context compression is on. Each task-config pair is run 3 times. Pass^3 counts success when completion exceeds 0.7. The primary cloud model is GLM-5.3, with DeepSeek-V4.1-Flash as a robustness check. — [arXiv html](https://arxiv.org/html/2610.17816)
- Edge hardware: none named. The full-text search finds zero mentions of GPU, vLLM, quantization, KV cache or hardware. Edge cost is estimated FLOPs, following the Kaplan et al. 2·N_act·T rule (Appendix A.11). Cloud cost uses OpenRouter prices as of Aug 2026. GLM-5.3 is $1.4 input / $0.26 cache-read / $4.40 output per M tokens. — [arXiv html](https://arxiv.org/html/2610.17816)
- Four strategies are compared: Query Routing (RouteLLM MF router, one decision per task), Per-step Routing (entropy of the edge model's next reasoning-token distribution, adapted from GlimpRouter), Edge-Controlled Cloud Delegation (the edge agent calls a tool that hands the next step to the cloud), and Edge-Controlled Cloud Advisory (the cloud returns advice and the edge acts). Router thresholds were calibrated to about 15% cloud participation. When the cloud is invoked it receives the task plus the full OpenClaw execution history, with no redaction. — [arXiv html](https://arxiv.org/html/2610.17816)
- Endpoints (Table 2, completion / Pass^3 / cloud $): edge-only 2B 12.75/2.34, 9B 39.12/9.38, 27B 61.79/30.47, Qwen3.7-Plus 71.34/53.12. Cloud-only GLM-5.3 82.70/71.88/$56.42. DeepSeek-v4-Pro 72.90/53.12/$16.41. — [arXiv html](https://arxiv.org/html/2610.17816)
- Collaboration at 2B: Per-step Routing reaches 39.97 completion for $12.80 cloud, which the paper reports as 22.7% of the cloud-only cost. Query Routing 23.98 ($8.76). Delegation 15.86 ($1.19). Advisory 14.75 ($2.36). — [arXiv html](https://arxiv.org/html/2610.17816)
- Collaboration at 9B: Per-step 52.71 ($6.07), Delegation 52.88 ($3.01), Advisory 60.46 ($8.73), Query 43.60 ($9.33). At 27B: Advisory 70.13 ($5.71), Delegation 69.06 ($4.93), Per-step 68.42 ($5.29), Query 65.53 ($10.76). At Qwen3.7-Plus: Advisory 76.84 ($6.8), Delegation 74.24 ($4.03), Query 73.17 ($14.03), Per-step 72.08 ($10.14). — [arXiv html](https://arxiv.org/html/2610.17816)
- Strategy sensitivity collapses with edge capability. The spread between the best and worst strategy falls from 25.22% (2B) to 3.67% (Qwen3.7-Plus). At 27B the strategies differ by only 4.60% in completion but by 35.93% in privacy exposure. — [arXiv html](https://arxiv.org/html/2610.17816)
- Rank reversal by edge capability (paraphrase of §6.3): with weak edge models, externally routed strategies beat edge-controlled ones (2B: Per-step 39.97 vs Delegation 15.86), and the pattern reverses as edge capability rises. Weaker edges benefit more from direct cloud execution, stronger edges from advisory support. — [arXiv html](https://arxiv.org/html/2610.17816)
- Edge self-assessment is weak for small models. Edge-controlled delegation beats a random baseline with the same call rate by only 1.2% at 2B, and by 3.0–4.4% for larger edge models. Instruction-following training on 2B lifts advisory completion from 24.8% to 28.8% after 600 steps. — [arXiv html](https://arxiv.org/html/2610.17816)
- Prior work framed as one-shot routing: the paper says earlier edge-cloud systems mostly treat collaboration as a per-query routing or escalation decision, and that trajectory-level effects are under-explored. — [arXiv html](https://arxiv.org/html/2610.17816)

### Inferences
- Is it hybrid? Yes, as a system design. But there is no real device, no device latency, no memory budget, and no configuration knob beyond model identity. It reinforces the earlier sweep's finding that hybrid agent papers simulate the device.
- C1 = 1. Under the same entropy router, calibrated to the same ~15% participation target, cloud spend for Per-step Routing falls from $12.80 (2B) to $6.07 (9B) to $5.29 (27B). The cloud bill therefore depends on the edge model, not just the tasks. This is the model-size slice of C1, and the paper never frames it as configuration-caused escalation.
- C2 = 1–2. Edge capability (model size) moves completion from 39.97 to 76.84 for the best strategy, while strategy moves it by at most 25.22 and by only 3.67 at the strongest edge. That is "the device-side choice dominates the policy choice," but only for model size, and model size is one of SEAM's six knobs. SEAM's within-model knobs (placement, KV precision, weight precision, residency, context retention) are untouched.
- C3 = 2. This is the closest prior statement of strategy rank reversal by device-side condition (edge model strength). SEAM must cite it and differentiate: SEAM's reversal is driven by hardware configuration with the model held fixed (Qwen3-4B), not by swapping the model.
- C4 = 0. JPR = 1: the paper says the preferred collaboration mode should change with edge capability, an implicit "choose mode given device model," but it does not optimize the two jointly. PFR = 1: the near-random self-delegation at 2B (+1.2% over random) shows small edge models cannot tell when they need the cloud, which is consistent with SEAM's silent-failure argument. There is no feasibility boundary. SWC = 1: cache-read and raw input tokens are billed separately (e.g., 2B Query Routing uses 1.81M raw / 10.49M cache-read), but switch or re-send cost is never isolated or modeled.
- Contradiction with SEAM data: none found. The fixed 128K window with automatic compression means the truncation/silent-context-drop regime that SEAM measures never arises.

### Gaps
- Appendix A.8 (alternative cloud model) and A.3–A.7 were not read in detail. Neither latency nor wall-clock time is reported anywhere.

## Q2. arXiv 2610.14209, "Should SLMs Be in the Driver's Seat? A Study of Local Models as Interpreters in Cloud-Written Agent Programs"

### Takeaway
This paper is hybrid by architecture. A cloud LLM writes a Python program, and a local SLM is called through an `slm()` function only to answer bounded questions over private data. All models run on datacenter GPUs (llama.cpp GGUF on A100/V100). The only knobs varied are SLM size (0.8B/2B/4B/9B) and planner LLM. The paper explicitly defers device hardware effects to future work, so it supports SEAM's gap rather than preempting it. Its one possible tension with SEAM is that sub-5B models driving a ReAct loop nearly fail on AppWorld.

### Cited Findings
- Metadata: Radovič (KAUST / Univ. Ljubljana), Canini (KAUST), Pejović (Ljubljana). Submitted 9 Oct 2026. Accepted at the SLM-Agents workshop, NeurIPS 2026. — [arXiv abs](https://arxiv.org/abs/2610.14209)
- Hardware and config: every model is served with llama.cpp (build b10162) on one GPU each. Planners: Qwen3.6-27B at UD-Q8_K_XL, Qwen3.5-122B-A10B at UD-Q4_K_XL, Qwen3-Coder-Next at Q6_K, all on A100-80GB. SLMs: Qwen3.5 0.8B/2B/4B/9B at UD-Q8_K_XL on V100. Decoding is greedy. — [arXiv html](https://arxiv.org/html/2610.14209)
- Motivation (Fig. 1, ReAct on AppWorld): no model under 5B parameters exceeds 5.9% on Test Normal or 3.8% on Test Challenge, and sub-2B models solve nothing. Gemma 12B reaches 73%, but the paper notes its weights alone need about 6 GB at 4-bit before any KV cache. — [arXiv html](https://arxiv.org/html/2610.14209)
- Main results (Table 2, TN success rates): FC to SLM agent goes 33.3 to 38.7 (Qwen-coder), 42.3 to 52.4 (Qwen-122B), and 45.8 to 60.7 (Qwen-27B, +14.9pp). Cloud ReAct gets 59.5 / 57.1 / 81.0. On TC: 13.4 to 15.6, 25.7 to 28.8, 36.2 to 41.5. — [arXiv html](https://arxiv.org/html/2610.14209)
- Local cost: with the same 9B client, the SLM agent beats a fully local ReAct agent (52.4% vs 45.2%). The client processes one to two orders of magnitude fewer input tokens and 1.8× fewer output tokens. Peak context is about 3× smaller (median 3.7k vs 12.0k tokens), so less memory is needed for KV. Cloud ReAct reaches 57.1%. — [arXiv html](https://arxiv.org/html/2610.14209)
- Cloud cost: the `slm` instructions add 3.7k tokens per program, about 32% more cloud input than FC. — [arXiv html](https://arxiv.org/html/2610.14209)
- SLM size barely matters in this role (Table 3, TN, Qwen-27B planner): FC 45.8, 0.8B 52.4, 2B 61.3, 9B 60.7. In the agreement study the 2B returns the same value as the 9B in 91.6% of constrained-format calls, against the 9B's own 97.0% reproducibility. — [arXiv html](https://arxiv.org/html/2610.14209)
- Failure handling: the SLM is required to report missing information instead of inventing it, and the call then raises a not-found exception. Not-found errors recur in the next program 55.6% of the time, against at most 35.6% for other exception types. Privacy leakage via tracebacks: 12 of 2,917 exceptions (0.4%). — [arXiv html](https://arxiv.org/html/2610.14209)
- Explicit deferral of hardware (paraphrase of §5): the resource claims rest on token and context proxies, actual latency and energy savings depend on edge hardware that varies widely, and the authors plan to measure them later. — [arXiv html](https://arxiv.org/html/2610.14209)

### Inferences
- Is it hybrid? Yes, architecturally (cloud planner plus device interpreter). The device is a V100.
- Scores: C1 = 0. C2 = 0. C3 = 0. C4 = 1: an architectural choice (SLM as interpreter, not driver) lets a 2B model replace a 9B and cuts peak context about 3×. That is substitution by architecture, not by hardware configuration. JPR = 0. PFR = 1: forcing the SLM to report "not found" instead of fabricating is a guard against silent local failure, but it is reactive (exception-based), not predictive. SWC = 1: Table 1 compares cloud-device round trips per strategy qualitatively, and the design avoids re-sending data rather than pricing it.
- Possible reviewer tension with SEAM: SEAM's local agent is Qwen3-4B, and this paper reports that sub-5B models running ReAct get at most 5.9% on AppWorld. BFCL v4 multi-turn is a different, easier tool-calling setting, so this is not a contradiction of SEAM's data. SEAM should still state its local model's baseline success to pre-empt the objection.
- The sentence deferring hardware measurement is useful gap evidence: even a 2026 NeurIPS-workshop hybrid paper admits that device hardware effects are unmeasured.

### Gaps
- No latency, energy, or real-device numbers are reported, by the authors' own statement.

## Q3. arXiv 2610.19292, "Whose Turn Is It? Context-Guided Model Routing for Stateful Agents" (Microsoft)

### Takeaway
This paper is not hybrid. Both candidates in every pair are cloud models (GPT-5.6 Sol/Luna, Claude Haiku 4.5, Claude Opus 4.8 high/low effort). It is nonetheless the strongest preemption found of SEAM's switch-cost claim: it prices switch cost in closed form from prompt-cache prices, shows that upward (cheap to expensive) switches never pay back, and recommends sticky, context-length-aware switching. It also says that choosing the candidate pair (including a reasoning-effort configuration of the same model) matters as much as routing within it, which is a cloud-only analogue of SEAM's C2/JPR.

### Cited Findings
- Metadata: Parashar, Dutta, Chauhan, Gulwani, Gupta, Hasanbeig, Le, Tiwari, Williams (Microsoft). The HTML has no visible date. The arXiv ID places it in October 2026, and the cited pricing was recorded 29 Aug 2026. — [arXiv html](https://arxiv.org/html/2610.19292)
- Setup: zero-shot LLM router (GPT-5.6 Luna) deciding at the user-turn boundary, on multi-turn SheetCopilot (112 tasks, average 2.88 turns) and SpreadsheetBench 2 (221 workflows, average 4.76 turns). Three pairs, each varying one factor: Sol vs Luna (size), Sol vs Haiku 4.5 (provider), Opus 4.8 high vs low (reasoning effort). Cost bills cached input at the cached rate and charges router calls. — [arXiv html](https://arxiv.org/html/2610.19292)
- History helps: at a matched offloading rate (23.3% vs 22.7% of turns to the cheap model), the history-aware router passes 28.3% vs 25.0% without history, a 3.3-point gain that holds for every pair (+5.4 Sol/Haiku, +2.7 Sol/Luna, +1.7 Opus). — [arXiv html](https://arxiv.org/html/2610.19292)
- Self-assessed escalation, de-escalation and random switching do worse. Random routing scores below both fixed endpoints in every pair on both benchmarks (mean 22.2% SheetCopilot, 26.6% SSB-2). Escalation keeps 90.4–99.4% of turns on the cheap model on SheetCopilot. — [arXiv html](https://arxiv.org/html/2610.19292)
- Switch-cost formula (§4.4, paraphrase): a downward switch at context L costs an extra L(p_in^c − p_cache^e) on the first call, then saves L(p_cache^e − p_cache^c) per later call. Breakeven is k* = (p_in^c − p_cache^e)/(p_cache^e − p_cache^c) calls, independent of L. k* = 1.25 for Sol→Luna and Sol→Haiku. An upward switch costs L(p_in^e − p_cache^c), about $4.9 per M context tokens (10× the $0.5 of a downward switch), and never pays back on input. At 75K tokens of context, one upward switch costs roughly an entire SheetCopilot task on Sol. — [arXiv html](https://arxiv.org/html/2610.19292)
- Design principle (paraphrase): switching should be sticky and context-length-aware. Switch down early and stay there, and switch up only when the expected quality gain exceeds a cost that grows with the session. — [arXiv html](https://arxiv.org/html/2610.19292)
- Pair choice matters as much as routing: Luna alone passes 28.6% at $0.061 per task-run against 26.8% for the router with history. Opus at low effort matches the router's 31.2% at $0.268 vs $0.369. The router ignores the pair and sends 21–24% of turns to the cheap model regardless. — [arXiv html](https://arxiv.org/html/2610.19292)
- Price per token is not cost per task: on SSB-2, Haiku makes about 41 calls and reads 1.6M input tokens per conversation (about 25 calls and 0.9M for the others). Its discount against Sol shrinks from 6.8× on short SheetCopilot sessions to 3.2× ($0.37 vs $1.18), while passing 16.4% vs 27.1%. Mean context per call roughly doubles from about 18K to about 38K tokens. — [arXiv html](https://arxiv.org/html/2610.19292)
- Silent errors motivate pre-decision routing: the paper argues that weak verification in spreadsheets (a formula over the wrong range returns a plausible number rather than an error) undermines cascades that decide after inspecting an output. — [arXiv html](https://arxiv.org/html/2610.19292)
- Cache-favorable baseline caveat: fixed-model baselines are assumed to keep the trajectory cache warm across turns. If disconnects, cache expiry or cold restarts invalidate it, fixed-model costs would rise. — [arXiv html](https://arxiv.org/html/2610.19292)

### Inferences
- Is it hybrid? No (cloud to cloud). The "configuration" analogue is reasoning effort (Opus high vs low).
- Scores: C1 = 0. C2 = 2 (cloud-only): pair or effort choice dominates routing, and the cheap configuration Pareto-dominates every routed policy in two of three pairs. C3 = 1: the best policy differs by pair, but the paper does not frame this as rank reversal. C4 = 0. JPR = 2 (cloud-only): the paper argues that choosing the pair matters as much as routing within it. PFR = 1: it argues for pre-turn, history-conditioned routing over output-inspecting cascades because errors are silent, but it uses an LLM judge with no measured feasibility boundary. SWC = 3 for cloud-only: closed-form pricing with an asymmetric up/down result.
- What SEAM must change: drop any claim of being first to price switch cost. Cite 19292 and differentiate on hybrid asymmetry. In device to cloud escalation (the "upward" direction), the re-sent context is billed as uncached cloud input. That is 19292's never-pays-back direction, so SEAM's escalation cost is the expensive case. In cloud to device fallback, the cost is local re-prefill latency and energy plus KV residency, not dollars, and it depends on device configuration (placement, KV precision, residency). 19292 cannot capture this. Its k* formula could be extended with a device re-prefill term that depends on configuration.
- 19292's caveat about cache expiry and cold restarts parallels SEAM's session-residency knob, where losing local prefix residency forces re-prefill. That is supporting evidence, not a contradiction.
- Contradiction with SEAM data: none.

### Gaps
- Exact submission date was not visible in the HTML.

## Q4. Brief checks: 2610.03394 EdgeAgent and 2610.03296 JOVE (abstracts only)

### Takeaway
Neither is a hybrid device-cloud agent paper. EdgeAgent is purely on-device (Apple M4 unified memory). JOVE allocates LLMs within a heterogeneous task graph under budget and latency, with paid verification. Its abstract does not frame this as device versus cloud. Both are low-overlap and only adjacent to SEAM.

### Cited Findings
- EdgeAgent (Long, Wei, Wu, Wei, Huang, Du; Sun Yat-sen Univ. and China Mobile; submitted 2 Oct 2026). On-device multi-agent inference on CPU-GPU unified memory. The abstract says memory-bound decode causes severe bus contention that breaks naive CPU-GPU co-execution. It proposes zero-copy UMA-aware tensor parallelism, adaptive speculative draft budgets, and suspend-and-yield during tool stalls. On an Apple M4, UMA-aware execution alone gives 1.29× over batched speculative decoding, and the full system 1.77× under extreme tool latencies. — [arXiv abs](https://arxiv.org/abs/2610.03394)
- JOVE (Zhang, Kim, Cha, Chan, Swami, De Veciana, Vikalo; submitted 2 Oct 2026). Online joint assignment of executor LLMs and selection of outputs for paid verification, solved with per-query MILPs under a long-term budget and per-query latency constraint, with sublinear quality-learning regret. The abstract notes that execution alone does not reveal output correctness. It reports cost and latency reductions of at least 3.17× at competitive accuracy across four reasoning benchmarks. — [arXiv abs](https://arxiv.org/abs/2610.03296)

### Inferences
- EdgeAgent: all scores 0. It is relevant to SEAM only as evidence that CPU-GPU placement and co-execution on unified-memory SoCs is a first-order performance knob, which supports SEAM's placement axis as a system concern.
- JOVE: PFR = 1. "Execution does not reveal correctness" is the silent-failure motivation, handled by learning quality estimates from verification, not from a hardware feasibility boundary. Other scores 0.

### Gaps
- Only abstracts were read. JOVE's full text was not checked for whether its "heterogeneous LLMs" include edge devices.

## Q5. Title scan for other very recent close competitors (Oct 2026)

### Takeaway
One new, close hybrid competitor surfaced: EdgeWise (arXiv 2610.17560, NVIDIA, 13 Oct 2026). It runs on a real edge device (DGX Spark) with cloud delegation, and studies what context to pass to the cloud. It does not vary hardware configuration, except for showing comparable results on A100 and DGX Spark, both at BF16 with ample memory. STEPGATE (2610.07816) came up again but was covered in an earlier sweep (new_hybrid_config_papers.md). Searches for AI-PC, NPU or OpenVINO hybrid agent studies found nothing new from October 2026.

### Cited Findings
- EdgeWise metadata: Shi, Jiang, Hachiuma, Fu, Lee, Belcak, Muralidharan, Agarwal, Tang, Dantrey, Molchanov, Patney, Radhakrishnan. Submitted 13 Oct 2026. — [arXiv abs](https://arxiv.org/abs/2610.17560)
- Setup: Qwen3.5-9B is the local SLM and GPT-5.5 (xhigh) or Claude Opus 4.8 (xhigh) the cloud LLM, on Terminal-Bench 2.1 and SWE-ReBench with Terminus2 or OpenHands, up to 80 turns. RL self-delegation was trained on 40 A100-80GB GPUs. — [arXiv html](https://arxiv.org/html/2610.17560)
- Random-delegation observation: at a 40% cloud-step ratio, performance varies widely across random allocations. Some allocations match full-LLM performance while cutting cost by at least 25%. — [arXiv html](https://arxiv.org/html/2610.17560)
- Results (Table 1): self-delegation versus vanilla LLM. On Terminal-Bench 2.1 with GPT-5.5, Pass@3 is 82.02 at $181.88 vs 82.02 at $279.73 (−34.98% cost). On SWE-ReBench with GPT-5.5, Pass@3 is 66.36 at $283.02 vs 63.64 at $598.08 (−52.68%). With Opus 4.8 on SWE-ReBench, cost falls 62.14% at −2.73 Pass@3. Average cost reduction is 46%. Baselines include MTRouter, STEER, RSD and random. — [arXiv html](https://arxiv.org/html/2610.17560)
- The SLM is a poor judge of when to escalate: as the binary-delegation judge, Qwen3.5-9B gets 50.56% Pass@1, versus 70.79% with Qwen3.8-27B and 71.91% with GPT-5.4-mini. Vanilla Qwen3.5-9B alone gets 19.10%. — [arXiv html](https://arxiv.org/html/2610.17560)
- Context sent to the cloud (§4.3): five handoff configurations (full history, previous step, recent k=3, no SLM reasoning, relevant steps). Full history performs best but costs most, and dropping the SLM's reasoning is second best at lower cost. The paper concludes context should not be compressed indiscriminately at model transitions. — [arXiv html](https://arxiv.org/html/2610.17560)
- Real device (Appendix G.2): Qwen3.5-9B on one DGX Spark, vLLM 0.19.1, BF16, GPU memory utilization 0.65. About 78.7 GB of unified memory is reserved (16.8 GiB weights, about 57.1 GiB KV). Throughput is 11.19 tok/s. Terminal-Bench 2.1 tasks take 11.72 min on average (median 8.30 min). Pass@3 is comparable to the A100 runs, with about 50% cost reduction against vanilla LLM. — [arXiv html](https://arxiv.org/html/2610.17560)
- Other search hits not new or not hybrid-close: STEPGATE 2610.07816 (covered in an earlier sweep); KV-quantization papers 2610.15384 and 2610.03027 (local compression only). — [STEPGATE](https://arxiv.org/abs/2610.07816); [2610.15384](https://arxiv.org/abs/2610.15384); [2610.03027](https://arxiv.org/abs/2610.03027)

### Inferences
- EdgeWise scores: C1 = 0. C2 = 0. C3 = 0. C4 = 0. JPR = 0. PFR = 1: the external judge decides before each step from history, but on action type (Write/Edit), not on feasibility. The 9B-as-judge result (50.56% vs about 71%) is further evidence that local models cannot tell when they are failing. SWC = 1: it studies how much context to hand off and the resulting cost, but does not price switches.
- EdgeWise is the most "real-device" October hybrid paper, and it reports that the same model gives comparable Pass@3 on A100 and DGX Spark. A reviewer could read that as hardware not mattering. SEAM should pre-empt this: both runs used BF16 weights with about 57 GiB of KV headroom, so neither was memory-constrained. SEAM's effects appear in the 16 GB / constrained-retention regime and when KV precision, weight precision, placement and residency change. EdgeWise holds all of these fixed.
- Across all October papers, no paper varies placement (CPU/GPU/NPU), KV precision, weight precision, session residency or context retention inside a hybrid loop. None runs on an Intel AI PC or OpenVINO. None attributes cloud spend to device configuration. SEAM's C1, C4 and the hardware-configuration form of C3 remain unclaimed as of 15 Oct 2026.

### Gaps
- The arXiv cs.AI and cs.MA October listings were not exhaustively scanned. The title scan relied on 6 web searches.

## Summary matrix (0–3)

| Paper | Hybrid? | Device knobs varied | C1 | C2 | C3 | C4 | JPR | PFR | SWC |
|---|---|---|---|---|---|---|---|---|---|
| 2610.17816 EC2-Bench | Yes (simulated edge, FLOPs) | Edge model size only | 1 | 1–2 | 2 | 0 | 1 | 1 | 1 |
| 2610.14209 SLM interpreter | Yes (V100 "device") | SLM size, planner | 0 | 0 | 0 | 1 | 0 | 1 | 1 |
| 2610.19292 Whose Turn | No (cloud to cloud) | Pair, reasoning effort | 0 | 2* | 1 | 0 | 2* | 1 | 3* |
| 2610.17560 EdgeWise (new) | Yes (A100 + DGX Spark) | Handoff context, judge, threshold; A100 vs Spark | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| 2610.03394 EdgeAgent | No (on-device only) | UMA CPU-GPU execution | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2610.03296 JOVE | Not device-cloud (abstract) | Executor allocation | 0 | 0 | 0 | 0 | 0 | 1 | 0 |

*Cloud-only setting. 19292's switch-cost formalism preempts "we are first to price switch cost" in general but not the hybrid device-side re-prefill asymmetry.
