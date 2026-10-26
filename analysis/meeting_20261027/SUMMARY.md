# Meeting Tue Oct 27: Beyond the KV Cache (locked title; the Nov 15 checkpoint decides any change)

**Headline.** On a 16 GB AI PC one non-KV prefill budget, not the KV cache, sets the context ceiling.
- u4 KV buys 1.79x context unchunked (25,000 vs 14,000) against a 3.12x compiled (3.56x
  nominal) byte ratio, and 3.18x once prefill is chunked.
- On 64 GB the model window binds instead.

Red flags (PLAN LOCK): R1 RED (8-bit 19,750 vs 19,900, "Keep going"). R2 RED (larger GPU share, less
context; balloons null; "ok on all" to the week-1 amendments). R3-R7 PASS. R8-R10 not yet measured.

## Findings (sealed run_ids or DERIVED)
1. **KV precision x prefill granularity.** u4 / f16 ceiling:
   - 1.79x unchunked (5943c992 / aa914c4c);
   - 3.19x at cap 1024 (f7542f68 / b48e4cfe) and 3.18x at cap 256 (f8df3847 / d782cf80);
   - 3.00 / 3.33 / 3.50x in sessions with 1K / 2K / 4K turns.
   - Compiled byte ratio 3.12x. The DERIVED law (k_f16 + a)/(k_u4 + a) gives 1.74x.
   - KV compression helps only as much as the prefill step allows.
2. **Where the bytes go (both hosts, every cell).**
   - The KV pool grows at exactly the compiled k: f16 147,456, i8 84,096, u4 47,232 B/token.
   - The prefill working set adds 87,056 B/token uncapped and 0 at cap 256 or 1024.
   - Cells: e4e797e7, ae16fcd5, 50d5a3a4, 460ec188, e442a753, b4a96d44, the bytes_* cells.
   - The non-KV term is the prefill step.
3. **One budget, 14 configurations (IN-SAMPLE).** B = P + k L + a min(L, cap) gives 3.09-3.39 GB,
   median 3.267 GB, +-4.6%. This covers single shot, caps 256 / 1024, f16 / i8 / u4 and a fixed 2 GiB
   cache (fig9). Held-out tests are registered (BR): SESS-1, STAT-1, 8B.
4. **Min of ceilings.**
   - 16 GB unchunked: memory binds (u4 25,000; f16 14,000).
   - 16 GB chunked: the window binds. u4 memory reaches 70,000 (f8df3847), but everything above
     Qwen3-4B's 40,960 is a capacity probe, not usable context.
   - 64 GB: the window binds (40,448 held 3/3 at f16 / i8 / u4: 7e249f7e, 6dfd1a12, 2d329db2).
   - Once memory is solved, TTFT binds: cap 256 costs +112% cold TTFT at 16K (8997aa4e vs d42040c1,
     A8 MISS), and 2K session turns at about 60K take 53 s (d7e8b43e).
5. **Agent sessions.** With the last held turn (ADDENDUM 5), the corrected law
   L_hist = (B - aT)/k - T is within -2.5% to +5.9% on all six uncapped session cells. It explains 92%
   (f16) and 114% (u4) of the 1K-to-4K turn-size slope (POST HOC). Gate B (Nov 8, SESS-1) is the
   held-out test.
6. **Ceilings are distributions.**
   - Repeats at the bisection maxima mostly fail: u4 cap 256 0/4 at 70,000 (0580176a); u4 25,000 3/6
     pooled; f16 14,000 4/6 pooled.
   - Robust ceilings: u4 24,250 (4/4), f16 12,288 (4/4), i8 19,500 (3/3).
   - STAT-1 replaces maxima with L50 / L90 and CIs.
7. **Candidate, gated at Gate A (Wed Nov 4); not a headline.** A larger Intel GPU share gave less
   context.
   - u4 22,750 / 21,250 / 17,750 at 50 / 57 / 74% (a2a7c763, f4abaf6e, 9e31d4cb).
   - n = 1 per setting; only 74% lies outside the ~15% drift (57% was 25,000 on Friday, 5943c992).
   - At 74% the failures moved from turn-1 prefill to turn-2 event errors, and the first children
     started with 3.5-3.9 GB Available (descriptive).
   - Leading hypothesis H1: OpenVINO sizes placement from the advertised device size
     (0.94 x shared - 450 MiB). INV-1 (ABAB x 4 boots) and XRT-1 (llama.cpp, same laptop) decide it.
8. **DEMO-1 existence proof** (fig4): moving from GPU to CPU flipped the router from 0 to 30 escalations
   and $0 to $0.297/task, and passes went 3/30 to 22/30 (f7343708 vs 1acc8c58; n = 30).

## Registered scores (full tables: analysis/cc_20261026/SCORES.md)
- HIT: 7 of 9 XPS limit bands, both ratio bands, the gate (registered L*), settled KV slopes on both
  hosts, the T2S window, A19 at three slider settings, A24 (15,232 vs 16,729), A31, the A32
  activation law, conc (iv).
- MISS:
  - u4 and 8-bit uncapped explicit limits;
  - A8 TTFT penalty;
  - A12 / BJ uncapped peak-minus-settled as registered (0; the buffers are retained after turn 1);
  - A20 f16 a (87.5 vs 93-98 kB);
  - A21 (R1);
  - A22 all balloon slopes;
  - A23 grow TTFT (3.6-6.2x slower);
  - A25 slider (negative slope);
  - A29 4.5 / 9 GiB;
  - A33;
  - conc (i) and (iii).
- UNRESOLVED: conc (ii) / A29 0 GiB (timeout at N = 10), CC-CEIL decode, the cliff exponent.
- DEMO-2 T2S: the primary is PENDING (it needs the shared cloud log, XPS after Oct 27).
  - F2: P is slower than A (wall -13.95 s, time to failure -13.16 s per entry, Holm p < 1e-6); C = A.
  - Bands partly missed; A had 0 silent overruns vs predicted 2-8.

## What is still TARGET
- F2 budget sweep: the slider inverted, so INV-1 runs first.
- F3 counters.
- F5 spill (Rithwik, 4070).
- F6 T2S cliff (blocked).
- F8 replication.
- Model leave-one-device-out (Nov 7-22).
- Fix prototype.
- XPS DEMO-2 held-out, including ho_cloud.
- CC-VALID, CC-RT (now XRT-1), M2 (8B).
- Rithwik's E3 / E4 / E5 and A35.
- STAT-1 L50 / L90.
- HYB-1 results (after Nov 6).

## Decisions for Zach
1. Push this commit, then run INV-1 boot 1 (already registered, BR).
2. Show figs 8, 1, 9 and 2 as the core. Fig 10 goes on the "candidate" slide. DEMO-2 dollars,
   concurrency and bisection maxima go to the appendix.
3. The XPS DEMO-2 held-out runs Sat Oct 31 daytime (command in the report).
4. Tell Rithwik:
   - the T2S hand-back record shows SIDECARS=1 in each CC window, likely the count query matching
     itself; PYTHON_COUNT=0 and the tree was clean;
   - send RITHWIK_ASKS_2026-10-26.md.
