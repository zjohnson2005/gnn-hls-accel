# E-ATTRIB audit log

## 2026-08-03 — mechanism fork and KV-geometry resolution

### Mechanism spike

- Run: `6b40e3fe-cbc1-4b6a-8867-46650b4ead61` (sealed; integrity verified).
- Conditions: AC online, charging false, charge rate 0 mW, Best Performance; shared machine lock
  acquired for all timed work; 120 s warm-up; five randomized seated/cold orders; greedy,
  `n_out=64`; context content 8,001 tokens; new-prompt content 65 tokens.
- Token pre-check: PASS, 5/5. Seated and cold full renderings were identical at 8,148 token IDs.
- Correctness: PASS, 5/5 greedy output byte-identical.
- Reuse: **FAIL**. Per-repeat TTFT ratios were 0.5890, 3.5123, 1.0218, 1.0276, 1.0274. Median
  1.0274; bootstrap CI95 [0.5890, 3.5123], failing the `<0.5` criterion.
- Fork: interaction route only. The chat-seating mechanism was not repaired after the result.
- Correction: E-FILTER's earlier 0.9936 stateless repeated-prompt result did not test chat mode.
  The runtime-wide “caching resolved” inference is withdrawn; reuse is calling-convention-specific.

### KV geometry

- Run: `1fd81d2a-3bae-40b1-b2a6-b9c5a50586b1` (sealed; integrity verified).
- Live CPU readback: `KV_CACHE_PRECISION=u8`.
- Model fields: 36 layers, 8 KV heads, explicit head dimension 128.
- Derivation counts both K and V:
  `2 * 36 * 8 * 128 * 1 byte = 73,728 bytes/token = 72 KiB/token`.
- The 144-KiB/token value is exactly the f16/bf16 counterfactual:
  `2 * 36 * 8 * 128 * 2 bytes = 147,456 bytes/token`.
- Resolution: dtype explains the exact 2x discrepancy. KV-head count is fixed at 8 by the model
  config and is not the source.

### Implementation and protocol amendments

- `docs/EXPERIMENT_attrib_spec.md`: 49,152→32,768 top context; centered interaction fallback;
  conditional A5; A6 dual-route agreement; stateless-cache conclusion withdrawn.
- `seam/bench/attrib.py`: sealed mechanism spike, full-factor preflight, lock-wrapped interaction
  sweep, exact total-prompt targeting, and sealed KV-geometry recorder.
- `seam/analysis/attrib_fit.py`: centered interaction fit, physical-parameter transform, bootstrap
  CIs, loud rank failure, full A/B/C/D dashboard, E-FILTER validation, and rotation calculation.
- Tests: known coefficients recovered within CI; rank-deficient designs refuse a pseudo-inverse;
  centered balanced interaction VIFs equal 1.

### Blocking prerequisites

- INT8 IR absent. The sweep preflight requires all declared quantization levels and refuses a
  reduced INT4-only run.
- STREAM bandwidth absent, so C4 cannot pass.
- No full interaction sweep or coefficient/materiality conclusion was produced.
