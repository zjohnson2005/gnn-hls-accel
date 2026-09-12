# Close-out: ceiling(gpu_only) `2804d7fa`

- **session_id:** `2804d7fa-d9d1-4d76-b376-48104d47b607`
- **arm run_id:** `693b44d2-8234-453c-bc8d-107a9ff259a0`
- **verdict run_id:** `f1b40956-1500-40cf-9af8-1be72d851d39`
- **sealed ceiling:** 36500 tokens (bracket `[36500, 36750]`, MIXED at 36750)
- **artifacts:** `derived/ceiling_a/2804d7fa-…/`, `raw/693b44d2-…/`, `derived/ceiling_a/_launches/ceiling_a_20260807_150154.log`

## 1. Exception identity (failing cells)

Exception type verbatim on every failing cell: **`RuntimeError`**.

Message head (identical class across cells):

```
Exception from src\inference\src\cpp\infer_request.cpp:224:
Exception from src\plugins\intel_gpu\src\runtime\ocl\ocl_common.hpp:62:
[GPU] CL_OUT_OF_RESOURCES exception.
```

| n | failing cells | artifact |
|---|---|---|
| 36750 | r0, r1 (r2 passed → MIXED) | `work/gpu_only.n36750.bisect.r{0,1}.a0.result.json` |
| 37000 | r2 only (r0/r1 passed → MIXED) | `work/gpu_only.n37000.bisect.r2.a0.result.json` |
| 38000 | r0, r1, r2 | `work/gpu_only.n38000.bisect.r{0,1,2}.a0.result.json` |
| 40000 | r0, r1, r2 | `work/gpu_only.n40000.ladder.r{0,1,2}.a0.result.json` |

**Allocator:** Intel GPU OpenCL path (`intel_gpu` → `ocl_common.hpp`), shared GPU / OpenCL resource exhaustion (`CL_OUT_OF_RESOURCES`). Not host `malloc` / process commit OOM as the thrown type.

**Not** openvino#34390, **not** a position/shape limit (`summary.json`: `ceiling_at_position_limit: false`). Memory story remains the right frame; the failure mode is GPU-plugin resource exhaustion at generate.

Traceback site: `_delta_n_child.py` → `pipe.generate(...)` (line 212).

## 2. Model context limit

From `models/Qwen3-4B-int4-ov/config.json` (pinned via `configs/models/Qwen3-4B-int4-ov.yaml`):

- `max_position_embeddings`: **40960**
- `rope_scaling`: **null**
- **YaRN enabled in this export:** **no** (`rope_scaling` absent/null)

**Beyond-native-context flag (rungs > 32768):**

| run | session / run_id | rungs > 32768 |
|---|---|---|
| this gpu_only | `2804d7fa-…` / `693b44d2-…` | 36000, 36500, 36750, 37000, 38000, 40000 |
| arm A ladder | `ad7b9288-42e6-42e8-be3e-ad1a1b1abc4c` (A/A_prime; `highest_pass` 36000, was entering 40000) | 36000, 40000 (+ any bisect above 32768) |

Config claims 40960 without YaRN metadata — treat >32768 as beyond-native for claim discipline until a YaRN-enabled export is verified.

## 3. Upper-rung curves (passing cells)

Sources: launch log `ceiling_a.cell` events (`peak_ws`, `free_peak`) and child `generation.*`.

| n | r | prefill_s | decode_tok_s | peak_ws | free_peak |
|---|---|---|---|---|---|
| 24000 | 0 (admitted a1) | 191.050 | 9.941 | 6821593088 | 1299169280 |
| 24000 | 1 | 196.168 | 10.039 | 6822117376 | 1512411136 |
| 24000 | 2 | 197.184 | 10.171 | 6821044224 | 1559764992 |
| 28000 | 0 | 137.957 | 9.302 | 7509647360 | 930615296 |
| 28000 | 1 | 155.209 | 9.249 | 7509569536 | 1128595456 |
| 28000 | 2 | 154.702 | 9.719 | 7512043520 | 999690240 |
| 32000 | 0 | 150.732 | 9.069 | 8191516672 | 576364544 |
| 32000 | 1 | 152.314 | 9.153 | 8191631360 | 798765056 |
| 32000 | 2 | 151.321 | 9.096 | 8195010560 | 873455616 |
| 36000 | 0 | 207.413 | 8.586 | 8755429376 | 337727488 |
| 36000 | 1 | 226.261 | 8.944 | 8883384320 | 561688576 |
| 36000 | 2 | 201.729 | 8.960 | 8881930240 | 670240768 |
| 36500 | 0 | 154.218 | 9.082 | 8968597504 | 2786566144 |
| 36500 | 1 | 168.789 | 9.732 | 8968998912 | 2564816896 |
| 36500 | 2 | 183.441 | 9.763 | 8967430144 | 2381340672 |

Rough `peak_ws` slope 24000→36000: `(8881930240−6821044224)/(36000−24000) ≈ 171.7 KB/token` — holds near the cited 171 KB/token into the upper ladder. Prefill is **not** monotonic in n (24000 and 36000 slower than 28000/32000).

## 4. n=24000 anomaly (19:31:58–19:47:46)

**Explained — do not flag the three admitted cells as unexplained.**

| event | ts (UTC) | wall_s / note |
|---|---|---|
| rung 20000 done | 19:31:58 | — |
| `gpu_only.n24000.ladder.r0.a0` | 19:35:57 | wall_s **208.32** |
| `delta_n.modern_standby_inadmissible` | 19:35:59 | Kernel-Power **506**; attempt 0 discarded |
| `gpu_only.n24000.ladder.r0.a1` (retry) | 19:39:49 | wall_s **199.45** (admitted as round 0) |
| r1.a0 | 19:43:46 | wall_s **204.35** |
| r2.a0 | 19:47:44 | wall_s **205.44** |
| rung PASS | 19:47:46 | — |

Four generate attempts (~817 s cell walls) vs three at n=28000 (~450 s) accounts for ~948 s vs ~571 s rung span. Only one settle/retry class event in-window: modern-standby inadmissible on r0. Pre-run settle (300 s) was earlier (19:01–19:06), outside this window.

## 5. Lock integrity (Ctrl-C `-Resume`)

- `ceiling_a.py` does **not** call `seam.locks.exclusive` / `.locks/machine` at all.
- `.locks/machine.lock`: **absent** now.
- `checkpoint.json` `"resumes": []` (line ~11803).
- `launches.json` mtime **2026-08-07T15:01:55** (original Orchestrate only); no `ceiling_a_resume_*` launch; all entries `resumed: false`.
- Heartbeat/checkpoint/result mtimes all **2026-08-07T16:51:32** (seal) — no post-seal resume write.

**Verdict:** Ctrl-C'd `-Resume` never spawned, never acquired `machine.lock`, never wrote session `2804d7fa`.

## 6. `-Status` hang — root cause and fix

**Blocking call:** `tools/ceiling_a.ps1` former Status path ~L105–107:

```powershell
Select-String -Path $last.log_path -Pattern '"session_id":\s*"([0-9a-f-]{36})"'
```

against the live `cmd.exe > log` from `spawn_detached.ps1` (orchestrator holds the log open for the whole ladder), plus `Get-Content $last.log_path -Tail 40` (~L154). Under upper-rung memory pressure this I/O wedged the SSH Status session (~80 min) while the run stayed healthy via heartbeat.

**Fix (in tree, uncommitted):** `-Status` is now job-wrapped with a **15 s** timeout; discovers `session_id` from newest heartbeat dir (preferred) or a **64 KiB** `FileShare.ReadWrite` head read; never opens `checkpoint.json`; tails log via bounded shared read; `Save-Launches` uses `ConvertTo-Json -InputObject` to stop nesting `{value,Count}` into `launches.json`.

## 3b. Boundary cells above reported ceiling (MIXED rungs)

Sources: `_launches/ceiling_a_20260807_150154.log` `ceiling_a.cell`; `raw/693b44d2-…/repeats.ndjson` `memory_instrumentation` / `envelope`; child `work/gpu_only.n{36750,37000}.bisect.*.result.json`.

### Passing cells

| n | r | prefill_s | decode_tok_s | peak_ws | free_peak (`free_physical_at_peak`) |
|---|---|---|---|---|---|
| 36750 | 2 | 146.918 | 9.465 | 9010741248 | 2864898048 |
| 37000 | 0 | 169.296 | 9.533 | 9051222016 | 2664312832 |
| 37000 | 1 | 183.025 | 9.338 | 9053454336 | 2354995200 |

### free_peak / headroom: pass vs fail at same n

Cell-event `free_peak` is null on failers (generate never completed). Comparable headroom: envelope `available_memory_mb_min` during the block, plus child `memory_at_failure.available_mb` where present.

| n | r | outcome | free_peak (bytes) | env `available_memory_mb_min` | `memory_at_failure.available_mb` |
|---|---|---|---|---|---|
| 36750 | 0 | FAIL | null | **0.617** | 2240.4 |
| 36750 | 1 | FAIL | null | **0.613** | 2738.1 |
| 36750 | 2 | PASS | 2864898048 | **2369.9** | — |
| 37000 | 0 | PASS | 2664312832 | **2355.6** | — |
| 37000 | 1 | PASS | 2354995200 | **1904.7** | — |
| 37000 | 2 | FAIL | null | **0.129** | 1881.8 |

Passers never drop below ~1.9 GiB free during generate; failers' envelope min is **&lt;1 MiB** (invalid_reasons: `available memory … < 500.000 MiB`). Host free at repeat start was similar (~10–12 GiB) for both outcomes.

**Verdict: memory/headroom-gated** — machine state during the generate window decides pass vs fail at identical n; item 1's `RuntimeError`/`CL_OUT_OF_RESOURCES` is the thrown face of that wall (not an indistinguishable non-memory class).
