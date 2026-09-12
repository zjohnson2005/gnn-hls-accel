# E-ATTRIB results

## Validity dashboard

Mechanism spike: sealed run `6b40e3fe-cbc1-4b6a-8867-46650b4ead61`.

| Test | Reported value | Criterion | Verdict |
|:--|:--|:--|:--:|
| Token pre-check | 5/5 repeats; seated and cold rendered sequences each 8,148 token IDs and were identical | identical | **PASS** |
| Correctness | greedy output UTF-8 bytes identical in 5/5 repeats | byte-identical | **PASS** |
| Reuse | median `TTFT_seated / TTFT_cold` = **1.0274**, bootstrap CI95 **[0.5890, 3.5123]** | median `< 0.5` | **FAIL** |

The mechanism therefore **failed reuse**. Chat seating is not an available identification route
under this calling convention, even though the rendered sequence and greedy result are
computationally equivalent. Per the pre-declared fork, E-ATTRIB proceeds with the centered
interaction route only. The failed mechanism was not repaired or tuned after observing the result.

The full A/B/C/D dashboard is not yet evaluable because the interaction sweep has not run. In
particular:

- the required INT8 IR is absent, so the driver refuses a reduced INT4-only sweep;
- measured STREAM bandwidth is absent (C4);
- A6 is not evaluable because the seated route failed the mechanism gate.

No coefficient, rotation, router-bias, or materiality conclusion is reported.

## Findings

### Identification route

Implemented Route 2:

```
t = a + P/R_prefill + n_out*d0 + (n_out*P)*d1
```

The fitter centers both `P` and `n_out` before forming the interaction, then transforms the fitted
coefficients back to physical `a`, `R_prefill`, `d0`, and `d1`. It refuses rank-deficient designs
before least squares rather than returning a pseudo-inverse. Synthetic known-coefficient recovery,
rank-deficiency refusal, and centered-VIF tests pass.

### KV-cache geometry

Sealed metadata run `1fd81d2a-3bae-40b1-b2a6-b9c5a50586b1` records the live CPU readback and
derivation:

```
2 (K and V) * 36 layers * 8 KV heads * 128 head_dim * 1 byte (u8) = 73,728 bytes/token
```

That is **72 KiB/token**. K and V are both counted. The model config fixes
`num_key_value_heads=8`; the live OpenVINO property is `KV_CACHE_PRECISION=u8`.

The competing **144 KiB/token** value is:

```
2 * 36 * 8 * 128 * 2 bytes (f16/bf16) = 147,456 bytes/token
```

The exact 2x discrepancy is therefore explained by the **KV dtype**, not KV-head count. The
144-KiB figure used an f16/bf16 assumption; it is not the live CPU runtime readback for this run.

## Scope and blockers

- The invalid 49,152-token cell was replaced with 32,768 because both model configs declare
  `max_position_embeddings=40,960`; 32,768 leaves generation/template headroom.
- `configs/attrib.yaml` declares both quantization levels and the interaction grid. The sweep
  preflight requires every level and refuses before measurement while INT8 is absent.
- No timed interaction sweep was started, so no comparison was made before the experiment's
  prerequisites were present.
