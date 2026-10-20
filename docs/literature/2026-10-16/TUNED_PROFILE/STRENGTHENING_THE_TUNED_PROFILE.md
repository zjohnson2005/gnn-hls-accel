# Rebuild the tuned profile around bytes moved

> Correction 2026-10-20 (Task AX): measured on XPS run 39c1c131 (arm A local_only, DEMO1_BASE_30, 118 local turns), a local turn generates a median of 91 tokens (p90 157), not 130-255.

The true OpenVINO default takes over three of the five knobs registered for DEMO-2's tuned profile. Against `LLMPipeline(model, "GPU")` on 2026.2.1, **RESIDENT, the 40,960 window and T2S's u8 KV are no longer differences**. The default already runs prefix caching with unlimited batch tokens. It has no window cap, and the trained context is 40,960 anyway. The GPU plugin also turns a u8 request into the same i8 it picks by default. What still separates the arms is **OBS_MASK retention on both hosts and u4 KV on the XPS**. The registered prediction of ~8× ($0.046 vs $0.356) therefore has to be withdrawn: 48 of its 60 control escalations came from a window overflow that no longer exists. The best internal proxy is the same 15 entries run with FULL retention and then OBS_MASK. It suggests the advantage that survives is about **1.7× on the XPS ($0.308→$0.184) and about 7× on the T2S ($0.096→$0.013)**. On the XPS that gain came with the same 9 escalated entries, so it comes from **cheaper escalations rather than fewer**. I recommend strengthening the profile with output-preserving runtime levers. Each is aimed at a byte stream the physics says dominates:

- **prompt-lookup decoding**, because decode is 67–91% of turn time;
- **u4 KV on the T2S as well**;
- a **bounded prefill chunk plus a KV pool preallocated to the window size** on the XPS, because a fit to our resident limits points to a precision-independent per-token transient.

Reject f16 KV, INT8 weights, model swaps, XAttention, cache eviction and grammar decoding. The binding risk is quality, not cost. Every hybrid pass in our runs came through escalation, so any lever that keeps more entries local trades paid cloud passes for silent local failures. At n=60, the paired lower bound stays above −0.15 only if **about 20 or fewer entries are discordant with zero net loss**. An A/A run of the control should therefore come before anything else.

## The true default absorbs three of five registered knobs

### What the control actually runs

When no `scheduler_config` is passed, LLMPipeline on GPU builds the PagedAttention/continuous-batching backend with a "latency-oriented" config. Only two fields differ from the struct: `max_num_batched_tokens = SIZE_MAX // don't limit total batch size` and `enable_prefix_caching = true // for better TTFT in chat scenarios` ([utils.cpp L808-813](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L808-L813)). Passing any SchedulerConfig **replaces** that config rather than merging with it. So a bare `SchedulerConfig()` silently goes back to 256-token chunks with prefix caching off, which is exactly the old control ([utils.cpp L794-806](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L794-L806); [scheduler_config.hpp](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/scheduler_config.hpp#L18-L86)).

On KV precision, the 2026.2.1 GPU plugin hard-codes `bool auto_enable_4bit_kv = false;`, so a PagedAttention model with INT4 weights gets **i8 KV**, not u4. It also normalizes a u8 request to i8 ("plugin is supposed to work with INT8 internally") ([execution_config.cpp L250-298, L353-361](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L250-L298)). This corrects the earlier literature check, which had read the 2026.2.1 default as u4. Automatic u4 arrives only in 2026.3.x ([2026.3.1 execution_config.cpp](https://github.com/openvinotoolkit/openvino/blob/2026.3.1/src/plugins/intel_gpu/src/runtime/execution_config.cpp#L268-L300)).

On context, GenAI imposes no prompt or context cap on GPU. `max_new_tokens` and `max_length` default to SIZE_MAX, and a grep for `max_position_embeddings` in the LLM and continuous-batching sources finds no check ([generation_config.hpp L635-636](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/include/openvino/genai/generation_config.hpp#L635-L636)). The control is therefore limited only by memory, and past 40,960 tokens it degrades silently.

### Knob-by-knob comparison

| Knob | Registered tuned (XPS / T2S) | True default control | Still a difference? |
|---|---|---|---|
| Placement / weights | GPU, INT4 / GPU, INT4 | GPU, INT4 (same IR) | No |
| Residency (prefix caching) | On / On | On | **No** |
| Prefill chunking | Unlimited (no SchedulerConfig) | Unlimited | No |
| KV precision | u4 / u8 (= i8 on GPU) | i8 | **XPS only** |
| Context window | 40,960 | Uncapped; trained max 40,960 | Only as an overflow→escalation boundary |
| Retention | OBS_MASK K=1024 | Full history | **Yes** |

### How the control will escalate

With the window gone, the control's escalations move to other triggers. This is a derived prediction from our sealed limits.

On the **XPS**, i8 KV holds about 20,000 resident tokens (553b3a5c, cf3555d5, e4a22dac). An unmasked long-context entry that grows past that becomes a local generation error, which is a sticky escalation that hands off a large, unmasked history. A large uncached tool observation can also push step-0 TTFT past 10 s. The cold edge is 10,000 tokens (c2246b1f), and the 8,500-token append in V5-CAL took 22.4 s, though that run is under re-check and was probably affected by 256-token chunking.

On the **T2S**, memory never binds. Prefix caching means only deltas are prefilled, so capacity triggers will rarely fire. The control will mostly escalate through quality bounces, and each bounce re-sends a fatter context than the tuned arm would.

The control is therefore likely to be **cheaper than the old 4096 control and lower in quality**. That is the regime the tuned profile now has to beat.

### Two framing consequences

The u4 advantage depends on the version. On 2026.3 the vendor default *is* u4, so the comparison must pin 2026.2.1 and say so. It is fair to describe XPS u4 as "the vendor's next default, applied early", but not as a novel discovery.

The tuned profile's cost advantage now rests mostly on OBS_MASK, which sits on the boundary between retention and agent software. If a reviewer reclassifies OBS_MASK as software, the T2S's pure-hardware differentiation falls to zero. The profile therefore needs real device-side levers added, and it needs an ablation that isolates them. The database-tuning literature sets the same bar: the gain should survive against the strongest reasonable baseline, not a minimal-hardware default ([Van Aken et al., VLDB 2021](https://vldb.org/pvldb/vol14/p1241-aken.pdf)).

## Decode on a ~68 GB/s data path sets turn latency

### Decode follows the bandwidth model

Our numbers fit a bandwidth roofline well. Qwen3-4B stores 36 layers × 8 KV heads × 128 dims × K and V, which is **147 KB/token in f16, 74 KB in i8 and 37 KB in u4**. XPS decode at 25–27 tok/s with about 3.5k context implies an effective bandwidth of about 68 GB/s (DERIVED). That is roughly 57% of the 119.5 GB/s theoretical peak for LPDDR5X-7467 on a 128-bit bus ([Notebookcheck 325](https://www.notebookcheck.net/Intel-Core-Ultra-5-325-Processor-Benchmarks-and-Specs.1196417.0.html); [Chips and Cheese](https://old.chipsandcheese.com/2025/10/14/panther-lakes-reveal-at-itt-2025/)). The memory speed of our unit is still unconfirmed.

Holding that bandwidth fixed, the model predicts 21.0 tok/s at 12k context against the **19.85 measured**. The T2S/XPS decode ratio of 1.31 (35.5 vs 27.1) matches the 1.29× memory-speed ratio rather than the 3× Xe-core ratio. That is the signature of decode limited by bandwidth (DERIVED, assuming the T2S runs LPDDR5X-9600).

Intel's own table for a Core Ultra 5 "330" lists Qwen3-4B INT4 at 17.6–18.1 tok/s and 775–815 ms TTFT at 1,024 input tokens, which agrees with our numbers within about 10% ([Intel 5-330 CSV](https://github.com/openvinotoolkit/openvino/blob/master/docs/sphinx_setup/_static/benchmarks_files/llm_models_5-330.csv)).

### Time per turn is mostly decode

Turn time is decode-dominated. On the XPS, 176 tokens at 27.1 tok/s is **6.5 s of a 10.0 s generate**. On the T2S, 133 tokens at 35.5 tok/s is 3.7 s. Under prefix caching TTFT falls to 9–20% of generate time (V3 71d33f7a, V4 a678926e). This matches H100 agent traces, where decode is 91–98.6% of LLM time once prefix caching works ([arXiv 2605.26297](https://arxiv.org/html/2605.26297v1)). On our iGPU one output token costs about as much wall time as 35–40 prefill tokens (DERIVED).

The output-token budget is therefore where turn latency lives. One finding reframes it. A turn emits a median of 91 tokens (p90 157; measured, run 39c1c131; the 130–255 first cited here was not measured), and tool-call blocks are about 35% of them (character-apportioned ESTIMATE, pilot P1). BFCL ends a turn at the first step with no decodable function call ([BFCL multi-turn blog](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html)). My hypothesis, which needs the ledger inspection in pilot P1, is that most of the excess is the **end-of-turn prose step**. BFCL's state and response checks never score that text.

Trimming it is the largest raw latency lever available. A 200-token turn cut to about 60 tokens saves about 5.4 s on the XPS (DERIVED). But trimming output is an agent-level change. It has to be applied to both arms, so it lowers absolute latency without creating an advantage.

### KV precision: prefill vs decode

KV precision trades prefill against decode, and with prefix reuse u4 or i8 wins.

| Context | f16 decode | i8 decode | u4 decode |
|---|---|---|---|
| 3.5k | 23.7 tok/s | 26.0 tok/s | 27.4 tok/s |
| 12k | 16.5 tok/s | 21.0 tok/s | 24.3 tok/s |
| 30k | 10.0 tok/s | 14.9 tok/s | 19.6 tok/s |

(DERIVED, at a fixed 68 GB/s. These are upper bounds that ignore dequantization cost.)

f16 does win prefill. It is 15–27% faster at depth, and warm turn-2 at 12k takes 0.639 s against 1.003 s for u8 (72776603, 1587d2f4). The likely reason is that f16 avoids the dequantization paths the compressed-KV attention kernels carry ([paged_attention_opt.cpp](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/graph/impls/ocl_v2/sdpa/paged_attention_opt.cpp#L1351-L1394)).

With prefix caching, though, a warm turn prefills only a few hundred tokens. f16 then saves 0.05–0.3 s of TTFT and loses 0.8–2.6 s of decode per 200-token turn (DERIVED). On the XPS, f16 also *lowers* the resident limit to 15,000, against the control's 20,000. **f16 loses on latency, memory and context held at once**, so the earlier latency note's f16 recommendation should not be adopted.

u4 against the control's i8 is the opposite case. Warm turn-2 is slightly faster (0.946 vs 1.003 s, dd2b0779), decode is predicted 5% faster at 3.5k and 16% faster at 12k, and KV memory is halved.

### The resident limits hint at a hidden per-token transient

Our three XPS resident limits (15,000 / 20,000 / 26,500 tokens for f16 / u8 / u4) do not hold KV bytes constant. A two-parameter fit (DERIVED) gives:

- a **fixed budget of about 4.4 GB**;
- a **precision-independent cost of about 147 KB per token**, which is exactly one f16 K+V per token.

The fit predicts a u4 limit of 24,000 against the measured 26,500, so it is within 10%. The hypothesis is that one-shot prefill with unlimited batch tokens (the default) materializes f16-sized K/V or activation transients for the whole prompt, and that this term is what binds.

If that is right, capping `max_num_batched_tokens` at 4,096 shrinks the term to about 0.6 GB. That would lift the u4 limit to the model's 40,960 ceiling and i8 to about 52k (aggressive DERIVED leap, test in P3). Two other things could produce the same pattern instead: the driver's shared-memory quota, or GenAI's available-memory estimate, which multiplies used memory by 1.1 on integrated GPUs ([utils.cpp L950-983](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/utils.cpp#L950-L983)).

### Dynamic KV growth also costs memory

Independently of that fit, dynamic KV growth is a real memory cost. Each 256-token growth step allocates new K and V tensors for every layer and copies the old cache into them ([kv_cache_manager.hpp L159-200](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/cache/kv_cache_manager.hpp#L159-L200)). Under prefix caching the cache never shrinks ([pipeline_impl.cpp L645-650](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/continuous_batching/pipeline_impl.cpp#L640-L650)). Setting `cache_size` preallocates once. That removes the transient old-plus-new peak and makes the footprint deterministic.

### Verifying drafted tokens is almost free

Decode at INT4 runs at about 4 FLOP/byte. The machine balance is roughly 170 FLOP/byte on the XPS and 400 on the B390 (DERIVED, from Xe2-rate estimates). Verifying 6 drafted tokens therefore adds about 4.4 ms to a 36.5 ms bandwidth-bound step on the XPS (12%), and about 2 ms to 28 ms on the T2S (7%).

Draft-free prompt lookup breaks even at about **0.1 accepted tokens per step** (DERIVED). The method copies n-gram continuations from prompt plus output, and that matches tool names, JSON keys and argument values ([prompt-lookup source](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/prompt_lookup/continuous_batching_for_prompt_lookup.cpp#L22-L81)). One caveat: our INT8-vs-INT4 cross-check shows the 4-Xe GPU carries INT4 kernel overhead beyond pure bandwidth, so the XPS gain will be smaller than on the B390.

## Cheaper escalations, not fewer, carry the cost advantage

### Escalations buy the quality

Our data says escalations buy almost all hybrid quality:

- In V4 XPS, **all 6 hybrid passes came from escalated entries** (a678926e).
- Local trajectory passes are 0–10%.
- Under emission routing, 122 of 141 non-escalated entries failed silently (d482c621).
- No router beat matched-rate random escalation.
- An oracle router reached only 23 passes at $0.21–0.28, against 22 for all-cloud at $0.297.

The headroom for buying quality cheaply is thin. The cost advantage therefore has to come from **lowering the price of each escalation**, not from suppressing escalations.

### OBS_MASK makes escalations cheaper, matching the literature

OBS_MASK fits that pattern. On the same 15 XPS entries it cut $/task 40% with the **same 9 escalated entries**, and hybrid passes rose from 4 to 6 (71d33f7a+ab88f47f → a678926e). The most plausible mechanism (INFERENCE) is that every sticky escalation hands Claude the retained history, so truncating observations at insertion shrinks every cloud request.

The literature agrees on both direction and size:

- Observation masking roughly halves agent cost while matching LLM summarization ([Complexity Trap, arXiv 2508.21433](https://arxiv.org/abs/2508.21433)).
- ACON cuts peak tokens 26–54% and *improves* smaller models ([ACON](https://arxiv.org/html/2510.00615v1)).
- Raw full-trajectory handoff is the worst cost/quality point for Claude escalation: it recovers 47% of the gap at more than 2× the cost of a strong-model-only run ([Handoff Tax](https://arxiv.org/html/2608.24358v1)).

On the T2S the same comparison gave $0.096→$0.013, but passes went 3→2 (a4284ab0 → 30caa847). That is a warning that masking can remove information the local model needed.

### The capacity paradox

The quality risk deserves a name. Call it the **capacity paradox**. Raising local capacity (u4, a chunk cap, masking that avoids OOM or TTFT triggers) keeps long entries local that the control would have escalated. At 0–10% local pass rates, each of those entries swaps roughly a cloud pass for a silent failure.

Two external results back this up. Agents detect quiet faults only 58.8% of the time, against 91.3% for loud ones ([Loud/Quiet, arXiv 2610.10062](https://arxiv.org/html/2610.10062)). STEPGATE shows routing value lives in exactly this low-competence regime ([STEPGATE](https://arxiv.org/html/2610.07816)).

The same logic explains why our INT4 weights help the hybrid. INT4 emits no parseable call on 32 entries against 7 for INT8, with equal completion. Those **loud** failures trigger quality bounces, and the bounces buy cloud passes (INFERENCE).

It also explains why grammar-constrained decoding must stay out. Hard schemas raised wrong-but-valid outputs from 8.5% to 52.0% on a Qwen2.5-1.5B tool-call task ([Constraint Tax](https://www.alphaxiv.org/abs/2605.26128.md)). That would blind the no-parse trigger.

### Some legitimate levers narrow the advantage

Some valid levers shrink the gap rather than widen it. Both Anthropic prompt caching ([docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)) and compact handoff are cloud-side or agent-level, so they must apply to both arms or neither. Both cut the control's large re-sent histories more than the tuned arm's already-masked ones. Keep both out of the primary comparison and report them as a labeled sensitivity arm.

### Pre-register a cost decomposition

To make the cost claim robust to the "retention is software" objection, pre-register this decomposition:

**Δ$/task = Δ(escalations) × payload + escalations × Δ(payload)**

Also add a device-only ablation arm (described below) that shows what u4 and the runtime levers buy without OBS_MASK.

## All options ranked against the true default

Class labels:

| Label | Meaning |
|---|---|
| DEVICE | Thesis-listed device knobs |
| DEVICE-RUNTIME | Scheduler or decoding settings that leave outputs unchanged under greedy decoding. They are analogous to residency; the thesis owner should confirm they belong with the device knobs, or they move to an ablation arm. |
| BOUNDARY | Retention |
| AGENT/SW, CLOUD | Both arms or excluded |

Evidence labels:

| Label | Meaning |
|---|---|
| M | Our sealed measurement |
| D | Derived from our numbers |
| S | Source code or documentation |
| L | Literature analogy |
| H | Untested hypothesis |

| Rank | Option | Class | Effect vs true default (cost / latency / memory / context / quality risk) | Evidence | Verdict |
|---|---|---|---|---|---|
| 1 | OBS_MASK retention, K swept over 512/1024/2048 | BOUNDARY | −40% (XPS) to −86% (T2S) $/task; faster decode at depth; KV bounded; quality mixed (+2 XPS, −1 T2S of 15) | M, L | **Keep**; choose K on pilot; pre-register decomposition and ablation |
| 2 | u4 KV on both hosts (T2S changes from u8≡i8) | DEVICE | Decode +5% at 3.5k, +16% at 12k; KV memory halved; XPS limit 20k→26.5k; accuracy risk low (per-channel keys, group 16) | M, D, S, L ([KIVI](https://arxiv.org/pdf/2402.02750)) | **Adopt** if P10 agreement holds; it is the only device-precision difference on the T2S |
| 3 | Prompt-lookup decoding (`num_assistant_tokens` 3–5, `max_ngram_size` 3) | DEVICE-RUNTIME | Decode an estimated 1.1–1.4×, i.e. about −1.0 to −1.5 s per XPS turn; no memory cost; outputs unchanged under greedy decoding | S, D, L ([Intel/HF 1.3–1.4× draft on Lunar Lake](https://huggingface.co/blog/intel-qwen3-agent)), H | **Adopt** if P4 shows ≥1.1×. No OpenVINO prompt-lookup numbers are published. |
| 4 | Prefill chunk cap of 4,096 plus `cache_size` sized to the window | DEVICE-RUNTIME | XPS context held possibly 26.5k→40,960; deterministic footprint; no growth copies; small cold-TTFT cost | D, S, H | **Adopt on XPS** if P3 confirms. Never use 256. |
| 5 | XPS window set to measured limit −10% | DEVICE | Clean escalation instead of an OOM or generation error; no cost effect | M | Adopt |
| 6 | Qwen3 think-block template fix or token-level append | AGENT/SW | About −0.1 to −0.26 s per XPS turn; reusable share is already 0.9935 | S ([chat template](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/tests/python_tests/data/tokenizer_configs.py#L313)), M, D | Both arms or exclude |
| 7 | End-of-turn prose cap or stop | AGENT/SW | Largest raw lever (about −5 s per turn); no relative gain | D, H | Both arms, after P1 |
| 8 | Classic Qwen3-0.6B draft | DEVICE-RUNTIME | Below 1.3×: the draft is about 15% of target cost, adds about 0.6 GB, and a CPU draft would contend for the bus | L ([Discussion #36484](https://github.com/openvinotoolkit/openvino/discussions/36484)), D | Only if 3 fails |
| 9 | Power mode or AC profile | Environment | B390 loses 33% at 20 W vs 45 W ([Notebookcheck](https://www.notebookcheck.net/Intel-Panther-Lake-Arc-B390-performance-and-efficiency-analysis-Intel-s-new-iGPU-trades-blows-with-the-Nvidia-GeForce-RTX-4050.1212582.0.html)) | L | Pin equal in both arms and report |
| 10 | f16 KV | DEVICE | Worse decode, memory and XPS context (15k < 20k) | M, D | Reject |
| 11 | INT8 weights | DEVICE | Decode 1.3–1.67× slower, +1.76 GB, fewer loud failures | M | Reject |
| 12 | Model tier (8B, or the 2507 checkpoint) | DEVICE (model) | 2507 public multi-turn score is 22.1% ([BenchmarkList, secondary](https://benchmarklist.com/models/qwen3-4b-instruct-2507/)); 8B roughly halves decode (D) | L, D | Exclude from the primary profile: it breaks the "model held fixed" novelty claim. Separate arm later. |
| 13 | XAttention | DEVICE-RUNTIME | Only f16/i8 (no u4) and no speculative decoding; about 52% of attention is dense at 4k | S ([CM kernel](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/graph/impls/cm/paged_attention.hpp#L24-L82), [XAttention](https://arxiv.org/html/2503.16428v1)) | Reject |
| 14 | Cache eviction, TriShape | DEVICE-RUNTIME | Eviction turns off micro-SDPA prefill and does not cut prefill; TriShape is a no-op with unlimited chunks | S ([paged_attention.cpp](https://github.com/openvinotoolkit/openvino/blob/2026.2.1/src/plugins/intel_gpu/src/plugin/ops/paged_attention.cpp#L91-L94)) | Reject |
| 15 | Dynamic quantization, precision hints | DEVICE-RUNTIME | Already on by default | S | No lever |
| 16 | Grammar-constrained calls | AGENT/SW | Turns loud failures into silent ones | L | Reject |
| 17 | Compact handoff, prompt caching, Batch API | AGENT/SW, CLOUD | Shrinks the control's cost more than the tuned arm's | L, S | Sensitivity arm only |
| 18 | NPU or CPU placement; EAGLE-3; DFlash | DEVICE | GPU is 17× faster at prefill and 3.2× at decode than CPU; no Qwen3-4B EAGLE-3 head; DFlash is unreleased and lacks prefix caching ([DFlash](https://huggingface.co/blog/ofirzaf/intel-dflash-ptl)) | M, S | Reject |

## Recommended profiles per host

Both profiles keep Qwen3-4B INT4 (the same IR), the GPU, GenAI 2026.2.1 pinned, policy `hybrid_full` unchanged, and greedy local decoding. `CACHE_DIR` should be set in both arms, since it affects load time only.

| Setting | XPS 16 (4-Xe3, 16 GB) | T2S (B390, 64 GB) |
|---|---|---|
| KV_CACHE_PRECISION | u4 (keys stay BY_CHANNEL) | **u4** (was u8, which equals the control's i8) |
| SchedulerConfig | `enable_prefix_caching=True`, `max_num_batched_tokens=4096` (fall back to 2**64−1 if P3 fails), `cache_size` ≈ window × 37 KB (≈1.0 GB at 26k, 1.5 GB at 40,960) | `enable_prefix_caching=True`, `max_num_batched_tokens=2**64−1`, `cache_size≈1.5 GB` |
| Decoding | `prompt_lookup=True`, `num_assistant_tokens` 3 or 5, `max_ngram_size=3` | Same |
| Retention | OBS_MASK at the pilot-chosen K (default 1024) | Same |
| Window | min(40,960, P3 resident limit −10%) | 40,960 (guards against silent degradation past the trained length) |

The full SchedulerConfig must restate prefix caching and the chunk size, because it replaces the default rather than merging with it.

### Predicted outcomes against the true default

| Metric | XPS prediction | T2S prediction | Basis |
|---|---|---|---|
| $/task | ≈$0.18 vs ≈$0.31 (≈1.7×) | ≈$0.013 vs ≈$0.096 (≈7×) | M (FULL→OBS_MASK proxy, n=15; the proxy's KV and window may differ from the true default) |
| Local turn latency p50 | −10% to −25% | −10% to −25% | D + H (prompt lookup, u4); larger gains on long entries where the control decodes at depth |
| KV memory | 0.13 vs 0.26 GB at the 3.5k p50; ≤1.0 GB vs ≤1.5 GB at limits | Halved at every depth | D |
| Context held | 26,500 vs 20,000 (+33%), up to 40,960 if P3 holds | KV capacity doubled; not binding at 64 GB | M, H |
| Pass rate | 6 vs 4 of 15 on the proxy; capacity-paradox risk | 2 vs 3 of 15 on the proxy | M (small n) |

Report turn latency separately for local and cloud turns, so that differences in escalation rate do not contaminate a device-attributable metric. Total memory is dominated by about 2.35 GB of weights, so headline footprint gains are modest at median depth. Present KV and peak footprint separately.

### Arms to pre-register on DEMO2_HELDOUT_60

| Arm | Configuration | Purpose |
|---|---|---|
| A | True-default control | Primary comparison |
| B | Device-only tuned: arm A plus u4, chunk/cache and prompt lookup, without OBS_MASK | Answers the "retention is software" objection |
| C | Full tuned | Primary comparison |
| D (optional) | Legacy 4096 control, labeled "ecosystem-typical (Ollama <24 GiB tier)" | Continuity with earlier results ([Ollama](https://docs.ollama.com/context-length)) |

## Pilot measurements before sealing

All pilots must run on DEMO-1 pins, never on DEMO2_HELDOUT_60.

The non-inferiority arithmetic drives the order of work. Using a Wald approximation to the paired difference at n=60 (DERIVED):

| Discordant entries | Net loss | Paired lower bound |
|---|---|---|
| 16 | 0 | −0.131 |
| 20 | 0 | −0.146 |
| 22 | 0 | −0.153 (fails) |
| 12 | 2 | −0.146 |

On BFCL multi-turn, two fault-free agent runs reached the same end state only 63.3% of the time ([Loud/Quiet](https://arxiv.org/html/2610.10062)). Cloud nondeterminism alone could therefore use up the margin. If the A/A run shows that, the fix is replicates per arm, not a different profile.

| # | Measurement | Decision rule |
|---|---|---|
| P0 | Read back the true default on both hosts: no "Falling back to SDPA" warning, i8 in the compiled `KV_CACHE_PRECISION` dump (`OPENVINO_LOG_LEVEL`≥INFO), no rt_info override | The control is valid only if confirmed ([pipeline.cpp](https://github.com/openvinotoolkit/openvino.genai/blob/2026.2.1.0/src/cpp/src/llm/pipeline.cpp#L214-L244)) |
| P1 | Break down the output tokens per turn (measured median 91, p90 157, run 39c1c131; earlier cited as 130–255) (tool call vs end-of-turn prose vs chatter) | Decides whether an output lever applies to both arms |
| P2 | Warm decode tok/s at 3.5k, 12k and 20k for i8 vs u4 (and f16) on both hosts | Validates the 68 GB/s model and the u4 decode gain |
| P3 | XPS resident limit and peak memory across chunk sizes {unlimited, 4096, 2048} × {i8, u4} × cache_size {0, sized}; cold 10k TTFT; re-run V5-CAL under the latency default | Adopt the chunk cap if the limit rises ≥20% at ≤10% cold-TTFT cost |
| P4 | Prompt lookup with K = 3 or 5: accepted tokens per step, decode speedup, byte-identical outputs under greedy decoding | Adopt if ≥1.1× and outputs are identical |
| P5 | OBS_MASK K sweep (512/1024/2048): $/task, passes, n_ctx, escalation reasons | Lowest $/task with passes ≥ K=1024 |
| P6 | True-default dry run: escalation-reason mix, n_ctx tail, any context above 40,960 on the T2S, local pass rate by n_ctx bucket | Sizes the capacity paradox |
| P7 | A/A: control run twice | If discordance is above ~15 of 60, plan 2 replicates per arm |
| P8 | u4 vs i8 step-level agreement and silent-failure share | Keep T2S u4 if silent share does not rise |
| P9 | Memory speed (HWiNFO), power mode, 10-minute sustained drift | Pin and disclose |

## Conclusion

Re-anchoring the control turns DEMO-2 into a different study. It no longer tests whether a sensible configuration beats a crippled one. It tests whether device knobs still matter once the vendor's own defaults are good. The honest answer from our data is "yes, but mostly through bytes". There are fewer KV bytes per decoded token (u4), fewer bytes re-sent per escalation (retention), and fewer bytes streamed per accepted token (prompt lookup), but no fewer escalations. That reframing also tells SEAM where its thesis is exposed. Configuration that increases local capacity is not automatically good in a hybrid, because escalation is what buys quality when the local model is weak.

The strongest device-side result available is probably not a speedup. It is the pre-registered decomposition showing which share of cost each byte stream removes, together with a device-only arm that still clears the margin. If the A/A pilot shows that cloud nondeterminism alone approaches 20 discordant entries, then replication, not tuning, is what decides whether the comparison reads as a win.
