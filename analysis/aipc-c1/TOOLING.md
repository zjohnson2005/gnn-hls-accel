# TOOLING.md — C1 Item 0 validation (BLOCKING GATE)

**Date:** 2026-07-28  
**Host:** see `MACHINE.md` (Dell XPS 16 DA16260 / Core Ultra 5 325)  
**Rule:** STOP after this file. Failures must be fixed **or** the metric declared unavailable in writing before Item 1 / Item 2.

Provenance for this gate:
- PresentMon Console 2.5.1 (`Intel.PresentMon.Console` via winget)
- Path: `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Intel.PresentMon.Console_Microsoft.Winget.Source_8wekyb3d8bbwe\presentmon.exe`
- Capture artifact: `tooling_validation/presentmon_f3_canvas_60s.csv` (638,359 bytes, 3476 frames, exit 0)
- Elevated helper log: `tooling_validation/elevated_pm_rerun.log`

---

## Summary

| ID | Check | Result |
|----|-------|--------|
| 0a | PresentMon 60s foreground capture → plausible frame times + CSV | **PASS** (with 120 Hz caveat) |
| 0b | PCM/VTune DRAM BW + stall counters respond | **FAIL — unavailable** |
| 0c | NPU util via Task Manager / typeperf under OpenVINO load | **FAIL — unavailable** |
| 0d | Teams/Zoom blur on NPU (not GPU fallback) | **FAIL — not run** (blocked by 0c) |
| 0e | F2–F6 automation twice, &lt;10% native frame-time median variance | **FAIL — not run** |
| 0f | Power-state pin (AC + plan vs `MACHINE.md`) | **FAIL** (AC offline; Balanced active) |

**Gate decision:** Item 1 may be written as pre-registration text, but **no Item 2 measurement cell is valid** until 0f is green. Metrics marked unavailable below must not appear as numeric results in the interference matrix.

---

## 0a PresentMon — PASS

**What ran:** 60 s PresentMon v2 metrics on `chrome.exe` rendering local fixture `fixtures/f3_canvas60.html` (rAF canvas; local 1080p60 mp4 for true F3 not yet staged — download blocked in this session).

**Elevation:** Unelevated PresentMon returned `access denied`. Elevated run succeeded after adding `COMPUTADORA\zjohn` to **Performance Log Users** and **Performance Monitor Users**. Unelevated capture still fails until **logoff/login** (group membership not yet effective in this session).

**Display:** Active mode **1920×1200 @ 120 Hz** → nominal interval **8.333 ms** (spec’s “~16.7 ms @60 Hz” is the wrong anchor on this panel).

| Metric | n | median | mean | p95 | p99 |
|--------|--:|-------:|-----:|----:|----:|
| `DisplayedTime` (ms) | 3474 | 8.357 | 17.040 | 41.704 | 41.802 |
| `FrameTime` (ms) | 3476 | 8.666 | 17.051 | 42.204 | 43.059 |

- Median ≈ 1× refresh interval → **plausible / nonzero / CSV written**.
- Mean ≫ median: heavy upper tail (canvas + windowed Chrome); fine for tooling smoke, not a QoS baseline.
- Present mode almost all `Hardware Composed: Independent Flip`.
- Column `ClickToPhotonLatency` exists; values `NA` in this click-free smoke (usable later when input is driven).
- v2 CSV has no `MsBetweenPresents`; use `DisplayedTime` / `FrameTime`.

**Definition locked for C1:**  
`jank_desktop` = fraction of frames with `DisplayedTime` (or agreed frame interval column) **> 1.5 × (1000 / refresh_Hz)**. On this machine that threshold is **12.5 ms** at 120 Hz (not 25 ms).

---

## 0b PCM / VTune — FAIL (declared unavailable)

| Probe | Result |
|-------|--------|
| `pcm.exe` / `pcm-memory` on PATH or disk | **Not installed** |
| GitHub `intel/pcm` release assets (tag 202604) | **No Windows binary assets** attached; README points to AppVeyor artifacts + `WINDOWS_HOWTO.md` (MSR/`msr.sys`, admin) |
| VTune / oneAPI | **Not installed** (`C:\Program Files*\Intel\oneAPI` absent) |
| Synthetic memcpy → DRAM BW peak | **Not executed** (no counter backend) |

**Declaration:** DRAM channel BW, `CYCLE_ACTIVITY.STALLS_L3_MISS` (or Lunar Lake nearest), and **CPLM-analog** are **unavailable** until PCM (or VTune memory-access) is installed, the MSR driver is loaded, and a memcpy smoke shows nonzero BW + stalls.

Do **not** substitute `\Memory\Pages/sec` as DRAM BW.

---

## 0c NPU counter — FAIL (declared unavailable)

| Probe | Result |
|-------|--------|
| Device present | Yes — `Intel(R) NPU` started (`oem127.inf`, driver **32.0.100.4724**) |
| `Get-Counter -ListSet *` names matching NPU/Neural | **None** |
| Elevated `typeperf -q` filtered for NPU/Neural | No real NPU objects (earlier “7 lines” were false positives on the substring `Input`) |
| OS build vs claimed NPU Task Manager counters | Host is **26200.8875**; prompt cites counters since **26300.8142** → this build is **below** that floor |
| OpenVINO GenAI sample load | **`openvino` / `openvino_genai` not installed** in Python 3.11 or 3.14 |

**Declaration:** NPU utilization logging via Task Manager / typeperf is **unavailable** on this OS build until (a) Windows build with NPU perf counters is confirmed, and (b) an OpenVINO NPU workload is installed and shown to move the counter.

---

## 0d Teams/Zoom blur on NPU — FAIL (not run)

Blocked by 0c: cannot verify blur is on NPU without a working NPU util signal.  
Teams (`ms-teams.exe`) and Zoom (`%APPDATA%\Zoom\bin\Zoom.exe`) are installed.  
If blur is later shown to be GPU-only, **F4 must be redefined in writing** before matrix use.

---

## 0e F2–F6 automation variance — FAIL (not run)

No replayable F2–F6 scripts existed at Item 0 (only canvas smoke for PresentMon).  
**Not executed.** Required before Item 2: scripted ~60 s loops, two native reps each, &lt;10% median frame-time variance, stored under `analysis/aipc-c1/`.

---

## 0f Power-state pin — FAIL

| Check | Required (`MACHINE.md`) | Observed at gate |
|-------|-------------------------|------------------|
| AC | online | **OFFLINE** (`ACLineStatus=0`, ~88%) |
| Plan | `Best Performance` `ec87a53a-19a6-4f4a-980f-ab27cc929b25` | **Balanced** `381b4222-...` active |

Assert script: `scripts/assert_power_pin.ps1` (exit 2=AC, 3=plan, 4=both).

**No measurement session may start until this passes.**

---

## Collateral (not separate gate items)

| Item | Status |
|------|--------|
| `% Processor Performance` | **Works** (`Get-Counter` and elevated `typeperf`) |
| Package power | Still unvalidated; `Win32_PowerMeter` historically null here |
| iGPU backend choice (SYCL/Vulkan vs ipex-llm) | **Not done** (30-min smoke pending) |
| OpenVINO NPU context ceiling | **Not measured** (engine missing) |

---

## Fix list before Item 2 (ordered)

1. Plug AC; `powercfg /setactive ec87a53a-19a6-4f4a-980f-ab27cc929b25`; run `assert_power_pin.ps1` → exit 0.  
2. Log off/on (or always elevate) so PresentMon works under Performance Log Users.  
3. Install OpenVINO GenAI; re-probe NPU counters (or declare NPU util permanently unavailable and keep NPU **throughput** column only).  
4. Install PCM (AppVeyor build + MSR driver) or VTune; pass memcpy smoke — else drop CPLM-analog / DRAM BW from matrix.  
5. Stage local 1080p60 fixture for true F3; author F2–F6 scripts; pass 0e variance.  
6. Run F4 blur NPU check; redefine F4 if GPU fallback.

---

## STOP

Item 0 complete as a **gated fail-with-declarations**. Do not begin Item 2. Item 1 (`PREREG.md`) may proceed only as pre-registration text with no measurement data.
