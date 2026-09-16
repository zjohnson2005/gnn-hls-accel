# TLP-01 methodology arc — SER-02 control and instrument trust

**Standing module (study-plan format).** Supersedes any earlier draft narrative about SER-02 in the study-plan lineage. Reference this module everywhere else; do not retell the story ad hoc.

**Artifacts:** died-ledger #6–#10; `out/tlp01/t2/ser02_diagnosis.md`; `out/tlp01/t2/edge_taxonomy_migration_report.md`; `out/tlp01/t2/t2_verdict_verification.md` (v2).

---

## Six beats (start to finish)

### 1. Control fails (ledger #7)

After the work-baseline fix (ledger #6), Check A flagged **MT-SER-02 Tier-S M1 max speedup 1.72×** — above the pre-registered 1.5× bound. Tier-C stayed at 1.0×; MT-SER-01 passed. Pre-registered disposition: **both ceiling and frontier tracks SUSPENDED**; nothing quotable until controls pass or are re-collected.

### 2. Pre-registered suspension held

The ladder report carried a **VERIFICATION PENDING** watermark. No rung language was promoted while suspended. G-SMOKE-LABEL and died-ledger #5 kept synthetic smoke off the claim ladder.

### 3. Three-branch diagnosis — all rejected before root cause

`ser02_diagnosis.md` tested:

- **Branch 1 (dep_refs dropped):** rejected — Tier-0 ⊆ Tier-S on all SER-02 seeds.
- **Branch 2 (paraphrase miss):** rejected — designed links present in traces.
- **Branch 3 (M1 semantics / SC-EMIT):** confirmed — legacy `break_control=True` let turn∥tools overlap without a classified SC-EMIT edge; counterfactual turn→first_tool edge restores 1.000×.

Ledger #8–#10 record mechanism and Check A miscalibration (scalar bound written for M1a semantics but applied to M1b-class overlap).

### 4. Category-level root cause — edge taxonomy

The graph layer lacked edge classes. SC-EMIT (turn→tools it emits) is an ordering fact, not data dependence. **Taxonomy v2** (`tlp01_edge_taxonomy_v2`) classifies SC-EMIT, SD-*, HO, D*; machines declare breakable classes. **M1a** (HO only) vs **M1b** (HO+SC) split retires unqualified M1 (ledger #11–#12).

### 5. Rungs revive on sounder semantics

Graphs re-frozen at `dependence_graphs_v2/` sha `29286aaa…`. Check A **v2** uses per-machine analytical expectations frozen before simulation (ledger #13). A–G **PASS** on v2: ceiling `rung_3a` near-serial (M1a Tier-C ~1×); frontier `rung_1b` boundary + Praetor Tier-D aggressive region.

### 6. The failure number becomes headroom

SER-02's 1.72× was always a **correct measurement** under M1b (perfect control speculation) / M1a — it is **M1b/M1a speculation headroom** on a serial agent workload, not invented tool parallelism. Under v2 semantics SER-02 Tier_S median **1.64×** (reported, unverdicted; H-1/H-2/H-3 criteria frozen in protocol v2.1, not evaluated retroactively).

---

## Q&A

### "Your negative control failed — why should we trust anything else?"

The control did its job: it forced suspension before any quotable claim. The pre-registered disposition held under pressure. Diagnosis was allowed to reject convenient explanations (missing deps, paraphrase) before the taxonomy fix. Re-verification on v2 graphs passed A–G independently.

### "You changed your oracle after seeing a failure — isn't that tuning?"

The change was **categorical** (edge taxonomy the graphs always needed), validated on reference sessions that pre-dated the failure, with Check A v2 expectations frozen before re-run. The fix made the **ceiling claim weaker** (near-serial under M1a Tier-C), not stronger — opposite signature of tuning.

### "Why is 1.72× a finding now when it was a failure last week?"

It was always a correct measurement; what was wrong was the **machine it was attributed to**. Pre-taxonomy it was read as "M1 width violation." Post-taxonomy it is **M1b headroom** on MT-SER-02 — the field's first measured speculation headroom on a serial agent control. Never quote 1.72× as a control failure; cite v2 M1b/M1a with tier and criteria status.

---

## Pointer

Canonical promotion claims: `apu_characterization/PROMOTION_SUMMARY.md`. Closeout: `out/tlp01/t2/tlp01_closeout_report.md`.
