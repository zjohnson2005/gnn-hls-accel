# TLP-01 pre-registered expectations (v2)

Freeze point: before T0 S2 collection completes and before any T1/T2
counterfactual numbers are published. Directional expectations, not
acceptance criteria. Gates and the S/C bracket form remain unchanged when
expectations fail.

`tlp01_v2` supersedes the v1 single claim ladder and any "nobody harvests
TLP" framing (died-ledger #2–#3).

## Ceiling track (M1/M2)

| Rung | Criterion | Paper that gets written |
|---|---|---|
| 1a | Tier-C M1 ≥ 3× on multi-tool classes | At least 3× TLP exists (bracket + tier + task-class scope; M1 is ceiling, not achievable). |
| 2a | Parallelism concentrated in a subset of classes | TLP taxonomy. |
| 3a | Tier-C TLP < 1.5× broadly | Agents near-serial; value shifts to the frontier track. |

## Frontier track (M4 phase diagram) — independent

| Rung | Criterion | Paper that gets written |
|---|---|---|
| 1b | Clear boundary AND Praetor Tier-D point in aggressive region | Flagship speculation-economics claim (Praetor position labeled Tier D). |
| 2b | Boundary exists; Praetor does not clearly clear it | Publish diagram + quantified penalty target. |
| 3b | No boundary (policy-invariant) | Speculation is not the lever; retire frontier claim plainly. |

Tracks are independent: 1a+3b is as legitimate as 1a+1b.

## Phase-diagram hypothesis (frozen now)

A boundary exists; confidence-gated optimal at software penalties; breadth-K
optimal below some threshold. Boundary LOCATION is measured from traces
(Tier A/B). Only Praetor's POSITION on the penalty axis is Tier D.

Penalty axis: 10 ms (software), 5 ms, 1 ms, 500 µs, 100 µs, 50 µs, 20 µs
(Praetor, Tier D — label every time). Sub-ms quote floor: 5 µs absolute,
frozen at protocol freeze (not after failure).

## Predictor sub-study

Train 80% / hold out 20% per task class. Top-1 ≈ 60–70%+ favors speculation
economics on low penalties; poor prediction is the honest boundary — pre-written
both ways.

## Task-design rationale (S2)

Yes, S2 tasks deliberately contain independent tool calls. Population of
interest is realistic multi-tool work. Pre-registered templates (including
serial negative controls `MT-SER-01` / `MT-SER-02`) live in
`tlp01/s2_task_manifest.json`, published before collection.
