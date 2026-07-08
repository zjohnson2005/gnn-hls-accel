> **AUDIT FAILED — DO NOT CITE.** Accounting assertions failed. Fix violations before using any numbers from this artifact.

# Replication batch (remote search, n=5 seeds)

- audit pass: **NO**
- publishable_ok: **NO**
- platform: `linux`
- git: **dirty** (refreshed with `--allow-dirty`; commit before final publishable stamp)

Seeds: [0, 1, 2, 3, 4]

## Aggregate (median [IQR])

- Batch host CPU ms: 13865.3 [12752.4–13914.5]
- Pooled TOOL_COMPUTE %: 4.4 [4.2–6.4]
- Pooled ORCH %: 1.5 [1.4–1.8]
- Pooled ORCH measured % (stream step residual): 1.5 [1.4–1.8]
- Pooled ORCH reconcile % (session-end gap booked to ORCH): 0.0 [0.0–0.0]
- Pooled harness_strict % (ORCH_SETUP+ORCH_DISPATCH+TOKENIZATION+SERIALIZATION): 3.4 [2.8–4.5]
- Pooled harness_broad % (strict + HTTP_CLIENT + PROMPT_ASSEMBLY + CONTEXT_MGMT + LOGGING): 26.5 [19.5–26.5]

TOOL_COMPUTE is not part of harness_strict or harness_broad.

- ORCH reconcile as % of total ORCH (per-seed batches): 0.0 [0.0–0.0] (see apu_characterization/ATTRIBUTION.md)

Execution: 10 sessions per batch, **sequential** (`workers=1`).

Comparison type: **distribution over seeds** (not matched per-call ablation).

- **VIOLATION:** seed 0: RH-01 (agent_4): category CPU sum 4749.5 ms exceeds instrumented 3604.2 ms (slack 237.5 ms)
- **VIOLATION:** seed 0: RH-01: RESIDUAL_UNATTRIBUTED 1145.3 ms (24% of host) exceeds 15% gate
- **VIOLATION:** seed 0: RH-02 (agent_5): category CPU sum 975.1 ms exceeds instrumented 111.4 ms (slack 48.8 ms)
- **VIOLATION:** seed 0: RH-02: RESIDUAL_UNATTRIBUTED 863.8 ms (89% of host) exceeds 15% gate
- **VIOLATION:** seed 0: RE-02 (agent_7): category CPU sum 833.8 ms exceeds instrumented 143.4 ms (slack 41.7 ms)
- **VIOLATION:** seed 0: RE-02: RESIDUAL_UNATTRIBUTED 690.3 ms (83% of host) exceeds 15% gate
- **VIOLATION:** seed 0: LH-01 (agent_8): category CPU sum 8886.1 ms exceeds instrumented 782.8 ms (slack 444.3 ms)
- **VIOLATION:** seed 0: LH-01: RESIDUAL_UNATTRIBUTED 8103.4 ms (91% of host) exceeds 15% gate
- **VIOLATION:** seed 1: RH-01 (agent_3): category CPU sum 1436.4 ms exceeds instrumented 132.1 ms (slack 71.8 ms)
- **VIOLATION:** seed 1: RH-01: RESIDUAL_UNATTRIBUTED 1304.3 ms (91% of host) exceeds 15% gate
- ... and 37 more violations
- **REPRO:** git tree dirty; numbers are valid but not reproducible from commit

Full data: `replication_remote_search_v2.json`
