# TurnTrace v2 — protocol notes (pre-hardware)

## Harness subset (P3)

**Committed for corpus cells in this phase:** `raw_python`, `langgraph` (3rd slot deferred).

Rationale: wiring all six v1 harnesses threatens schedule; raw_python gives call-site control; LangGraph exercises graph-node semantic labels. Remaining v1 harnesses (AutoGen, Rust, +2) stay configured-but-dormant until post-box or a protocol amendment.

## Open question #1 — cloud T_prefill (resolved for machinery)

See `SCHEMA.md` provider table. Summary:

| Provider | Fields used | Error bars |
|----------|-------------|------------|
| OpenAI | streaming TTFT; `openai-processing-ms` when present; `usage.*` | If server timing present: network = TTFT − processing. Else: subtract NetworkBaseline median; quote ±(P95−median) as half-width |
| OpenAI-compatible cheap tier | streaming required; usage if present | Same as generic; cell excluded from headline prefill attribution if streaming or usage missing |

## Open question #3 — trajectory count vs API budget

Before launching full C1 cell, compute:

```
cost ≈ n_traj × n_harness × n_cache_modes × mean_tokens_in × $/1M_in
     + n_traj × … × mean_tokens_out × $/1M_out
```

**Floor from spec:** ≥10 trajectories per (workload × harness × deployment × cache-mode) cell.

**Working budget lock (fill before C1 launch):**

| Cell | Harnesses | Cache modes | Trajectories | Est. USD | Status |
|------|-----------|-------------|--------------|----------|--------|
| C1 frontier | 2 (raw, langgraph) | 1 (provider-default) | 10 | TBD | blocked on key + price quote |
| C2 cheap | 2 | 1 | 10 | TBD | blocked on key + price quote |

Do not start C1 collection until Est. USD is filled and approved.

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
