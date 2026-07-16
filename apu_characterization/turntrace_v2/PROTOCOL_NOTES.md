# TurnTrace v2 — protocol notes (pre-hardware)

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

## Open question #3 — trajectory count vs API budget (**locked**)

Canonical lock file: `apu_characterization/turntrace_v2/budget_lock.json` (enforced by `spend_guard.py` / `collect_cloud --live`).

**N lock:** 10 traj/cell. Prior: CPU dry-run turns 1–5 prefill/harness-tax CV ≤0.07 → N_raw≪10 for 90% CI half-width ≤15% of mean; spec floor binds. Turn-0 tax CV spike excluded (attribution floor artifact).

**Pricing (OpenAI published 2026-07-16):** C1 `gpt-4.1` $2/$8 per 1M; C2 `gpt-4o-mini` $0.15/$0.60. Token estimate: 4000 in / 400 out × 6 turns (dry-run ×18 scale — **estimate**).

| Cell | Harnesses | Cache | N | Est. USD | Status |
|------|-----------|-------|---|----------|--------|
| C1 frontier (gpt-4.1) | 2 | 1 | 10 | **$1.34** | locked |
| C2 cheap (gpt-4o-mini) | 2 | 1 | 10 | **$0.10** | locked |
| **Total projected** | | | | **≈ $1.44** | |
| **Hard ceiling (1.5×)** | | | | **$2.17** | hard-stop |

`--live` refuses to start if planned+spent > ceiling unless `--allow-spend-override` (logged). Ceiling trip proven in tests (`hard_ceiling_usd=0.001` → exit 2).

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
