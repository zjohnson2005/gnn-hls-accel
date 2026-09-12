# OPERATOR_CMD — DISPATCH H (KV precision u8/u4 chain)

> **SUPERSEDED for launch sequencing by DISPATCH O** (2026-08-11):  
> `derived/kv_precision/OPERATOR_CMD_DISPATCH_O.md`  
> Reason: chain_kv_precision.ps1 died on Object[]→Int32 after u8 ceiling; old grid unmatched / NON_RESIDENT-max-only; DISPATCH O uses manual ceiling_a + run_delta_prefill_matrix on the matched in-range grid. This file retained as historical pointer.

## Status: BLOCKED_ON_OPERATOR

Wiring complete. Prediction + estimate recorded. **Not launched.**

DryRunGate (this session): AC ok; estimate 4.74 h (upper 5.50 h ≤ 6); Tier-1 resident (Cursor + chrome); Available ~6414 MB < 7000.

## Preconditions

1. XPS on **AC**.
2. Close Tier-1 on the XPS: Cursor, Chrome, Edge, Code, browsers, Slack, etc.
3. Confirm gate:

```powershell
cd C:\Users\zjohn\Projects\gnn-hls-accel
powershell -NoProfile -File tools\chain_kv_precision.ps1 -DryRunGate
```

Must show: AC ok, `TIME_ESTIMATE` ≤6 h, prediction present, Available ≥7000, no Tier-1.

## Launch (Mac → detached)

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/chain_kv_precision.ps1 -Orchestrate"
```

## Poll

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/chain_kv_precision.ps1 -Status"
```

Heartbeat: `derived/kv_precision/<chain_id>/heartbeat.json`  
Result: `derived/kv_precision/<chain_id>/chain_result.json`

## Stages (order)

1. `ceiling_a -Arms gpu_only_u8` (native seal)
2. `delta_prefill -Arms gpu_only_u8 -NCached 4000,12000 -Deltas 100,400,1000,2000` + derived seal
3. `ceiling_a -Arms gpu_only_u4`
4. `delta_prefill` for `gpu_only_u4` + derived seal

Failed stage records and chain continues. Estimate ~4.7 h (upper ~5.5 h). See `TIME_ESTIMATE.md`, `PREDICTION_BEFORE_RUN.md`.
