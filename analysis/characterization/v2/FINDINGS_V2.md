# FINDINGS_V2

## 1. ANCHOR STATUS

| anchor | pass | disagreement | fitted_params |
|---|---|---:|---|
| A_BATCH_A100 | PASS | 1.075x | NONE |
| A_BATCH_HERALD_8K | PASS | 1.176x | NONE |
| A_BATCH_HERALD_32K | PASS | 1.142x | NONE |
| A_ENERGY_CLOUD | PASS | 1.000x | NONE |
| A_ENERGY_LOCAL | PASS | 1.008x | NONE |
| A_ENERGY_RATIO | PASS | 1.006x | NONE |
| A_CACHE_TIERS | PASS | 1.000x | NONE |

**All seeded anchors: PASS.**
Blocked regimes: none.

A failing anchor BLOCKS findings in its regime. Batch arithmetic (A_BATCH_*)
and the Mac Studio energy identity (A_ENERGY_*) are the licenses for everything
below.

## 2. The coherent finding — both tiers memory-bound, different axes

**Cloud is CAPACITY-bound per user.** KV does not amortize across users, so each
115K session monopolizes a large share of an expensive accelerator. This is why
~73% of cloud *price* is residency rent (cache reads), and why Gemini bills
storage by the hour (G3: $0.1169/h on our
median turn — rent, explicitly metered). Evidence: A_BATCH_A100 and
A_BATCH_HERALD PASS with no fitted parameters; collapse ratio 8K→context_floor
is exactly 14.09x by `B ∝ 1/L`.

**Local is BANDWIDTH-bound per turn.** No batching, so prefill at depth is slow
and energy per token is poor. Evidence: A_ENERGY_LOCAL / A_ENERGY_RATIO PASS —
Mac Studio at batch 1 draws 5.9–10.3 Wh/query against cloud ~1.6 Wh/query
(3.7–6.4×), and prima.cpp independently finds cloud total energy ~28% below a
local cluster. Same direction, two methods.

**Cost, energy, and latency therefore disagree**, because the tiers are scarce
in different resources. No single "cost" metric can decide placement. This is
why Phase 1's `C_marg` (local energy $ vs cloud price $) was structurally
invalid as a placement rule — it compared a capex-excluded marginal to a
margin-included price.

## 3. Energy decomposition — the novel result, licensed by F2

On the ANCHORED Mac Studio row (DeepSeek V3.2 Q4KM, 8.3 Wh vs cloud 1.6 Wh,
ratio 5.18×):

| term | Wh attributed | fraction of gap | uncertainty |
|---|---:|---:|---|
| batching_amortization | 6.69 | 100.0% | Counterfactual: local at cloud batch B=59.55 would draw 0.14 Wh (below cloud 1.6 |
| prefill_inefficiency_at_depth | 0.00 | 0.0% | Difference between context_floor local Wh and short-context local Wh, capped so  |
| idle_fixed_power | 0.00 | 0.0% | Assumed idle_fraction=0.15 of local Wh (Mac Studio paper notes ~25 W idle vs 140 |
| unallocated_residual | 0.00 | 0.0% | Remainder after sequential batching → prefill → idle. Contains model-size mismat |
| cloud_pue_cooling_SIDE_NOTE | 0.32 | n/a | NOT part of the local-worse gap sum. Cloud Wh already includes PUE=1.25; this is |
| TOTAL_GAP_local_minus_cloud | 6.69 | 100.0% | Sum target. batching+prefill+idle+residual = gap by construction. |

**Batching amortization is the dominant term**
(100% of the gap under the
A100-@8K batch counterfactual). That is the capacity-axis finding expressed in
energy units: the same silicon, shared across B users, divides per-query energy
by B. On the *anchor* workload (output-dominated) batching alone closes the
entire gap — local-at-batch would draw below cloud. Prefill-at-depth, idle
draw, and PUE are secondary there. On *our* workload (prefill-dominated ~560:1)
the prefill term grows; Item H's fitted α = 0.344
licenses the direction of that growth, with magnitude still EXTRAPOLATED to
115K / 7–8B.

Three comparisons are now reported side-by-side in `energy_three_way.csv`:
`C_energy`, `C_price`, `C_marg`. Phase 1's claim is labelled
`marginal_vs_fully_loaded` wherever it appears.

## 4. Prefill exponent and the Item B re-run

Fitted power-law exponent **α = 0.344**
(leave-one-out [0.270, 0.454]),
R²=0.888, depths=[512, 2048, 8192, 32768, 65536].

Discrimination against the Phase-2 bracket: Primary verdict=linear_attention_theoretic; ratio-error winner=linear_attention_theoretic; alpha=0.344 votes inconclusive. Excluded (log-error >2x best): ['optimistic_flat', 'quadratic_pessimistic'].

Item B re-run under fitted α (hit-rate × hardware sweep, no 3-model bracket):
**1/15 combinations survive** with `T_local < T_cloud`.

Conclusion **STRENGTHENED**: under the fitted exponent, local-first is dead on latency for nearly the entire grid. The only survivor is discrete_gpu_rtx5090 at perfect cache hit rate (h=1.0). The unified-memory boxes do not clear even at h=1.0. Collapsing the 29× bracket did not rescue them — it removed the optimistic-flat escape hatch that previously left Strix Halo / Apple barely alive.

**Regime: EXTRAPOLATED.** Measured to ≤64K on Lunar Lake CPU + Qwen2.5-0.5B.
Absolute rate does not transfer. Only α is claimed when applied at 115K on
7–8B / Strix Halo / Apple / RTX 5090. Distance:
`context_floor / deepest_measured ≈ 1.8x` beyond the deepest
requested depth, on a different model class and memory hierarchy.

## 5. Cells still EXTRAPOLATED, with distances

| cell | distance |
|---|---|
| 2a (agent energy) | output-dominated Mac Studio identity → prefill-dominated 560:1 agent turns |
| 2c | 225× beyond pp512; fitted α (if present) still ≤64K → 115K on different hw |
| 4c | not measured |
| 4d | corpus has 0 RESOLVED — UNREACHABLE |

ANCHORED cells: 1a–1c, 2b, 3a, 3b, 4a, 4b, 4e, and the Mac Studio energy identity
inside 2a.

## 6. What the mini PC must measure first, ranked

1. **Prefill tok/s vs depth on the target 7–8B quantization**, depths
   512 / 8K / 32K / 64K / 115K, with allocation-success recorded. This collapses
   the central uncertainty of cell 2c and licenses the agent-workload half of
   the energy decomposition. (Item H on the XPS gives the *shape*; the mini PC
   gives the *rate*.)
2. **Wall power under that prefill sweep** (not the platform power-profile
   setting). Turns `C_energy` from estimated to measured on local.
3. **`prompt_cache_hit_rate_local` under realistic session counts** at
   context_floor — the mixture weight that decides whether the 2c survivors
   exist at all.
4. A corpus with **≥1 RESOLVED** trajectory, to unblock cell 4d.

## Guardrails observed

- Anchor gate binding; every finding names its license.
- No parameter fitted to an anchor it validates against (`fitted_params: NONE`
  on every row of `anchors.csv`).
- `C_energy` / `C_price` / `C_marg` never conflated.
- Cache overstatement reported as a RANGE (1.95x–
  8.16x), not a single number.
- D1 headline carries 26.1% beside 73.3%.
- OA-01 apparatus caveat attached wherever the corpus is cited.
- Cell 4c not started. No admission controller designed.

*Generated by `censor/characterization_v2.py`.*
