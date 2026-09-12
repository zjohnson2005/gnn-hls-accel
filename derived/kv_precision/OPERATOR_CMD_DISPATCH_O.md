# OPERATOR_CMD — DISPATCH O (matched KV precision grid)

> **SUPERSEDED for launch / precision comparison by DISPATCH P (2026-08-12).**  
> Sequential u4 then u8 matrices confounded arm with thermal drift (u8 session `7f569929`: turn1 cold 5.12× within-matrix). Use `OPERATOR_CMD_DISPATCH_P.md` for the interleaved + canary design. **Do not delete this file or the O session trees.** Ceilings still stand; O delta matrices are not authorized for cross-precision ranking.

## Status: SUPERSEDED_BY_DISPATCH_P (historical; was BLOCKED_ON_OPERATOR / then partially run)

Wiring + prediction + estimate recorded. Stages 2–3 (u4/u8 deltas) ran and are retained under `derived/delta_prefill/` with `SUPERSEDED.json` for comparison use.

Preconditions failed on 2026-08-11 (this session) at first attempt; later stages ran on a hot machine — see DISPATCH P.

| check | observed |
|---|---|
| AC | **FAIL** — BatteryStatus=1, PowerOnline=False, discharging @ ~99% |
| Tier-1 closed | **FAIL** — Cursor ×16, chrome ×17 |
| Available ≥ 7000 MB | **FAIL** — ~5607 MB |
| Detached / ssh path | not attempted |
| upper_estimate_h ≤ 6 | **FAIL** — 6.89 h (central 5.30 h); overrun noted |

Do **not** use `chain_kv_precision.ps1` for this dispatch (prior Object[]→Int32 death; manual one-stage-at-a-time).

## Preconditions (before any stage)

1. XPS on **AC** (`PowerOnline=True`).
2. Close Tier-1 on the XPS: Cursor, Chrome, Edge, Code, browsers, Slack, etc.
3. Available MBytes ≥ 7000.
4. Acknowledge upper wall **6.89 h > 6 h** if running stages 2–4 the same day.

Dry-run (delta matrix gate; same tier-1 / Available floor):

```powershell
cd C:\Users\zjohn\Projects\gnn-hls-accel
powershell -NoProfile -File tools\run_delta_prefill_matrix.ps1 -DryRunGate -Arms gpu_only_u4 -NCached "2000,4000,8000,12000" -Deltas "50,150,400,1000"
```

## Mac → XPS (manual, one stage at a time)

### Stage 1 — u4 ceiling (~71 min if early-exit like u8; up to ~1.8 h)

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/ceiling_a.ps1 -Orchestrate -Arms gpu_only_u4"
```

Poll:

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/ceiling_a.ps1 -Status"
```

Heartbeat: `derived/ceiling_a/<session_id>/heartbeat.json`  
Done when `result.json` present with `"sealed": true`.

### Stage 2 — u4 delta matrix (96 cells; ~1.4 h) — only after stage 1 seals

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Orchestrate -Arms gpu_only_u4 -NCached 2000,4000,8000,12000 -Deltas 50,150,400,1000 -Tag dispatch_o_u4"
```

Poll:

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Status"
```

Heartbeat: `derived/delta_prefill/<session_id>/heartbeat.json`  
Seal (after `plan.json` status=complete):

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; .venv-seam/Scripts/python.exe -u tools/seal_delta_prefill_session.py --session-id <session_id> --allow-dirty"
```

### Stage 3 — u8 delta matrix (same grid)

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Orchestrate -Arms gpu_only_u8 -NCached 2000,4000,8000,12000 -Deltas 50,150,400,1000 -Tag dispatch_o_u8"
```

Poll/seal: same as stage 2 with the new session_id.

### Stage 4 — f16 delta matrix (`gpu_only`, same grid)

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Orchestrate -Arms gpu_only -NCached 2000,4000,8000,12000 -Deltas 50,150,400,1000 -Tag dispatch_o_f16"
```

Poll/seal: same as stage 2 with the new session_id.

## Quotes

Prefer quoting CSV lists if the local shell eats commas:

```bash
-NCached \"2000,4000,8000,12000\" -Deltas \"50,150,400,1000\"
```

Scripts now accept Object[] or CSV string for `-NCached`/`-Deltas`/`-Arms` (DISPATCH O parameterization fix).

## Do not re-measure

- f16 ceiling 36500 / `CL_OUT_OF_RESOURCES`
- u8 ceiling ≥40000 / `early_exit_position_limit` (run `29253ddc`, verdict `2d385fa3`)

## Artifacts

- Prediction: `derived/kv_precision/DISPATCH_O_PREDICTION.md`
- Estimate: `derived/kv_precision/DISPATCH_O_TIME_ESTIMATE.md`
- Prior DISPATCH H chain docs superseded for launch sequencing (see banners on `OPERATOR_CMD.md` / `TIME_ESTIMATE.md` / `PREDICTION_BEFORE_RUN.md`).
