# Related-work search log

Search date for every section below: 2026-09-23. This file is the log required
before any "first" claim. Do not strengthen a verdict without a new dated section.

## Config-aware routing

- Claim: hardware-aware routing of local vs cloud execution.
- Date searched: 2026-09-23
- Verdict: NARROWED to a single consumer device to cloud, with static config axes.
- Allowed wording: single consumer device -> cloud with static config axes.
- Forbidden wording: "first hardware-aware routing".
- Citations: 2608.14575 (HW-Router), 2604.10907 (RouterWise), 2607.18253, 2502.11007, 2509.24050.

## Schema and context retention

- Claim: schema or context retention as a method contribution.
- Date searched: 2026-09-23
- Verdict: NARROWED to the hardware consequence (limit, TTFT, cloud $).
- Allowed wording: the hardware consequence of retention (limit, TTFT, cloud $).
- Forbidden wording: none recorded on 2026-09-23.
- Citations: 2604.21816 (Tool Attention), 2606.15508 (ToolMenuBench), 2510.00615 (ACON), "The Complexity Trap", 2608.16370 (compression costs hidden by task completion; report more than pass/fail).

## Tier penalty as a memory effect

- Claim: a tier penalty is caused by memory.
- Date searched: 2026-09-23
- Verdict: SURVIVES as a measured platform-dependent number only.
- Allowed wording: a measured platform-dependent number.
- Forbidden wording: "we discover memory causes".
- Citations: none recorded on 2026-09-23.

## Phase split on unified memory

- Claim: novelty for splitting prefill and decode across devices on unified memory.
- Date searched: 2026-09-23
- Verdict: DEAD as a novelty claim. AMD Lemonade ships NPU prefill + iGPU decode. HET-1 stays as a measurement of Intel handoff cost.
- Allowed wording: HET-1 measures Intel handoff cost.
- Forbidden wording: phase split on unified memory as a novelty claim.
- Citations: AMD Lemonade (NPU prefill + iGPU decode). No paper id recorded on 2026-09-23.

## Competitors to cite

- Claim: on-device and AI-PC agent characterization.
- Date searched: 2026-09-23
- Verdict: CITE. Not a novelty claim.
- Allowed wording: cite these systems for what they measured.
- Forbidden wording: "first characterization of on-device agents".
- Citations: 2605.10380 Agent-X; 2608.25053 Hydra (1k-5k inputs, roughly linear TTFT); 2603.23640; 2508.06753 (AI-PC hybrid).
- Correction 2026-10-15: 2508.06753 (Georganas et al., ultra-low-bit
  quantized models on Intel client parts) is local-only, not AI-PC hybrid as
  logged on 2026-09-23 (docs/literature/2026-10-15/notes/known_hybrid_papers.md).
- Added 2026-10-15 (sweep below): EC2-Bench 2610.17816; STEPGATE 2610.07816;
  CARGO 2607.20481; ECO-LLM 2507.09003; Edge-First 2505.16508; HybridInfer
  2609.30270; "Whose Turn Is It?" 2610.19292; EdgeWise 2610.17560; SLM
  interpreter 2610.14209; "Loud Failures, Quiet Failures" 2610.10062; routing
  survey 2603.04445; Hera 2605.24598 (step-level device-cloud agent routing;
  not HERA 2504.00434, a different paper). Also ConfigSpec 2604.09722,
  RouterWise 2604.10907, HW-Router 2608.14575 (already logged) as wording
  constraints. What each one forces is in the 2026-10-15 section.

## Mechanism references

- Claim: mechanism citations for allocation, GPU memory, speculative decoding, and NPU failure modes.
- Date searched: 2026-09-23
- Verdict: RECORDED.
- Allowed wording: cite the issue or paper for the mechanism it names.
- Forbidden wording: none recorded on 2026-09-23.
- Citations: OpenVINO #37501 (logits buffer alloc); Intel Shared GPU Memory Override; 2503.03777 FlexInfer; OpenVINO discussion #36484 (NPU/CPU draft speculative decoding); openvino.genai #3255 (NPU garbage past prompt limit); openvino.genai #4367 (CB prefix-cache greedy divergence); openvino #35641 (NPU int8 crash).

## Q-1 anomaly

- Claim: published Qwen3-4B 35.25% and Qwen3-8B 34% on multi_turn_base.
- Date searched: 2026-09-23
- Verdict: TO CONFIRM. Source URL not yet recorded.
- Allowed wording: quote 35.25% and 34% only with this TO CONFIRM mark until the URL is recorded.
- Forbidden wording: citing those percentages as a confirmed published source.
- Citations: source URL NOT YET RECORDED.

## DEMO-2 default-control runtime settings

- Claim: the "default hybrid" control uses runtime defaults: a 4096-token
  context window, OpenVINO GenAI default KV precision, backend and device.
- Date searched: 2026-10-14
- Verdict: PARTLY CONFIRMED (per item below).
- Findings:
  - 4096 window: CONFIRMED. Ollama FAQ (https://docs.ollama.com/faq): "By
    default, Ollama uses a context window size of 4096 tokens." Third-party
    guides and the Open WebUI docs note older builds used 2048.
  - GPU KV precision: CONFIRMED for 2025.1 only. OpenVINO 2025.1 release
    notes
    (https://www.intel.com/content/www/us/en/developer/articles/release-notes/openvino/2025-1.html):
    "Int8 compressed KV-cache is enabled for LLMs by default on all GPU
    platforms." The OpenVINO nightly Optimum Intel page, as summarized by
    search, says GPU KV quantization is default only on platforms without
    XMX. That conflicts, and the page text was not read. The default on
    2026.2.1 (our runtime) is NOT CONFIRMED; it must be read back on the
    host.
  - LLMPipeline backend: CONFIRMED for 2025.1 ("LLMPipeline now uses Paged
    Attention backend by default.", same release notes).
  - Prefix caching default for LLMPipeline: NOT FOUND. The SchedulerConfig
    docs describe enable_prefix_caching without a default in the text read;
    the OVMS docs give false for the server, which is not LLMPipeline.
  - Default device: CONFIRMED for the GenAI chat sample
    (openvino.genai samples/python/text_generation/chat_sample.py, master):
    `parser.add_argument("device", nargs="?", default="CPU", ...)`.
- Allowed wording: "Ollama's default 4096-token window"; "the GenAI chat
  sample's default device (CPU)"; "int8 KV by default on GPU as of OpenVINO
  2025.1".
- Forbidden wording: "the OpenVINO 2026.2 GPU default is int8 KV" and any
  claim about the default prefix-caching state, until read back on the host.

## 2026-10-15 hybrid configuration sweep

- Date searched: 2026-10-15 (7 sweeps, about 60 papers and reports, 27 true
  hybrid device/edge-cloud papers).
- Report: docs/literature/2026-10-15/LIT_CHECK_HYBRID_CONFIG_20261015.md.
  Sweep notes: docs/literature/2026-10-15/notes/*.md (known_hybrid_papers,
  new_hybrid_config_papers, october_gap_papers, routing_silent_failure,
  local_only_inspiration, verify_failure_regimes_quality,
  verify_intel_measurements).
- Headline: none of the 27 hybrid papers sweeps placement, KV precision,
  weight precision, residency or context retention inside a hybrid loop;
  none runs an Intel AI PC with OpenVINO; none splits cloud spend by cause.
  These are absences in a search, not proofs of absence (MLSys, MobiSys and
  MobiCom 2026 not scanned title by title; October arXiv covered by six
  searches; three close papers appeared 9-13 Oct).
- Supersedes for wording: the 2026-09-23 "Config-aware routing" section's
  claim name ("hardware-aware routing") is now forbidden wording (below).
- Verdicts come from the report's closeness matrix (0-3; no hybrid cell
  reaches 3) and its wording table.

### H-A attribution (configuration-caused cloud spend; matrix C1)
- Verdict: NARROWED. Highest overlap 2 (ConfigSpec, HybridInfer,
  Edge-First); Edge-First and HybridInfer say device limits cause offload,
  qualitatively, with no same-task counterfactual.
- Allowed: "We quantify the share of cloud spend that disappears under an
  alternative device configuration at fixed task difficulty."
- Forbidden: "first to show device limits cause escalation"; any unquantified
  "configuration causes cloud spend".
- Citations: 2505.16508 Edge-First; 2609.30270 HybridInfer; 2604.09722
  ConfigSpec; 2610.17816 EC2-Bench (model-size version of cloud spend
  falling, $12.80 at 2B to $5.29 at 27B, not framed as configuration).

### H-B lever size (configuration vs routing policy; matrix C2)
- Verdict: NARROWED. EC2-Bench (1-2) and STEPGATE show model-size dominance
  over routing; ECO-LLM (2) shows it for application-pipeline knobs;
  RouterWise (2) and Whose Turn (2) in datacenter / cloud-only settings.
- Allowed: "With the local model held fixed, within-model hardware
  configuration (placement, KV/weight precision, residency, retention)
  moves cost and quality more than routing policy."
- Forbidden: "configuration matters more than routing" without "model held
  fixed"; any claim that covers model choice or pipeline knobs.
- Citations: 2610.17816 EC2-Bench; 2610.07816 STEPGATE; 2507.09003 ECO-LLM;
  2604.10907 RouterWise; 2610.19292 Whose Turn.

### H-C rank reversal (matrix C3)
- Verdict: NARROWED. Model-driven reversal is published (EC2-Bench,
  STEPGATE, CARGO, each 2). Reversal from hardware configuration with the
  model fixed is open.
- Allowed: "Routing-policy behaviour and ranking are not portable across
  placements and precision settings for the same model." Back it with a
  matched-rate random-escalation baseline and rank confidence intervals.
- Forbidden: "router rankings flip across devices" without "same model";
  any rank claim without the random-escalation-at-matched-rate baseline.
- Citations: 2610.17816; 2610.07816 (random 90.8% beats learned 90.4% at
  3B); 2607.20481 CARGO; 2609.30270 (cross-device transfer named as open).

### H-D substitution (configuration vs hardware purchase; matrix C4)
- Verdict: OPEN. Highest overlap 1 (Edge-First, ConfigSpec, Splitwise,
  adaptive split 2511.04002, carbon-aware 2609.13559, on-device agents
  2511.03728).
- Allowed: "a configuration change on 16 GB substitutes for a 64 GB
  purchase on <workload>, at <passes>" with run_ids; cite hardware prices.
- Forbidden: any BOM figure without a cited price; generalising past the
  measured workload.
- Citations: 2505.16508; 2604.09722; 2503.03777 FlexInfer (memory-budget
  sweep method).

### Joint provisioning + routing (Paper 2; matrix JPR)
- Verdict: NARROWED. RouterWise (2) owns joint deployment and routing for
  datacenters (no cost, no quantization or KV); Whose Turn (2) shows picking
  the cheaper configuration can Pareto-dominate every routed policy,
  cloud-only.
- Allowed: "Joint device memory/BOM provisioning and routing for hybrid
  device-cloud with a priced cloud tier."
- Forbidden: "joint resource allocation and routing" (unqualified); "first
  joint deployment and routing".
- Citations: 2604.10907 RouterWise; 2610.19292 Whose Turn; 2606.09613
  AgentServeSim (residency, datacenter simulator).

### Predictive feasibility routing under silent failure (Paper 2; PFR)
- Verdict: NARROWED. No hybrid paper above 1-2, but "routers are reactive"
  is contradicted (survey 2603.04445: pre-generation routers exist; Hera
  2605.24598: one-shot decisions before inference); probe routers reach
  about 65-69 AUROC (RouterXBench 2602.11877).
- Allowed: "Pre-generation routers predict capability from query text and
  assume faithful execution; post-generation routers react to outputs;
  neither models a runtime/hardware feasibility boundary." "Indistinguishable
  at runtime" only for the truncation-induced regime, next to a
  probe/uncertainty baseline.
- Forbidden: "existing routers are reactive"; "hardware-aware routing" (use
  "configuration-aware" or "feasibility-aware"; HW-Router 2608.14575 holds
  the term and assumes quality is hardware-independent); "silent failures
  are undetectable" without the regime restriction.
- Citations: 2603.04445; 2605.24598 Hera; 2404.14618 Hybrid LLM;
  2602.11877 RouterXBench; 2608.14575 HW-Router; 2610.10062 Loud/Quiet
  failures (BFCL multi-turn: 91.3% of loud faults flagged vs 58.8% of quiet;
  fault-free runs agree on end state 63.3%, so report run-to-run variance).

### Switch cost (Paper 2; SWC)
- Verdict: PRE-EMPTED for "first to price switch cost" (Whose Turn
  2610.19292 and vLLM SAAR blog both reach 3, cloud-only). The device-cloud
  asymmetry is OPEN (no hybrid paper models handoff cost).
- Allowed: "First to price the device-cloud switch asymmetry: uncached
  full-context re-send upward, configuration-dependent re-prefill downward."
- Forbidden: "first to price switch cost"; "first to model switching cost".
- Citations: 2610.19292; SAAR https://vllm.ai/blog/2026-06-02-session-aware-agentic-routing;
  2605.24598 Hera (objective does not penalise handoffs); 2509.24050;
  2609.30270; 2605.30102.

### ISPASS OL (operating limit)
- Verdict: OPEN as a hybrid/consumer AI PC characterization (highest
  overlap 1: Edge-First, Splitwise, adaptive split, Minions, on-device
  agents).
- Allowed: six-axis characterization on Intel AI PC / OpenVINO with the
  binding constraint per configuration; "platform speed is not
  configuration" (TMO 2502.11007 and EdgeWise 2610.17560 report
  device-insensitivity only across speed, never under memory limits).
- Forbidden: "first characterization of on-device agents" (2026-09-23 rule
  stands); using TMO/EdgeWise as counter-evidence without the speed vs
  capacity distinction.
- Citations: 2505.16508; 2512.23310; 2511.03728; 2502.11007; 2610.17560.

### ISPASS FR (failure regimes)
- Verdict: OPEN, wording NARROWED. Highest hybrid overlap 1 (HybridInfer,
  Rainone et al.: out-of-context errors loud). The regimes depend on runtime
  policy x memory architecture, not memory architecture alone.
- Allowed: "a runtime policy x memory architecture grid with named runtime
  versions"; "unified memory removes the capacity cliff but not
  driver-imposed allocation cliffs".
- Forbidden: "three failure regimes selected by memory architecture" without
  the runtime; "llama.cpp truncates silently" without a build number
  (current llama-server b7062 returns HTTP 400; b6721 truncated); "NVIDIA
  discrete GPUs raise an explicit error" without the runtime (Ollama
  offloads layers to CPU; vLLM refuses at startup); "Ollama default context
  is 4096" without version and VRAM tier (tiered since Feb 2026: <24 GiB 4k,
  24-48 GiB 32k, >=48 GiB 256k; num_ctx via /v1 silently dropped).
- Citations: https://docs.ollama.com/context-length; llama.cpp #17284 and
  PR #16391; vLLM #19407; 2605.30102; 2609.30270; Desbiens blog (practitioner).

### ISPASS RET (retention)
- Verdict: NARROWED. On-device agents 2511.03728 (2) studies context
  management on a phone; observation masking and ACON report cost and
  peak-token cuts.
- Allowed: "consistent with observation masking (about 2x cost cut) and
  ACON (26-54% peak-token cut), measured at a fixed small window on
  memory-capped devices"; the hardware consequence of retention (limit,
  TTFT, cloud $), as in 2026-09-23.
- Forbidden: retention as a new method; "retention gives N x usable context"
  stated without that framing.
- Citations: 2511.03728; 2508.21433 (Complexity Trap); 2510.00615 (ACON);
  2610.07816 STEPGATE (handoff context); 2610.17560 EdgeWise.

### "No single configuration wins" and "prior work holds configuration fixed"
- "No single configuration wins": cite ConfigSpec 2604.09722 as precedent
  (hybrid speculative decoding, lossless, so no quality or routing); claim
  it for quality- and feasibility-changing configurations only.
- "Prior work holds configuration fixed": supported by this search of hybrid
  papers only. Keep this section's citation next to it.

### Measurement re-checks raised (see registry rows KV-DEFAULT-READBACK,
PREFIX-CACHE-AUDIT, V5-CAL-2, NPU-DRIVER, NPU-PROMPT-PLAIN, B390-OOR,
BFCL-BASELINE, INT4-SCHEME)
- OpenVINO 2026.2.1 GPU KV default: "dynamic" is the property placeholder;
  for PagedAttention models with 4-bit weights the plugin resolves u4.
  [CORRECTED 2026-10-16: wrong. 2026.2.1 hard-codes auto_enable_4bit_kv =
  false, so the PA default is i8; u4 becomes automatic only in 2026.3.x.
  See the 2026-10-16 section.]
  Forbidden until read back from the compiled model's key_cache/value_cache
  ports: "the default KV is u8/f16"; "dynamic means no compression".
- LLMPipeline with no SchedulerConfig: prefix caching ON, batch tokens
  unlimited; a bare SchedulerConfig(): prefix caching off,
  max_num_batched_tokens 256. Forbidden: "the runtime default is prefix
  caching off" (the 2026-10-14 readback read the struct default).
- B390 CL_OUT_OF_RESOURCES: the ~4 GB per-allocation cap applies to pre-Xe2;
  probably not the cause on Xe3. Cause open.
- BFCL Qwen3-4B: public 22.1% multi-turn (FC) from a secondary aggregator
  (BenchmarkList), not the Gorilla leaderboard. TO CONFIRM.

### Sources read only via abstract or a secondary source (re-read before citing)
Copied from the report. Nothing below is cited in a paper on this evidence.

| Source | How it was read |
|---|---|
| Carbon-aware function calling 2609.13559 | Abstract only |
| Adaptive split computing 2511.04002 | Abstract only |
| Quantize-Sample-and-Verify 2507.00605 | Abstract only |
| Speculation at a Distance 2606.25091 | Abstract only |
| EdgeAgent 2610.03394 | Abstract only |
| JOVE 2610.03296 | Abstract only |
| Apple Foundation Models report 2507.13575 | Abstract only |
| HW-Router 2608.14575 | Abstract page in sweep 1, partial HTML in sweep 3; the PDF returned no text |
| Fang et al. 2509.24050 | Abstract only in sweep 1, HTML v4 in sweep 3; sweeps disagree on the venue (none vs ICML 2026) |
| 2607.18253 | Truncated before its results |
| MALBO | Truncated |
| "Flat Score, Amplified Failures" 2607.27275 | DevelopersDigest summary only (PDF not machine-readable) |
| Cross-model KV transfer 2608.03893 | Emergent Mind summary |
| Compression Breaks Discipline | NeurIPS poster page |
| Qwen3-4B BFCL v4 scores | BenchmarkList aggregator, not the Gorilla leaderboard |
| Ollama default-context history, /v1 discard, log levels | Particula Tech's reading of Ollama source |
| Apple unified-memory spill behaviour | LocalAIMaster blog |
| Ollama 200-OK truncation | Desbiens practitioner blog |
| Pipeline Shards 2608.19147 | KV-hint finding is an extractor paraphrase |
| LaTune, llm-tuna, MTRouter, Workload-Router-Pool, TRACE-ROUTER, Agentic Routing, Agent Memory Below the Prompt, FlexSpec, GPU Goldmines | Seen only as search results |
| RouteLLM, Lost in the Middle | Not re-read |
| Nguyen et al. on remote-fetch energy | Known only second-hand |
