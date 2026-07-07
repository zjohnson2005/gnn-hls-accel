> **AUDIT FAILED — DO NOT CITE.** Accounting assertions failed. Fix violations before using any numbers from this artifact.

# Replication batch (remote search, n=5 seeds)

- audit pass: **NO**
- publishable_ok: **NO**
- platform: `linux`
- git: **dirty** (refreshed with `--allow-dirty`; commit before final publishable stamp)

Seeds: [0, 1, 2, 3, 4]

## Aggregate (median [IQR])

- Batch host CPU ms: 8830.1 [7525.3–10144.4]
- Pooled TOOL_COMPUTE %: 8.0 [7.3–9.1]
- Pooled ORCH %: 79.6 [77.7–83.2]
- Pooled ORCH measured % (stream step residual): 4.0 [2.5–4.1]
- Pooled ORCH reconcile % (session-end gap booked to ORCH): 75.6 [72.9–79.1]
- Pooled harness strict % (ORCH+TOKEN+SER): 84.0 [81.2–85.7]

- ORCH reconcile as % of total ORCH (per-seed batches): 95.1 [95.0–96.2] (see apu_characterization/ATTRIBUTION.md)

Execution: 10 sessions per batch, **sequential** (`workers=1`).

Comparison type: **distribution over seeds** (not matched per-call ablation).

- **VIOLATION:** git tree is dirty; commit all changes then re-run `replication_batch --refresh-only` (or pass --allow-dirty for exploratory only)

Full data: `replication_remote_search.json`
