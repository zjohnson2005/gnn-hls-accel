> **Publishable run.** Live OpenAI API agent decisions (`--backend openai`), real open-source tool bodies, audit PASS, Linux-resolution platform (or replication n≥5). Numbers may be used in research outputs subject to denominators and deployment caveats in VERIFIABLE_DATA.md and ATTRIBUTION.md.

# Replication batch (remote search, n=5 seeds)

- audit pass: **YES**
- publishable_ok: **YES**
- platform: `linux`

Seeds: [0, 1, 2, 3, 4]

## Aggregate (median [IQR])

- Batch host CPU ms: 2066.8 [1606.7–2206.8]
- Pooled TOOL_COMPUTE %: 20.5 [17.1–27.3]
- Pooled ORCH %: 29.5 [27.1–29.8]
- Pooled ORCH measured % (stream step residual): 29.5 [27.1–29.8]
- Pooled ORCH reconcile % (session-end gap booked to ORCH): 0.0 [0.0–0.0]
- Pooled harness_strict % (ORCH_SETUP+ORCH_DISPATCH+TOKENIZATION+SERIALIZATION): 36.4 [34.0–43.7]
- Pooled harness_broad % (strict + HTTP_CLIENT + PROMPT_ASSEMBLY + CONTEXT_MGMT + LOGGING): 71.7 [64.1–82.3]

TOOL_COMPUTE is not part of harness_strict or harness_broad.

- ORCH reconcile as % of total ORCH (per-seed batches): 0.0 [0.0–0.0] (see apu_characterization/ATTRIBUTION.md)

Execution: 10 sessions per batch, **sequential** (`workers=1`, c=1 anchor — not c=10 parallel).

Comparison type: **distribution over seeds** (not matched per-call ablation).

## Task exclusions (v3.1 hygiene)

| Task | Status | Notes |
|------|--------|-------|
| **SH-01** | `excluded_pending_investigation` | n=1 (seed 0 only); framework-saturated (97.6% FRAMEWORK); agent short-circuited 10-turn plan to 3 searches. See `SH01_DISPOSITION.md`. Excluded from equal-weight headline averages until post-sweep review. |
| **FO-01** | sweep canary (included) | Fan-out residual bounded <11% at c=1; does not block sweep. See `FO01_RESIDUAL.md`. |


Full data: `replication_remote_search_v3.json`
