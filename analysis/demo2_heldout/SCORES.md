# DEMO-2 T2S held-out: registered values (Task BK)

## Primary (DEMO2_PREFREEZE PF 2; DEMO2_BF0_PREDICTIONS.json T2S rows)
- PENDING. dC_iso (splice) of P vs A needs the one shared cloud-only held-out log (ho_cloud), which runs
  on the XPS after Oct 27 (DEMO2_FREEZE_2026-10-23.md). Nothing about the primary is reported yet; the
  XPS test is reached only if the T2S test rejects.

## F2 (DEMO2_AMEND_2026-10-23_OBJECTIVES.md; not gated on the $ primary; m = 6, Holm)
Computed by tools/demo2_f2_objectives.py -> analysis/demo2_heldout/F2_T2S.json (A 1f13b75e, P 9eb71a3a,
C 89676c43). Scoring rule (DEMO2_BH_F2_PREDICTIONS.json): HIT if the statistic is inside [p05, p95] AND the
test outcome equals the predicted one; PARTIAL if one of the two.

| Contrast / member | Predicted (band; test) | Measured | Verdict |
|---|---|---|---|
| A vs P, wall per entry | -20.5 s [-29.3, -14.3]; REJECT | -13.95 s, Holm p 4.5e-8, REJECT (A faster) | PARTIAL (stat 0.3 s outside) |
| A vs P, time to failure | -24.8 s [-35.3, -17.6]; REJECT | -13.16 s, Holm p 4.8e-7, REJECT (A faster) | PARTIAL |
| A vs P, hang/loop | A 1 [0, 3]; NOT REJECT | A 0, P 0; NOT REJECT | HIT |
| A vs P, silent overrun (mechanism check, outside Holm) | A 5 [2, 8] | A 0 | MISS |
| A vs C, wall per entry | -0.012 s [-0.030, 0.012]; NOT REJECT | -0.042 s, NOT REJECT | PARTIAL |
| A vs C, time to failure | -0.012 s [-0.026, 0.013]; NOT REJECT | -0.043 s, NOT REJECT | PARTIAL |
| A vs C, hang/loop | A 1 [0, 3]; NOT REJECT | 0 / 0, NOT REJECT | HIT |
| A vs C, silent overrun | A 5 [2, 8] | A 0 | MISS |

- Claims under the family rule: "A is better than P for wall per entry and for time to failure" (Holm).
- Local failures: A 57/60, P 48/60, C 56/60 entries fail locally (escalate); no generate past the cap in
  any arm (generates_over_cap 0); 0 hangs/loops.
- Arms B and I-4K: secondaries, interpreted only if the primary rejects; ho_i4k crashed (RUNS.md).
