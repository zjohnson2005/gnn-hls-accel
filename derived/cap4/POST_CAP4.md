# POST-CAP4 — fold CAP-4 into models + residency decomposition

Generated: 2026-09-16T17:52:13.632559+00:00

CAP-4 sealed run: `2b3316b6-7f6e-474f-9177-bd5a89aeb58c` · tag `MEASURED(2b3316b6)`

## 1. Prefill model refit (fdr_replay)

Form: `prefill_s = C · n^b` per KV arm, fitted on CAP-4 PASS medians.

| arm | b | C | fit_range_n | tag |
|---|---:|---:|---|---|
| `gpu_only_f16` | 2.2516 | 7.049677e-09 | [12000, 76000] | `MEASURED(2b3316b6)` |
| `gpu_only_u4` | 2.1512 | 1.983636e-08 | [12000, 76000] | `MEASURED(2b3316b6)` |
| `gpu_only_u8` | 2.1244 | 2.527464e-08 | [12000, 76000] | `MEASURED(2b3316b6)` |

### Legacy C-2 quadratic vs CAP-4 measured (signed)

Legacy source: `62395fdb-1899-415f-b708-6adc81a24dda` (gpu_only_f16 quadratic; used for all-KV comparison as the prior fdr_replay gpu prefill).

| kv | n | measured median s | legacy pred s | measured/legacy | sign |
|---|---:|---:|---:|---:|---|
| f16 | 20000 | 32.124 | 43.622 | 0.736 | overpredicted |
| f16 | 46000 | 252.708 | 286.837 | 0.881 | overpredicted |
| f16 | 76000 | 739.248 | 845.372 | 0.874 | overpredicted |
| u4 | 20000 | 32.105 | 43.622 | 0.736 | overpredicted |
| u4 | 46000 | 239.801 | 286.837 | 0.836 | overpredicted |
| u4 | 76000 | 663.553 | 845.372 | 0.785 | overpredicted |
| u8 | 20000 | 32.065 | 43.622 | 0.735 | overpredicted |
| u8 | 46000 | 230.360 | 286.837 | 0.803 | overpredicted |
| u8 | 76000 | 660.427 | 845.372 | 0.781 | overpredicted |

Note: the **pre-registered n^1.6 ~115 s** headline underpredicted at 46k (measured/predicted ≈ 2.0–2.2×). The **legacy fdr_replay quadratic** extrapolated from n≤12k **overpredicts** absolute seconds at 20k/46k/76k relative to CAP-4 medians; both are wrong at depth — CAP-4 replaces them for `n ≥ 12000`. Below the fit range, `prefill_s` still uses the C-2 quadratic (BFCL / X-2 operating depths).

Re-emitted artifacts (new model):

- `derived/d1_replay/X2_REPLAY_CHECK.md`
- `derived/d1_replay/x2_decomposition.json` / `X2_DECOMPOSITION.md`
- `derived/d1_replay/configs.json` (48-point table)

## 2. Timing variance (result)

On Platform A under CAP-4 interleaved gpu_only RESIDENT, within-rung prefill CV first exceeds ~10% at n=32000 on all three KV arms. That is the depth beyond which this platform stops reproducing prefill timing to the low-n instrument standard. CV is not monotonic thereafter (paging / quiescence pressure), but 32000 is the first crossing.

### First n where CV > 10%

- `gpu_only_f16`: **32000**
- `gpu_only_u4`: **32000**
- `gpu_only_u8`: **32000**

### Contrast — low-n cross-session reproducibility

- W-2 ref turn-1: **2.819416 s**
- N-1 measured: **2.820283 s** (session `c4ddfd55-f64f-4c72-842c-a6470daaf5ca`)
- Relative error: **0.031%** (~0.03%)
- Citation: docs/PROJECT_STATE.md Amendment 2026-08-31

### CV table (PASS cells)

| arm | n | median | min | max | CV% |
|---|---:|---:|---:|---:|---:|
| `gpu_only_f16` | 12000 | 13.505 | 13.047 | 14.842 | 6.76 |
| `gpu_only_f16` | 16000 | 21.574 | 21.461 | 21.740 | 0.65 |
| `gpu_only_f16` | 20000 | 32.124 | 32.100 | 33.616 | 2.66 |
| `gpu_only_f16` | 26000 | 51.842 | 51.715 | 51.873 | 0.16 |
| `gpu_only_f16` | 32000 | 80.474 | 77.485 | 127.243 | 29.35 |
| `gpu_only_f16` | 40000 | 124.303 | 123.330 | 128.813 | 2.33 |
| `gpu_only_f16` | 46000 | 252.708 | 172.022 | 254.463 | 20.80 |
| `gpu_only_f16` | 52000 | 301.927 | 217.927 | 320.399 | 19.50 |
| `gpu_only_f16` | 58000 | 411.869 | 387.919 | 434.650 | 5.68 |
| `gpu_only_f16` | 64000 | 516.115 | 390.557 | 558.383 | 17.87 |
| `gpu_only_f16` | 70000 | 572.111 | 555.241 | 640.647 | 7.68 |
| `gpu_only_f16` | 76000 | 739.248 | 674.963 | 773.181 | 6.84 |
| `gpu_only_u4` | 12000 | 13.550 | 13.003 | 13.565 | 2.39 |
| `gpu_only_u4` | 16000 | 21.931 | 21.621 | 22.297 | 1.54 |
| `gpu_only_u4` | 20000 | 32.105 | 32.035 | 33.592 | 2.70 |
| `gpu_only_u4` | 26000 | 52.207 | 51.795 | 52.389 | 0.58 |
| `gpu_only_u4` | 32000 | 105.012 | 79.994 | 133.023 | 25.02 |
| `gpu_only_u4` | 40000 | 143.385 | 125.571 | 189.205 | 21.50 |
| `gpu_only_u4` | 46000 | 239.801 | 168.246 | 249.965 | 20.31 |
| `gpu_only_u4` | 52000 | 274.620 | 218.659 | 368.632 | 26.38 |
| `gpu_only_u4` | 58000 | 420.365 | 364.799 | 429.785 | 8.67 |
| `gpu_only_u4` | 64000 | 341.573 | 322.199 | 381.938 | 8.74 |
| `gpu_only_u4` | 70000 | 551.630 | 453.517 | 552.356 | 10.95 |
| `gpu_only_u4` | 76000 | 663.553 | 660.324 | 673.217 | 1.01 |
| `gpu_only_u8` | 12000 | 13.277 | 13.124 | 13.637 | 1.97 |
| `gpu_only_u8` | 16000 | 21.900 | 21.529 | 22.054 | 1.24 |
| `gpu_only_u8` | 20000 | 32.065 | 31.994 | 32.287 | 0.48 |
| `gpu_only_u8` | 26000 | 52.299 | 51.692 | 52.523 | 0.82 |
| `gpu_only_u8` | 32000 | 94.596 | 83.825 | 127.326 | 22.23 |
| `gpu_only_u8` | 40000 | 153.845 | 121.936 | 166.923 | 15.68 |
| `gpu_only_u8` | 46000 | 230.360 | 165.252 | 241.860 | 19.44 |
| `gpu_only_u8` | 52000 | 216.644 | 215.063 | 217.448 | 0.56 |
| `gpu_only_u8` | 58000 | 370.803 | 320.813 | 381.177 | 9.03 |
| `gpu_only_u8` | 64000 | 328.815 | 323.940 | 394.602 | 11.30 |
| `gpu_only_u8` | 70000 | 568.354 | 492.026 | 592.356 | 9.51 |
| `gpu_only_u8` | 76000 | 660.427 | 595.812 | 802.644 | 15.42 |

## 3. RES-DECOMP — residency as avoided prefill

cpu-p X-2 wall ratio = 5.169× (8148.5 s NON_RESIDENT / 1576.4 s RESIDENT). Avoided prefill explains 100.1% of the 6572.1 s wall delta; everything else is -6.1 s (-0.1%). Residency payoff on this platform is almost entirely avoided re-prefill.

- NON_RESIDENT: `cb781dbf-3486-4fbc-a69a-34026f801abe` wall **8148.547 s**
- RESIDENT: `9fdedb46-3318-4abc-a56f-50b7d23d25ca` wall **1576.441 s**
- Ratio: **5.169×**
- Avoided prefill (step ttft sum): **6578.174 s** (100.09% of wall delta)
- Everything else: **-6.068 s** (-0.09%)
- Mechanism prior: `41e419bd-f3e9-43b1-8364-0ebd89fa086b` (RESIDENT delta-prefill << full re-prefill)

Residency is a **session-management decision** whose payoff is set by how expensive prefill is on that hardware.

## 4. Headline arithmetic (measured range)

9,750 tokens @ 10 s TTFT SLO (c647f0c7 u8/u4) versus 46,000 tokens @ median prefill 230.4–252.7 s (full min–max across arms 165.3–254.5 s; 2b3316b6-7f6e-474f-9177-bd5a89aeb58c). Token depth ratio 4.72×; time ratio vs 10 s SLO is 23.0–25.3× (not ~12× / ~2 min).

Old claim (~115 s / ~2 min at 46k) is **falsified** — see CAP-4 P1.

