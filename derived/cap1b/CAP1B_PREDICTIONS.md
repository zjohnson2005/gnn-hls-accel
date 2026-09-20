# CAP-1b — cpu-p cold-start TTFT limit (pre-registration)

**Status:** `pre_registered_before_measurement`  
**Registered UTC:** 2026-09-16T18:02:41+00:00  
**Do not edit after the first probe starts.**

## Question

What is the largest cold-start context `n` (tokens) on **cpu-p** (delta_n arm `A`)
where median turn-1 `prefill_s` ≤ 10 s (C-2 / `ttft_slo` criterion)?

## Design

| axis | value |
|---|---|
| launcher | `tools/launch_c2.ps1` |
| worker | `tools/run_c1_ceiling.py --criterion ttft_slo --slo-s 10` |
| arm | `A` (alias `cpu-p`) |
| model | Qwen3-4B-int4-ov |
| residency | RESIDENT (ceiling child path) |
| search | `-Low 500 -High 8000` (bracket sits **below** the cited 7,743-token SLO miss) |
| resolution | 250 |
| repeats | 3; median |

Invoke:

```text
powershell -NoProfile -File tools/launch_c2.ps1 -Arms A -Low 500 -High 8000
```

`-Low`/`-High` flow end-to-end: launcher → worker `--low`/`--high` → `bisect_arm(low, high)`.

## Pre-registered prediction

### P1 — Limit below the X-2 / 7,743-token SLO miss

**Claim:** the cpu-p cold-start TTFT limit (`ttft_limit_n`) is **strictly below 7,743
tokens**. Equivalently: no n ≥ 7,743 in the search satisfies median `prefill_s` ≤ 10 s,
and the measured limit (or `REFUSED_LOW_OVER_SLO` if even `low=500` fails) lies below
7,743.

**Basis:**

1. **X-2** sealed `cb781dbf-3486-4fbc-a69a-34026f801abe` (cpu-p × NON_RESIDENT):
   `fraction_turns_slo_ok = 0.0` (70/70 turns failed TTFT≤10 ∧ decode≥6). First-step
   contexts start ~4,193 tokens with TTFT ≈ 30–80 s.
2. **7,743-token workload:** cited BFCL multi-turn full-prompt size at which the
   placement already misses the USER_FACING TTFT SLO on cpu-p paths (limit must sit
   below that operating point). See also `derived/bfcl_feasibility/c3_cloud_cost_curve`
   note on 7,743 as a measured max mid-session prompt.
3. **D-1 replay** (`derived/d1_replay/configs.json`): for every
   `cpu-p|*|int4|4B` config, `cold_start_slo_limit_tokens.value = 0`, tagged
   `derived from prefill[cpu-p] + decode; SLO predicate`, with cpu-p prefill from
   ceiling_a arm A `b5ce21e5-9f29-46f4-8319-f74adcdeb628` (seal `ad7b9288…`). The
   fitted curve gives `prefill(500) ≈ 18 s` and `prefill(7743) ≈ 116 s` — both over
   the 10 s SLO.

**Stronger (same basis):** expect `REFUSED_LOW_OVER_SLO` at `low=500`, or
`ttft_limit_n < 500` if the bracket is widened downward later. The binding
pre-registration falsifier is the claim against **7,743**.

### Falsified if

- Bisect reports `ttft_limit_n ≥ 7743`, or
- `high=8000` passes (`abort_reason=no_slo_crossing_in_range` with
  `highest_slo_ok_n ≥ 7743`), or
- Any complete arm result places a median-prefill≤10 s point at n ≥ 7743.

## Non-claims

- Not a KV-precision comparison (single arm `A`).
- Not a quality / BFCL claim.
- Do not cite 50 TOPS / ~120 GB/s / 1.38× topology as measurements.

## Machine-readable twin

`derived/cap1b/CAP1B_PREDICTIONS.json`
