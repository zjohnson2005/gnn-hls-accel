# H1-3POLICY predictions (re-anchored)

**Status:** filed before interleaved live session. Superseded W-3-anchored values kept visible.

**Session design (INF-5):** `interleaved` — entry-by-entry over policies
`slo_escalate` → `emission_escalate` → `full_signal_bounceback`.

**Config:** gpu_only RESIDENT int4-4B, KV=u8 matching `86d0f4cf`.

**Caps:** R2a $5 / R2b $20 / R2c $10 / session $35.

## Baseline regime (current, not W-3)

| run | arm | emission failures | trajectory_pass |
|---|---|---:|---:|
| `137f6f46` | gpu_only_u8 | 65 | 13 |
| `6dd387aa` | gpu_only | 61 | 14 |
| `72d270e2` | int4_4B | 64 | 10 |

Band used: completion **10–14/200** (mid **12/200 = 0.06**); emission failures **61–64** (mid **63**).

**Superseded W-3 anchors (kept):** completion **0.100** (20/200); empty_turn **45**.

## Cost fit (sealed R2b `8ffd8371`)

`usd ≈ 0.006739 + 0.084306 × n_cloud_turns`
Per escalated entry (mean n_cloud_turns=3.1077): **$0.2687**
Per single bounce turn: **$0.0910**

## Predictions

| arm | field | re-anchored | superseded (kept) |
|---|---|---|---|
| R2a | completion | **0.06** [0.05, 0.07] | 0.100 |
| R2a | cloud $ | **0.00** | 0.00 |
| R2a | emission | **0.685** [0.68, 0.695] | 0.775 |
| R2b | n_escalated | **63** [61, 64] | 45 |
| R2b | cloud $ | **16.93** [16.39, 17.20] | 13.08 [11.88, 14.29] |
| R2b | completion floor/indep | **0.0600 / 0.2648** | 0.1000 / 0.2463 |
| R2c | n_bounces | **66** [64, 67] | 68 |
| R2c | cloud $ | **6.01** [5.83, 6.10] | ~6.19 |

### Arithmetic

**R2b $:** `63 × (0.006739 + 0.084306 × 3.1077) = 63 × 0.268737 = 16.9304`
Alt scale from measured: `17.467878 × (63/65) = 16.9304`

**R2b completion indep:** `0.06 + (63/200)×0.65 = 0.06 + 0.20475 = 0.26475`

**R2c bounces:** `63 + 3 (max_steps on 86d0f4cf) + 0 (class C) = 66`
**R2c $:** `66 × 0.091045 = 6.0090`
**Superseded R2c $:** `68 × 0.091045 = 6.1911` (filed as ~$6.19)

## SLO rule

New: MEASURED `ttft_s` / `decode_tok_s` only.
Old-vs-new on `86d0f4cf`: see `slo_rule_old_vs_new_86d0f4cf.json` — **0 vs 0** (max ctx 6279).

## Class C / R2c trigger surface

See `r2a_class_c_census.json` — **0** on sealed R2a; **0** on post-LEDGER-C Q seals.

**R2c is a two-trigger policy on BFCL `multi_turn_base`:** class C
(`tool_exec_error`) is live in code but contributes **zero** expected bounces
on this workload. Active triggers are (A) no parseable tool call and
(B) step budget / max_steps. Do not treat R2c as a three-trigger policy in
planning or analysis for this corpus.

Cloud→local context injection (R2C-INJECT): bounce cloud output enters local
`ChatHistory` as an assistant turn; resident KV is **invalid** after inject
and the next local generate **re-prefills** (`re_prefill_s` on the bounce
ledger). Stub path records `re_prefill_s=0` / `stub_zero`; live
measurement via `tools/measure_r2c_reprefill.py`.

## Launch (no measurement from this filing)

```powershell
powershell -NoProfile -File tools/launch_h1.ps1 -Interleaved
```
