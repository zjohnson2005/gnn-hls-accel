# TurnTrace v2 (rev. C)

TurnTrace v2 measures how much of an agent's model-side cost the orchestration
layer *causes* and tests that claim causally with a paired
`baseline_naive`/`orchestration_optimized` intervention. Replay bundles and
task-success labels remain mandatory audit products; downstream routing and
hardware studies are not dependencies of this characterization.

## Status

Rev. B's completed work is retained. Rev. C protocol freeze is the governing
next cycle; no rev. C live run is permitted before its CPU wall budget and
cloud spend lock are recorded.

| Phase | Status |
|-------|--------|
| P1 CPU dry-run | **Done**; tagged `v2-cpu-dryrun-pass`; provisional forever |
| P2 Cloud C1/C2 | **Done**; live corpus on disk under `out/turntrace_v2/cloud_full/` |
| P3 Harness subset | **FINAL**: `raw_python` + `langgraph` |
| P4 D4 analysis | **Done**; synthetic freeze against ≥3 configs |
| D5 taxonomy | **Done**; idempotent report under `out/turntrace_v2/d5/` |
| Track C cloud prefill semantics | **Closed**; methodology recorded in exported `SCHEMA.md` |
| Rev. B D2 figures | **Closed as superseded** by rev. C C-D2/C-D3 figures; never built |
| Rev. C C-P0 | **Done**; protocol and payload manifests SHA-256 locked |
| Rev. C C-P1 | **Done**; paired arm flags, five-class suite, schema/gates, economics, exchange derivation, mock end-to-end path, and `make turntrace-v2-gate` green — no quotable A/B numbers yet |
| Rev. C C-P2 | **Blocked** on new ≥16K CPU model calibration + G-BUDGET-WALL artifact; no long run launched |
| Rev. C C-P3 | Budget locked conservatively; `live_authorized=false` pending price recheck and smoke readiness |
| Box | Dormant; `runbook-box-arrival.md` now prioritizes the rev. C full-context A/B suite |

## Gate

```bash
make turntrace-v2-gate
# or Windows:
.\apu_characterization\run_turntrace_v2_gate.ps1
# After P1 artifacts exist:
$env:TTV2_REQUIRE_CPU_DRYRUN=1; .\apu_characterization\run_turntrace_v2_gate.ps1
```

Tag when committing the dry-run-pass state: `git tag v2-cpu-dryrun-pass`

## Rev. C locked decisions (see `protocol_turntrace_v2.json`)

- **Step unit:** one model call = one step; parallel tools after that call are `fanout_siblings`, not separate steps.
- **Retemplating:** LCP failures count as new tokens; `retemplated_tokens` is a first-class CallRecord field.
- **Tool replay:** live for deterministic local tools; archived for network/flaky; mode recorded per swapped run.
- **Arms:** paired `baseline_naive` versus software-only
  `orchestration_optimized`; interventions are toggleable, not harness forks.
- **Claim form:** recovery, parity, and software exchange-rate bands across
  seeds; CPU pre-box cells remain provisional forever.
- **Layer 1:** incidental byproduct only; characterization requirements win
  every design conflict.

## Layout

| Module | Role |
|--------|------|
| `schema.py` | CallRecord / TrajectoryRecord / StepFeatures |
| `attribution.py` | token LCP, f(n) necessary/redundant split, harness tax |
| `calibration.py` | prefill/decode/network profiles + R² ≥ 0.99 gate |
| `audit.py` | conservation, profile_drift, cache_state checks |
| `labeling.py` | mechanism + semantic layers, PrefixSpan validation |
| `replay.py` | append-only replay bundles, delta contexts, swap replay |
| `derive.py` | raw event stream → CallRecords (re-runnable) |
| `export.py` | JSONL (+ parquet if pyarrow), SCHEMA.md |
| `runner.py` | `--synthetic-debug` smoke |
| `arms.py` | rev C arm/intervention configuration (flags, not forks) |
| `workload/rev_c_suite.py` | five-class deterministic real-payload suite + payload lock |
| `collect_rev_c.py` | paired mock/local collector; live path remains gated |
| `economics.py` | provider three-way split and published-rate model cost |
| `exchange.py` | offline paired recovery/exchange-rate bands |
| `wall_budget.py` | pre-launch f(n)-based CPU runtime projection |

## Non-goals

No routing policy, no Layer 1 swap sweeps at scale, no APU-advantage claim
from Arm B, no losslessness/generalization claim beyond the tested suite, and
no CPU-cell headline. See protocol `non_goals` and `blocked_claims`.
