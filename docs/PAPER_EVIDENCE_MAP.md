# Paper evidence map (2026-10-15)

One table per paper. Every number or claim in the paper maps to sealed
run_id(s) on our side, to "Rithwik side (needs his run ids)", or to NOT YET
MEASURED / NEEDS RUN_ID. Nothing here is a new finding; it points at sealed
data or says it is missing. Thesis: docs/THESIS.md. Abstracts are verbatim
and are not edited here; flags for Zach are listed under each table.

Status words: SEALED (run_id named, sealed tree in derived/), HELD /
WITHDRAWN (derived/WITHDRAWN.md), RITHWIK, NOT YET MEASURED, NEEDS RUN_ID.

## ISPASS combined paper (docs/PAPER_ISPASS_ABSTRACT.md)

| # | abstract number or claim | our evidence | status |
|---|---|---|---|
| I-1 | "latency binds at approximately 9,750 tokens" (unified memory, 10 s TTFT SLO) | 9,750 is c647f0c7: HELD in derived/WITHDRAWN.md (canary never armed, RECONSTRUCTED_UNGUARDED) and SUPERSEDED 2026-09-24 by the guarded 10,000 (c2246b1f, XPS GPU 4B u8). SLO-SENS interpolates the XPS GPU edge at 10,175 (2b3316b6). | HELD; cite 10,000 (c2246b1f) or re-measure |
| I-2 | "while memory remains uncommitted" at the latency limit | Memory binds far above the latency limit: resident-session limits f16/u8/u4 15,000/20,000/26,500 (553b3a5c, cf3555d5, e4a22dac); C-1 f16 completed n = 44,742 by paging (83127e1b, no seal in the census). c2246b1f canary free memory 7,143-7,189 MB at canary start; no committed-memory reading at the 10,000 rung was located. | PARTIAL; committed-memory at the limit NEEDS RUN_ID (read c2246b1f probes.ndjson) |
| I-3 | placement: "service-level swing from zero to complete compliance" | x2 feasibility table (derived/bfcl_feasibility/x2_feasibility_table/x2_derived_table.json), BFCL multi-turn, SLO TTFT <= 10 s and decode >= 6 tok/s: cpu-p NON_RESIDENT 0.0 (cb781dbf) vs gpu_only NON_RESIDENT 1.0 (afd1aa21). Also cpu-p RESIDENT 0.729 (9fdedb46), gpu_only RESIDENT 1.0 (0963168f). Seals record WSH contamination, bounded at 6.6% / 7.5% of wall (cb781dbf / 9fdedb46). Note: docs/README_characterizations.md prints 95.7% for gpu_only no residency from the older a621ff7d session; the sealed x2 cell is 100%. | SEALED |
| I-4 | residency "5.17-fold improvement" | cpu-p session wall NON_RESIDENT 8,148.5 s / RESIDENT 1,576.4 s = 5.169 (cb781dbf, 9fdedb46). It is a cpu-p result; on gpu_only the same ratio is 750.5 / 489.5 = 1.53 (afd1aa21, 0963168f). | SEALED (state "on CPU placement") |
| I-5 | combined limit "from 9,750 to approximately 46,000 tokens at the same service level objective and the same measured correctness" | Measured by us per Zach (corrected 2026-10-16, Task AS: not Rithwik side). The data is not in this repo or in ~/seam_closeout_10{06,08,12,13}; Zach will supply the location or run_ids. SEM-IMPL is built but has no sealed run in this repo; RET-0/RET-1 are blocked here. Baseline check needed: the sentence's 9,750 (c647f0c7) is HELD in derived/WITHDRAWN.md and the citable XPS cold edge is 10,000 (c2246b1f); confirm which baseline run the 46k measurement used. 2b3316b6 is an unrelated 46k cold-turn timing on our side (u8 230.4 s, u4 239.8 s, f16 252.7 s). | MEASURED (Zach), data location/run_id pending; not yet in this repo |
| I-6 | "tasks require roughly 21 percent of their artifact" | From 95-234-token probes only (registry R-SIZE, OPEN). No run in this repo. | RITHWIK (needs his run ids); R-SIZE open |
| I-7 | "positional truncation retains 44 to 76 percent" | No run in this repo. | RITHWIK (needs his run ids) |
| I-8 | three failure regimes (context-managed silent drop; unified-memory spill with latency; discrete VRAM explicit OOR) | Ours, unified memory: C-1 f16 to n = 44,742 by paging with Available 0 MB (83127e1b); CAP-3 8B allocation ceiling 3,312 CL_OUT_OF_RESOURCES (322b2f86); a 36,500 CL_OUT_OF_RESOURCES ceiling on the default ("dynamic") KV arm, once mislabelled f16 and matched to u8 in August (2804d7fa; docs/PROJECT_STATE.md retraction 2); T2S B390 CL_OUT_OF_RESOURCES in the GPU canary with the NPU model loaded (c759d72f). Silent-drop and discrete-VRAM regimes: Rithwik side. | PARTIAL: unified side SEALED (83127e1b unsealed); others RITHWIK |
| I-9 | silent drop gives "confident, categorical wrong answers in every case measured, with no hedging language and no abstention in two of three model families" | No run in this repo. | RITHWIK (needs his run ids) |
| I-10 | six-axis characterization with failure regime per run | Axes on our side: placement (c2246b1f, 7f232f86), residency (cb781dbf, 9fdedb46, afd1aa21, 0963168f), KV precision (553b3a5c, cf3555d5, e4a22dac), weight precision (a784f5ec, 6225d6e1, 1d8db970), model tier (a427233b, 69234ed5), context budget / retention (DEMO-1 V3 71d33f7a + ab88f47f vs V4 a678926e). Regime recorded per run: not a field today. | PARTIAL |

Flags for Zach (abstract not edited):
1. "Intel Arrow Lake" does not match our hardware. The XPS is a Core Ultra 5
   325 (Panther Lake, Xe3) and the T2S has an Arc B390 (Panther Lake / Xe3).
   Check whether Rithwik's Intel machine is Arrow Lake.
2. Sixth axis naming: ISPASS "context budget" vs repo "retention" vs ERN
   "attention window".
3. Failure regimes depend on runtime policy x memory architecture, not
   memory architecture alone. Current llama.cpp (llama-server b7062) returns
   HTTP 400 on overflow; older builds (b6721) truncated silently. Ollama on
   NVIDIA offloads layers to CPU rather than raising OOM. vLLM refuses at
   startup. We hit OpenCL CL_OUT_OF_RESOURCES on unified-memory Intel (B390,
   c759d72f, GPU canary with the NPU model loaded). Intel's ~4 GB
   per-allocation limit applies to pre-Xe2 hardware, so it probably does not
   explain an Xe3 failure; the cause is open (registry B390-OOR).
4. Ollama default context is tiered by VRAM since Feb 2026 (< 24 GiB 4k,
   24-48 GiB 32k, >= 48 GiB 256k). Still 4096 on our machines; cite the
   Ollama version. num_ctx sent via /v1 is silently dropped.
5. The ~46,000 combined limit (I-5) is MEASURED (Zach), data location/run_id pending; not yet in this repo (corrected 2026-10-16;
   not Rithwik side).
   Separately, 9,750 (c647f0c7) is HELD (I-1) and the citable XPS cold edge
   is 10,000 (c2246b1f); check the sentence's baseline against whichever
   run the 46k measurement used.
6. 5.17x is a CPU-placement number (I-4).

## Paper 2 (docs/PAPER2_ABSTRACT.md)

| # | claim / input | evidence | status |
|---|---|---|---|
| P-1 | reactive routing data (paging / OOR regimes give a signal) | DEMO-1 slo_escalate cells: XPS V1 f7343708, V2 1acc8c58, V3 71d33f7a + ab88f47f, V4 a678926e; T2S V1 b026f3fd, V3 a4284ab0, V4 30caa847 (f7de976b local share only) | SEALED |
| P-2 | quality-reactive routing | d482c621 (slo / emission / bounceback on W-3 200; triggers 81 no_parseable, 11 step_budget, 0 tool_exec) | SEALED (per-policy local TTFT withdrawn, ORDER_AUDIT) |
| P-3 | pre-generation feasibility check (small prototype) | DEMO-2 hybrid_full ctx_overflow (checked before every local generate); registered (DEMO2_PREREG_v1), not run | NOT YET MEASURED |
| P-4 | switch cost: re-sent context on escalation | measured cloud input tokens per escalated entry (docs/amendments/DEMO2_DESIGN_2026-10-14.md): base V2 1acc8c58 median 91,286 (30 billed); long FULL V3 T2S a4284ab0 median 122,071 (4); OBS_MASK V4 XPS a678926e 70,111 (9), V4 T2S 30caa847 62,907 (1). Range 63k-122k on long context. | SEALED (cloud side); device-side re-prefill by configuration NOT YET MEASURED (P2-SWITCH-COST) |
| P-5 | orchestration overhead decomposition | apu_characterization/OPEN_QUESTIONS.md: harness_strict 3.9-7.0 ms/turn (table medians), from a mock LLM, labelled debug_only ("verify before citing") | NEEDS RUN_ID (mock; not citable as is) |
| P-6 | hardware BOM prices | none recorded | NOT YET MEASURED (P2-BOM; cited prices only) |
| P-7 | measured context-dropping regime under a context-managed runtime | none on our side (R-LLAMA / Ollama) | NOT YET MEASURED (P2-CONTEXT-DROP) |
| P-8 | difficulty classifier | none | NOT YET MEASURED |
| P-9 | cached path | none (CACHE arm row PLANNED) | NOT YET MEASURED |
| P-10 | predictive router | none | NOT YET MEASURED (P2-PREDICTIVE-ROUTER) |
| P-11 | Pareto surface quality x cloud $ x BOM; provisioning case study | DEMO-1 cells give quality and $ per configuration; BOM missing | NOT YET MEASURED |

Wording constraints from the 2026-10-15 sweep apply to every P2 sentence
("existing routing systems ... react to observed quality" must become the
pre-/post-generation wording; see docs/RELATED_SEARCHES.md).

## ERN (docs/PAPER_ERN_ABSTRACT.md)

Every ERN number is dated 2026-09-07 and is to be refreshed with current
data. Run_ids below are where each number comes from today.

| # | ERN number or claim | source run_id(s) | refresh note |
|---|---|---|---|
| E-1 | "Placement and residency change latency and leave memory alone" | contradicted for placement: peak working set cpu-p 9.46-10.70 GB vs gpu_only 5.12 GB at n = 12,000 (docs/README_characterizations.md axis 1) | working-set run_ids NEEDS RUN_ID (added in 8ca29e9 with no run_id); rewrite the sentence |
| E-2 | turns meeting the target "from 0% to 100%" | cb781dbf (cpu-p NON_RESIDENT, 0%) -> 0963168f (gpu_only RESIDENT, 100%); gpu_only alone already 100% (afd1aa21) | SEALED; say placement alone gives 0 -> 100% on this workload |
| E-3 | 16-bit "runs prefill 15 to 27 percent faster at depth" (turn-2 delta prefill, n >= 8,000, delta 1,000) | 41e419bd (Finding 2) | SEALED; WARM-KV 72776603 / 1587d2f4 / dd2b0779 at 12k (f16 0.639 s vs u8 1.003 / u4 0.946) is the current figure |
| E-4 | "INT8 holds 1.76 GB more resident memory" | a784f5ec: predicted +1.763 GB, observed +1.737 GB | SEALED; cite the observed 1.74 GB |
| E-5 | INT8 "decodes 1.3 to 1.5 times slower than INT4" | a784f5ec: 1.508 / 1.496 / 1.339 at n = 2,000 / 5,000 / 12,000. Registry DECODE-MATCH 180dfbb9 says 30-34% slower. Intel's published tables give about 1.52-1.67x at short context (OpenVINO 2026.3) | SEALED; reconcile with 180dfbb9 and cite Intel's range |
| E-6 | same completion "10.0% vs 11.5%, McNemar p = 0.55" | 6225d6e1 (int4 20/200) vs 1d8db970 (int8 23/200), b = 4, c = 7 | SEALED |
| E-7 | no parseable tool call "32 entries ... against 7 (odds ratio 4.57, p = 7 x 10^-5)" | same pair 6225d6e1 / 1d8db970; OR 4.57 [1.98, 12.27], p = 7.0e-5 (docs/PROJECT_STATE.md) | SEALED; "Compression Breaks Discipline" (NF4, single-turn) finds no rise for Qwen3-4B; state the INT4 scheme and multi-turn setting |
| E-8 | 200 BFCL v4 multi-turn entries, checker passes 200 gold | W-3 pin (d482c621 entry set) | refresh with run_id of the gold check (NEEDS RUN_ID) |
| E-9 | "Every cell reads its cache precision back" | readback in delta_n / run_h1_hybrid (_assert_kv_readback) | Part 5a: the property reads "dynamic"; the compiled port type is the real readback (KV-DEFAULT-READBACK) |
| E-10 | "no configuration wins on all four" | hypothesis | cite ConfigSpec 2604.09722 as precedent |
| E-11 | 64 GB extension | T2S limits 5c714535, 051d2681, d2d5cc4a, 56c116a6; DEMO-1 T2S cells | SEALED (partial) |

## Threats to validity (running list, 2026-10-15)

- BFCL baseline gap (registry BFCL-BASELINE). Our multi_turn_base pass
  rate is 10.0% (6225d6e1, int4) and 11.5% (1d8db970, int8). The official
  leaderboard (last updated 2026-04-12) has no row for the model we run.
  Its nearest row, Qwen3-4B-Instruct-2507 in FC mode, scores 26.50% on
  multi-turn base and 22.12% on multi-turn overall. Our variant is base
  Qwen3-4B, OpenVINO INT4 IR, thinking off, native <tool_call> format, own
  harness with the official checker. These differences are not separated.
- KV default (KV-DEFAULT-READBACK). The "default" KV precision is read
  from a property that says "dynamic" (the pre-compile placeholder). By
  the 2026.2.1 source the compiled default on a PA model is i8, not u4
  (corrected 2026-10-16); not yet read back on our hosts (pilot P0).
- Scheduler settings (PREFIX-CACHE-AUDIT, NONRES-CHUNK). The
  NON_RESIDENT hybrid cells passed a bare SchedulerConfig. The sealed cold
  limits used a plain LLMPipeline. The two may prefill in different batch
  sizes.
- Run-to-run variance. Fault-free BFCL multi-turn runs reach the same end
  state only 63.3% of the time (2610.10062). Most of our hybrid cells are
  single runs.
- NPU timings split at the 2026-10-14 Windows Update reboot (NPU-DRIVER).
- Retention numbers (21%, 44-76%) rest on 95-234-token probes (R-SIZE).
