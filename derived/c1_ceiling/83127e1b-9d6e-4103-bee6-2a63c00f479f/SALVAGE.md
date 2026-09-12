# C-1 salvage — session `83127e1b-9d6e-4103-bee6-2a63c00f479f`

**Status:** `aborted` · **reason:** `no_ceiling_found_in_range`  
**Machine-readable:** `salvage_analysis.json` · **corrections:** AM-037

Analysis only. No new runs.

## (1) Per-probe extract

18 `work/*.result.json` files: **17 completed**, **1 incomplete**
(`n=44871` r0, mid-generate when salvage cut). Fit uses the 17 completed.

| n | r/a | peak_rss_GB | peak_commit_GB | avail_min | free_phys_min | prefill_s | decode_tok_s | r_prefill | wall_s |
|---|-----|-------------|----------------|-----------|---------------|-----------|--------------|-----------|--------|
| 12000 | 0/0 | 5.52 | 5.73 | 4016 | 4017 | 14.32 | 18.36 | 838 | 14.70 |
| 12000 | 1/0 | 5.53 | 5.74 | 4201 | 4201 | 12.99 | 18.46 | 924 | 13.37 |
| 28500 | 0/0 | 9.37 | 9.63 | 461 | 462 | 62.85 | 6.53 | 453 | 63.92 |
| 28500 | 1/0 | 9.40 | 9.62 | 1090 | 1091 | 62.22 | 10.93 | 458 | 62.86 |
| 36750 | 0/0 | 11.34 | 11.56 | **0.0** | 0.6 | 116.47 | 4.64 | 316 | 117.98 |
| 36750 | 1/0 | 11.34 | 11.56 | 134 | 135 | 186.71 | 5.44 | 197 | 188.00 |
| 36750 | 1/1 | 11.34 | 11.57 | 511 | 513 | 233.96 | 5.51 | 157 | 235.23 |
| 40875 | 0/0 | 12.30 | 12.54 | 4 | 5 | 407.45 | 3.81 | 100 | 409.29 |
| 40875 | 1/0 | 12.26 | 12.54 | 347 | 348 | 455.06 | 3.55 | 90 | 457.03 |
| 42937 | 0/0 | 12.57 | 13.04 | 1 | 2 | 356.17 | 1.01 | 121 | 363.13 |
| 42937 | 1/0 | 12.75 | 13.01 | 493 | 494 | 205.48 | 3.45 | 209 | 207.50 |
| 43968 | 0/0 | 12.96 | 13.26 | 178 | 179 | 200.57 | 1.88 | 219 | 204.29 |
| 43968 | 1/0 | 13.00 | 13.26 | 440 | 441 | 162.14 | 2.56 | 271 | 164.88 |
| 44484 | 0/0 | 13.10 | 13.38 | 289 | 289 | 226.54 | 3.04 | 196 | 228.85 |
| 44484 | 1/0 | 12.94 | 13.38 | 14 | 14 | 243.98 | 1.08 | 182 | 250.48 |
| 44742 | 0/0 | 11.93 | 13.44 | **0.0** | 0.2 | 252.16 | 1.13 | 177 | 258.37 |
| 44742 | 1/0 | 12.84 | 13.44 | 349 | 350 | 229.65 | 3.02 | 195 | 231.97 |
| 44871 | 0/0 | — | — | — | — | — | — | — | incomplete |

RSS near the 12 GB working-set lock above ~n=42k while commit keeps climbing.

## (2) Commit-based additive refit

Model: `peak_commit_bytes ≈ W + (k+w)·n` over all 17 completed probes.

| | W (bytes) | k+w (B/tok) |
|---|----------:|------------:|
| **refit (this session)** | **2,913,453,904** | **235,384** |
| 41e419bd reference | 2,290,768,181 | 234,827 |
| Δ | +27.2% | +0.24% |

**Residuals (refit):** max |resid| 0.12% of measured commit; RMSE ≈ 6.1 MB.
Slope matches 41e419bd; intercept is higher on this full-range / paging corpus.

**Hand check n=44,742 (r0):** 41e419bd predicts **12.80 GB** vs measured commit
**13.44 GB** → **4.79% under-predict** (operator 5.0%). Refit residual at that
point ≈ 0.03%.

## (3) SLO crossings (capability)

Definition: prefill_s ≤ 10 s; decode_tok_s ≥ 6 tok/s.  
Corpus: sealed `41e419bd` `gpu_only_f16` turn1 + this session’s probes.

| SLO | ok-side n (median) | fail-side n (median) |
|-----|--------------------|----------------------|
| **prefill crosses 10 s** | **8000** (7.18 s) | **12000** (13.54 s) |
| **decode crosses 6 tok/s** | **28500** (8.73 tok/s; min 6.53) | **36750** (5.44 tok/s) |

These — not a hard wall in [12k, 45k] — are the real capability numbers for
pinned f16 on this host.

## (4) Corrections (AM-037)

1. `max_position_embeddings=40960` is **not** enforced; probes passed at 44742.
2. **No hard memory ceiling** on 16 GB: Available hit 0.0 and the run continued
   (OS paging). Fit commit, not RSS.

## (5) Abort + launcher fix

- Session marked `aborted` / `no_ceiling_found_in_range` in `plan.json` +
  `summary.json`.
- `tools/run_c1_ceiling.py`: after low passes, probe **high**; if high passes,
  return `status=aborted`, `abort_reason=no_ceiling_found_in_range` instead of
  converging onto the search upper bound. Session summary propagates that
  status. `tools/launch_c1.ps1` header documents the contract.
