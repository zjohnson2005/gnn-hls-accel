# CAP-4 — Prefill curve to failure, per KV precision, gpu_only (merges MEM-CEIL)

**Status:** `pre_registered_before_measurement`  
**Registered UTC:** 2026-09-16T01:12:00+00:00  
**Do not edit after the first probe starts.**

## Open questions

**(a)** The 9,750 → 46,000 headline extrapolates the prefill fit ~4.8× past the measured
range (~12,000). "~2 minutes at 46,000" is unmeasured.

**(b)** `c647f0c7` f16 threw `CL_OUT_OF_RESOURCES` at n=8000 on gpu_only while CPU pages.
Whether the GPU allocation ceiling binds before SLO has never been measured on this
interleaved per-KV design — decides if the failure regime depends on placement / KV.

## Arms / design

| axis | value |
|---|---|
| placement | `gpu_only` |
| residency | `RESIDENT` (working-set lock + standing reservation before generate; same child path as C-1/C-2 / ceiling_a) |
| model | Qwen3-4B-int4-ov (`ir_sha256` `c1821f29332faa48871c7f16426a21443fbc701fa4e4c8a581a8c51ab7bf2cb2`) |
| KV | `{f16, u8, u4}` → arms `gpu_only_f16`, `gpu_only_u8`, `gpu_only_u4` |
| design | **interleaved** across arms (fresh shuffle each round); one arm failing does **not** end the sweep for the others |
| repeats | 3 per cell; report **median** |
| session_design (INF-5) | `interleaved` |
| arm_order (INF-5) | `[gpu_only_f16, gpu_only_u8, gpu_only_u4]` (declared order; realized order logged per round) |

## Sweep

Primary rungs: `n ∈ {12000, 16000, 20000, 26000, 32000, 40000, 46000}`.

Continue past 46000 in +6000 steps while any arm still completes, until that arm stops
working (non-pass). Model `max_position_embeddings=40960` (no YaRN) — rungs above 40960
are beyond the native context claim; failures there may be position/shape rather than
memory and must be classified from the **verbatim** exception.

## Per-cell record

- `prefill_s`, `decode_tok_s`
- Available MB at cell start and cell end (INF-5 also books session start/end)
- On non-pass: verbatim error string + class ∈
  `{SLO_EXCEEDED | ALLOC_FAILURE | PAGING | OTHER}`

Pass = child `outcome==pass` (generation completed). Cells that complete with
`prefill_s > 10` or `decode_tok_s < 6` still count as curve successes and set
`slo_exceeded=true` (CAP-4 intentionally measures past the C-2 TTFT SLO). Soft SLO
breach alone does **not** stop an arm. Hard stop = non-pass (alloc / paging / other).

## Pre-registered predictions

### P1 — Prefill at 46,000

Assuming prefill ~ `n^1.6` anchored at sealed turn-1 median ~13.54 s at n=12,000
(`41e419bd` / C-2 family):

```
prefill(46000) ≈ 13.54 × (46000/12000)^1.6 ≈ 115 s
```

**Claim:** if n=46,000 is reachable under any KV arm, median `prefill_s` lands near
**~115 s** (order-of-magnitude: not 30 s and not 600 s).

**Falsified if:** 46,000 is reached and median prefill is outside **[60 s, 230 s]**
(factor-of-two band around 115 s), or 46,000 is unreachable for all arms (then P1 is
**not evaluable**, not confirmed).

### P2 — Ceiling order by KV

**Claim:** allocation ceiling order is **f16 < u8 < u4** (f16 hits allocation ceiling
first; u4 reaches the highest successful n). Ceilings track bytes/token if KV size is
the cause (`41e419bd` k+w: f16 234827, u8 171532, u4 ~135000 B/token).

**Falsified if:** all three arms reach 46,000 **without** allocation failure
(`ALLOC_FAILURE`), or the highest-success order is not f16 < u8 < u4.

### P3 — Failure regime (question b)

**Claim:** on `gpu_only` / RESIDENT, at least one KV arm fails by `ALLOC_FAILURE`
(verbatim containing `CL_OUT_OF_RESOURCES` or equivalent alloc markers) at an n where
the cell would otherwise be a curve point — i.e. GPU allocation can bind in this
placement. Relative to SLO: every primary rung starts at n≥12,000, already past the
C-2 TTFT limit (~9,750 for u8/u4; f16 alloc at 8,000 on `c647f0c7`), so **SLO binds
before ALLOC on the TTFT axis for u8/u4**; CAP-4 asks whether ALLOC still binds before
the extrapolated 46k operating point.

**Falsified if:** all three arms reach 46,000 without `ALLOC_FAILURE` (same joint
falsifier as P2).

## Citing priors (not re-measured here)

| fact | run / session |
|---|---|
| f16 `CL_OUT_OF_RESOURCES` at n=8000 (C-2) | `c647f0c7-5cc9-47bb-a491-3450533c34d1` |
| u8/u4 TTFT limit 9750 (C-2, canary never armed) | same |
| bare `gpu_only` ceiling 36500, `CL_OUT_OF_RESOURCES` | `2804d7fa` / arm `693b44d2` |
| turn-1 prefill ~13.5 s at 12000 | `41e419bd` |

## Non-claims

- No BFCL quality claim.
- Do not cite 50 TOPS / ~120 GB/s / 1.38× topology as measurements.
- Do not treat rungs >40960 as within native context without YaRN evidence.
