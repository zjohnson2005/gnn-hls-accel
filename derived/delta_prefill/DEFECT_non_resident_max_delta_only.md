# DEFECT — NON_RESIDENT scheduled only at max(-Deltas)

**Status:** RECORDED · **Class:** design defect (matrix harness) · **Date:** 2026-08-10  
**Fixed in:** `tools/run_delta_prefill_matrix.ps1` (`Get-CellSpecs`)  
**Do not re-run** sealed / completed matrices to “backfill” missing cells.

## Defect

`Get-CellSpecs` scheduled:

- `RESIDENT` at every `-Deltas` entry
- `NON_RESIDENT` only at `max(-Deltas)`

With defaults `{500,2000}` (or later `{100,400,1000,2000}`), cold controls existed only at the largest delta. Residency ratios and falsification at small deltas therefore compared a measured RESIDENT cell to a **missing** matched NON_RESIDENT peer — or silently reused the max-delta cold median.

## Why it matters

Real BFCL turn deltas are ~40–350 tokens, not 2000. At `n_cached=4000`, RESIDENT turn-2 at `delta=100` is ~0.54 s while cold full prefill is ~2.65 s (ratio ~0.20). A ratio computed only at `delta=2000` (e.g. 0.550 → FALSIFIED) does not answer the small-delta regime the session-level claim cares about.

## Fix

NON_RESIDENT runs at **every** provided delta, paired with RESIDENT. Summary item 1 reports RESIDENT vs NON_RESIDENT per `(arm, n_cached, delta)`.

## Historical artifacts

Prior sessions under the defective rule remain valid for the cells they actually ran. Do not edit sealed `raw/` or rewrite past summaries to invent NON_RESIDENT cells at smaller deltas.
