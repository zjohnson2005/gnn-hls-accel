# cost_model_3d — HLS-level 3D-IC co-design for GNNs (Phase B)

Pure standard-library Python (no numpy/torch) so it runs on the remote box or
locally. Coefficients in `tech.py` are **analytical, not silicon** — the model's
fidelity bounds the trustworthiness of any rule it produces.

## Idea

An HLS GNN accelerator is a *kernel graph*: nodes are kernels (with QoR
attributes from `csynth`), edges are inter-kernel data volumes. A GNN splits
cleanly into a memory-bound aggregate stage and a compute-bound combine/update
stage — a natural seam to cut between two stacked dies. This package asks, for
that seam: *when, and how much, does an HLS-level 3D-aware partition help?*

## Modules (map to the roadmap rungs)

| File | Rung | Purpose |
|------|------|---------|
| `kernel_graph.py` | — | EGNN kernel graph (`k_mlp1`/`k_magg`/`k_mlp2`), mirrors `src/egnn_layer.cpp` |
| `tech.py` | — | 3D technology config (TSV/energy/thermal/area coefficients) |
| `tier_model.py` | B1–B3 | Per-tier model: latency, energy/inf, peak temp, TSV (computed together) |
| `partition.py` | B1–B3 | Arms: `flat_2d` / `blind_3d` / `aware_3d`, plus constrained `best_aware_partition` |
| `experiment.py` | B1–B3 | The single comparative table for a fixed EGNN + headline finding |
| `sweep.py` | B4 | Open the architecture; emit the labeled corpus (`corpus.csv`) |
| `surrogate.py` | B4 | Dependency-free graph-regression QoR predictor (drop-in for `evaluate`) |
| `rules.py` | B5 | Extract seam / balance / precision design rules |

## Run

```bash
python -m cost_model_3d.experiment   # B1-B3: flat-2D vs 3D-blind vs 3D-aware
python -m cost_model_3d.sweep        # B4: architecture sweep -> corpus.csv
python -m cost_model_3d.surrogate    # B4: train QoR surrogate, report error
python -m cost_model_3d.rules        # B5: seam / balance / precision rules
```

## The three arms

- **flat_2d** — 2D reference: one planar die, far (off-chip) memory, low thermal
  coupling, no vertical interconnect.
- **blind_3d** — stacked but partition-blind: dies are stacked (cheap vertical
  access, high coupling) yet nothing is repartitioned, so memory traffic crosses
  TSVs and all power lands on one tier (hotspot / TSV blowout). This is 3D with
  no HLS-level semantic knowledge.
- **aware_3d** — the HLS-level decision: push memory-bound kernels onto the
  memory tier, keep compute on the logic tier, cut at the low-bandwidth seam,
  split power across tiers.

## Methodology notes

- Objectives are **coupled** (latency tuning can create hotspots; energy tuning
  can blow the TSV budget), so the end state is a Pareto/conditional
  characterization, not independently-solved stages. `best_aware_partition`
  uses the ε-constraint form: minimize energy subject to a TSV budget and a
  peak-temperature ceiling.
- "More 3D-friendly" is measured as each design's 3D benefit **relative to its
  own 2D baseline** (a ratio), at fixed accuracy, to avoid confounding "better
  GNN" with "more 3D-friendly".
- Accuracy is currently an explicit, documented proxy (`sweep.accuracy_proxy`),
  a stand-in for measured task accuracy of the trained PyG EGNN. Replace it with
  real eval accuracy when the training loop is wired in.

## Hardening with real data

Every kernel-graph attribute (cycles, MACs, bytes, LUT/DSP/BRAM, activity) is
exactly what HLS `csynth` + an activity model provide. Populate `kernel_graph.py`
from `egnn_proj/sol1/syn/report/*.rpt` (per-tier synthesis) and an activity-based
power estimate to replace the analytical defaults; the arms, metrics, surrogate,
and rules are unchanged.
