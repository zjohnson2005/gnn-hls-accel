# ORCH reconcile attribution verdict

Generated: 2026-07-07T21:30:32.272022+00:00

## Profile session: LH-01

- Host CPU ms: 9873.6
- Timer ORCH reconcile: 7538.9 ms (76.4% of host)
- RESIDUAL_UNATTRIBUTED ms: 0.0

# py-spy bucket table: apu_characterization\out\pyspy_lh01.speedscope.json

Total weighted samples: 55.17999999999759

| Bucket | Samples | Share % |
|--------|---------|---------|
| INTERPRETER_OTHER | 33.28000000000195 | 60.3 |
| CLIENT_PARSE | 16.329999999999753 | 29.6 |
| TOOL_BODY | 1.7600000000000013 | 3.2 |
| CLIENT_HTTP | 1.500000000000001 | 2.7 |
| TOKENIZER | 1.450000000000001 | 2.6 |
| FRAMEWORK | 0.7700000000000005 | 1.4 |
| THREADPOOL | 0.08 | 0.1 |
| EVENT_LOOP | 0.01 | 0.0 |

## Cross-check
- py-spy reconcile proxy (INTERPRETER_OTHER + THREADPOOL leaf): **60.5%** of sampled time
- py-spy harness-labeled leaf (HTTP/parse/framework/tokenizer): **36.4%**
- Delta (timer reconcile vs proxy): **15.9 pp**
- **Verdict (a):** reconcile mass aligns with native/unclassified + thread-pool stacks in py-spy. Proceed to Phase C (v2 replication).
