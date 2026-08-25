# OPERATOR_CMD -- DISPATCH P (interleaved precision, drift-immune)

## Status: BLOCKED_ON_OPERATOR

**f16 control:** pinned arm `gpu_only_f16` (bare `gpu_only` is not the DISPATCH P arm). Equivalence probe: `tools/probe_f16_equivalence.ps1`.

Wiring + prediction + estimate recorded. **Matrix not launched.**

Preconditions probed **2026-08-12T17:53:17Z** (this session):

| check | result | observed |
|---|---|---|
| AC / PowerOnline | **PASS** | PowerOnline=True, Charging=True, BatteryStatus=2, ~89% |
| Tier-1 closed | **FAIL** | Cursor x16, chrome x18, msedge x9 |
| Available >= 7000 MB | **FAIL** | **1038** MB (`\Memory\Available MBytes`) |
| Package temperature | **unreachable** | `MSAcpi_ThermalZoneTemperature` Not supported; Thermal Zone counter instance absent |
| CPU frequency (proxy) | recorded | Processor Frequency **1850** MHz; % Processor Performance **174.5** |
| Detached / cool | **not attempted** | machine contaminated -- do not invent a cool reading |
| upper_estimate_h <= 6-8 | **PASS note** | central **4.52 h**, upper **5.55 h** (see `DISPATCH_P_TIME_ESTIMATE.md`) |

Do **not** use `chain_kv_precision.ps1`. Use `tools/run_dispatch_p_precision_matrix.ps1` (wrapper) or `run_delta_prefill_matrix.ps1` with the same flags.

A run that silently degrades 5x is worse than a run that stops -- canary aborts with `FAIL_CANARY_DRIFT`.

## Why blocked

Sequential DISPATCH O u4->u8 already demonstrated thermal drift as the arm variable (`DISPATCH_P_PREDICTION.md`). Launching another long GPU matrix while Cursor/Chrome are resident and Available~1 GB would contaminate the interleaved design the same way.

## Preconditions (before launch)

1. XPS on **AC** (`PowerOnline=True`).
2. Close Tier-1 on the XPS: Cursor, Chrome, Edge, Code, browsers, Slack, etc.
3. Available MBytes >= 7000.
4. Machine **idle and cool** after the overnight O load -- record Available + Processor Frequency (and package temp if reachable) at launch **and** at end.
5. Acknowledge estimate: central ~4.5 h, upper ~5.6 h (under 6-8 h).

Dry-run:

```powershell
cd C:\Users\zjohn\Projects\gnn-hls-accel
powershell -NoProfile -File tools\run_dispatch_p_precision_matrix.ps1 -DryRunGate
```

Equivalence probe (bare `gpu_only` vs pinned `gpu_only_f16`, 12 cells):

```powershell
powershell -NoProfile -File tools\probe_f16_equivalence.ps1 -DryRunGate
powershell -NoProfile -File tools\probe_f16_equivalence.ps1 -Run -Tag f16_equiv
```

## Mac -> XPS (when gates pass)

Launch (detached):

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_dispatch_p_precision_matrix.ps1 -Orchestrate"
```

Equivalent explicit matrix flags:

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Orchestrate -Arms gpu_only_f16,gpu_only_u8,gpu_only_u4 -NCached 2000,4000,8000,12000 -Deltas 50,150,400,1000 -Tag dispatch_p_interleaved -CanaryEveryN 12 -CanaryArm gpu_only_f16 -CanaryNCached 4000 -CanaryDelta 400 -CanaryMode RESIDENT -CanaryCalibrationCount 3 -CanaryRelDriftFloor 0.05"
```

Poll:

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Status"
```

Heartbeat: `derived/delta_prefill/<session_id>/heartbeat.json`
Done when `plan.json` / `result.json` show `status=complete` **or** `status=FAIL_CANARY_DRIFT` (abort is success of the guard).

Seal (only if `complete`; canary-abort still seal as FAIL with reason):

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; .venv-seam/Scripts/python.exe -u tools/seal_delta_prefill_session.py --session-id <session_id> --allow-dirty"
```

## Canary (required)

| field | value | derivation |
|---|---|---|
| config | `gpu_only_f16`, nc=4000, d=400, RESIDENT | pinned f16 control (not bare gpu_only) |
| N | **12** | floor(657 s last-good->first-bad onset / 51.34 s mean cell wall) from session `7f569929` -- see TIME_ESTIMATE |
| threshold | in-run | `max(2x early_max_rel, 0.05)` on turn1 and turn2 vs median of first 3 OK canaries -- **not** a pre-chosen 2x/5x round number |

## Supersession

Prior sequential DISPATCH O u4/u8 delta matrices are **superseded for precision comparison** (thermal confound). Do not delete. Ceilings still stand. See `SUPERSEDED.json` under those sessions and `DISPATCH_P_PREDICTION.md`.

## Artifacts

- Prediction: `derived/kv_precision/DISPATCH_P_PREDICTION.md`
- Estimate: `derived/kv_precision/DISPATCH_P_TIME_ESTIMATE.md`
- Wrapper: `tools/run_dispatch_p_precision_matrix.ps1`
- Equivalence probe: `tools/probe_f16_equivalence.ps1`
- Matrix + canary implementation: `tools/run_delta_prefill_matrix.ps1` (`-CanaryEveryN`, ...)