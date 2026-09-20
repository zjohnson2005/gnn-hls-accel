# T2-3 — Cross-platform predictions for EVO-T2 / T2S (pre-registration)

**Status:** `pre_registered_before_measurement`  
**Registered UTC:** 2026-09-20T14:55:13+00:00  
**Do not edit after the first T2S probe starts.**  
**T2-3-PREP only — no probe, no session, box not touched.**

Machine-readable twin: `derived/t2_3/T2_3_PREDICTIONS.json`.

## Why now

Platform A CAP-4 (`MEASURED(2b3316b6)`) fixed the gpu_only prefill curve, CV onset,
and paging-driven stop. Before first contact with Platform B (GMKtec EVO-T2 / Core
Ultra X7 358H / Arc B390 / 64 GB LPDDR5X-8533), file the generalization claims that
the replay will be scored against. Error on these is the claim.

## Platforms and bandwidth (theoretical only)

| axis | Platform A (XPS) | T2S (EVO-T2) |
|---|---|---|
| id | `aipc-c1` | `evo-t2` |
| silicon | Core Ultra 5 325 | Core Ultra X7 358H |
| iGPU | Xe3 (Platform A) | Arc B390 |
| DRAM | 16 GB unified | 64 GB LPDDR5X-8533 |
| theoretical BW (this prep) | **~102 GB/s** (operator-stated comparator) | **273 GB/s** (operator-stated) |
| ratio | — | **273/102 ≈ 2.676 ≈ ~2.6×** |

**SEAM rule:** do **not** cite ~120 GB/s as *measured* XPS bandwidth until M2.4.
The ~102 figure is the operator-stated theoretical comparator for this
pre-registration only. Blueprint’s unverified ≈136 GB/s (8533×128-bit) is **not**
used here; 273 is the operator-stated theoretical for T2S.

**Efficiency assumption (explicit):** both platforms realize the **same fraction**
of theoretical peak memory bandwidth on the decode path. Under that assumption,
decode tok/s scales with the theoretical BW ratio; prefill wall-time scales by
the inverse (**×102/273**) when the regime remains bandwidth-bound at equal
efficiency.

---

## Platform A anchors (`MEASURED(2b3316b6)`)

Sealed run: `2b3316b6-7f6e-474f-9177-bd5a89aeb58c`  
Sources: `derived/cap4/POST_CAP4.md`, `derived/cap4/CAP4_RESULTS.md`,
`derived/cap4/sealed_2b3316b6-7f6e-474f-9177-bd5a89aeb58c/cells.json`

| fact | value |
|---|---|
| Prefill exponent (gpu_only) | **2.12–2.25** (u8 2.1244, u4 2.1512, f16 2.2516) |
| Prefill CV > 10% from | **n=32000** (all three KV arms) |
| Paging / quiescence stop | **n=82000** (`quiescence_refusal_under_paging_pressure`) |

### Median `prefill_s` (3 repeats) — scaling inputs

**Arm policy:** all three CAP-4 KV arms; **headline representative = `gpu_only_f16`.**

| n | `gpu_only_f16` | `gpu_only_u8` | `gpu_only_u4` |
|---:|---:|---:|---:|
| 12000 | **13.505** | 13.277 | 13.550 |
| 46000 | **252.708** | 230.360 | 239.801 |

### Median `decode_tok_s` (Platform A baselines for P1)

| n | `gpu_only_f16` | `gpu_only_u8` | `gpu_only_u4` |
|---:|---:|---:|---:|
| 12000 | 17.348 | 19.848 | 19.389 |
| 46000 | 1.159 | 6.386 | 4.947 |

Caveat: f16 decode at n=46000 is already collapsed on A (~1.16 tok/s). Score the
ratio primarily on non-paging depths / arms (e.g. n=12000, or u8/u4 at 46k).

### 8B allocation ceiling (Platform A)

Qwen3-8B-int4-ov `gpu_only_f16` hit **RuntimeError** at **n=10000**:

| session_id | artifact |
|---|---|
| `1269eaca-adce-42ec-a164-eb09ba654b6b` | `derived/c2_ttft/…/work/gpu_only_f16.n10000.r0.a0.result.json` |
| `9c037801-342b-478e-8e95-5b66d369eab8` | `derived/c2_ttft/…/work/gpu_only_f16.n10000.r0.a0.result.json` |

These are derived session workdirs (not sealed `raw/` runs). Related 4B prior:
`c647f0c7` f16 `CL_OUT_OF_RESOURCES` at n=8000.

---

## Predictions (before measurement)

### P1 — Decode tok/s at depth ≈ 2.6×

**Claim:** T2S decode ≈ **2.6×** Platform A at matched depth, from **273/102** at
**equal bandwidth efficiency**.

Predicted absolutes (= A × 273/102):

| n | arm | A median | T2S predicted |
|---:|---|---:|---:|
| 12000 | f16 | 17.348 | **46.43** |
| 12000 | u8 | 19.848 | **53.12** |
| 12000 | u4 | 19.389 | **51.89** |
| 46000 | f16 | 1.159 | **3.10** |
| 46000 | u8 | 6.386 | **17.09** |
| 46000 | u4 | 4.947 | **13.24** |

**Falsified if:** measured T2S/A ratio outside **[2.0, 3.4]** at a matched
non-paging depth; ratio ≈1; or T2S slower than A (ratio < 1).

### P2 — Prefill exponent stays 2.1–2.2

**Claim:** T2S gpu_only power-law exponent **b ∈ [2.1, 2.2]** — property of
attention computation, not platform.

**Falsified if:** fitted b **< 1.9 or > 2.4**, or shifts by **>0.3** vs the matched
Platform A arm (`MEASURED(2b3316b6)`).

### P3 — Prefill absolute = A × (102/273)

**Claim:** scale Platform A CAP-4 medians by **102/273 ≈ 0.3736** (faster = lower
`prefill_s`). Representative arm: **`gpu_only_f16`**; all arms tabulated.

| n | arm | A median s | T2S predicted s (= A × 102/273) |
|---:|---|---:|---:|
| 12000 | **f16** | **13.505** | **5.05** |
| 12000 | u8 | 13.277 | 4.96 |
| 12000 | u4 | 13.550 | 5.06 |
| 46000 | **f16** | **252.708** | **94.42** |
| 46000 | u8 | 230.360 | 86.07 |
| 46000 | u4 | 239.801 | 89.60 |

**Falsified if:** measured/predicted outside **[0.7, 1.4]** at n=12000 or 46000,
or T2S prefill slower than A at matched n.

### P4 — No paging within sweep; onset ~4×

**Claim:** with **64 GB vs 16 GB (4×)**, **no paging-driven quiescence loss** for
**n ≤ 82000** on T2S. Memory-linear onset ≈ **4 × 82000 = 328000** tokens.

**Falsified if:** CAP-4-class paging/quiescence stop within **n ≤ 82000**, or the
same pattern appears below **n = 164000** (half the scaled onset).

### P5 — No 8B ceiling within range

**Claim:** **no** 8B-int4 `gpu_only` RuntimeError / alloc ceiling on T2S for
**n ≤ 10000** (Platform A failed at 8B/n=10000).

**Falsified if:** RuntimeError / `CL_OUT_OF_RESOURCES` / alloc failure at any
**n ≤ 10000**, or 8B fails to load/compile on T2S `gpu_only`.

---

## Joint generalization claim

If P1–P5 hold, Platform A CAP-4 / 8B ceilings generalize to T2S by theoretical
bandwidth and DRAM capacity under equal efficiency. If they fail, the failure
mode **is** the published generalization result — do not silently re-fit.

## Non-claims

- Not an M2.4 STREAM measurement on either platform.
- Not a citation of 50 TOPS, ~120 GB/s measured, 180 TOPS as NPU-alone, or 1.38×
  topology as performance.
- Not a quality / BFCL accuracy claim.
- **No measurement performed in T2-3-PREP.**
