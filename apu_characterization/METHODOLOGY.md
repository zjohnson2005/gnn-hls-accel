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

## Platform decision for the concurrency sweep (recorded before B1)

The concurrency sweep runs on WSL2 (the v3.1 baseline platform). Native-Linux
validation (Track A, 4 vCPU DigitalOcean VM, footnote-grade) runs in parallel
on separate compute and never gates the sweep. Until Track A resolves,
scheduling-sensitive categories (THREADPOOL, FRAMEWORK, ORCH_DISPATCH) carry
a stated platform caveat: measured under WSL2 kernel virtualization, not
native Linux. If Track A returns AGREEMENT, the caveat is retired with one
sentence citing bare_metal_comparison.md. If Track A returns DELTA, the
caveat stays as-is with the one-sentence 4 vCPU disclaimer. If the droplet
is not stood up this week, the fallback is explicit: sweep runs on WSL2;
native-Linux validation deferred; scheduling-sensitive categories carry the
platform caveat.

Track A and Track B never share a machine. If both draw on one OpenAI key,
starts are staggered by 10-15 minutes so the droplet's 18-session run clears
before the sweep's heavier levels ramp up.

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

- Machine option used: **B** (DigitalOcean Basic Regular 4 vCPU / 8 GB, NYC2,
  slug s-4vcpu-8gb). Label: native-kernel Linux VM (KVM), not bare metal.
- Commit run on the native box: `8b84ddfa` (freeze commit; v3.1 baseline
  measured at `d5fd7b8`; FO-01 post-tools sampling fix differs).
- Version deltas vs v3.1: Python 3.12.3 (native) vs 3.14.4 (WSL2); packages
  matched (numpy 2.5.1, psutil 7.2.2, tiktoken 0.13.0, sympy 1.14.0).
- Load hygiene: start 0.008, end 0.002 (1-min loadavg); all sessions PASS.
- OpenAI key: same key as WSL2 runs; droplet completed before sweep smoke.
- Verdict: **DELTA** (LH-01 ORCH_DISPATCH 28.6 pp WSL2 vs 11.2 pp native).
  RH-01 THREADPOOL agreed within 10 pp (-4.8 pp). FO-01 residual 7.9% vs 8.0%.
  WSL2 caveat retained; no rerun triggered.
- Deviations: 4 vCPU native VM vs 8-core WSL2 baseline (core-count confound).

Non-goals: no concurrency levels beyond the optional labeled `smoke_c5`
(excluded from all statistics), no ablations, no new tasks. Native sessions
never merge into v3.1 statistics.
