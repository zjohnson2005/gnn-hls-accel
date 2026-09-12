# BLOCKED_ON_OPERATOR — BFCL session-level residency A/B (DISPATCH L)

## Status (2026-08-10)

**BLOCKED_ON_OPERATOR** — DISPATCH L cold fix is in the harness; positive control and
four-cell matrix were **not** run (host contaminated). Do not invent control or matrix
numbers.

| Check | Result |
|---|---|
| AC (`BatteryStatus=2`) | PASS |
| Available MBytes ≥ 7000 | **FAIL** (~5936) |
| Tier-1 clean | **FAIL** (Cursor ×16, chrome ×16) |
| DISPATCH L cold fix (code) | in tree — `SchedulerConfig(enable_prefix_caching=False)` for NON_RESIDENT |
| Cold control (`session_residency_cold_control`) | **not run** (gate refused) |
| Four-cell matrix | **not launched** |
| Time estimate | PASS — central ~120 min, upper ~165 min; see `TIME_ESTIMATE_SESSION_RESIDENCY.md` |

## Fix summary (already in tree)

- **DISPATCH K:** ChatHistory with `set_tools` + `enable_thinking=False`. RESIDENT:
  `generate(ChatHistory)`. NON_RESIDENT: same render as cold string
  (`apply_chat_template=False`). Full texts sealed.
- **DISPATCH L:** NON_RESIDENT pipeline loads with
  `SchedulerConfig(enable_prefix_caching=False)`. Root cause was ContinuousBatching
  prefix caching ON by default under LLMPipeline (not missing `finish_chat`).
  Rejected (b) fresh pipeline per turn unless cold control fails.
- Arm A NON_RESIDENT = **n=20** (paired).

See `DISPATCH_L_NON_RESIDENT_COLD.md`.

## Operator steps (XPS)

1. Stay on **AC**.
2. Close **Cursor**, **Chrome**, and other tier-1 names.
3. From Mac over SSH:

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_bfcl_session_residency.ps1 -DryRunGate"
```

Must print `dry-run PASS`.

4. Positive control (must PASS before matrix; under ~1 min on gpu_only):

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_bfcl_session_residency.ps1 -ColdControl"
```

Or rely on `-Orchestrate`, which runs the same control and refuses the matrix on FAIL.

5. Launch detached chain (only after dry-run + cold control PASS):

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_bfcl_session_residency.ps1 -Orchestrate"
```

6. Poll (non-blocking):

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_bfcl_session_residency.ps1 -Status"
```

## Artifacts (after complete)

Under `derived/bfcl_feasibility/session_residency/`:

- `_cold_control/session_residency_cold_control_gpu_only.json` (gate)
- `<session_id>/session_residency_{gpu_only,A}_{RESIDENT,NON_RESIDENT}_report.json`
- `<session_id>/session_residency_compare_{gpu_only,A}.json`
- `<session_id>/plan.json` / `summary.json` / `heartbeat.json`

## Cells

| Arm | Mode | n | Note |
|---|---|---:|---|
| gpu_only | RESIDENT | 20 | paired |
| gpu_only | NON_RESIDENT | 20 | prefix caching OFF |
| A | RESIDENT | 20 | paired |
| A | NON_RESIDENT | 20 | cold ~55 s turn-1; fails TTFT≤10 s by construction |
