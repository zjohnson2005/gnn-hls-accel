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

## Appendix: bare-metal validation (pre-sweep platform gate)

Purpose: quantify how much of the v3.1 CPU composition is WSL2-specific by
replicating a 6-task, n=3-seed subset of the c=1 baseline on native Linux.
The verdict (AGREEMENT / SCHEDULING DELTA / DISAGREEMENT, rules in
`tools/bare_metal_compare.py`) decides whether the WSL2 caveat is retired
and which platform the concurrency sweep runs on.

Protocol: `experiments/bare_metal_validation.py` (runner, load hygiene,
platform label) and `run_bare_metal_native.sh` (native-box driver: clone at
pinned commit, venv, BLAS pin assertion, capture, self-tests, run).
Comparison artifact: `out/bare_metal_comparison.md`.

Fill in when executed (values come from artifacts, never hand-typed):

- Machine option used: [A native lab machine | B cloud VM ("native-kernel
  Linux VM", not "bare metal") | C dual-boot or live-USB on the primary
  laptop]. Record hostname or instance type.
- Commit run on the native box: [hash]. Note: the v3.1 baseline artifact
  was measured at `d5fd7b8`; the native run uses the freeze commit, which
  differs only by the FO-01 post-tools sampling fix and this experiment.
  The FO-01 residual comparison must account for that fix (residual is
  expected to shrink for code reasons, independent of platform).
- Version deltas vs v3.1 (Python 3.14.4, numpy 2.5.1, psutil 7.2.2,
  tiktoken 0.13.0, sympy 1.14.0): [list every delta, from the native
  setup.json].
- Load hygiene records: 1-min loadavg at start and end plus per-session
  before/after samples are embedded in the native artifact
  (`load_records`). Start limit 1.0, mid-run abort limit 2.0.
- OpenAI key and quota handling: [same key as sweep during a sweep pause |
  separate key]. The subset costs roughly one v3.1 seed of API usage.
- Deviations: [none | list].

Non-goals: no concurrency levels beyond the optional labeled `smoke_c5`
(excluded from all statistics), no ablations, no new tasks. Native sessions
never merge into v3.1 statistics.
