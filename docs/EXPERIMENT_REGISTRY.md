# SEAM experiment registry

Single source of truth for every experiment, planned, running, done or
superseded. Rebuilt 2026-10-03 from every task list and plan in the project
history (Aug-Oct 2026) after several planned experiments were found missing
from the working plan.

## Rules (read first, every session, both workspaces)

1. Read this file at session start. Update it at session end, in the same
   commit as the work.
2. No experiment is ever deleted. It can only be marked DONE (with run_id),
   SUPERSEDED (with the replacing id), CHANGED (date + reason, old design kept
   in the row), or PARKED (date + reason + what would revive it).
3. Novelty is not a reason to drop an experiment. Only "no longer necessary"
   (say why) or "changed to fit what we know now" (say what changed).
4. Every DONE row names its sealed run_id(s). No run_id, not DONE.
5. Status VERIFY means the history is unclear. Check the repo before acting
   and replace VERIFY with a real status.
6. New ideas get a row immediately, even if not scheduled.

Status: DONE, RUNNING, NEXT (scheduled), PLANNED, BLOCKED (say on what),
PARKED, SUPERSEDED, VERIFY.
Priority: A = paper 1 cannot ship without it; B = strengthens a main claim;
C = extends (paper 2 or appendix). Priority orders work; it never removes it.

Deadlines: draft to Dr. Hao Nov 2; data freeze Nov 16; ISPASS December.

## Claims the experiments serve

- C1 Operating limit: hardware configuration sets how much context an agent
  can serve inside the SLO, and which constraint binds (latency, memory wall,
  context window, toolchain).
- C2 Retention: keeping only needed context moves the limit (23-25x headline).
- C3 Routing and cost: which routing triggers fire, and what the cloud bill
  is, depends on the device configuration.
- C4 Budget-quality: hardware configuration sets the test-time compute budget
  per turn, and that budget decides local quality.
- C5 Space shape: the configuration space differs in shape across platforms
  (axes appear, flip, collapse), not just in values.
- P2 Paper 2: DSE / replay that predicts configurations.

---

## 1. DONE (sealed)

| id | result | run_id(s) |
|---|---|---|
| CAP-1 placement | GPU 10,000 vs CPU 468 tokens (21.4x) | c2246b1f, 7f232f86 (CPU 500 d3dcbd3b superseded) |
| CAP-3 weight + tier (XPS, matched u8) | 4B-int8 9,890 SLO, wall at 10,500; 8B-int4 4,062 memory wall | a427233b, 69234ed5 |
| CAP-3 earlier f16 cells | 8B 3,156; 4B-int8 7,781 (allocation-bound) | 322b2f86, fea55e0c |
| T2S f16 limits | 4B 18,687; 8B 16,437 (coverage note pending, see VOIDS) | 5c714535, 051d2681 |
| CAP-4 / T2-3 prefill curves | XPS to 76k, exponent 2.12-2.25; T2S to ~100k, exponent 1.85 | 2b3316b6, 65e33de8 |
| 46k cold turn | u8 230 s, f16 253 s | 2b3316b6 |
| Residency | session prefill 5.17x; turn-0 hit 2.6 s to 0.10 s | cb781dbf, 9fdedb46, POST-CAP4 |
| DET-PROBE (+KV) | cache hits change greedy output 4/20 (u8 and f16); cold 60/60 same | cb9773be, c46d9c94 |
| WARM-KV | warm turn-2 at 12k: f16 0.639 s, u8 1.003, u4 0.946 | 72776603, 1587d2f4, dd2b0779 |
| DECODE-MATCH | int8 decodes 30-34% slower than int4 | 180dfbb9 |
| RESIDENT-LIMIT | f16/u8/u4 = 15,000 / 20,000 / 26,500 | 553b3a5c, cf3555d5, e4a22dac |
| H1-3POLICY (4B GPU) | passes 21/46/30; $0/$16.12/$8.17; triggers 81 no_parseable / 11 step_budget / 0 tool_exec | d482c621 |
| P0-v2 exchange rate | warm TTA GPU 2.47/3.26 s, CPU 9.29/11.17 s (4k/6k) | ac4e5472 |
| P1 A0 | 23/200 in budget | 8a529053 |
| P1 A1 unbounded [:100] | no gain vs A0 | 385cd4f6 |
| P1 A4 as implemented [:100] | 2/100; design flaw (no greedy fallback, greedy thinking) | 3b4d8207 |
| T2S parity control | median 9.8754 s, in band | c76fed24 (unsealed until closeout) |

Voids: b1a291f0 (dual residency on XPS corrupted state), 6c7f88f1 (BFCL cache
leak + credits), 52fab50c (T2S u8 cell, foreign launch). Unsealed/aborted:
16a6368b (control, clean), 98bf5873 (8B f16 range miss).
Seal MISMATCH, not citable until fixed: Q-8B 72d270e2, Q-KV 137f6f46, q_repro.

Seal check 2026-10-03 (`tools/seal_verify.py` on the `sealed_` tree when one exists). MATCH_LEGACY_SELF_REF is the verifier's accepted legacy seal, not a mismatch. Manifest-format seals (`.sealed` is the word sealed, plus `manifest.sha256.json`) are MATCH_MANIFEST when every other file is listed, none listed is missing, and every hash matches.

| run_id | under derived/ | seal |
|---|---|---|
| c2246b1f | derived/c2_ttft/sealed_c2246b1f-c588-4998-838a-5507da87e9ee | MATCH |
| 7f232f86 | derived/c2_ttft/sealed_7f232f86-2525-481b-a000-c6b8491bc224 | MATCH |
| d3dcbd3b | derived/c2_ttft/sealed_d3dcbd3b-5107-4b5e-a0dd-402f99f6f90c | MATCH |
| a427233b | derived/c2_ttft/sealed_a427233b-df1c-4c4a-87b9-c368bb270b31 | MATCH |
| 69234ed5 | derived/c2_ttft/sealed_69234ed5-a716-4274-b851-33509bdb9972 | MATCH |
| 322b2f86 | derived/c2_ttft/sealed_322b2f86-9571-46ae-be6a-ba1cec44e018 | MATCH |
| fea55e0c | derived/c2_ttft/sealed_fea55e0c-b9f8-4ba9-b5ea-558401910d74 | MATCH |
| 5c714535 | derived/c2_ttft/sealed_5c714535-9f36-4614-a594-698b6cd09296 | MATCH |
| 051d2681 | derived/c2_ttft/sealed_051d2681-4bb8-4f50-b9fc-b14441359ba6 | MATCH |
| 2b3316b6 | derived/cap4/sealed_2b3316b6-7f6e-474f-9177-bd5a89aeb58c | MATCH |
| 65e33de8 | derived/cap4/sealed_65e33de8-ac07-405a-a1f8-53698974afe9 | MATCH |
| cb781dbf | derived/bfcl_feasibility/x2_feasibility_table/sealed_cb781dbf-3486-4fbc-a69a-34026f801abe | MATCH |
| 9fdedb46 | derived/bfcl_feasibility/x2_feasibility_table/sealed_9fdedb46-3318-4abc-a56f-50b7d23d25ca | MATCH |
| POST-CAP4 | derived/cap4/POST_CAP4.md (analysis, not a run_id) | no seal |
| cb9773be | derived/h1_hybrid/sealed_det_probe_cb9773be-71a7-4cc8-b9ff-f7b18e5231f8 | MATCH |
| c46d9c94 | derived/h1_hybrid/sealed_det_probe_c46d9c94-3928-4e29-98c3-779f19895e25 | MATCH |
| 72776603 | derived/delta_prefill/sealed_72776603-7ea0-4279-a425-941d73a0bf57 | MATCH_MANIFEST |
| 1587d2f4 | derived/delta_prefill/sealed_1587d2f4-b30f-4be9-9c1d-6d0d04690c4b | MATCH_MANIFEST |
| dd2b0779 | derived/delta_prefill/sealed_dd2b0779-48c1-4ad6-9567-ed38e8e1fec9 | MATCH_MANIFEST |
| 180dfbb9 | derived/c2_ttft/sealed_180dfbb9-5ad6-446e-a3f2-0d6fa8eea196 | MATCH_MANIFEST |
| 553b3a5c | derived/delta_prefill/sealed_553b3a5c-dd68-4502-bb3f-1b6a10a61eb1 | MATCH_MANIFEST |
| cf3555d5 | derived/delta_prefill/sealed_cf3555d5-1361-434f-b1fb-745fc17e6843 | MATCH_MANIFEST |
| e4a22dac | derived/delta_prefill/sealed_e4a22dac-6301-4dfa-ae12-882328b6ba7c | MATCH_MANIFEST |
| d482c621 | derived/h1_hybrid/interleaved_d482c621-4292-4281-b6a1-8635e5eeb6da | MATCH_LEGACY_SELF_REF |
| ac4e5472 | derived/exchange_rate/sealed_ac4e5472-76a9-4999-bf0b-8274d27ce0ca | MATCH_MANIFEST |
| 8a529053 | derived/p1_quality/sealed_8a529053-fc47-486d-8809-6c699d156b06 | MATCH |
| 385cd4f6 | derived/p1_quality/sealed_385cd4f6-47d4-4ed0-8031-87ac7ef21816 | MATCH tree_sha256 01adc99801c5f571b0c912bbab91865ce68c12679ea1fa173dcaf9512f90bc13 |
| 3b4d8207 | derived/p1_quality/sealed_3b4d8207-ad36-480a-a717-1c146828d53c | MATCH tree_sha256 6bb5728cffb58c9409e3b94ba68767e640318e41e9fc67d2d39b51882e74c216. entries.jsonl companion seal not needed: pass and in_budget duplicate passed and in_budget_pass on all 100 rows |
| c76fed24 | NOT IN derived/ (searched derived/, docs/, repo filenames) | NOT IN derived/ |

---

## 2. XPS planned

| id | question | claim | pri | status | blocked by / notes |
|---|---|---|---|---|---|
| A4-FIX + B sweep | greedy-first, sampled thinking, only finished valid calls; B = 10/20/30 s | C4 | A | NEXT | amendment 8 registered, not started. Crossing: smallest B with McNemar p < 0.05, predicted B=20. Close-fraction floor 160/489 (3b4d8207). Order: A5 both halves, then B=10, B=20, B=30, then second-half entries. sha256 292ac69df1cf87d25b24c5a50fb8c37ee5b97049d379ba180482d0c7822da408 |
| A5 feedback-retry | retry with the wrong answer and error in context | C4 | A | NEXT | amendment 7 pred 23-28.06; amendment 8 runs both halves of seed 20260930 before the sweep |
| A2 retry-on-empty | resample on empty/unparseable while TTA < B | C4 | B | PLANNED | after A5 and the budget sweep |
| A3 check-and-retry | resample on tool error while TTA < B | C4 | B | PLANNED | note: 0 tool_exec errors in d482c621; may be near-null, still run |
| A1 bounded | best-of-4 cut at B, both seeds | C4 | B | PLANNED | unanimous-extras rule (amendment 6) |
| A6 CONSTRAINED (from Q-MECH) | xgrammar constrained decoding as a budget-spending arm | C4 | A | PLANNED | CHANGED 2026-10-03: Q-MECH arm folded into P1; constraint costs decode time |
| A7 SCHEMA-8 oracle / retrieval (from Q-MECH) | trim tool schema to 8 tools; frees prefill budget | C4, C2 | B | PLANNED | CHANGED 2026-10-03: folded into P1 |
| A8 SCHEMA-8 + CONSTRAINED | combined | C4 | C | PLANNED | after A6, A7 |
| OBS-COST | does constrained decoding turn loud failures silent and kill the emission trigger? | C3 | A | PLANNED | analysis on A6 data + one hybrid run; emission trigger did all routing work in d482c621 |
| SCHEMA-RET | published tool-gating method (embedding top-k); measure its hardware effect (limit, TTFT, cloud $) | C2, C3 | B | PLANNED | |
| P2 CPU infeasibility | CPU greedy on seeded 40-task subset; predicted ~0 in budget | C4 | A | PLANNED | prepared in P1 build |
| P3 hybrid cost | best P1 arm + emission escalation | C3, C4 | A | PLANNED | spend approval; cap from d482c621 |
| ALLOC-DIAG | decode past GPU alloc failures (logits-buffer pattern, OpenVINO #37501); read budget values on both hosts | C1 | A | NEXT | read-only; gates TIER-T2 error classes and ALLOC-MODEL |
| BUDGET axis | Shared GPU Memory Override: 4B + 8B limits at default vs max | C1 | A | NEXT | Zach sets driver setting by hand + reboot |
| ALLOC-MODEL (redesigned) | 4B at its limit, stateful vs CB chunked prefill: logits artifact or budget? | C1 | B | PLANNED | same boot as BUDGET if it fits |
| M-1 | 8B memory model; unexplained ~106 KB/token non-KV term | C1 | B | PLANNED | fold into ALLOC-DIAG analysis |
| CB-XPS | does chunked prefill change the 2.12 exponent and the limit? | C1, C5 | B | PLANNED | must include output-equivalence check (DET-PROBE) |
| RES-QUALITY | residency on vs off: does pass rate change, given 4/20 outputs change? | C1, C3 | A | PLANNED | local-only pair, $0 |
| H1-CPU | same 3 policies on CPU placement; SLO trigger should fire | C3 | A | PLANNED | spend approval |
| R0 cloud-only | 200 entries; cap v2 $72.03; expected ~$64.65 | C3 | A | PLANNED | spend approval |
| CACHE arm | cloud prompt caching (cloud analog of residency) | C3 | B | PLANNED | spend approval |
| H1 cache on/off rerun | counterbalanced policy order with cache flush | C3 | B | PLANNED (not folded into H1-CPU; derived/h1_hybrid/H1_CPU_PREREG.json measurement_status not_started; h1_rerun_cost_estimate.json scores 86d0f4cf and 8ffd8371, not a cache flush) | runner fix done; was the rerun folded into H1-CPU? |
| COST-DEEP | cloud cost on a workload that exceeds the limit (BFCL long_context or Rithwik trajectories); gives retention a dollar value | C2, C3 | A | PLANNED | without it, retention's cost effect is $0 by construction |
| Q-4 | add BFCL long_context, miss_func, miss_param categories | C3, C4 | B | PLANNED | long_context also serves COST-DEEP |
| Q-TIER-CLEAN | 8B vs 4B quality, clean seal | C1, C3 | A | PLANNED | fix 72d270e2 seal mismatch first |
| Q-KV-CLEAN | KV precision vs quality, clean seal | C1 | B | PLANNED | fix 137f6f46 seal mismatch first |
| SEM-IMPL | build semantic retention (required spans, original order) | C2 | A | BUILT (seam/retention_prompt.py; CPU smoke tools/retention_smoke.py; fixture tests/fixtures/retention_labels.json; RETENTION_PROTOCOL.md still absent; no sealed run) | was it built? |
| RET-0 | retention pilot: FULL / POSITIONAL / OBS-MASK / SEMANTIC | C2 | A | BLOCKED | SEMANTIC arm on Rithwik labels; OBS-MASK can run now |
| OBS-MASK | label-free observation masking arm | C2 | A | NEXT | no labels needed |
| RET x RES | retention under residency; append-stable variant | C2 | A | PLANNED | after RET-0 |
| RET-1 | full retention experiment (36 trajectories) | C2 | A | BLOCKED | R-LABELS, R-SIZE |
| XPS-PWR | 3 power plans x canary cell; battery vs AC; energy per task on the laptop | C1, C5 | B | PLANNED | was "Power/TDP probe" in Aug plan; needs energy read path (PCM/RAPL gate) |
| W-3 trajectory gap | 20 vs 10-14 unexplained | - | C | PLANNED | analysis only (6dd387aa) |
| Q-1 / anomaly | our ~10% vs published ~35% on multi_turn_base (XLAM format arm) | C4 | B | PLANNED (10% is 6225d6e1; published 35.25% / 34% in docs/RELATED_SEARCHES.md, source URL TO CONFIRM) | a reviewer will ask; status unclear |
| EMIT-GAP | emission 0.675 vs 0.775 on same entries | C3 | C | DONE (86d0f4cf, 8ffd8371; measured 0.675 vs predicted 0.775 in derived/h1_hybrid/H1_RESULTS.md; seal MATCH_LEGACY_SELF_REF) | |
| X-3 arm B | cpu-p + igpu: measure one cell or formally exclude | C1 | C | NO SEALED CELL (unsealed checkpoint derived/ceiling_a/fbe3ea9c; raw/af8b59e7 in_progress; no .sealed under derived/) | |
| N-2 window sweep | eviction window sizes vs ~95 KB/token residual | C1 | C | PLANNED (zero cells; docs/README_characterizations.md Axis 4; residual from 41e419bd) | |
| INF-2 onset | derive the uptime gate instead of the provisional 7200 s | infra | B | PLANNED | also T2S onset |
| X-1 reproducibility | sigma <= 0.10 instrument pair | infra | B | FAIL (raw/09dfe95d, raw/9e3ca312; sigma 0.145 and 0.159 in derived/fixed_throughput/kernel_power_repeat_correlation_20260806.md and docs/README_characterizations.md) | standing FAIL on XPS in Aug |
| PREREG-AMEND protocol | RETENTION_PROTOCOL.md with OBS_MASK, residency-interaction, interaction-cost outcomes | C2 | A | WRITTEN (docs/RETENTION_PROTOCOL.md) | builder seam/retention_prompt.py |
| PREREG-AMEND bisection | bisection runners record error_class and requested_bytes, including alloc_logits_pattern | C1 | A | WRITTEN (tools/run_c1_ceiling.py classify_c1_failure) | failure_kind is unchanged |
| PREREG-AMEND NPU control | NPU positive-control rule | C5 | A | WRITTEN (docs/NPU_PROTOCOL.md, seam/npu_validity.py) | registered before any NPU run |
| PREREG-AMEND predictions | OBS_MASK, CB_VS_STATEFUL, and BUDGET prediction files | C2 | A | WRITTEN (derived/retention/OBS_MASK_PREDICTIONS.json, CB_VS_STATEFUL_PREDICTIONS.json, BUDGET_PREDICTIONS.json) | no numeric limit invented |
| PREREG-AMEND alloc_diag | tools/alloc_diag.py | C1 | A | WRITTEN (tools/alloc_diag.py) | classifies a result JSON; does not open a prereg |

---

## 3. T2S planned

Window: Oct 2-6 (Rithwik takes it back Wed for a 90-min test). Ask for more
time after Wednesday; this list does not fit in the window.

| id | question | claim | pri | status | blocked by / notes |
|---|---|---|---|---|---|
| PARITY u8 | 4B and 8B u8 limits vs f16 | C1, C5 | A | DONE | c76fed24 control tree 1986ba64bda37fb148aca44d163e0076d814c4c01490df01e8a603c5a8df373e MATCH; d2d5cc4a 4B u8 18500 tree 2b0a94c6cefc92aac4cc4c5a2e049a7300bff6fd81ae2707a43c8ea2231e9f07 MATCH; 56c116a6 8B u8 16437 tree c9bc509818485bd98e09b3611afb3ceba744a89d9cbb0efd9558c61a2bb7e7bf MATCH. plan.json and summary.json of the first two used the launcher boot-end stamp rule. |
| RESIDENT-T2 | 4B: one f16 point at 131,072 (context window binds, not memory); 8B: predicted memory walls, search if inside context | C1, C5 | A | PLANNED | CHANGED 2026-10-03 from full 3-precision search |
| P1-T2 | A0 + fixed A4 at B = 10/20 on the faster GPU: does thinking fit? | C4, C5 | A | PLANNED | A4 fix committed; amendment 8 registered |
| P0-T2 | exchange rate on T2S | C4 | B | PLANNED | launcher profile |
| P1-T2 8B | P1 arms with 8B (more quality headroom) | C4 | B | PLANNED | |
| NPU-1 | NPU as third placement; limit set by toolchain (MAX_PROMPT_LEN) | C1, C5 | A | PARTIAL | MAX_PROMPT_LEN is the load-time axis (1024, 2048, 4096, 8192, then double until load fails). One detached session per setting: the pilot-extrapolated bound of the fixed ladder is above 7200 s. IR is INT4_SYM group_size 128. Binding per setting is TOOLCHAIN_CAP, LATENCY, or LOAD_FAIL. Profile tools/launch_t2s_npu1.ps1. Prereg derived/npu/NPU1_PREREG.json sha256 483ed364c2fef94b65e6822404702bf576c5e80d600ab40e701e60196565ce07. Predictions registered. Attempt c3caa5fc crashed before any cell (T2S_NPU1_SUMMARY state crashed, cells empty). No data. Boot 792e909d session 1 cell 680b031a (readback 1024, ttft_limit_n 960) is UNGUARDED (derived/VOIDS/notes/680b031a.md), sealed tree ed702af0d10f87e4b3fb7f0058f167a408d8ee82e3550e85b27e0a07e9426989 MATCH. prompt_length at 960 is 960, 960, 960. prompt_length at 1024 is null, null, null. The summary file says LATENCY; corrected classification TOOLCHAIN_CAP is analysis/npu/680b031a_binding.md. Prediction b is not scored from an UNGUARDED run. Next NPU run: rerun 1024 with the GPU canary armed, then 2048, 4096, 8192, and 16384 load-only. Amendment 2026-10-05 in docs/NPU_PROTOCOL.md. Update 2026-10-07: 04d189da = guarded 1024 rerun (armed; t1 0.161907, t2 0.187115), TOOLCHAIN_CAP, readback 1024, decode at limit 16.53 tok/s vs GPU 34.3, ttft_limit_n to confirm (expected 960). NOT YET SEALED, not DONE. 28cf811d (request 2048): REFUSED (readback mismatch; request 2048, readback 1024, load_s 94.72), UNGUARDED (refused before arming), kept, not void, not yet sealed. CHANGED 2026-10-07: 2048 rerun and 4096 / 8192 / 16384 HOLD pending NPU-MAXLEN-DIAG (derived/npu/diag/NPU_MAXLEN_DIAG_RULE.md); the ladder continues per its verdict. Note 2026-10-07 (NPU-MAXLEN-DIAG run 1): the runner's readback can never read the pipeline on genai 2026.2.1 (LLMPipeline has no get_property; it always falls back to the core value), so hypothesis b is confirmed. The 1024 rungs (680b031a, 04d189da) are unaffected because 1024 equals the default. Amendment 2026-10-07 (Zach approved, pre-run): docs/amendments/NPU_AMEND_2026-10-07.md sha256 e985ef645097b977e5b9c7de004122d254f5df345e9ae15a83c25af2488a2db8: key MAX_PROMPT_LEN + MIN_RESPONSE_LEN=8; readback replaced by realized-capacity probes P1 (cap-64 accepted, exact count, valid) and P2 (cap+64 refused by the runtime length check), else REFUSED_CAPACITY; single template (apply_chat_template=False, list form, prompt_length = pipeline count); ladder: guarded 1024 rerun, then 2048, 4096, 8192, 16384 load-only. Sealed 2026-10-07 from host listings derived/npu/NPU_SHA256_20261006b.txt and NPU_SOURCE_MANIFEST_20261006b.txt (12 files HASH_MATCH): 04d189da sealed tree 9c3fce99996ca1fc099d39ec4072ffa4a83bf213605ab60facae0a74076a364f MATCH, ttft_limit_n 960 (summary), TOOLCHAIN_CAP, armed; 28cf811d sealed tree 00659bdf64424db125b03c461c4109ec95739d1c6d877413ffdcd69dc901b98a MATCH, REFUSED (readback artifact), UNGUARDED, kept. Annotation (amendment 2026-10-07 item 5): 680b031a and 04d189da sent n+8 tokens through a double chat template; ttft_limit_n 960 = 968 sent; exact_match_vs_gpu confounded and not interpretable; binding TOOLCHAIN_CAP unchanged. NPU-1 is not DONE: the 1024 rerun under the amendment is next. Update 2026-10-08: 1024 rerun 8ccfb38c (git 75436f8) ended REFUSED_UNARMED_CANARY, UNGUARDED (6 probes; 2 canaries; gate arms on the 3rd). Amendment 2026-10-08 (pre-run): docs/amendments/NPU_AMEND_2026-10-08_GUARD.md sha256 e58dd98d7c6656bca39d72298fd351fadeb2ac67be21d1522fab934939c37abf: C=3 canaries before the first probe (else REFUSED_UNARMED_CANARY, no probe), interval canaries unchanged, closing canary after the last probe; min_new_tokens=8 so decode is measurable; thresholds, drift rule and N formula unchanged; 04d189da unaffected. Next: guarded 1024 rerun under both amendments. Sealed 2026-10-08 from host listings derived/npu/NPU_SHA256_20261007.txt and NPU_SOURCE_MANIFEST_20261007.txt (4 files HASH_MATCH): 8ccfb38c sealed tree 2dbab172a35255ab4e59d8defd63b8f925cf7e4687f9e931cdcaa376f5aaaf4d MATCH, REFUSED_UNARMED_CANARY, UNGUARDED, kept as a record, not cited, not void; capacity check passed (P1 960 accepted, pipeline 960; P2 1088 refused by the length check, stated cap 1024); decode_tok_s_at_limit null (one streamed token per generate). Prediction b is not scored from it. Update 2026-10-08b: 1024 rerun 9d6d7f66 (git f86a137) ended FAIL_CANARY_DRIFT (armed; turn1 0.9113 vs ref 1.0137, rel 0.101 > 0.0771) at the first canary after the paired GPU pipeline was created (+2.5 GB working set; same step in 8ccfb38c). Amendment 2026-10-08b (pre-run): docs/amendments/NPU_AMEND_2026-10-08b_GUARD_STATE.md sha256 68d577215c7f674e7f97eadf5aa07316af488af29d6f64a3cce894f629984147: create the paired GPU pipeline and run one untimed GPU warm-up generate (the 64-token rung prompt) before the C=3 calibration canaries; else REFUSED_GPU_WARMUP; everything else in 2026-10-08 unchanged. Observation: 04d189da's calibration likely included the same step (threshold_t1 0.161907); not relabeled. |
| NPU-MAXLEN-DIAG | diagnostic for 28cf811d readback mismatch (request 2048, readback 1024): is MAX_PROMPT_LEN applied, is the readback right, or is 1024 a runtime clamp | C1, C5 | A | DONE (diagnostic; nothing cited) | Diagnostic, not a measurement; nothing cited. Arms K-DOC (MAX_PROMPT_LEN=2048 + MIN_RESPONSE_LEN=8) and K-NPUW (NPUW_LLM_MAX_PROMPT_LEN=2048), one child each, prompts ~900 and ~1500 tokens. Decision rule D1-D4 committed before the script: derived/npu/diag/NPU_MAXLEN_DIAG_RULE.md sha256 f7af7798e30410f17b3d6fb79695da6b77f250aea9cd8c67b146b57d84ee388d. Outputs derived/npu/diag/. Decides how the NPU-1 ladder continues. Script tools/npu_maxlen_diag.py (tests/test_npu_maxlen_diag.py); foreground on T2S, under 10 min. Run 1 (rule v1, git 22a1a9b, EVO-T2S 2026-10-07 18:03-18:06 UTC): derived/npu/diag/diag_20261007T180320Z/, verdict D4 (kept, not relabeled). Cause: pipeline_input_tokens null for all 4 prompts -> truncation_unknown -> band A not accepted in either arm. Observations (diagnostic, not citable): both loads OK (~95 s); K-NPUW 1500 refused by the runtime check "input_ids.get_size() <= m_max_prompt_len" ("up to 1024 tokens. 1508 is passed"); K-DOC 1500 generated, TTFT 2.77 s vs 1.39 s at 900; r1 = 1024 via core fallback in both arms because LLMPipeline (genai 2026.2.1) has no get_property. Rule v2 (pre-run, before the v2 script): derived/npu/diag/NPU_MAXLEN_DIAG_RULE_V2.md sha256 38dc1416271662a963dd809a234ca9a323d89e4d3e0f62848db6e6ae036dab93; changes: input tokens from generate([prompt]) DecodedResults.perf_metrics.get_num_input_tokens(), band C [2100,2150] must be refused by the runtime length check in the D1 arm, explicit recorded greedy config. v2 implemented in tools/npu_maxlen_diag.py (--rule-version 2 default; --rule-version 1 and --classify keep run 1 readable, run 1 re-classifies D4); not yet run. Run 2 (rule v2, git 29a5214, EVO-T2S 2026-10-07 22:06-22:09 UTC): derived/npu/diag/diag_20261007T220633Z/, verdict D1 key_fix+readback_fix. K-DOC: ~900 accepted, pipe_in 908, valid, TTFT 1.392 s; ~1500 accepted, pipe_in 1508, valid, TTFT 2.742 s; ~2125 refused by runtime check input_ids.get_size() <= m_max_prompt_len (stated cap 2048). K-NPUW: ~900 accepted, pipe_in 908, valid, TTFT 1.389 s; ~1500 refused; ~2125 refused (same runtime check, stated cap 1024). r1 after load = 1024 in both arms (core fallback). pipe_in = realized + 8 (double chat template). |
| NPU-1-CW | channel-wise int4 (group_size -1) on NPU | C1 | C | PARKED | conversion or download of Qwen/Qwen3-4B INT4_SYM group_size -1 waits for Rithwik's OK |
| NPU-2 | int8 on NPU crashes: first infeasible cell | C5, P2 | B | PARTIAL | Boot 792e909d cell 27b4841d, infeasible, generated false, reason npu_int8_not_run_past_load. error_class null. load_error null. Sealed tree 2a1ff44dafb64e11ee77f34e6a688b2bb59e2f20a43121d2f3ec5eaad2de28d2 MATCH. |
| HET-1 | phase split across devices; primary arm NPU prefill -> GPU decode (AMD direction), contrast GPU prefill -> NPU decode; measure handoff cost | C5 | B | PLANNED | feasibility spike first: can OpenVINO pass KV across devices? |
| CB-T2 | continuous batching + prefix caching: dominated on XPS, best on 64 GB? Includes concurrency (sessions/hour) | C5 | A | PLANNED | output-equivalence check required (DET-PROBE, #4367) |
| SPEC-T2 | speculative decoding, 0.6B draft on CPU / GPU / NPU | C4, C5 | A | PLANNED | re-verify 0.6B pin; pair with A4 budget sweep |
| TIER-T2 limits | 14B and 30B-A3B cold limits | C1, C5 | A | PLANNED | YAMLs in hold_configs_models; error class per ALLOC-DIAG; download OK from Rithwik |
| TIER-T2 quality | 14B / 30B-A3B BFCL quality: where does local approach cloud? | C3, C5 | B | PLANNED | ~3 h each |
| FP16-T2 (W-4) | unquantized weight baseline: limits + quality (also tests the 35% anomaly) | C1, C5 | B | PLANNED | fp16 IR pinned (3dabb409) |
| DUAL-T2 | two models resident (corrupted on XPS, b1a291f0) | C5 | B | PLANNED | short; gates SPEC-T2 |
| PWR-T2 | energy per completion split by prefill/decode; PL 25 W vs 80 W | C5 | B | BLOCKED | energy read path; power-limit change needs Zach + Rithwik OK |
| THERMAL | XPS variance past 32k: heat or memory? | C1 | C | PLANNED | fold into PWR |
| T2-4 MEM-SWEEP | bcdedit removememory: same silicon at 16/24/32/48/64 GB; memory as a within-machine axis | C1, C5 | A | BLOCKED | needs reboots: Tailscale unattended + Rithwik OK |
| R2b-8B / R2c-8B | 8B routing: same policy, different hardware, different cloud cost | C3 | A | BLOCKED | API key on T2S (Zach), spend approval |
| T2S onset | derive onset on evo-t2 (currently borrowed 657 s from XPS) | infra | B | PLANNED | |
| T2S exponent | reconcile 1.85 vs 1.891 (65e33de8) | C1 | C | PLANNED | analysis |

---

## 4. Analysis and writing (no machine time)

| id | what | pri | status |
|---|---|---|---|
| OPLIMIT-FIG | operating limit per config, colored by binding constraint | A | PARTIAL (evo-t2 u8 points added: 4B 18500 d2d5cc4a, 8B 16437 56c116a6; f16 rows kept, kv distinguished) |
| COST-FRONTIER | cost vs completions, one curve per configuration | A | 4B row done (d482c621); needs R0, H1-CPU, 8B |
| CENSUS-D | failure classes A/B/C/D (silent failures) | A | PARTIAL (A/B/C on 86d0f4cf in derived/h1_hybrid/H1_RESULTS.md; D UNAVAILABLE; trigger split d482c621) |
| SPACE-SHAPE | axes that appear / flip / collapse across platforms | A | PLANNED (after T2S runs) |
| P2 DSE / replay | fdr_replay predictor, cross-platform prediction (D-1c, T2-3) | C | PLANNED (paper 2) |
| CORRECTIONS | KV claim wording, OPLIMIT colours | B | PARTIAL (KV wording in derived/WITHDRAWN.md 2026-09-23 and 2026-09-25; OPLIMIT colours NOT FOUND (searched: docs/, derived/)) |
| RELATED-LOG | docs/RELATED_SEARCHES.md before any "first" claim | A | DONE (docs/RELATED_SEARCHES.md, search date 2026-09-23) |
| P1 slow canary | f16 canary turn-2 0.86-0.96 s vs 0.70-0.76 | B | OPEN |

---

## 5. Rithwik dependencies

| id | what | gates | status |
|---|---|---|---|
| R-LABELS | span labels per trajectory | RET-0 SEMANTIC, RET-1 | DATE NEEDED |
| R-SIZE | artifact size sweep 100-8,000 tokens (the 21% is from 95-234 token probes) | RET-1 headline | OPEN |
| R-SCORE | four-way scoring | correctness numbers | OPEN |
| R-LLAMA / RET-1L | llama.cpp arm on T2S | RET-1L | OPEN |
| R-EVICT | published eviction methods vs ablation truth | related work | OPEN |
| T2S time | window extension after Wed; watchdog paused; Tailscale unattended; model downloads | all T2S rows | ASKED |
| 0921 coverage | confirm no T2S jobs 2026-09-21 16:30-19:00Z | 5c714535, 051d2681 note | ASKED (derived/VOIDS/PENDING_T2S_0921_coverage.md) |
| GRID-1 / PROTO-1 | shared config grid; retention protocol sign-off | joint paper | NOT FOUND (searched: docs/, derived/, git log --all --grep GRID-1) |

---

## 6. Superseded (kept for the record)

| old id | replaced by | why |
|---|---|---|
| CAP-2 turn-2 limit | WARM-KV + RESIDENT-LIMIT | measured warm turn and resident capacity directly |
| MEM-CEIL, F16-REPRO | CAP-3 walls + RESIDENT-LIMIT | ceiling characterized |
| RES-DECOMP | POST-CAP4 | residency = ~100% avoided prefill |
| C-1 / C-2 / C-3 | CAP-1..4, COST-FRONTIER | renamed and extended |
| Q-MECH BoN-3 | P1 A1 | same mechanism under the budget rule |
| Q-MECH constrained / schema | P1 A6-A8 | CHANGED 2026-10-03, still planned |
| ALLOC-MODEL fp16-4B | ALLOC-MODEL stateful vs CB | fp16 fails at load under both hypotheses |
| Thinking-mode axis question | P1 A4 | thinking now tested under the budget |
| T-1 8B-int8 / 14B-int8 ladder | PARKED | no 8B-int8 IR in OpenVINO org; revive if one is published |

---

## 7. Schedule to freeze (each XPS boot ~2 h; ask before any launch or spend)

- Oct 3-6, T2S: PARITY (done) -> NPU-1/NPU-2 session 1 (680b031a UNGUARDED) -> guarded 1024 rerun, then 2048, 4096, 8192, 16384 load-only + DUAL-T2 -> P1-T2
  A0 + A4 B=10 -> SPEC-T2 decode -> CB-T2 -> TIER-T2 limits -> FP16-T2.
  Ask for time after Wed for the rest (HET-1, PWR-T2, T2-4, TIER quality,
  R2b/R2c-8B, P0-T2, P1-T2 8B, RESIDENT-T2).
- Oct 5-11, XPS: A5 both halves, then sweep B=10, B=20, B=30, then
  second-half entries (amendment 8) -> ALLOC-DIAG + BUDGET (+ ALLOC-MODEL) ->
  RES-QUALITY -> OBS-MASK.
  Cursor builds A6-A8 and SCHEMA-RET meanwhile; fix Q-TIER/Q-KV seals.
- Oct 12-18, XPS: A6/A7 -> OBS-COST -> P2 -> A2, A3, A1 bounded ->
  Q-TIER-CLEAN, Q-KV-CLEAN -> CB-XPS -> XPS-PWR gate.
  Spend block (approval): H1-CPU, R0, CACHE arm.
- Oct 19-25: RET-0 (labels) / RET x RES -> COST-DEEP + Q-4 long_context ->
  P3 (spend) -> SCHEMA-RET.
- Oct 26-Nov 2: analysis, figures, SPACE-SHAPE, draft to Dr. Hao.
- Nov 2-16: fill gaps from this registry in priority order; freeze Nov 16.
