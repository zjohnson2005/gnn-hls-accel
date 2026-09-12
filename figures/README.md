# `figures/` — REGENERABLE

Governed by blueprint §5.3 and implementation spec §9.3.

**Figures read from `derived/` only.** No hardcoded values in plotting code, ever. A figure must name
the derived tables it consumes, and those tables name the run IDs they consume — so every mark on
every plot traces back to a manifest.

Rebuilt by `python -m seam.analysis.regenerate --all` (arrives with the analysis layer, M3 onward).
CI asserts regeneration produces no diff against the committed figures.

Reporting standards (blueprint §5.5, spec §8):

- **Bootstrap 95% CIs**, not standard error bars.
- Effect sizes alongside any p-value.
- ECDF or violin plots for heavy-tailed quantities. Tool durations and JCT are both heavy-tailed.
- Any claimed effect smaller than $2\times$ CV is reported as **null**, against
  `derived/noise_floor.json`.

Prohibited in any caption (spec §9.4): 50 TOPS as achieved NPU throughput, ~120 GB/s as measured
bandwidth, 180 TOPS as anything other than a Platform B CPU+GPU+NPU aggregate.
