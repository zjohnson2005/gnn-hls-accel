# `derived/` — REGENERABLE

Governed by blueprint §5.3 (three-tier layout: `raw/` → `derived/` → `figures/`).

Every file here is rebuilt from `raw/` alone. Nothing in this directory is a source of truth, and
nothing may be hand-edited.

**Regeneration invariant (spec §2):** `python -m seam.analysis.regenerate --all` rebuilds every file
in `derived/` and `figures/` from `raw/` alone, and CI asserts this produces no diff. The command
arrives with the analysis layer (M3 onward); it does not exist yet.

**A derived table must name the run IDs it consumes.** That is what makes the chain from a paper
number back to a manifest unbroken.

Expected contents as later milestones land:

| File | Milestone | Contents |
|---|---|---|
| `energy_calibration.json` | M2.5 | S1/S2 regression slope, intercept, $R^2$, residuals, load levels |
| `noise_floor.json` | M3.5 | Per-metric CV from $n \ge 20$ repeats. Every effect is reported against this |

**Analysis code in this tier consumes `blinded_label` only, never `condition_label`** (spec §8).
