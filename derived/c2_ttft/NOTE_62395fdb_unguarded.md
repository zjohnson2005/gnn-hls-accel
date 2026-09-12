# C-2 session 62395fdb — unguarded note (sibling of sealed tree; seal dir not mutated)

**Session:** `62395fdb-1899-415f-b708-6adc81a24dda`  
**Seal:** `derived/c2_ttft/sealed_62395fdb-1899-415f-b708-6adc81a24dda/`  
**tree_sha256:** `95cc9d5c28fc87dcefd7c990ab216854997c5fffdf2b8212d6173173da25ae0c`

## Finding

This session ran the `ttft_slo` criterion path **without** a drift canary.
At the time, `tools/run_c1_ceiling.py --criterion ttft_slo` emitted no
canaries (matrix / `docs/CANARY_PROTOCOL.md` guard was not wired). About
55 probes across roughly 40 minutes completed with no in-run drift guard.

## Mitigation (incidental, not a substitute for the protocol)

All three sequentially-run arms (`gpu_only_f16`, `gpu_only_u8`,
`gpu_only_u4`) landed on exactly the same cold-start TTFT limit
(**10,000** tokens; AM-038 span 0). That agreement is incidental evidence
the instrument held for this session; it is **not** a canary calibration
and does not authorize further unguarded `ttft_slo` runs.

## Closure

INF-1 (2026-09-08): `tools/ttft_slo_canary.py` + wiring in
`run_c1_ceiling.py` for `--criterion ttft_slo`. Trip aborts with
`FAIL_CANARY_DRIFT` via `CanaryDriftAbort` (not a soft return). CAP-1
through CAP-3 must use the guarded path.
