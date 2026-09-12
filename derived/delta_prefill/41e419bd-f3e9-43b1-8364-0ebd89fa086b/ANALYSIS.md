# DISPATCH P analysis — run_id `41e419bd-f3e9-43b1-8364-0ebd89fa086b`

Canonical machine-readable analysis lives in the seal:
`derived/delta_prefill/sealed_41e419bd-f3e9-43b1-8364-0ebd89fa086b/analysis.json`
(included in the sealed tree hash).

Caveats applied: use `ttft_ratio` / turn2 times; do **not** filter on `cache_retained`
(false on all 288 cells — WS arm does not track KV delta). Residency confirmation
(operator: 48-group RESIDENT/NON_RESIDENT ratios) not re-derived.

## (a) delta=50 anomaly

RESIDENT turn2 median at d=50 **exceeds** d=150 in **12/12** (arm × n_cached) groups.
Per-repeat: **12/12** groups have all three repeats with d50 > d150.
NON_RESIDENT shows the same shape in only **1/12** groups — not the same shape.
No mechanism proposed.

## (b) RESIDENT turn2 fit (d=50 excluded)

Form: `turn2 ~ a0 + a1·n_cached + C·n_cached·delta`.

| arm | a0 | a1 | C | R² | max \|rel err\| on medians |
|-----|----|----|---|----|---------------------------|
| gpu_only_f16 | 0.226 | 3.97e-5 | 2.59e-7 | 0.995 | 0.109 |
| gpu_only_u8 | 0.209 | 2.66e-5 | 3.46e-7 | 0.997 | 0.083 |
| gpu_only_u4 | 0.269 | 1.58e-5 | 3.29e-7 | 0.995 | 0.138 |

Pure `C·d·n` falsified. Hypothesis form acceptable for u8; strained for f16/u4 (>10% on ≥1 median).

## (c) Precision effect

At d=1000, n∈{8000,12000}: f16/u8 ∈ {0.791, 0.819}; f16/u4 ∈ {0.864, 0.858}.
Direction confirmed; 15–27% band holds for u8, slightly loose for u4.
Full grid: f16 faster than u8 in 14/16; than u4 in 10/16.

## (d) peak_ws slope

| arm | slope KB/tok | nominal KV | workspace | resid vs 95+nom |
|-----|-------------|------------|-----------|-----------------|
| f16 | 230.3 | 144.0 | 86.3 | −8.7 |
| u8 | 168.4 | 72.0 | 96.4 | +1.4 |
| u4 | 131.3 | 36.0 | 95.3 | +0.3 |

Workspace approximately constant across arms (~86–96 KB/tok).

## (e) Canaries

25 canaries / 4.327 h. Thresholds used: t1=0.2315, t2=0.6019.
turn1 relative spread 0.189 (below threshold). No abort.
