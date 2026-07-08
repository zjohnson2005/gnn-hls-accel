> **AUDIT FAILED — DO NOT CITE.** Accounting assertions failed. Fix violations before using any numbers from this artifact.

# Replication batch (remote search, n=5 seeds)

- audit pass: **NO**
- publishable_ok: **NO**
- platform: `linux`
- git: **dirty** (refreshed with `--allow-dirty`; commit before final publishable stamp)

Seeds: [0, 1, 2, 3, 4]

## Aggregate (median [IQR])

- Batch host CPU ms: 11669.7 [9915.4–15017.8]
- Pooled TOOL_COMPUTE %: 7.8 [7.3–8.8]
- Pooled ORCH %: 2.7 [2.6–3.6]
- Pooled ORCH measured % (stream step residual): 2.7 [2.6–3.6]
- Pooled ORCH reconcile % (session-end gap booked to ORCH): 0.0 [0.0–0.0]
- Pooled harness_strict % (ORCH_SETUP+ORCH_DISPATCH+TOKENIZATION+SERIALIZATION): 3.8 [3.1–4.6]
- Pooled harness_broad % (strict + HTTP_CLIENT + PROMPT_ASSEMBLY + CONTEXT_MGMT + LOGGING): 85.0 [84.3–85.5]

TOOL_COMPUTE is not part of harness_strict or harness_broad.

- ORCH reconcile as % of total ORCH (per-seed batches): 0.0 [0.0–0.0] (see apu_characterization/ATTRIBUTION.md)

Execution: 10 sessions per batch, **sequential** (`workers=1`).

Comparison type: **distribution over seeds** (not matched per-call ablation).

- **VIOLATION:** seed 0: SH-02: residual-provenance 58.8 ms (43% of host) exceeds 15% gate
- **VIOLATION:** seed 1: SH-02: residual-provenance 75.7 ms (45% of host) exceeds 15% gate
- **VIOLATION:** seed 1: CH-02: residual-provenance 43.0 ms (37% of host) exceeds 15% gate
- **VIOLATION:** seed 1: FO-01: residual-provenance 315.2 ms (38% of host) exceeds 15% gate
- **VIOLATION:** seed 2: CH-01: residual-provenance 35.6 ms (34% of host) exceeds 15% gate
- **VIOLATION:** seed 2: CH-02: residual-provenance 34.2 ms (32% of host) exceeds 15% gate
- **VIOLATION:** seed 2: RE-02: residual-provenance 30.1 ms (42% of host) exceeds 15% gate
- **VIOLATION:** seed 2: FO-01: residual-provenance 433.1 ms (54% of host) exceeds 15% gate
- **VIOLATION:** seed 3: FO-01: residual-provenance 352.3 ms (53% of host) exceeds 15% gate
- **VIOLATION:** seed 4: RE-01: residual-provenance 43.4 ms (29% of host) exceeds 15% gate
- ... and 1 more violations
- **REPRO:** git tree dirty; numbers are valid but not reproducible from commit

Full data: `replication_remote_search_v3.json`
