# SH-01 disposition (v3.1 replication)

**Status:** `excluded_pending_investigation` — do not use in headline CPU shares until root-caused.

## Coverage

| Field | Value |
|-------|-------|
| **n** | 1 (seed 0 only — task rotation; see task assignment) |
| **Session** | agent_0, first session in batch |
| **Wall** | 11.3 s |
| **Host CPU** | 175 ms |
| **Residual provenance** | 5 ns (~0%) |

## Step table (planned vs observed)

| Step | Planned (task spec) | Observed (OpenAI) |
|------|---------------------|-------------------|
| 0 | search: rain storm | search("storms") |
| 1 | search: temperature | search("rain") |
| 2 | search: wind forecast | search("temperature changes") |
| 3–8 | additional search + calculator | *(not invoked)* |
| 9 | final response | merge turn |

The live agent **short-circuited** the 10-turn plan to **3 remote searches** + synthesis. This is expected ReAct variance, not instrumentation failure.

## Category breakdown (why it looks anomalous)

| Category | % host CPU |
|----------|------------|
| **FRAMEWORK** | **97.6%** |
| ORCH_setup | 0.9% |
| All others | <1% |

**Interpretation:** SH-01 is **framework-bound** at n=1: almost all host CPU is LangGraph stream/orchestration on the main thread, not tool or threadpool work. Remote search adds wall I/O, not local TOOL.

**Note:** seed 0 / agent_0 carries `parallel_cpu_trim_ns ≈ 11.3 s` metadata from first-session category scaling in the artifact ledger. Host CPU after trim is 175 ms — the trim field is diagnostic overhead from early-batch accounting, not 11 s of real work. Post–cold-start-fix replication should be re-checked if SH-01 appears again in a later seed window.

## Report hygiene

- **Excluded** from equal-weight task averages and slide headlines pending post-sweep investigation.
- **Reason stated:** n=1, framework-saturated profile, non-representative of retrieve/ORCH/TOOL mix; root cause analysis deferred until after concurrency sweep.
- **Not a sweep blocker:** audit PASS; exclusion is publishable hygiene, not a failed gate.

Regenerate step data from: `replication_remote_search_v3.json` → seed 0 → agent_0.
