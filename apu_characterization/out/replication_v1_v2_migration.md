# Replication v1 vs v2 mass migration

- v1 artifact: `replication_remote_search.json`
- v2 artifact: `replication_remote_search_v2.json`

| Headline | v1 median | v2 median | Notes |
|----------|-----------|-----------|-------|
| Batch host CPU ms | 8830.1 | 13865.3 |  |
| Pooled TOOL % | 8.0 | 4.4 |  |
| Pooled ORCH total % | 79.6 | 1.5 |  |
| Pooled ORCH measured % | 4.0 | 1.5 |  |
| Pooled ORCH reconcile % (v1) | 75.6 | 0.0 | v1 reconcile bucket |
| Pooled harness strict % | 84.0 | 3.4 |  |
| Pooled harness broad % | 0.0 | 26.5 |  |
| Pooled RESIDUAL_UNATTRIBUTED % (v2) | 0.0 | 81.8 | v2 residual gate target <15% |
| Pooled CLIENT_HTTP % (v2) | 0.0 | 5.4 |  |
| Pooled CLIENT_PARSE % (v2) | 0.0 | 0.0 |  |
| Pooled FRAMEWORK % (v2) | 0.0 | 14.2 |  |

Old reconcile mass (v1 median): **75.6%** of batch host CPU.

v2 should decompose this mass into CLIENT_*, FRAMEWORK, THREADPOOL, EVENT_LOOP, and leave RESIDUAL_UNATTRIBUTED below 15% per session.
