# Meeting with Rithwik, Tue Oct 27 2026, 8 PM ET (prep note, Task BS; Zach decides everything here)

## 1. Paper split: a starting point only
Rithwik proposes splitting "the formula" and "the router" between two papers.
- **ISPASS 2027 (ours, combined):** the measured ceiling model, which covers:
  - bytes per token (KV pool = compiled k);
  - the prefill working set;
  - one budget across 14 configurations (in-sample);
  - the min of ceilings;
  - session law (Gate B);
  - vendor replication (XRT-1, E3, E5a).
  
  It also carries the HYB-1 feasibility section: a predictor that decides before generation whether a
  call fits locally, scored by trace replay. There is no deployed router and no savings claim.
- **Rithwik's paper:** the route-at-start router. It consumes our predictor as an input and cites the
  ISPASS paper for it.
- **Must not be duplicated** (dual-submission risk is the same figure or the same claim in both):
  - In ours only:
    - the ceiling law and its measured numbers;
    - fig1 (where the bytes go), fig8 (granularity), fig9 (one budget), fig2/3 (min of ceilings);
    - the slider candidate;
    - HYB-1 predictor accuracy tables (H-NARROW, H-BAND, H-KV, ...).
  - In his only: router policy, routing traces and end-to-end cost/latency of routing, and any
    deployed-router result.
  - In neither as a claim of novelty: DEMO-1/DEMO-2 dollars (descriptive only).
- **Shared data:**
  - E3/E5 run on his machines from our runbooks. The proposal is that they appear in ours as a
    replication of the law, while his paper may use the same runs as router inputs with a citation.
  - Who seals and holds them: we do, by sha256 on receipt.
- **Authorship questions:**
  - Is he a co-author on ISPASS as now?
  - Is Zach on the router paper?
  - Where does Dr. Hao sit on each?
  - Where does the retention section (his part of the combined paper) go if the split happens?
  - Which venue and deadline is his paper aimed at?
- **Dates:**
  - ISPASS abstract Fri Dec 11, full paper Fri Dec 18 (AoE, 9 pages, double-blind);
  - our data freeze Sun Nov 22; draft to Dr. Hao about Dec 1.
  - Gates: A Wed Nov 4 (inversion), Fri Nov 6 (fleet + mechanism), B Sun Nov 8 (session law), framing Sun Nov 15.

## 2. Machine time: concrete slots
| Ask | What | Time | When |
|---|---|---|---|
| RTX 4070 (his laptop) | runbook seam_xrt_rtx4070 (E3: 5 cells, llama.cpp CUDA 12.4); needs "Prefer No Sysmem Fallback" + screenshot | about 2-3 h | this week, by Sun Nov 1 |
| evo-x2 queue | job seam_xrt_evo-x2, E5a at the default share (4 cells, Vulkan); no setting changed | about 3-4 h (job timeout 6 h) | one slot by Wed Nov 4 (Gate A) |
| T2S evening (our queue, his OK) | llama.cpp boundary at the default share (f16, q4_0) + read-only A19 record; no reboot, no setting change; install only in our folder | about 2-3 h | option 1: Wed Oct 28, 7-10 PM ET; option 2: Sat Oct 31, 7-10 PM ET |
| E5b (only if he says share changes are OK) | 3+ VGM points, one job and one reboot per point | about 2-3 h per point | by Sun Nov 8 (Gate B) |
- E4 (vLLM) is dropped: it needs WSL/Docker. It is recorded as a deviation and nothing replaces it.

## 3. Open items he owes
- The T2S Shared GPU Memory Override value (or "not set").
- Retention run_ids (R-RUNIDS: the ~46,000 combined limit and the 23-25x retention headline).
- The E1/E2 task source (R-CTXKV: the short tool-task source and the 150 pilot ids).
- (From BK) The T2S hand-back shows SIDECARS=1 in every CC window. This is very likely the count query
  matching itself; PYTHON_COUNT=0 and the tree was clean. Tell him; no action expected.

## 4. Bring
- analysis/meeting_20261027/SUMMARY.md, the two runbook PDFs, and docs/RITHWIK_ASKS_2026-10-26.md.
