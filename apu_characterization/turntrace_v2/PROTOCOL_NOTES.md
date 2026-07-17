# TurnTrace v2 — protocol notes (pre-hardware)

## Rev C redirect — C-P0 protocol freeze (2026-07-16)

**Validity class:** `orchestration_significance_characterization`.

Rev C replaces the rev B co-mission and its never-built D2/D3 figures. P1,
P2, P3, D4, D5, Track C, CallRecord attribution, and replay-bundle work remain
valid inputs. Layer 1 is now an incidental output: characterization
requirements win any design conflict.

The claim, null, rungs 1c/2c/3c, paired arms, intervention ablations, five
task classes, new gates, blocked claims, and C-D1 through C-D5 deliverables are
frozen in `protocol_turntrace_v2.json` (`turntrace_v2.1`, rev C). No rev C
intervention run or live API call is permitted until G-BUDGET-WALL is closed.

**Phase status (2026-07-16):** C-P0 and C-P1 are **done** (protocol/payload
freeze + collector/gates/mock path; `make turntrace-v2-gate` green). C-P2 is
**blocked** on ≥16K CPU model calibration and a passing G-BUDGET-WALL
projection. No quotable rev C A/B headline numbers exist yet.

### G-ARM-A-HONESTY — baseline evidence map

Arm A is not a deliberately damaged prompt. It preserves the actual baseline
path for each adapter and deployment:

| Axis | Baseline evidence | Arm A rule |
|------|-------------------|------------|
| raw Python context assembly | `harnesses/raw_python.py` passes each turn's complete `turn.messages` list to `engine.complete`; it does not maintain an append-log object or stable-prefix contract | Preserve that supplied full-message/retemplate path |
| LangGraph-shaped context assembly | `harnesses/langgraph_harness.py` passes each `GraphStep.messages` list in full; no byte-immutability or layout contract exists | Preserve the graph-step full-message path |
| Local cache lifetime | Current llama.cpp adapter exposes `use_cache`; cache-disabled calls are an existing measured path. Continuum/CacheTTL documents the production pattern that finished-request KV is ordinarily reclaimable/evicted across tool pauses and adds TTL retention specifically to override it | Arm A uses verified cache-disabled/evicted behavior only where that deployment default or documented pattern applies; it may not disable a cache that the selected framework actually retains by default without labeling a separate mechanism-control cell |
| Cloud prefix caching | OpenAI caching is automatic for eligible stable prefixes; the baseline collector makes no prefix-stability effort and records whatever `cached_tokens` the provider reports | Keep incidental provider hits; never force them to zero |
| Optimized cloud layout | OpenAI's prompt-caching guidance explicitly recommends static instructions/examples/tools first and variable content last, with identical tool order | This guidance defines B-LAYOUT/B-SHAPE, not an artificially bad Arm A |

External evidence:

- Continuum/CacheTTL, *Efficient and Robust Multi-Turn LLM Agent Scheduling
  with KV Cache Time-to-Live*:
  https://arxiv.org/abs/2511.02230 — finished-request KV retention across tool
  pauses is the intervention; ordinary serving may evict that state.
- OpenAI Prompt Caching guide:
  https://developers.openai.com/api/docs/guides/prompt-caching — caching is
  automatic, `cached_tokens` is reported, and stable static-first prefixes are
  the recommended request shape.

Before every run, the generated cell manifest must resolve each row above to
the exact framework/engine version and effective settings. If the real
default is already prefix-friendly, Arm A keeps it and the corresponding
intervention may correctly show zero recovery.

### Rev C cloud budget model (locked; not launch-authorized)

`budget_lock.json` is the **rev C** lock (`campaign=turntrace_rev_c_cloud_class_ii`,
`schema_version=2`). It is spend-projected and payload-hash-bound, but
`live_authorized=false` until C-P3 price recheck + paired smoke. The historical
rev B P2 lock lives at `budget_lock_rev_b.json` and must not authorize rev C.

The frozen conservative model assumes:

- full context targets for cloud;
- linear accumulation from zero to each class's final target;
- no provider-cache discount (**0% hit rate**) for either arm;
- 128 output tokens/turn;
- 5 seeds × 2 arms × 2 harnesses for every class and deployment;
- published 2026-07-16 rates already used by P2: C1 `gpt-4.1` $2/$8 per
  million input/output tokens; C2 `gpt-4o-mini` $0.15/$0.60.

The frozen linear-accumulation model gives 580,000 input tokens per full
five-class trajectory set. Full-stack cells consume **11.60M input tokens per
deployment** and 207,360 output tokens at the conservative 128-token cap.
Required B-CACHE and B-APPEND+B-LAYOUT ablations run locally on TT-EDIT and
TT-RET. They are not duplicated in cloud cells, where the full intervention
already is B-APPEND+B-LAYOUT+B-SHAPE and direct B-CACHE control does not exist.

| Cell | Conservative estimate |
|------|-----------------------|
| C1, base + 10% smoke/variance | **$27.344768** |
| C2, base + 10% smoke/variance | **$2.0508576** |
| Total projected | **$29.3956256** |
| 1.5× hard ceiling | **$44.0934384** |

The conservative **base** estimate is $26.723296, below the ~$60 cut
threshold, so no C2 class is cut.
It is deliberately conservative; the optimistic TraceLab-style 97.5% cache
prior is recorded only as a sensitivity bound and is **not** used for spend
authorization. The refreshed `budget_lock.json` carries these rev C values but
has `live_authorized: false`; C-P3 still requires a price recheck and explicit
authorization after smoke readiness.

### Rev C CPU feasibility gate

TinyLlama is prohibited for rev C because its 2,048-token context is below
every suite target. C-P2 requires a new ≥16K-context CPU-viable model/engine
tuple, full calibration over the effective CPU target range, and an f(n)-based
wall-clock projection before launch. If projected compute exceeds ~24 hours,
reduce CPU-only context targets before CPU-only seed count and record the
amendment here. CPU results remain provisional forever.

**Pre-box candidate (not yet a measured tuple):**
`Qwen/Qwen2.5-1.5B-Instruct`, Q4 GGUF under llama.cpp. The official model card
states 1.54B parameters and a 32,768-token context:
https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct. This clears the ≥16K binding
constraint and all CPU/full-suite final-turn targets. Selection is not final
until the exact GGUF provenance, chat template, llama.cpp version, and
`n_ctx` are pinned. The TinyLlama tool→user role allowlist must not transfer.

`wall_budget.py` computes the required sum of f(cumulative context) over the
full paired suite and local ablations. It intentionally refuses to project
from a fit that has not passed R² ≥ 0.99. Therefore there is no honest numeric
CPU wall estimate yet: the candidate model is not calibrated, and no suite
run is authorized.

## Harness subset (P3) — **FINAL for remainder of v2**

**Decision (2026-07-16):** stay at **2 harnesses** — `raw_python` + `langgraph` — for all remaining v2 corpus work (no third harness this phase).

| Factor | Choice |
|--------|--------|
| Coverage | Call-site control (raw) + graph-node / fanout labels (langgraph) |
| Schedule | Third harness would need CPU dry-run + smoke before any `--live`; deferred |
| D5 evidence | Semantic labels align in *meaning* across both; agreement_rate stable by harness×endpoint |

Remaining v1 harnesses (AutoGen, Rust, +2) stay **configured-but-dormant** until a protocol amendment post-box.

## Open question #1 — cloud T_prefill (**surveyed 2026-07-16**)

See `SCHEMA.md` § Cloud timing methodology. Artifacts: `out/turntrace_v2/cloud_ttft_survey/`.

**Pre-launch field survey:**

| Check | C1 (gpt-4.1-mini survey) | C2 (gpt-4o-mini) |
|-------|--------------------------|------------------|
| Streaming SSE with `stream_options.include_usage` | ☑ | ☑ |
| `usage.prompt_tokens` / `completion_tokens` on final chunk | ☑ | ☑ |
| `openai-processing-ms` present | ☑ | ☑ |
| First-byte = first content token (not raw TCP) | ☑ | ☑ |
| Formula + error bars documented in SCHEMA.md | ☑ | ☑ |
| Tool-role remap not applied on cloud engine | ☑ | ☑ |

Both cells use: `t_prefill ≈ openai-processing-ms`; `t_network = TTFT_content − processing`. Probe half-widths logged in survey JSON (C1 prefill median≈334 ms, P95−median≈179 ms on n=5).

## Open question #3 — trajectory count vs API budget (**rev C lock; not live-authorized**)

Canonical lock file: `apu_characterization/turntrace_v2/budget_lock.json`
(enforced by `spend_guard.py` / future `collect_rev_c --live`). Historical rev B
figures (~$1.44 / $2.17) are superseded and must not authorize rev C spend.

**N lock (rev C):** 5 seeds × 2 arms × 2 harnesses = 20 trajectories per class
per deployment. Bands: min/median/max; sparse n<5 seed cells excluded.

**Pricing (OpenAI published 2026-07-16; recheck before C-P3):** C1 `gpt-4.1`
$2/$8 per 1M; C2 `gpt-4o-mini` $0.15/$0.60. Conservative 0% provider-cache
discount; see lock `token_estimate`.

| Cell | Projected USD | Status |
|------|---------------|--------|
| C1 frontier (gpt-4.1) | **$27.344768** | locked_not_live_authorized |
| C2 cheap (gpt-4o-mini) | **$2.0508576** | locked_not_live_authorized |
| **Total projected** | **≈ $29.40** | |
| **Hard ceiling (1.5×)** | **≈ $44.09** | hard-stop |

`--live` refuses unless `live_authorized=true`, campaign matches, payload
manifest hash matches, and planned+spent ≤ ceiling (override logged).

## P3 collection entrypoint

```bash
# Mock plumbing (no API spend) — both harnesses × N trajectories
python -m apu_characterization.turntrace_v2.collect_cloud \
  --out apu_characterization/out/turntrace_v2/cloud_c1_mock \
  --cell C1 --n-trajectories 2

# TTFT survey (cheap probes)
python -m apu_characterization.turntrace_v2.ttft_survey \
  --out apu_characterization/out/turntrace_v2/cloud_ttft_survey

# Live smoke (1× raw_python per cell)
python -m apu_characterization.turntrace_v2.smoke_live \
  --out apu_characterization/out/turntrace_v2/cloud_smoke

# Full C1/C2 under budget_lock (phased 10% monitor + replay sample ≥5)
python -m apu_characterization.turntrace_v2.collect_full \
  --out apu_characterization/out/turntrace_v2/cloud_full --spent-usd 0.05
```

## P2 pre-spend gate status (2026-07-16)

| Step | Status |
|------|--------|
| 1 Budget lock (`budget_lock.json`, ceiling enforced) | ☑ Projected **≈ $1.44**; ceiling **$2.17** |
| 2 TTFT survey + SCHEMA methodology | ☑ both cells |
| 3 Live smoke C1+C2 + replay + hand flags | ☑ |
| 4 Full corpus + replay sample ≥5 | ☑ spent ≈ **$1.49** (under ceiling); phase_a flag_rate 0; replay 5/5 each cell |

Artifacts: `out/turntrace_v2/cloud_{ttft_survey,smoke,full}/`.

## D5 + P3 completion (2026-07-16)

- **D5 report:** `python -m apu_characterization.turntrace_v2.d5_report` → `out/turntrace_v2/d5/D5_taxonomy_report.md` (idempotent; agreement_rate=1.0 on C1/C2).
- **Env snapshots (spot-check):** 3 bundles/harness carry `git_commit` + `container_image_id`; `dirty_patch` may be null when clean (`env_snapshot.py` no longer stores the sentinel `"unknown"`).
- **Track C (D2 gate):** `openai-processing-ms` confirmed prefill-isolate on corpus (corr with `tokens_out`≈0); see SCHEMA § Cloud timing methodology.

## Provisional vs headline

| Artifact | provisional |
|----------|-------------|
| CPU0 dry-run calibration + trajectories | `true` forever |
| Laptop network baselines | `true` until box re-run |
| C1/C2 whole-trajectory corpus (excl. network baselines) | `false` (headline) when audit PASS |
| L1a/L1b/L2 | dormant until box runbook |

## D1 — Prefill intercept booking (conservative)

`f(n)` carries a fixed per-call intercept. Under `t_redundant = t_prefill − f(necessary_tokens)`, that intercept is booked entirely into `t_prefill_necessary`, which biases harness tax downward — against the thesis — by deliberate conservative choice.

## D2 — Variable decode lengths

P4 synthetic configs include `variable_decode_lengths` (per-step-type `tokens_out` distributions, heavy-tailed `reason`). The CPU dry-run runs one trajectory with unpinned `max_tokens` so the live pipeline sees variable outputs before P2.

## CPU dry-run model note

P1 uses TinyLlama-1.1B-Chat Q4_K_M via llama.cpp `b10012` win-cpu `llama-server`. The model **training context is 2048**; the server caps `n_ctx` accordingly. Prefill sweep for P1 is `{32,64,128,256,512,1024,1536}` (engine-token currency; not 8k). This still exercises real-engine f(n) fitting + R²≥0.99. A longer-context small model may replace it without changing the pipeline.

TinyLlama chat templates accept only `system`/`user`/`assistant`; harness `tool` roles are remapped to `user` (`tool_result: …`) before `/apply-template` **only when `model_id` matches the TinyLlama allowlist** (or an explicit engine flag). P2/P3 models must not inherit this remap — a dropped tool role there is a real bug that F3 should catch.

Prefill grid *requests* n=32; chat-shaped TinyLlama system+user floor landed at `grid_min_engine≈39`. Workload contexts were ≥48 (covered). Next full CPU calib uses user-only pads for `n≤48` to hit 32; `attribution_out_of_domain` fires for any call below the fitted floor.

## Deployment dormancy

L1a/L1b/L2/L3 remain in protocol JSON as configured cells. No code path may require GPU sysfs / ROCm to import or unit-test.
