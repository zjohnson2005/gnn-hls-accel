# Q-8B — int4-4B vs int4-8B tier quality (pre-registration)

**Status:** `pre_registered_before_measurement`  
**Registered UTC:** 2026-09-16T18:02:41+00:00  
**Do not edit after the first generate starts.**

## Runner change note (Q8B-FIX — prediction content unchanged)

Re-registered with the same claims vs Q-KV f16 (**62** emission failures,
**10** completions of 200). Runner defaults changed before the valid
measurement session:

- **Default pipeline:** single-pipe block interleave (reload on arm switch);
  dual-resident is opt-in only (`--allow-dual-resident` /
  `-AllowDualResident`) and **known-broken** on this iGPU (citing void
  `b1a291f0` — see `derived/q8b/DUAL_RESIDENCY_FINDING.md`).
- **Raw persist:** `model_result_raw_per_turn` in every quality row
  (`tools/quality_row_persist.py`).
- **Degenerate guard:** N=3 consecutive max_new_tokens + zero-decode cells →
  `SeamError` refuse (`derived/q8b/DEGENERATE_GUARD.json`).

Prediction P1/P2/joint text below is **unchanged**.

## Why this session

W-3 vs Q-KV showed **absolute** emission/completion rates are not cross-session
comparable. A fresh 8B session scored alone against Q-KV’s 4B numbers would be
uninterpretable. Q-8B therefore **interleaves** both tiers in one session
(same 200 entries, block-interleaved, paired McNemar) — the Q-KV design
generalized so an arm varies **model spec**, not only KV.

## Design

| axis | value |
|---|---|
| arms | `int4_4B`, `int4_8B` |
| weight precision | **int4** for both (tier comparison) |
| KV | **f16** pinned (`gpu_only_f16` placement arm) |
| entries | same 200 as W-3 / Q-KV (`3502c535…` pin) |
| session_design (INF-5) | `interleaved` |
| arm_order (INF-5) | `[int4_4B, int4_8B]` |
| scoring | W-3 scorer path (`entry_quality.json` + paired McNemar) |
| launcher | `tools/launch_q8b.ps1` |
| worker | `tools/run_q_8b_quality.py` |
| pipeline default | `block_interleave_single_pipe` |

### Model specs (registry)

| arm | FetchedModelSpec | ir_sha256 (prefix) |
|---|---|---|
| int4_4B | `configs/models/Qwen3-4B-int4-ov.yaml` | `c1821f29…` |
| int4_8B | `configs/models/Qwen3-8B-int4-ov.yaml` | `cd97874b…` |

**No `Qwen3-8B-int8-ov` in the registry.** This experiment does **not** silently
substitute int8. It is int4-vs-int4 at different parameter tiers.

**Quant recipe confound (stated):** 4B is INT4_SYM; 8B is INT4_ASYM +
scale_estimation on wikitext2. Acceptable for a tier probe only if the confound
is recorded (model-spec notes).

Invoke (default = single-pipe):

```text
powershell -NoProfile -File tools/launch_q8b.ps1
# known-broken opt-in (do not use for the measurement session):
powershell -NoProfile -File tools/launch_q8b.ps1 -AllowDualResident
```

## Q-KV baseline (prediction context only)

Sealed Q-KV `137f6f46-cd3a-42d5-8479-4ff46a1074f1`, arm `gpu_only_f16`
(int4-4B, KV f16):

| metric | value |
|---|---|
| emission failures | **62 / 200** |
| trajectory_pass (completions) | **10 / 200** |

These absolutes are **not** a cross-session comparator for a solo 8B run; they
anchor the within-session prediction for the interleaved 4B arm and the
direction of the 8B claim.

## Pre-registered predictions

### P1 — Emission (paired)

**Claim:** int4-8B has **fewer emission failures** than int4-4B on the same 200
entries (McNemar exact two-sided p < 0.05 on discordant pairs, with more
4B-fail/8B-ok than the reverse). Absolute band for int4-8B: **≤ 50 / 200**
emission failures (vs Q-KV f16’s 62 as the 4B reference level).

**Falsified if:** emission McNemar p ≥ 0.05 (or zero discordant), **or**
int4-8B has significantly *more* emission failures than int4-4B (p < 0.05
favoring 4B), **or** int4-8B emission failures > 50 when the 4B arm is within
±10 of 62.

### P2 — Completion (paired)

**Claim:** int4-8B has **more** `trajectory_pass` than int4-4B (McNemar p < 0.05
favoring 8B). Absolute band for int4-8B: **≥ 15 / 200** completions (vs Q-KV
f16’s 10).

**Falsified if:** completion McNemar p ≥ 0.05 (or zero discordant), **or**
int4-8B has significantly fewer completions than int4-4B, **or** int4-8B
completions < 15 when the 4B arm is within ±5 of 10.

### Joint (tier quality axis)

**Claim:** model tier (4B vs 8B at fixed int4 + f16 KV) is a quality axis at
this resolution — i.e. P1 and P2 both hold.

**Falsified if:** arms **agree** on both endpoints (same rule as Q-KV:
McNemar p ≥ 0.05 or zero discordant on **both** emission and completion).

## Reload / residency (pre-measurement expectation)

IR bytes: 4B ≈ 2.13 GiB + 8B ≈ 4.55 GiB ≈ **6.68 GiB** weights alone.
**Default:** block-interleave with explicit reload on arm switch. Dual resident
is **known-broken** (citing `b1a291f0`) and requires `--allow-dual-resident`.
Reload cost is logged in `reload_events.json` with
`excluded_from_decode_metrics=true`; cell wall and turn `ttft_s` /
`decode_tok_s` start **after** the pipe is ready.

## Non-claims

- Not an int8-8B comparison (no such IR in registry).
- No cloud spend.
- Do not cite 50 TOPS / ~120 GB/s / 1.38× topology as measurements.
- Do not seal void dual-resident session `b1a291f0`.

## Machine-readable twin

`derived/q8b/Q8B_PREDICTIONS.json`
