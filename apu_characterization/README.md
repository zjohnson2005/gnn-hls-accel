# APU characterization instrument

Host-CPU characterization for LangGraph-style agent sessions: exclusive-nesting
timers, thread-identity tracing (instr_version >= 3), residual/audit gating
(process CPU = tagged + residual; per-session residual provenance gate < 15%),
and a 14-task mixed suite. Publishable baseline is the live-OpenAI c=1
replication (`out/replication_remote_search_v3.json`, audit PASS, n=5 seeds,
Linux/WSL2). Concurrency on the live API hit a rate-limit ceiling near c=25-50
at ~2% host util (not a host-capacity N_max). The latest mock latency-collapse
promotion report (`out/latency_collapse_promo_report.md`, still
`debug_only` / scripted LLM) finds a scale-invariant software floor with
harness_strict ~4.1-7.0 ms/turn and primary process band ~10.2-16.0 ms/turn at
c=1 (corrected process band under remote retrieve ~4.2-11.9 ms/turn); crossover
range ~6.2-11.8 ms. Quotable CPU shares still require
`VERIFIABLE_DATA.md` gates and `tools/validate_publishable.py`.

## Directory map

- `harness/` - session runner, OrchEngine mirror, thread hooks, mock LLM/API, payload defaults.
- `taxonomy.py` - functional CPU categories (ORCH_*, FRAMEWORK, THREADPOOL, TOOL_COMPUTE, residual, etc.).
- `tasks.py` / `profiles.py` - 14-task main pool (plus excluded AH-01/MX-01), mixed/fanout profiles.
- `instr.py`, `thread_identity.py`, `audit.py`, `attribution.py` - timers, per-thread schedstat booking, residual gate, ORCH split.
- `experiments/` - live/mock drivers (replication_batch, real_agent_breakdown, concurrency_sweep, locality ablations).
- `tools/` - validate_publishable, sweep/latency-collapse report generators, probes.
- `tests/` - resolution, provenance, audit, reconcile unit tests (run via `make apu-gate`).
- `tlp01/` - TLP-01 limit study (trace schema, dependence oracles, M0–M5 sim).
- `fixtures/` - corpus + vectors for real tool bodies.
- `out/` - artifacts; see `out/ARTIFACT_NOTES.md` and `out/README.md`.

## Start here

- Methodology and clocks: `METHODOLOGY.md`
- What is quotable: `VERIFIABLE_DATA.md`
- Stable vs in-flux surfaces: `STABILITY.md`
- Open questions for adapters: `OPEN_QUESTIONS.md`
- Latest mock latency-collapse promotion report: `out/latency_collapse_promoted.md`
  (also `out/latency_collapse_promo_report.md`)
- Publishable v3 replication summary: `out/replication_remote_search_v3.md`
- Publishable live c-ladder (n=5): `out/concurrency_sweep.md` /
  `out/concurrency_sweep_report.md` (validate with `tools/validate_sweep.py`)
- MCP-01 controlled protocol-tax arm: `METHODOLOGY_MCP.md` and `mcp_tax/`
  (`protocol_microbenchmark`; WSL smoke only, bare-metal publication matrix)
- CAP-01 capability-scaling arm: `METHODOLOGY_CAP01.md` and `cap01/`
  (`capability_scaling`; frozen real-model pools, matched replay, WSL smoke
  only, bare-metal publication matrix, Tier D projection quarantined)
- TLP-01 turn-level parallelism limit study: `METHODOLOGY_TLP01.md`,
  `PROMOTION_SUMMARY.md`, and `tlp01/` (`turn_level_parallelism`; S/C
  brackets; M0–M5; v2 speculation phase diagram; no bare metal; Praetor
  axis position Tier D only)

Install LangGraph deps from this subtree:

```
py -3 -m pip install -r apu_characterization/requirements-langgraph.txt
```

Workflow (repo root): `make apu-gate`, then `make apu-replicate-v3` /
`make apu-validate` / `make apu-validate-sweep`.Windows: `apu_characterization/run_apu_gate.ps1`.
