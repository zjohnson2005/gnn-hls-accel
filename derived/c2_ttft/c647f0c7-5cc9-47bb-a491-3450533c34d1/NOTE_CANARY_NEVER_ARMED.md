# c647f0c7 -- canary never armed (INF-1b)

**Session:** `c647f0c7-5cc9-47bb-a491-3450533c34d1`  
**Location:** this note lives in the **derived** session dir only. No seal
directory exists for this session; this file is not part of any seal tree.

## What happened

INF-1 derived `N = floor(657 / 9.93) = 66` from the onset bound alone against
a **39-probe** run. After the opening canary, the interval never elapsed
(`probes_since_canary` never reached 66), so zero in-run canaries fired,
calibration never completed (`C=3`), and `canary_gate.armed` stayed **false**.
The session still finished with `status=complete`.

## Caveat on the reported limits

Read the session's u8/u4 TTFT limits (**9,750** tokens each in
`summary.json` / `ttft_limits`) with this caveat: the drift guard never
armed, so those numbers were produced without a post-calibration trip
surface. They are not authorized as a canary-guarded C-2 seal.

## Failure class

Unguarded complete: the drift guard was present but never armed, so the run
had no post-calibration trip surface. Recording that fact here documents the
instrument gap without mutating a seal.

## Fix (INF-1b)

`N = min(floor(onset_s / mean_probe_wall_s), floor(planned_probe_count / (C + 1)))`.
Refuse to start if the budget cannot fit `C` calibration canaries plus one
armed check. Refuse to seal with `armed == false` unless launched with
`-AllowUnguarded` / `--allow-unguarded`, which writes `UNGUARDED` into the
summary and the seal.
