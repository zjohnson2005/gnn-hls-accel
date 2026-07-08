# v2 replication audit failure (2026-07-07)

Run completed but **audit FAILED**. This is expected for the first v2 attempt with
thread hooks only; see fix below.

## What the run showed

| Headline | v1 median | v2 (failed run) |
|----------|-----------|-----------------|
| ORCH reconcile % | ~75.6% | **0.0%** (gap no longer booked to ORCH) |
| RESIDUAL_UNATTRIBUTED % | n/a | **~68% pooled** (91% on LH-01) |
| TOOL % | ~8% | ~4.4% |

v2 **renamed** the reconcile blob to `RESIDUAL_UNATTRIBUTED` without decomposing it.
That is the characterization worst case you flagged: opaque unattributed mass.

## Root cause

1. **OpenAI/httpx runs on worker threads** — `ThreadPoolExecutor` / sync `httpx.Client`
   hooks did not cover the async transport path.
2. **LLM callback booked main-thread `thread_time` only** (~0 ns during network I/O).
3. **Session-end gap** = `process_cpu - tagged_cpu` → almost all host CPU → RESIDUAL.
4. **Audit category sum > instrumented** — RESIDUAL booked after `instrumented_cpu_ns`
   snapshot (fixed in code).

## Fix applied (re-run required)

Per LangGraph stream step, book **process-time gap** (same basis as host CPU):

- `step_proc_ns - step_tagged_cpu` → `CLIENT_HTTP` (agent/LLM steps) or `FRAMEWORK` (tools)
- Plus `httpx.AsyncClient.send` hook, thread-pool context propagation, accounting refresh

Re-run:

```powershell
$env:OPENAI_API_KEY = "sk-..."
.\apu_characterization\run_linux_replication_v2.ps1 -AllowDirty
```

**Pass criteria:** `audit pass: True`, RESIDUAL &lt; 15% per heavy session, explicit
`CLIENT_HTTP` / `FRAMEWORK` medians in aggregate.

Compare v1 vs failed v2 vs new v2:

```powershell
py -3 apu_characterization/tools/replication_v2_compare.py
```
