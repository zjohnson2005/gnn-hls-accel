# TLP-01 promotion summary (one page)

**Validity class:** `turn_level_parallelism` · **Protocol:** `tlp01_v2.1` · **Graph input:** `dependence_graphs_v2/` sha `29286aaa16b8e85207948db0ac84698466da3a8bdaebc6e80bbfa88f180a24d0`

**Verification:** A–G PASS (v2) · ceiling `rung_3a` **CONFIRMED** · frontier `rung_1b` **CONFIRMED** · quotable **True**

**Scope:** S1 standing suite + S2 multi-tool templates (n≥5 seeds, 80 banded sessions). **S3 (Rithwik / Claude Code) not in this cycle** — stated limit. OpenAI live harness for S2; work-serial denominator (ledger #6). Sparse S1 task_ids excluded from bands.

**Methodology trust:** `METHODOLOGY_ARC_TLP01.md` (SER-02 arc — suspension, diagnosis, taxonomy v2, headroom reinterpretation).

---

## Canonical claim sentences (frozen — all paraphrases derive from these)

### Ceiling — `rung_3a` (near_serial)

Under a perfect non-speculative scheduler (M1a), the conservative dependence floor (Tier-C) finds agent turn-level work broadly near-serial (~1×) across this task suite — including templates designed to contain independent work. Width is not the available lever; the bracket's upper edge (Tier-S) is where remaining headroom lives, and that headroom is speculative, not width-based.

**Attachments (required when quoted):** Tier-C basis · task-suite scope · S2-designed-for-independence note.

### Frontier — `rung_1b` (boundary + Praetor aggressive)

A phase boundary exists in speculation economics, measured from real traces as a function of misprediction penalty: above it, confidence-gated conservative speculation is provably optimal (the PASTE-class regime); below it, aggressive breadth-K speculation dominates. The boundary sits at **[5 ms, 10 ms]** ns grid interval (pooled @ acc=0.8; per-class table in verification Check E); a Praetor-class penalty (~20 µs, **Tier D**, promotion path csynth) sits **250×** inside the aggressive region (boundary_lower / 20 µs).

**Attachments (required when quoted):** M4 delta-over-M3 basis · Tier-D label on Praetor position only · grid resolution · predictor operative top-1 **0.871** (seed-held-out) vs generalization **0.307** (template-held-out) — different questions.

### Composite (requires BOTH rungs + all attachments)

Agent workloads are near-serial to any scheduler that doesn't bet; betting has a measured economic boundary; software sits on the wrong side of it and Praetor-class silicon sits on the right side. The only way to parallelize agents is to speculate, and only hardware makes speculation rational.

---

## Headroom (M1b/M1a) — reported, criteria pre-registered, **unevaluated**

| task_id | Tier_S median | Tier_C median | status |
|---|---:|---:|---|
| MT-SER-02 (serial control) | 1.64× | 1.64× | calibration anchor |
| MT-SER-01 | ~1.00× | ~1.00× | serial baseline |
| MT-FAN-01 (S2 independence-designed) | see aggregate | see aggregate | reported_unverdicted |

**Protocol v2.1 rungs (frozen, not applied to current data):** H-1 (≥1.5× on ≥½ classes) · H-2 (concentrated taxonomy) · H-3 null (<1.2× broadly). First evaluation: next collection cycle or designated re-analysis run.

---

## Bridge — floor tax (M2 − M1b)

Per-class M1b−M2 gap ties TLP-01 to the prior floor-coupled program. S2 multi-tool classes show **~0** median gap at Tier-S (floor already credited in M1b); S1 RE/RH show small positive gaps (0.001–0.007). See `t2_verdict_verification.md` Check G.

---

## Tier ledger

| Quantity | Tier | Promotion |
|---|---|---|
| M1a S/C brackets, M2−M1b gap, phase boundary **location** | A/B measured | quotable now |
| Predictor accuracies, bystander contention | A/B measured | quotable; bystander secondary |
| Praetor **position** on penalty axis (20 µs) | D projected | csynth path; never "Praetor achieves" |
| Speculation headroom verdict | — | blocked until H-* evaluation run |

**Bystander contention:** **ran** (median primary slowdown 0.08–0.27 under breadth policies). Phase diagram uses **nominal** penalties — conservative for the frontier claim; stated not silent.

---

## Headline figures

- M-ladder brackets: `out/tlp01/t2/figures/fig_m_ladder_brackets.png`
- Phase diagram @ acc=0.8: `out/tlp01/t2/figures/fig_phase_diagram_rung1b.png`

Captions carry scope attachments in-figure.

---

## Module 13 — blocked claims (never quote)

- Ceiling near-serial claim as "agents can't be parallelized" (width-under-Tier-C only).
- Boundary location as Tier-D-dependent (Praetor position only is Tier D).
- SER-02 **1.72×** as control failure (history / methodology arc only).
- Headroom with verdict language before H-* evaluation.
- Composite sentence with either rung's scope stripped.
- v1 graph hash `a45e88c2…` as data source (G-V1-QUARANTINE).

---

## Ownable firsts (real T0 only)

1. First limit study of agent turn-level parallelism (M1a/M1b bracket discipline)
2. First floor-coupled parallelism measurement (M2 vs M1b)
3. First speculation-economics phase diagram (policy × penalty)

**Closeout:** `out/tlp01/t2/tlp01_closeout_report.md` · supersession: `v2_supersession_table.md`
