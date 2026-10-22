# DEMO-2 sprint schedule, Oct 22-26 (Task BE, folds Task BD). Priority 1: the iso-quality dollar win

Rules: docs/amendments/DEMO2_ISO_QUALITY_2026-10-21.md (+ ARMS_REVISED, PER_DEVICE). Times are ET.
- The T2S is ours until 9:44 PM Sun Oct 25. Logs must be off by 8:44 PM, which the queue's
  deadline guard enforces.
- XPS reboots take up to ~30 min, and the launcher gate (uptime < 7,200 s) forces one before
  a runner cell once uptime passes 6,900 s.
- Durations are DERIVED from measured per-entry times (4B INT4, local-only):
  - T2S: base 23 s (b90f1d5b), long 78 s (1a634610 + daa6c026), entry 123 loop 26 min
    (cddcd9fd);
  - XPS: base 29 s (39c1c131), long 206 s (15367c3a);
  - cloud-only: 9.7 min of cloud time for 30 entries (1acc8c58);
  - scaling: 8B INT4 x2.1, 8B INT8 x3, 4B INT8 x1.8 (weight bytes / prefill FLOPs);
    budgeted arms x0.7 on long entries.

## Order
| when (ET) | T2S | XPS | Mac (Claude) |
|---|---|---|---|
| Thu Oct 22 9:00 | download_models_t2s.sh (8B INT4 + 8B INT8, 13 GB; 0.5-1 h) | X0 closeout check; download_models_xps.sh (waits for no python; 9 GB; 0.5-1.5 h on the flaky TLS link) | X0-XPS closeout |
| Thu ~10:00 | ladder part 1 UNTIL=6 (R0 + R1 i8/u4: budget B; ~2.5 h) | ladder UNTIL=4 (R0-XPS + R1-XPS: confirms 8,192; ~1.5 h incl. reboot) | |
| Thu ~12:30 / ~13:00 | BE queue calibration UNTIL=13 (A, A, C, P = 8B INT8; ~2.5 h) | BE queue calibration UNTIL=15 (A, A, C, P = 8B INT4, P' = 4B INT8, cloud log $20 cap; ~6.5 h + ~3 h reboots) | |
| Thu ~15:30 -> Fri 9:00 | stretch: ladder R2 (T2S-cap levers; reported, no dollar claim) | calibration continues to ~Thu 23:00 | calibration replay, A/A floor, P' rule |
| **Fri Oct 23 by 12:00** | | | **FREEZE** (TASK_BF_PROMPT.md): fill the rule-computed values; Zach pushes |
| Fri 12:00 -> ~20:00 | BE queue held-out FROM=30 (A, P, C, R-full, B, I-4K; ~7.5 h) | BE queue held-out FROM=30 (cloud log $20 cap first, then A, P/P', C, I-4K, R-full, B; ~13 h + ~3.5 h reboots, to ~Sat 05:00) | |
| Sat Oct 24 | stretch: live hybrid validation A + P, ~15 entries (P7 approval); R6 / 2x2 T2S half | stretch: live hybrid validation; matched-rate control from the logs (offline) | held-out replay, provisional |
| Sun Oct 25 by 20:44 | logs off, hand-back check (the deadline guard stops new cells) | stretch cells | |
| Mon Oct 26 | (Rithwik) | finish any stretch | TASK_BG_PROMPT.md: replay, analysis, demo package |

## Per-cell durations (DERIVED; reserve in the queue scripts)
| cell | T2S | XPS |
|---|---|---|
| calibration A (x2) | 25 min each | 59 min each |
| calibration C | 20 min | 44 min |
| calibration P | 60 min (8B INT8) | 92 min (8B INT4) |
| calibration P' | - | 79 min (4B INT8) |
| calibration cloud log | - | 15-30 min, <= $20 (approved) |
| held-out cloud log | - | 30-45 min, <= $20 (approved) |
| held-out A | 1.5-2 h (3 jump entries may loop up to 26 min) | 2-4 h (stall/turn-budget risk; resume rule) |
| held-out P | 2-2.5 h | 3 h |
| held-out C | 40 min | 1.5 h |
| held-out R-full | 1 h | 2.2 h |
| held-out B | 40 min | 1.5 h |
| held-out I-4K | 20 min | 45 min |

## Go / no-go by Oct 26 evening
| status | items |
|---|---|
| **Guaranteed** (if downloads and the freeze land) | calibration logs both hosts; held-out local-only A, P, C on both hosts; the held-out cloud log; the iso-quality replay for P and C vs A per host, with CIs |
| **Likely** | held-out R-full, B, I-4K on both hosts; T2S budget from R1; XPS 8,192 confirmed; the A/A floor; the P' decision |
| **Stretch** | live hybrid validation (A, P, ~15 entries, P7-approved spend); T2S R2 / T2S-cap; R6 / 2x2; emulated caps R5; the matched-rate control (needs no new run, but needs time) |
| **Not run** | T2S thinking-budget arm (no harness); tiers 14B / 30B-A3B; 2 replicates (not approved) |

## Stop rules
- The T2S queue starts no cell that would end after 8:44 PM Sun.
- If the T2S download fails, its P cells are NOT_RUN and the T2S runs A/C/B/R-full/I-4K only.
- If the freeze slips past Fri 12:00, held-out starts at the freeze. Arms are cut in reverse
  priority: I-4K, B, then R-full. A, P and C are never cut.
