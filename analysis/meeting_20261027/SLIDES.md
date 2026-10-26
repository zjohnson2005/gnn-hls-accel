# Slide texts, Tue Oct 27 (figures in figs/; every number with a run_id in SUMMARY.md)

## 1. Beyond the KV cache: one prefill budget sets the ceiling (fig8, fig1)
- u4 / f16: 1.79x unchunked, 3.18x at cap 256, against a 3.12x compiled (3.56x nominal) byte ratio.
- The KV pool grows at exactly the compiled k. The prefill working set adds 87 kB per token unchunked
  and nothing once chunked.

## 2. One budget explains 14 configurations (fig9)
- Median 3.267 GB, +-4.6%. This is IN-SAMPLE; held-out tests are registered (SESS-1, STAT-1, 8B).
- R1 as scored: 8-bit 19,750 vs 19,900 (RED, "Keep going"). The compiled-k reading is 19,037
  (DERIVED, not a rescore).

## 3. Min of ceilings (fig2, fig3)
- 16 GB unchunked: memory. 16 GB chunked and 64 GB: the 40,960 window. Points above it are capacity
  probes.
- Once memory is solved: TTFT. Cap 256 adds +112% at 16K; 2K turns at 60K take 53 s.

## 4. Agent sessions
- The corrected law (subtract one turn) fits all six cells within -2.5% to +5.9%. Gate B (Nov 8)
  holds the held-out test.

## 5. Candidate: more GPU share, less context (fig10), gated at Gate A (Wed Nov 4)
- u4 22,750 / 21,250 / 17,750 at 50 / 57 / 74%; n = 1 each; only 74% lies beyond the drift.
- H1: the runtime sizes placement from the advertised size (0.94 x shared - 450 MiB).
- INV-1 (ABAB, 4 boots) and XRT-1 (llama.cpp, same laptop) decide it.

## 6. Hybrid execution: feasibility, not savings (HYB-1 registered; results after Nov 6)
- The ceiling model decides before generation whether a call can run locally.
- A KV-only router overestimates the default ceiling by 1.59x (f16), 2.04x (i8) and 2.85x (u4)
  (DERIVED). Every call admitted in that gap is a hard failure.
- Reconfiguring can gain at most the share of calls between the default ceiling and the window:
  (19,750, 40,960] on 16 GB, and empty on 32 and 64 GB.
- Median production coding calls exceed every 16 GB ceiling and the window: about 68K (Copilot) and
  about 119K (TraceLab), LITERATURE.
- DEMO-1, one line: placement flipped the router (fig4, n = 30). DEMO-2 goes under fallacies: tuning
  below a fixed ceiling moves cost little.

## 7. Next 2 weeks
| When | What |
|---|---|
| Oct 26-28 | INV-1 boots 1-4; XRT-1 install, E2 at 74 / 50, E1 |
| Oct 28-29 | SESS-1 (window probe first) |
| Oct 29-Nov 1 | STAT-1 overnights; DEMO-2 XPS held-out Sat; M2 (8B) |
| Rithwik | E3 / E4 (4070), E5 (Strix Halo) |
| Gates | A Wed Nov 4 (inversion), fleet + mechanism Fri Nov 6, B Sun Nov 8 (session law), framing Sun Nov 15 |
| Then | data freeze Sun Nov 22; draft Sun Nov 29 |
| ISPASS 2027 | abstract Fri Dec 11 evening ET; full paper Fri Dec 18 evening ET; 9 pages, double-blind, in person NYC May 9-11 |

## Appendix (not headlines)
- DEMO-2 T2S F2: A faster than P by about 14 s per entry; C = A. The $ primary is pending.
- T2S concurrency, 32,768-token f16 sessions:
  - (i) failed at 4;
  - (ii) held 9 and timed out at 10;
  - (iii) and (iv) were refused at construction by the budget check.
  - Balloons of 4.5 and 9 GiB changed nothing.
- Bisection maxima vs repeats (SUMMARY item 6).
