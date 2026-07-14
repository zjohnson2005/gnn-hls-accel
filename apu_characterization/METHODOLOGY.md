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

## OpenAI c-ladder result (rate-limit bound) and mock CPU-saturation arm

The live OpenAI c-ladder (`out/concurrency_sweep.json`, publishable) hit a
**provider rate-limit / external throughput plateau** near c=25 (~37–38
sessions/min at c=10 and c=25; collapse at c=50) while host CPU stayed
~1.5–2% of wall. **N_max=25 and B3 uplift k from that artifact are not
quotable as CPU-bound capacity.** Quotable from that run: FRAMEWORK+THREADPOOL
composition shift vs c, per-task CPU clusters, ~1.5–2% CPU-of-wall, and the
rate-limit ceiling as a deployment-realism finding for metered API consumers.

The **mock CPU-saturation arm** closes the host-bound gap:

```bash
bash apu_characterization/run_sweep_mock_saturation.sh [--allow-dirty]
# PowerShell: .\apu_characterization\run_sweep_mock_saturation.ps1
```

- Backend: `--backend scripted` (seeded LLM wall sleeps; no TPM)
- Levels: 50,100,150,200,300,400,500 with `--saturate-on-cpu-only`
  (override `OE_MOCK_LEVELS`; stops only when host util >85%)
- Artifact: `out/concurrency_sweep_mock.json` - `result_validity: debug_only`
- Purpose only: measured CPU-bound N_max / k when util >85%. Never cite mock
  CPU shares as publishable. A throughput stall at util ≪85% is
  **coordination soft saturation**, not a CPU-bound N_max.

### Observer effect (self-correction, mock arm)

At c≥200 the mock ladder was **invalidated by instrumentation overhead**.
A py-spy cross-check on the live high-c process showed
`thread_identity.register` / `sample_and_book` (per-thread schedstat
bookkeeping + Thread.start wrap) dominating on-CPU samples - an observer
effect, not agent work. The ladder was killed; heights above c=200 are
**not usable** until re-measure under throttled/stripped instrumentation.

Control modes (`--instr-mode` or `OE_INSTR_MODE` / `OE_THREAD_IDENTITY`):

| Mode | Per-thread schedstat | Mid-session sample | Burst | Thread.start register |
|------|----------------------|--------------------|-------|------------------------|
| `full` (default) | yes | yes | yes | yes |
| `throttle` | end-of-session only | no | no | no |
| `stripped` (`OE_THREAD_IDENTITY=off`) | none | no | no | no |

All modes still measure **process CPU**, **wall/throughput**, **turn-transition
timestamps** (`llm_response_to_tool_entry`), and **sysmon util**. Instrumentation
tax at a fixed c is `(CPU_full − CPU_stripped) / CPU_full`. Mock results remain
`debug_only` / not publishable for CPU-share headlines.

Quantified tax (mock, seed-matched where noted): ~33% relative at c=1
(CH-01 full→stripped), ~93% at c=100 full→stripped; throttle residual ~9.6%
at c=100 (under the 10–15% bar for using throttle category shares).

### Latency-collapse centerpiece (mock; still debug_only)

Driver: `run_latency_collapse.sh` (exploratory stripped, n=3) and
`run_latency_collapse_promote.sh` (throttle, n≥5, Groq-band ~300 ms point).
Report: `tools/latency_collapse_report.py` → `out/latency_collapse_report.md`.

Headline (exploratory, stripped, n=3): software floor is **scale-invariant**
across a 200× LLM-latency range. Report both bounds (medians over seeds):

- **process CPU/turn** (host CPU / LLM calls; includes tool bodies) ≈ 17–32 ms
- **harness_strict/turn** (ORCH+TOKEN+SER only) ≈ 4.5–8 ms at c=1
  (≈ 4–6 ms at c=10; TOOL % rises with concurrency, so process/turn is more
  tool-contaminated at c=10)

**Crossover X** is a **range** [strict, process]. Exploratory (stripped, n=3):
≈ **5.9-20.5 ms (c=1)** / **5.5-20.4 ms (c=10)** where cpu/turn ≥ nominal LLM
median wait; strict was extrapolated below the 20 ms floor. Promotion
(throttle, n=5, `out/latency_collapse_promoted.md`): c=1 band **5.4-8.4 ms**,
both bounds MEASURED at the 5 ms row. At today's 1-4 s inference even the
process upper bound is ~0.5-3% of the turn cycle; Groq-class 100-400 ms is
where process share enters the teens-thirties; harness_strict alone reaches
majority only well below ~10 ms. Turn-transition excludes mock sleep.

The measured crossing point (5 ms row, strict share 53.6%, process share
69.9%) is sensitive to per-scale task-mix composition: the 5 ms row's ms/turn
values (strict 5.79, process 11.60) sit above the 10 ms row's (strict 3.90,
process 7.83) despite the shorter model latency, because per-turn cost
depends on which tasks were drawn at that scale, not purely on model speed.
The crossover band (5.4-8.4 ms) is the reliable claim; the specific row where
share first exceeds 50% is not. In the sub-10 ms regime, ordinary task-mix
variation swings the harness between minority and majority of the turn
cycle, itself evidence that this is the contested regime.

**Category-attribution limitation (Track A decision, promotion run):**
Per-session category attribution is reliable at c=1. At c>1, overlapping
session clocks produce a structural batch-level reconcile gap that inflates
residual (observed: 3/5 seeds at the 4000ms/c=10 cell, 15.6-17.6% vs the 15%
gate). This is not fixed by rerunning. Category-level claims (per-stage
ms/turn, harness_strict/process bands) are therefore drawn from c=1 only;
c=10 is used for wall-axis metrics (p99, throughput) which do not require
category attribution. The 15% residual gate itself is unchanged and the c=10
FAILs stay recorded FAILs.

**Hybrid-router residual-gate limitation (same class as c>1 reconcile-gap;
corrected):**
`audit_pass` uses the **per-session** residual-provenance gate in `audit.py`
(`provenance.residual > host * 15% + slack`), not pooled
`pooled_residual_provenance_pct` (pooled share is below 15% on every seed,
including FAILs). On the mock hybrid-router sweep, max per-session residual ms
is flat across local fraction
(`out/hybrid_router_audit_diagnostic.md`: f=90/100 medians inside the f=0/10
spread), so high-f FAILs are denominator-shrink of that per-session
proportional gate, not pooled-share inflation and not attribution leak.
FAILs remain recorded FAILs; the threshold is unchanged. Quotability of f>=50
latency / harness-floor claims rests on the absolute max-session residual view
plus this documented mechanism.

### Survives / died (mock arm ledger - preserve verbatim)

**Survives (attenuated):**

- Fixed software floor, scale-invariant: ~4.5–8 ms/turn harness_strict and
  ~17–32 ms/turn process (tool-inclusive upper bound).
- Crossover range ~6–20 ms (strict–process); invisible at API latencies;
  process upper bound becomes material in the Groq-class band; strict
  majority only at sub-~10 ms inference.
- Matched stripped p99 ~190× (c=1 → c=100); c=10 p99 grows as LLM wait shrinks
  (concurrency-conditional jitter).
- Throttle residual tax ~9.6% at c=100 - usable for promotion runs.
- True N_max still unmeasured (host ~5% util at c=100 stripped).

**Died / retired:**

- ~24% util plateau as a coordination ceiling (observer effect).
- FRAMEWORK 76→88% share curve under full mode.
- Absolute CPU/session growth on the tall full-instrument ladder.
- Pegged-asyncio-event-loop mechanism (EVENT_LOOP=0%; ThreadPoolExecutor).
- Mode-mixed 4.6→3412 ms p99 pair (full c=1 vs full c=100).

### Open items / deferred queue (priority order)

0. **Aggressive expansion (Angles 1-5):** report-generation citation rules
   live in `PRIOR_ART_CITATIONS.md` (no experiment config changes). Angle 3
   velocity law reference: `out/agent_velocity_law.md`. Universality /
   overlap / delegation / throughput reports regenerate with those citations
   after runs complete. Live OpenAI c-ladder (n=5) is in
   `out/concurrency_sweep.json` (validate with `tools/validate_sweep.py`).
1. **Latency-collapse promotion run** (done for mock class): see
   `out/latency_collapse_promoted.md` and living floors/budgets in
   `out/turn_path_derivation.md`. Hybrid-router sweep artifacts + report done
   (`run_hybrid_router_sweep.sh`, `out/hybrid_router_sweep_report.md`,
   residual diagnostic `out/hybrid_router_audit_diagnostic.md`). Live Groq
   anchor: prior `tool_use_failed` on `llama-3.1-8b-instant`; fix landed
   (default `openai/gpt-oss-20b` + retries); re-run blocked on free-tier
   TPD Limit 2000 (`out/live_anchor_comparison.md`, n=0).
2. **Stripped/throttle N_max ladder** (after the C1 draft): supporting density
   number, demoted vs the crossover centerpiece.
3. **Live OpenAI c=50 instrumentation-tax check** (before citing live category
   shares at high c): fewer threads than mock c=100, but verify first.
4. **Full three-task retrieve ablation** (A2 retrieve variant extends the
   search-locality precedent): quantifies the on-host TOOL_COMPUTE share that
   `turn_path_derivation.md` marks out of scope.
5. **Bare-metal RAPL** (replaces `out/energy_budget_modeled.md`): RAPL absent
   under WSL2 (probe in `out/_run_c1_stripped_throttle_rapl.sh`); the interim
   TDP-weighted CPU-time estimate is clearly labeled modeled.
6. **Second model / framework generalization** (post-draft): repeat the
   collapse ladder on a second model and a second agent framework before
   claiming the turn-path floor generalizes.
7. **SH-01 root cause** (flagged, excluded): framework-saturated n=1 outlier,
   see `SH01_DISPOSITION.md`; stays excluded from headline averages until
   investigated.
8. **Explicitly out of this phase per advisor direction:** any HLS, cosim, or
   RTL work on the turn-path structure. That work becomes the next phase's
   proposal, written against the requirements derived in
   `out/turn_path_derivation.md` (per-stage budgets, per-session state,
   tail-determinism properties; exploratory precursor
   `out/turn_path_structure.md`). This phase is measurement and writing only.

Comprehensive report: `tools/sweep_comprehensive_report.py` →
`out/concurrency_sweep_comprehensive_report.md`.

### Mock hybrid-router sweep (debug_only)

Driver: `run_hybrid_router_sweep.sh`. Report:
`tools/hybrid_router_sweep_report.py` →
`out/hybrid_router_sweep_report.md`.

This arm keeps the scripted LangGraph path but adds a fixed Bernoulli router
per LLM call. The API tier uses the existing seeded lognormal mock sleep at
scale 0.1667 (about 300 ms median for the mixed profile); the local tier uses
scale 0.0111 (about 20 ms median) with the same sigma 0.6. The default sweep
runs local fractions 0, 10, 25, 50, 75, 90, and 100 percent at c=1 with the
14-task main pool once per seed and n=5 seeds.

The purpose is to isolate the system-level effect of steering easy turns into
the crossover regime, not to evaluate routing-policy quality. Artifacts carry
promotion class `mock_hybrid_router_sweep` and remain `debug_only`. The report
derives measured local-tier fraction, router overhead, strict/process
ms/turn, harness consumed of the API-to-local latency gap (~280 ms), harness
share of a pure local-tier turn, and an absolute residual ms/session column
alongside the proportional 15% PASS/FAIL, all from JSON artifacts only. See
also the hybrid residual-gate limitation above and
`out/hybrid_router_audit_diagnostic.md`.

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
