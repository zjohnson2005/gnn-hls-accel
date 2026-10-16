# Agent- and Hybrid-Level Levers for the Tuned Configuration (cloud cost, local latency, tool-calling quality)

Scope note: hybrid demo = local Qwen3-4B INT4 (OpenVINO, Intel AI PC) escalating to Claude Sonnet on BFCL v4 multi-turn. Each lever is tagged:
- **[HW-CONFIG]** device "hardware configuration" (placement, KV/weight precision, residency, context window/retention, model tier)
- **[AGENT/SW]** software / agent / harness-level
- **[CLOUD]** cloud-side, orthogonal to the device config (apply equally to both arms or exclude from the comparison)

Access problems during research (the report writer should know): arXiv rate-limited (HTTP 429) the fetches of **EdgeWise (arxiv.org/html/2610.17560 and /abs/2610.17560)**, **EC2-Bench full text (arxiv.org/html/2610.17816)**, and the full ACON tables. The PDFs for 2609.23742 and 2608.13959 returned no machine-readable text. The Qwen function-calling docs (qwen.readthedocs.io) and the live BFCL leaderboard table (rendered by JS) could not be read. Claims from these sources appear only where another page provided them; otherwise they are listed as gaps.

---

## Q1. Prompt/format effects on small-model BFCL multi-turn accuracy (FC vs prompting, Hermes/xLAM/Qwen formats, thinking on/off, why the harness gets 10% vs 22–35%)

### Takeaway
BFCL multi-turn scoring is unforgiving and depends on the harness. An entry passes only if **both** a state check and a response check pass on **every** turn. A turn ends at the first step with no decodable function call. FC and prompting models are fed differently (tool results come back under the `user` role in prompting mode, and held-out functions arrive in a user message). So parser, role, and end-of-turn differences alone can plausibly explain a 2–3x gap. Separately, the public 22% figure is for a **different checkpoint** (Qwen3-4B-Instruct-2507) than the hybrid-thinking Qwen3-4B used with thinking off. I could not verify the exact leaderboard numbers or any measured effect of thinking on/off from a primary source.

### Cited Findings
- BFCL multi-turn correctness: "An entry is marked as correct if it passes *both* checks in *all* turns." The checks are state-based (backend state, ignoring `_`-prefixed private attributes) and response-based (the execution path must contain the minimal viable path; extra calls are allowed because matching is subset-based). — [BFCL v3 multi-turn blog](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html)
- End-of-turn rule: "If the model doesn't output any valid function calls in a step, we consider this the end of the current turn". This includes undecodable outputs, which the blog says is common for prompting models. — [BFCL v3 multi-turn blog](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html)
- Step limit: more than 20 steps in one turn force-terminates the turn, marks the entry incorrect, and skips later turns. Typical cause is looping (e.g., repeated `ls`). — [BFCL v3 multi-turn blog](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html)
- FC vs prompting handling: in Missing Functions, FC models get the new functions appended to `tools`, while prompting models get them in a user message. Prompting models get execution results under the `user` role, since they lack a `tool` role. — [BFCL v3 multi-turn blog](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html)
- Category composition: Base (200), Missing Parameters (200), Missing Functions (200), Long-Context (200), Composite (200). — [BFCL v3 multi-turn blog](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html)
- Leaderboard definitions: "FC = native support for function/tool calling. Prompt = walk-around for function calling, using model's normal text generation capability." Overall = unweighted average of sub-categories. Last updated 2026-04-12. — [BFCL V4 leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html)
- BFCL failure modes from the official error analysis: missed implicit actions (fueling without checking the level), acting without checking state, unnecessary planning (re-authenticating), and looping until the step cap. — [BFCL v3 multi-turn blog](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html)
- xLAM-2 serving requires its own tool parser (`--tool-call-parser xlam`, plugin `xlam_tool_call_parser.py`) and `vllm>=0.6.5`, "as earlier versions degrade Qwen-based models". BFCL numbers on the card exist only as an image. — [Salesforce Llama-xLAM-2-8b-fc-r card](https://huggingface.co/Salesforce/Llama-xLAM-2-8b-fc-r)
- The on-device context paper reports a 3B xLAM-2 base baseline at an initial prompt of 3,200 tokens, and a "qualitative test on Qwen-3 4B". — [Vijayvargiya & Lokesh, 2511.03728](https://arxiv.org/html/2511.03728v1)
- SECONDARY / weak: a vendor blog gives Qwen3-4B-Instruct-2507's BFCL v4 composite as "high 80s". It labels that figure "illustrative", draws it from single-turn and parallel subsets, and gives no multi-turn numbers. The author sells fine-tuning tooling. — [Ertas AI blog](https://www.ertas.ai/blog/on-device-tool-calling-2026-qwen3-gemma4-phi4)
- SECONDARY: an aggregator lists Qwen3.5 (not Qwen3) BFCL-v4 overall as 9B 0.661 and 4B 0.503, and tau2-Telecom for Qwen3 4B-2507 as 27% (citing ToolMind 2511.15718). — [d-central.tech](https://d-central.tech/local-llm-agent-capability/)

### Inferences
- **Checkpoint mismatch is a first-order explanation.** The leaderboard's ~22% multi-turn (26.5% base) is for Qwen3-4B-Instruct-2507 (FC). The harness runs the April-2025 hybrid Qwen3-4B with thinking off, which is a different model. A fair "tuned profile" either swaps to the 2507 Instruct checkpoint (a model-tier/weights choice, **[HW-CONFIG]**) or should not cite 22% as the reachable target.
- **Harness levers to audit [AGENT/SW]:**
  1. Tool-result role. The 4B model may follow `tool`/`<tool_response>` results better than results under `user`.
  2. The end-of-turn rule. Any malformed `<tool_call>` ends the turn, so a parser stricter than BFCL's converts near-misses into turn ends.
  3. Missing-function injection: tools list vs user message.
  4. The 20-step cap versus the harness's own step budget.
  5. Whether the INT4 OpenVINO chat template matches the HF Qwen3 template exactly. Template drift is a known degradation source; the xLAM card warns that old vLLM degrades Qwen-based models.
- The ~35% "XLAM-format arm" in the registry likely reflects a fine-tuned xLAM-family model or the xLAM parser, not prompt format alone. Before attributing the gain to format, check whether that arm uses xLAM-2 weights (**[HW-CONFIG]**, model tier) or only the format (**[AGENT/SW]**).
- Since ≥85% of non-escalated local failures are silent (well-formed but wrong), format fixes alone will move few entries. BFCL errors are mostly state and planning errors (missed implicit actions, redundant actions), not parse errors.

### Gaps
- Exact BFCL v4 leaderboard rows for Qwen3-4B, Qwen3-8B, Qwen3-4B-Instruct-2507 (FC vs Prompt) and xLAM-2-3b/8b multi-turn: the leaderboard table is JS-rendered and could not be read. The xLAM-2 BFCL table is image-only. The registry's 22%/26.5%/35% values remain unverified here. Check the [BFCL-Result repo](https://github.com/HuanzhiMao/BFCL-Result) or `data_overall.csv` directly.
- No primary source found measuring Qwen3 enable_thinking on vs off on BFCL multi-turn.
- The Qwen function-calling docs (Hermes-style template recommendation and handling of reasoning content in history) could not be fetched. Treat any claim about Qwen's official format guidance as unverified.
- "Compression Breaks Discipline" was not found by search. The closest hit was "Which Decisions Low-Bit Quantization Breaks" ([2608.06564](https://arxiv.org/html/2608.06564v4)), which was not read. Hammer and ToolACE numbers were not retrieved.

---

## Q2. Observation masking / context management (Complexity Trap, ACON, on-device adaptive context, LLMLingua, etc.)

### Takeaway
Simple observation masking is the strongest cost-per-accuracy baseline in the literature. It roughly halves cost while matching or beating LLM summarization (Complexity Trap, SWE-bench). ACON-style learned compression cuts peak tokens 26–54% and *improves* small-model accuracy. The on-device paper shows that structured state plus compact schemas gives 6x smaller initial context, 10–25x slower context growth, and ~5x faster TTFT. The measured result here (OBS_MASK K=1024: −40% cloud $/task, hybrid 4→6 passes) is consistent with all three.

### Cited Findings
- Complexity Trap (SWE-agent, SWE-bench Verified, 5 model configs): observation masking "halves cost relative to the raw agent" while "matching, and sometimes slightly exceeding, the solve rate of LLM summarization". Initial evidence says it generalizes to OpenHands. — [arXiv 2508.21433 abstract](https://arxiv.org/abs/2508.21433)
- Complexity Trap parameters: masking keeps a rolling window of **M=10 turns**. LLM-Summary uses N=21 turns before summarizing with M=10 tail turns kept (the hybrid section uses N=43). Trajectory cap is 250 turns. — [alphaXiv overview of 2508.21433](https://www.alphaxiv.org/overview/2508.21433) (secondary summary of the paper)
- Qwen3-Coder 480B: masking is 52% cheaper than the raw agent with +2.6 pp solve rate. The hybrid (masking then summarization) is 7% cheaper than masking and 11% cheaper than summarization. LLM-Summary lengthens trajectories by 13–15% (Gemini 2.5 Flash, Qwen3-Coder 480B). Summary calls cost up to 7.2% of instance cost. — [alphaXiv overview](https://www.alphaxiv.org/overview/2508.21433) (secondary)
- ACON: "reduces memory usage by 26-54% (peak tokens) while largely preserving task performance". It preserves ">95% of accuracy when distilled into smaller compressors". It improves smaller LMs by "32% on AppWorld, 20% on OfficeBench, and 46% on Multi-objective QA" (relative vs absolute not stated in the visible text). It "even improves accuracy on smaller models (gpt-4.1-mini and Qwen-14B)". Baselines: No Compression, FIFO, Retrieval, LLMLingua, Prompting. AppWorld gpt-4.1 no-compression: 56.0% avg accuracy, 16.14 steps, 9.93k peak input tokens. — [ACON 2510.00615v1](https://arxiv.org/html/2510.00615v1)
- On-device adaptive context (CMU/Samsung): a Context State Object (append-only KV log updated by a ~119M-param State-Tracker LoRA) replaces raw history. Compact schemas cut ~40% tokens per tool (121→72). Just-in-time schema passing is used. Initial prompt drops from 3,200 (xLAM-2) to 400 tokens (Tool-Efficient). Memory-Efficient context grows 100–200 tokens over 25 turns (~10x less than baseline). In cloud-delegation scenarios the baseline grows to 10–12k tokens vs ~500 tokens (>20x less). TTFT is ~5x faster on a CPU Galaxy S25. Cost is ~80 MB and ~500 ms per turn for the CSO update. F1 for the Combined model: 0.99 / 0.93 / 0.94 (cloud-tool / multi-tool / on-device+cloud) vs base xLAM-2 3B at 0.41 / 0.87 / 0.57. The paper's headline figures (6x vs 8x, "~25% of baseline") don't fully agree with each other. — [arXiv 2511.03728v1](https://arxiv.org/html/2511.03728v1)
- Quote: tool-schema verbosity "floods the context with thousands of tokens". — [arXiv 2511.03728v1](https://arxiv.org/html/2511.03728v1)
- Loud vs quiet failures: agents detect loud tool faults 91.3% of the time but quiet (well-formed, wrong-value) faults only 58.8%, with a 26.8% false-alarm rate. The authors recommend validating values "at the point where a value enters the agent's context". — [Loud Failures, Quiet Failures, 2610.10062](https://arxiv.org/html/2610.10062)

### Inferences
- **Classification:** OBS_MASK is best tagged **[AGENT/SW]** but sits on the boundary with **[HW-CONFIG] "context window/retention"**. If the demo frames "retention" as a device knob, OBS_MASK K belongs there. Since it also cuts cloud tokens in the cloud-only arm, apply it to both arms or report it separately.
- **Truncate-at-insertion is the cache-friendly variant.** OBS_MASK as implemented truncates each observation once, at insertion, so the message prefix stays byte-stable. That is compatible with Anthropic prompt caching (Q5). A Complexity-Trap-style rolling window (M=10 turns), where old observations are replaced by placeholders as the window slides, rewrites earlier messages every turn and **invalidates the message cache from the first changed block onward**. Recommendation: keep insertion-time truncation, and if a window is added, mask in large stable chunks.
- **Best K:** no source gives an optimal per-observation token cap for BFCL. The published "best" is window-based (M=10 turns), not size-based. BFCL long-context entries deliberately inject large distractor data, so K=1024 is plausibly near a sweet spot, but only a sweep (e.g., 512/1024/2048) on the same 15 tasks would settle it.
- ACON's finding that compression *improves* small-model accuracy matches hybrid passes going 4→6. Shorter, cleaner context helps the 4B model as well as cost.
- A structured state object (CSO-style), maintained locally and sent on escalation, could serve as both a context reducer and the handoff payload (Q4).

### Gaps
- LLMLingua / LongLLMLingua compression rates and accuracy on tool-use tasks were not retrieved. ACON lists LLMLingua as a baseline but its numbers were not readable.
- SWE-agent history-processor specifics beyond M=10 were not retrieved. Exact per-model solve rates for Complexity Trap were not available (only the abstract and a secondary overview were readable).
- No study found that sweeps per-observation truncation size on BFCL.

---

## Q3. Tool-schema reduction (dynamic tool selection / retrieval)

### Takeaway
Shrinking the visible tool menu can sharply cut prompt tokens (90–98%) and, done well (state/causal-aware), can improve accuracy a lot. Naive lexical top-k filtering *hurt* accuracy versus all tools in ToolMenuBench, and dynamic menus can break prompt caching unless they are handled carefully. Evidence on small local models and TTFT is thin: one on-device paper measured ~5x TTFT gain, and the rest are simulations or frontier-model results.

### Cited Findings
- ToolMenuBench (125-tool mixed-distractor setting, 30 tasks per condition): All tools 32.1% success at 56,062 tokens/task. Keyword top-5 22.1% at 3,200. Keyword top-10 22.4% at 5,356. State-aware 24.0% at 13,522. CMTF (causal minimal tool filtering, ~1 visible tool) 85.7% at 1,125 tokens. Quotes: "lexical relevance alone is not sufficient for reliable tool use"; "executability is not equivalent to usefulness". — [ToolMenuBench 2606.15508](https://arxiv.org/html/2606.15508)
- ToolMenuBench caveats: synthetic registry, mocked execution, no latency measurement, recall of the gold tool not reported. The authors also proposed CMTF, which needs good tool contracts. — [ToolMenuBench 2606.15508](https://arxiv.org/html/2606.15508)
- Tool Attention (simulation only, no live LLM): per-turn tool tokens down 95% (~47.3k → 2.4k) on a synthetic 120-tool testbed. Prompt-cache hit rate 84% vs 22% for naive full-schema injection over 30 turns. MiniLM encoder costs 30–60 ms on CPU. Task-success figures are "projections". — [Tool Attention 2604.21816](https://arxiv.org/html/2604.21816)
- On-device: compact schemas save ~40% per tool. JIT schema passing plus compact schemas take the initial prompt from 3,200 to 400 tokens, for ~5x TTFT on device. — [arXiv 2511.03728v1](https://arxiv.org/html/2511.03728v1)
- Anthropic caching: changing tool definitions "invalidates the entire cache" (tools, system, and messages). A beta header `inline-tools-2026-09-15` lets you add tools mid-conversation through a system-message `tool_addition` block without changing the `tools` array. — [Anthropic prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- SECONDARY: a news report says Anthropic evals showed Tool Search raised Opus 4 accuracy from 49% to 74% (headline only; not read). — [MarkTechPost](https://www.marktechpost.com/2026/05/29/hermes-agent-ships-tool-search-for-mcp-anthropic-evals-show-49-to-74-accuracy-gain-on-opus-4/)

### Inferences
- In this setup the ~4k-token system+tools prefix is re-prefilled on every local turn. Prefill cost scales with prompt length on CPU/iGPU/NPU, so trimming it to ~1–1.5k (compact JSON schemas, dropping verbose descriptions) is a direct local TTFT lever **[AGENT/SW]** that also helps the >10 s TTFT escalation trigger. Expected TTFT gain is roughly proportional to prefill share. The ~5x figure is from a phone CPU going 3,200→400 tokens, so it is an upper bound for this case.
- BFCL multi-turn domains expose only a few API classes (tens of functions) per entry, not hundreds. Retrieval-style filtering has less headroom here than in ToolMenuBench and risks dropping a needed function, which BFCL scores as failure. Schema *compaction* is safer than *selection* on BFCL. BFCL's Missing-Functions category also deliberately withholds tools, so a selector would confound that category.
- For the cloud side, keep the `tools` array static across escalations (tool changes invalidate the whole cache), or use the inline-tools mechanism.

### Gaps
- No primary measurement found of tool-count vs accuracy for 3–8B models on BFCL multi-turn specifically. Gorilla retrieval and "less is more" tool-selection papers were not retrieved.
- No measured TTFT-vs-schema-size curve for OpenVINO on Intel AI PC.

---

## Q4. Handoff context for escalation (what to send the cloud)

### Takeaway
Sending the full raw trajectory to the strong model (as now: 63k–122k input tokens per escalated long-context entry) is the worst cost/quality point in the newest evidence. The Handoff Tax study finds raw escalation recovers less than half the quality gap, and for Claude costs over 2x the strong-model-only run. Compacting or dropping the weak model's trajectory, or restarting the cloud from scratch, did better. STEPGATE proposes a minimized step-level handoff: subgoal, needed schemas, compact state, proposed action plus uncertainty, and only the observations needed.

### Cited Findings
- Handoff Tax (58k agent runs; Haiku 4.5 → Opus 4.7, GPT-5.6 Luna → Sol; SWE-bench Verified). Claude escalation pass rates: LC-only 60.7, HC-only 79.2, Raw handoff 69.2 (recovers 47% of the gap), Compact-prefix 71.8 (60%), Traj-drop 72.4 (64%). GPT escalation: LC 58.7, HC 83.7, Raw 67.5 (36%), Compact 68.8, Traj-drop 79.7 (84%). — [The Handoff Tax, 2608.24358](https://arxiv.org/html/2608.24358v1)
- Cost: raw escalation ≈ 4.0x LC-only (Claude) and 6.1x (GPT). For Claude, raw escalation ($1.61) cost more than 2x HC-only ($0.72). Compaction improved Claude cost retention from −285% (raw) to −11%. Abort-and-restart with HC cost $0.90 vs $1.61 for raw: "restarting costs less and solves more tasks". Raw escalation is "a poor bargain" for Claude. — [The Handoff Tax, 2608.24358](https://arxiv.org/html/2608.24358v1)
- STEPGATE handoff payload: "the user subgoal, the current tool schemas needed for the decision", a compact state summary, the proposed local action with uncertainty evidence, and only the observations needed to resolve the step. Full-context handoff is kept only as an accuracy upper bound. — [STEPGATE 2610.07816](https://arxiv.org/html/2610.07816)
- STEPGATE results (Qwen2.5-1.5B local, Qwen2.5-7B 4-bit as "cloud"). Single-step: 82.7% at 30.8% escalation vs 67.3% local-only and 92.3% strong-only; remote tokens 134.5 vs 475.0; latency 0.777 s vs 2.255 s. Multi-turn trajectory success: 69.0% at 30% cloud actions vs 48.0% local and 82.0% strong; beats random escalation at the same rate (60.0%) and query-level routing (57.0%). ~55% of successful trajectories mixed local and cloud. — [STEPGATE 2610.07816](https://arxiv.org/html/2610.07816)
- STEPGATE signals: token uncertainty, tool margin, schema validity, sample consistency (computed only for ambiguous steps), state/history, risk tier. "Schema validity or low uncertainty never grants authorization." Token uncertainty alone: AUROC 0.565. — [STEPGATE 2610.07816](https://arxiv.org/html/2610.07816)
- On-device CSO in cloud delegation: baseline context grows to 10–12k tokens vs ~500 with the state object, with F1 0.94 (Combined) vs 0.88 (baseline FT) in the on-device+cloud setting. — [arXiv 2511.03728v1](https://arxiv.org/html/2511.03728v1)

### Inferences
- **Highest-value handoff lever [AGENT/SW]:** replace full-context re-send with a compact handoff:
  - the original user task and current-turn request;
  - the static system+tools prefix, which caches (Q5);
  - a local state digest, e.g., BFCL backend-visible facts already observed such as cwd, auth status, and IDs;
  - the last 1–2 local actions and observations, truncated.

  This should cut the 63k–122k tokens per escalation by roughly an order of magnitude. On BFCL, the state check is unforgiving, so the digest must preserve every state-relevant fact the cloud needs. Test it against the full-context arm on the same 15 tasks.
- **Cheaper alternative:** keep full-context handoff but make it cacheable (append-only history + cache breakpoint). Re-sent history then bills at 0.1x on the second and later escalations within the TTL. That changes cost but not quality, and it is **[CLOUD]**.
- The "one cloud turn then bounce back" design resembles the Handoff Tax "downshift" (strong → weak) case. There, raw downshift kept 80% of the cost advantage (Claude), and dropping the strong model's trajectory was the worst downshift option. **Keep the cloud turn's actions in the local history when bouncing back.**
- Because ≥85% of local failures are silent, step-level signals from STEPGATE (tool margin, sample consistency) target the right problem better than parse-failure triggers. STEPGATE's own AUROC/ECE numbers warn that these gates are weakly calibrated.

### Gaps
- **EdgeWise (2610.17560)** and its five handoff options could not be read (arXiv 429), so no numbers are available.
- Minions (local–remote protocol) cost/quality numbers were not retrieved.
- No study found measuring handoff payload variants on BFCL multi-turn specifically.

---

## Q5. Cloud-side cost levers orthogonal to device config (prompt caching, batch)

### Takeaway
Anthropic prompt caching bills cache reads at 0.1x base input (0.05x on Sonnet 5.5). Writes cost 1.25x (5-min TTL) or 2x (1-hour TTL). The prefix order is tools → system → messages. Caching only the ~4k system+tools prefix saves little per escalation, since it is ~3–6% of a 63k–122k request. Caching the append-only conversation history can cut the cost of repeated escalations within an entry by up to ~90% on the cached part. The Batch API gives 50% off and stacks with caching, but returns results asynchronously (most within 1 hour, up to 24 h), so it only suits offline eval runs, not the interactive demo. Both are **[CLOUD]** levers and should apply equally to both arms or be excluded.

### Cited Findings
- Multipliers: 5-min cache write 1.25x, 1-hour write 2x, cache read 0.1x. "Sonnet 5.5 is an exception at 0.05x." Prices per MTok: Sonnet 5.5 $2 in / $10 out, write $2.50 (5m) / $4 (1h), read $0.10. Sonnet 5 read $0.20. Sonnet 4.6/4.5/4: $3 / $15, write $3.75 / $6, read $0.30. — [Anthropic prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- TTL: default 5 minutes, refreshed free on each use. Optional 1 hour. Lifetime is measured from the start of the request, so streaming time counts. — [Anthropic prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- Minimum cacheable length: Sonnet 5.5 512 tokens. Sonnet 5 / 4.6 / 4.5 / 4: 1,024 tokens. Shorter prompts silently go uncached. — [Anthropic prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- Up to 4 explicit breakpoints. Lookback is at most 20 blocks per breakpoint. Order is tools → system → messages. Changing tool definitions invalidates everything. `tool_choice` changes invalidate messages only. Thinking-parameter changes invalidate messages (and possibly tools and system on some models). — [Anthropic prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- Latency: "You will generally see improved time-to-first-token for long documents". Caching "has no effect on output token generation". — [Anthropic prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- Stacking: multipliers "stack with other pricing modifiers such as the Batch API discount". Batch cache hits are best-effort. — [Anthropic prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- Batch API: "reducing costs by 50%". Most batches finish within 1 hour. Batches expire if not done within 24 h. The docs suggest a 1-hour cache TTL for batches. `max_tokens: 0` pre-warming is not allowed in batches. — [Anthropic batch processing docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- Tool Attention (simulation): naive full-schema injection gave a 22% cache hit rate vs 84% for its stable gated approach over 30 turns. — [Tool Attention 2604.21816](https://arxiv.org/html/2604.21816)

### Inferences (worked arithmetic; Sonnet 4.6 pricing $3/MTok input assumed — swap in the actual model)
- **Prefix-only caching:** 4k tokens × $3/MTok = $0.012 per call uncached vs $0.0012 cached (after a $0.015 5-min write). With ~9 escalations across 15 tasks (mostly one per entry), the prefix is often written once and never re-read within the TTL, so savings are near zero or slightly negative (1.25x write). **Prefix-only caching pays mainly in the cloud-only arm** (many calls per entry) and in multi-escalation entries.
- **History caching:** the cloud-only arm sends ~91k input tokens per base entry across its calls. Putting a breakpoint on the last message each call makes each call pay 0.1x for the already-seen prefix. For an agent loop with linearly growing context, that can cut input cost by a large fraction (rough estimate 60–85%, depending on turn count and output share; not measured here). This would **shrink the cloud-only arm's cost much more than the hybrid's**, which narrows the hybrid's cost advantage. Hence the instruction to apply caching to both arms or to neither.
- **TTL risk in hybrid:** with local turns between escalations (local TTFT can exceed 10 s, plus multi-step local turns), the gap between cloud calls can exceed 5 min. The 1-hour TTL (2x write) is then needed for re-reads. Arithmetic, in units of base input price per cached token: 1h write + 1 read = 2.0 + 0.1 = 2.1 vs 2.0 uncached (roughly break-even at one hit). With 2 reads it is 2.2 vs 3.0, so it pays from the second re-read. The 5-min TTL pays from the first hit (1.25 + 0.1 = 1.35 vs 2.0) if the gap stays under 5 minutes.
- **Cache stability requirements:**
  1. Insertion-time observation truncation (current OBS_MASK) is stable; rolling masks are not.
  2. A static `tools` array across escalations.
  3. No thinking-parameter toggles between cloud calls.
  4. The handoff must be append-only relative to the previous cloud request if history caching is wanted. A compact digest (Q4) and history caching are partly in tension: you either send less, or send the same bytes cheaply.
- **Batch API** suits offline BFCL evaluation runs (cloud-only baseline, re-scoring) but not the live demo. Its 50% discount makes eval cost accounting differ from demo cost, so report list-price $ for the demo comparison.

### Gaps
- No public measurement found of cache hit rates for Claude in an escalation-style hybrid agent.

---

## Q6. Output control (stop at first tool call, terse output, constrained decoding/grammars) and the loud→silent failure risk

### Takeaway
Grammar or schema-constrained decoding reliably removes *structural* failures in small models, but the 2026 evidence says it can *lower* semantic accuracy and turns loud parse errors into silent well-formed-but-wrong calls. Constraint Tax measured wrong-but-valid outputs on a Qwen2.5-1.5B calendar tool-call task rising from 8.5% to 52.0%, with executable accuracy falling 91.5% → 48.0%. That is exactly the OBS-COST concern: with ≥85% of local failures already silent, a grammar would also blind the "no parseable tool call" escalation trigger. Stopping generation at the first complete `</tool_call>` and terse output instructions are lower-risk latency levers, but I found no primary measurements of them.

### Cited Findings
- Constraint Tax main suite (15,000 generations): hard schema decoding raised validity from 61.5% to 100.0%, but answer accuracy fell from 19.7% to 11.0%. Wrong-but-valid outputs rose from 49.5% to 88.9%. "The error is semantic, not structural." — [The Constraint Tax, 2605.26128](https://www.alphaxiv.org/abs/2605.26128.md)
- Calendar tool-call analogue (Qwen2.5-1.5B-Instruct, 200 examples per mode): prompt-only JSON 91.5% executable accuracy vs hard tool-call schema 48.0% (−43.5 pts, 95% CI [−51.0, −36.0]). Wrong-valid went from 8.5% to 52.0%. 102 of 104 failures were single-field duration errors. A delayed-packaging control ("solve first, then serialize") kept 91.5%. — [The Constraint Tax](https://www.alphaxiv.org/abs/2605.26128.md)
- Qwen2.5-3B: accuracy 39.0% → 23.7% under hard schemas. Validity 82.6% → 98.9%. Wrong-valid +31.6 pts. In the expanded study, "delayed_constraint" reached 40.7% answer accuracy at 100% validity vs answer_only_schema 26.8%. Design pattern: "reason free, constrain late". — [The Constraint Tax](https://www.alphaxiv.org/abs/2605.26128.md)
- Constraint Tax limits: synthetic tasks, few models, the calendar task is an analogue rather than logged agent traffic. — [The Constraint Tax](https://www.alphaxiv.org/abs/2605.26128.md)
- Loud vs quiet: detection is 91.3% for loud faults vs 58.8% for quiet ones. Agents "respond to the error channel rather than to the content of what a tool returns". Prompting the agent to check each result changed quiet-failure detection from 60.6% to 59.6% (no effect). — [Loud Failures, Quiet Failures, 2610.10062](https://arxiv.org/html/2610.10062)
- STEPGATE: "Schema validity or low uncertainty never grants authorization". Schema validity is one routing feature among six. — [STEPGATE 2610.07816](https://arxiv.org/html/2610.07816)
- Titles found but not read: "Constrained Decoding Eliminates Structural Failures in Small LLMs but Reveals a Scale-Dependent Semantic Gap" ([2609.23742](https://arxiv.org/pdf/2609.23742)); "Repair, Not Improvement: Decomposing Constrained Decoding in Tool-Call Abstention" ([2608.13959](https://arxiv.org/pdf/2608.13959)); XGrammar-2 ([2601.04426](https://arxiv.org/pdf/2601.04426)). The titles align with the Constraint Tax finding, but their PDFs had no extractable text, so no numbers are given.

### Inferences
- **Do not add hard grammar-constrained tool calls to the tuned profile** without measuring wrong-valid rate and escalation-trigger rate. Doing so would likely (a) cut "no parseable tool call" escalations, so less cloud spend *looks* like a win, while (b) raising silent failures that the policy cannot see. If a grammar is used, constrain late: let the model emit free text or reasoning, then constrain only the `<tool_call>` JSON span, and keep a separate semantic check.
- **Stop-at-first-complete-tool-call [AGENT/SW]:** a stop string on `</tool_call>` saves decode tokens and wall time whenever the 4B model would otherwise ramble. It does not change the call itself, so silent-failure risk is low. One caveat: BFCL rewards parallel or multiple calls in a step, so stop after the *last* call block (e.g., at end-of-message) rather than truncating legitimate multi-call steps. Use it only if the harness confirms single-call steps are sufficient.
- **Terse-output instructions** cut decode tokens. Their accuracy effect on small models is unmeasured here, and Constraint Tax suggests that removing room to "reason" before committing can hurt.
- Report wrong-valid rate (silent failure rate) as a primary metric next to pass rate for any output-control change, as Constraint Tax recommends.

### Gaps
- No primary measurements found of stop-sequence or terse-instruction effects on BFCL accuracy or latency.
- XGrammar/outlines per-token overhead numbers were not retrieved.

---

## Q7. Local model tier (Qwen3-8B vs 4B) and where local competence makes routing pay

### Takeaway
The routing literature agrees that selective handoff pays most when the local model is **mid-competence**: weak enough to leave headroom, strong enough to handle most steps and to decide when to ask. In STEPGATE, gains from learned routing saturate at the 3B local model (88.5% local-only vs 92.3% strong). EC2-Bench finds that stronger edge models bring collaboration closer to cloud-only performance and favor edge-controlled collaboration. With local Qwen3-4B at ~10% pass vs ~73% cloud-only, the system sits at the *low-competence* end, where most value comes from escalation, and silent failures cap what routing can catch. A tier upgrade (Qwen3-8B or the 2507 4B Instruct) is a legitimate **[HW-CONFIG]** lever. I could not verify its BFCL multi-turn delta.

### Cited Findings
- STEPGATE local-only single-step success: 55.8% (0.5B), 67.3% (1.5B), 88.5% (3B). At the 50% sweep, learned routing reaches 84.6–88.5% for 1.5B but only 90.4% for 3B, against a random baseline of 90.8%. "As local SLM capacity approaches the strong model's ceiling, the value of selective handoff naturally saturates". "routing offers substantially more headroom for weaker local models". — [STEPGATE 2610.07816](https://arxiv.org/html/2610.07816)
- STEPGATE calibration: the 1.5B logistic gate has ECE 0.212 (GBT 0.121). "A router that ranks failures well but is miscalibrated can violate an escalation budget". "Wrong risky" actions fell from 15.4% (local-only) to 3.8%. — [STEPGATE 2610.07816](https://arxiv.org/html/2610.07816)
- EC2-Bench (OpenBMB): collaboration "achieves a favorable balance among task performance, resource usage, and privacy exposure". As edge models get stronger, collaboration approaches cloud-only and strategies converge in performance, and the preference shifts toward edge-controlled collaboration. Cloud-invocation decisions and instruction following are named as key edge abilities. No numbers were readable (abstract only). — [EC2-Bench 2610.17816 abstract](https://arxiv.org/abs/2610.17816); repo [OpenBMB/EC2-Bench](https://github.com/OpenBMB/EC2-Bench)
- Handoff Tax: when the weak model starts and the strong model takes over, raw handoff recovers only 36–47% of the gap. Weak-model trajectory contamination is costly. — [The Handoff Tax](https://arxiv.org/html/2608.24358v1)
- SECONDARY: tau2-Telecom 4B-2507 27% vs 14B 32% (ToolMind via aggregator). Qwen3-8B is listed only as "fair". — [d-central.tech](https://d-central.tech/local-llm-agent-capability/)

### Inferences
- At ~10% local pass with ≥85% silent failures, the hybrid's quality is bounded by detection, not escalation capacity. Raising local competence through **model tier [HW-CONFIG]** (Qwen3-8B INT4, or the Qwen3-4B-Instruct-2507 checkpoint that the public 22% refers to) likely matters more than routing finesse. The cost is memory residency and TTFT on the AI PC: 8B INT4 roughly doubles weight bytes, which lengthens prefill/decode and pushes toward the >10 s TTFT trigger. Pair a tier upgrade with schema compaction (Q3) and OBS_MASK (Q2) to stay within the TTFT budget.
- Given the Handoff Tax result, a weaker local model also contaminates the context the cloud inherits. That argues for a compact handoff (Q4) when the local tier is weak.
- Label the experiment clearly. Swapping checkpoints changes "model tier / weights" (**[HW-CONFIG]**). Changing format, thinking, or parsers is **[AGENT/SW]**. Caching and batch are **[CLOUD]**.

### Gaps
- Public BFCL v4 multi-turn numbers for Qwen3-8B vs Qwen3-4B (FC and Prompt), with or without thinking, could not be extracted (JS-rendered leaderboard). This is the key missing datum for Q7.
- EdgeWise (2610.17560) local-competence thresholds were unreadable (429).
- No source found on INT4 OpenVINO accuracy loss on BFCL for Qwen3-4B/8B. "Compression Breaks Discipline" was not located.

---

### Lever classification summary (for the report writer)
| Lever | Class | Evidence strength |
|---|---|---|
| Model tier (4B→8B, or 4B-Instruct-2507, xLAM-2 weights) | [HW-CONFIG] | STEPGATE/EC2-Bench qualitative; BFCL numbers unverified |
| Context retention: observation truncation K / rolling window | [AGENT/SW] (boundary: [HW-CONFIG] "context retention") | Strong (Complexity Trap, ACON, own data) |
| Structured state object instead of raw history | [AGENT/SW] | Moderate (2511.03728, single paper) |
| Tool-schema compaction (prompt prefix 4k→~1k) | [AGENT/SW] | Moderate (2511.03728: ~5x TTFT on phone CPU) |
| Tool filtering/retrieval | [AGENT/SW] | Mixed (ToolMenuBench synthetic; keyword filters hurt; BFCL risk) |
| Compact handoff vs full-context re-send | [AGENT/SW] | Strong (Handoff Tax, STEPGATE) |
| Prompt format/parser/role/template fidelity, thinking on/off | [AGENT/SW] | BFCL rules documented; effect sizes unverified |
| Stop at end of tool call / terse output | [AGENT/SW] | No primary measurement found |
| Grammar-constrained decoding | [AGENT/SW] | Negative on accuracy (Constraint Tax); converts loud to silent failures |
| Prompt caching (5m/1h), Batch API 50% | [CLOUD] | Official docs; apply to both arms or exclude |
