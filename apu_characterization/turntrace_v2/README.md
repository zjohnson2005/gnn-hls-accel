# TurnTrace v2 (rev. B)

Dual-purpose arm: (1) decompose turns into `T_orch + T_prefill + T_decode + T_network` and attribute redundant prefill as orchestration-induced model time; (2) produce a replayable, success-labeled, step-typed corpus for Layer 1 swapped-trajectory execution.

## Status

Pre-hardware workstream in progress. Core pipeline + P1 CPU dry-run + P4 D4 freeze + P5 runbook are in-tree.

| Phase | Status |
|-------|--------|
| P1 CPU dry-run | Pass (provisional corpus under `out/turntrace_v2/cpu_dryrun/`) |
| P2 Cloud C1/C2 | Machinery ready (`engines/openai_compat.py`, `network_probe.py`); collection blocked on API key + budget lock in `PROTOCOL_NOTES.md` |
| P3 Harness + SWE scaffold | `raw_python` + `langgraph` adapters + `swebench_lite` fixture scaffold |
| P4 D4 analysis | Frozen against ≥3 synthetic configs |
| P5 Box runbook | `runbook-box-arrival.md` |

## Gate

```bash
make turntrace-v2-gate
# or Windows:
.\apu_characterization\run_turntrace_v2_gate.ps1
# After P1 artifacts exist:
$env:TTV2_REQUIRE_CPU_DRYRUN=1; .\apu_characterization\run_turntrace_v2_gate.ps1
```

Tag when committing the dry-run-pass state: `git tag v2-cpu-dryrun-pass`

## Locked decisions (see `protocol_turntrace_v2.json`)

- **Step unit:** one model call = one step; parallel tools after that call are `fanout_siblings`, not separate steps.
- **Retemplating:** LCP failures count as new tokens; `retemplated_tokens` is a first-class CallRecord field.
- **Tool replay:** live for deterministic local tools; archived for network/flaky; mode recorded per swapped run.

## Gate

```bash
make turntrace-v2-gate
# or
bash apu_characterization/run_turntrace_v2_gate.sh
# Windows:
.\apu_characterization\run_turntrace_v2_gate.ps1
```

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

## Non-goals

No routing policy, no Layer 1 swap sweeps at scale, no cache remediation, no custom models. See protocol `non_goals`.
