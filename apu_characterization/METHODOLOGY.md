# py-spy sanity and reconcile attribution methodology

## Python build

Record at capture time via `sysconfig.get_config_var('Py_GIL_DISABLED')`.
None or 0 means GIL enabled. 1 means free-threaded build.

## Verifiable data (not synthetic)

See `VERIFIABLE_DATA.md`. Publishable runs require `--backend openai` (live agent
decisions) and real open-source tool bodies. Scripted/mock paths are instrumentation
tests only. Mock remote search is a labeled deployment model, not production HTTP.

## Clock semantics

- Session host CPU: `process_time()` delta (all threads, overlap counted once).
- Region timers: exclusive `thread_time()` on the entering thread.
- v1 reconcile: `process_cpu - tagged_cpu` booked to `ORCH_DISPATCH`.
- v2 residual: same gap booked to `RESIDUAL_UNATTRIBUTED` only.

## Instrumentation v2 thread hooks

- `concurrent.futures.ThreadPoolExecutor.submit` wrapped (FRAMEWORK + THREADPOOL).
- `httpx.Client.send` wrapped (CLIENT_HTTP + CLIENT_PARSE).
- `asyncio.run` wrapped (EVENT_LOOP).

Document the seam used in `harness/thread_hooks.py`.

## Timer overhead

Re-measure with `measure_timer_overhead_ns` after enabling v2 hooks.
Overhead estimate: `(regions_per_session * overhead_ns_per_pair) / session_cpu`.
Must stay below 3% or be mitigated.

## py-spy on WSL2

Record flags used: `--subprocesses` plus optional `--native` if stable.
Sanity: 2 s busy loop, dominant frame should be the loop function.

## Trim vs reconcile

See `out/reconcile_bug_checks.md` section A2.4.

## Concurrency sweep gate G2

Gate G2 (harness share vs c not built on unattributed bucket) is satisfied when
`replication_remote_search_v2.json` exists with audit PASS and
`RESIDUAL_UNATTRIBUTED` below 15% on every session.

Reference: `out/replication_v1_v2_migration.md`.
