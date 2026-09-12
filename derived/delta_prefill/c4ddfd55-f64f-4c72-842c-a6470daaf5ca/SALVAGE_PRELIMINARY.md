# N-1 salvage — PRELIMINARY / INCOMPLETE

**run_id:** `c4ddfd55-f64f-4c72-842c-a6470daaf5ca`  
**Label:** PRELIMINARY / INCOMPLETE — **no seal**  
**Machine artifact:** `SALVAGE_PRELIMINARY.json` (same directory)

16 of 36 matrix cells completed before the orchestrator was killed stuck in `inter_cell_settle`. Design is unbalanced. This informs whether axis 5 can reuse the corpus; **it does not settle it**.

---

## 1. Inventory

Design: `pipeline ∈ {llm, cb_no_eviction}` × `n_cached ∈ {2000,4000,12000}` × `mode ∈ {RESIDENT, NON_RESIDENT}` × `repeat ∈ {0,1,2}` = **36**.

### Present (16)

| repeat | mode | n_cached | llm | cb_no_eviction |
|--------|------|----------|-----|----------------|
| 0 | NON_RESIDENT | 2000 | OK | OTHER |
| 0 | NON_RESIDENT | 4000 | OK | OTHER |
| 0 | NON_RESIDENT | 12000 | OK | OTHER |
| 0 | RESIDENT | 2000 | OK | OTHER |
| 0 | RESIDENT | 4000 | OK | OTHER |
| 0 | RESIDENT | 12000 | OK | OTHER |
| 1 | RESIDENT | 2000 | OK | OTHER |
| 1 | RESIDENT | 4000 | OK | — |
| 1 | RESIDENT | 12000 | OK | — |

### Missing (20)

- All of **repeat 2** (12 cells)
- All **NON_RESIDENT** for repeat 1 (6 cells)
- **cb_no_eviction** RESIDENT nc=4000/12000 repeat 1 (2 cells)

Stall after completing r1 RESIDENT nc=2000 `cb_no_eviction` (16th matrix cell; heartbeat `cell_index=19` counting canaries).

---

## 2. Paired coordinates vs pre-registered criterion

**Criterion (N1_CB_EQUIVALENCE_PREDICTION.md):** significant iff `abs(cb/llm − 1)` exceeds session canary `early_max` on that turn.

**Canary early_max (this session):** t1 = **0.06097**, t2 = **0.14031**  
(calibration complete; drift thresholds = `max(2×early_max, 0.05)` → t1 **0.1219**, t2 **0.2806**)

### Prefill ratios

**Not evaluable.** Seven coordinates have both pipelines on disk; every `cb_no_eviction` cell is `classification=OTHER` with `turn1/turn2 prefill_s = null`.

Root cause (uniform): `ContinuousBatchingPipeline.generate([prompt], gen_cfg, streamer)` — CB requires either `(str, GenerationConfig, …)` or `(Sequence[str], Sequence[GenerationConfig], …)`. TypeError before any CB prefill timing.

### Peak WS ratios (completeness only — not the equivalence metric)

CB failed on turn1; `peak_ws_turn2` always null. `peak_ws_turn1` still recorded (process RSS before/during failed generate).

| n_cached | mode | repeats | peak1 ratio cb/llm | spread |
|----------|------|---------|--------------------|--------|
| 2000 | RESIDENT | r0, r1 | 0.8878, 0.8869 | 0.0009 |
| 2000 | NON_RESIDENT | r0 | 0.8851 | — |
| 4000 | RESIDENT | r0 | 0.8071 | — |
| 4000 | NON_RESIDENT | r0 | 0.8076 | — |
| 12000 | RESIDENT | r0 | 0.5910 | — |
| 12000 | NON_RESIDENT | r0 | 0.5894 | — |

CB peak1 is nearly flat (~3.04 GB) across depths; llm peak1 grows with `n_cached`, so the ratio shrinks with depth. That is a failure-mode footprint, not an equivalence result.

**Equivalence verdict:** `not_evaluable` — criterion not applied.

---

## 3. Canary series

Calibration **completed** (`canary_gate.calibration_complete=true`, armed after C2).

| idx | after matrix cell | t1 (s) | t2 (s) | rel_drift t1 | rel_drift t2 | tripped |
|-----|-------------------|--------|--------|--------------|--------------|---------|
| 0 | −1 (start) | 2.599 | 0.953 | — | — | no |
| 1 | 3 | 2.519 | 0.819 | — | — | no |
| 2 | 7 | 2.682 | 0.828 | — (arms gate) | — | no |
| 3 | 11 | 2.533 | 0.812 | 0.0557 | 0.1473 | no (within threshold) |

ref = median of first 3: t1 **2.682**, t2 **0.953**. Instrument looked stable through C3; abort was settle/host, not canary drift.

---

## 4. Label and scope

| | |
|--|--|
| Status | **PRELIMINARY / INCOMPLETE** |
| Seal | **no** |
| Cells | 16 / 36 |
| Design | unbalanced (no r2; incomplete r1) |
| Axis 5 corpus reuse | **not settled** — CB path never produced prefill timings |

What it does inform: the CB smoke path as invoked is API-incompatible with GenAI ContinuousBatching on this stack; fixing `generate` arity is a hard gate before any equivalence or axis-5 window cell.

---

## 5. Runner defects recorded

1. **`inter_cell_settle` can block indefinitely.** Configured `max_wait_s=420` and settle 20s. After cell 16, Available was ~6.4 GB (below floor 7000); earlier settles recovered to ~9.3 GB. Launch log ends on the settle banner with no WARNING/continue; heartbeat stayed `inter_cell_settle` for ~4h until kill. If `Get-AvailableMBytes`/`Get-Counter` stalls, the deadline loop never advances — max-wait is not effective under that failure mode.

2. **Heartbeat frozen during settle.** Heartbeat is written once when entering `inter_cell_settle` and not refreshed while polling. A multi-hour settle stall is indistinguishable from a crash in `heartbeat.json` / `-Status`.
