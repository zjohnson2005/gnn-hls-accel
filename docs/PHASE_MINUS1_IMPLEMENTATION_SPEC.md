# Phase −1 Implementation Spec — Platform A Characterization Harness

**Project:** SEAM (Silicon-aware Exploration of Agentic Model partitioning), Sharc Lab @ Georgia Tech
**Governing document:** `docs/SEAM_research_blueprint.md` — this spec implements §16 (Phase −1) under the audit standard in §5.
**Target platform:** Platform A — Dell XPS 16 DA16260, Intel Core Ultra 5 325 (Panther Lake), Windows build 26200
**Version:** 1.0 (2026-07-29)

---

## 0. Read this first

This spec builds the *instrument*, not the results. The order is deliberate and the acceptance criteria are hard. Under the blueprint's audit standard, **no comparison may be run before its noise floor is measured** (§5.5), so the A/A test and variance baseline gate all science.

Two prohibitions that override any convenience:

- **Never write to `raw/` after a run completes.** Raw is append-only and checksummed.
- **Never emit a number that lacks a run-manifest ID.** If a value cannot be traced to a manifest, it does not exist.

---

## 1. Platform constraints (encode these; do not rediscover them)

| Property | Value | Consequence for implementation |
|---|---|---|
| CPU | Core Ultra 5 325: 4 Cougar Cove P + 4 Darkmont LP-E | **8 logical CPUs, no SMT.** Default worker-pool sizes must be explicit, never `cpu_count()`-derived heuristics tuned for 16T. |
| iGPU | Intel Xe3, 4 cores, PCI `VEN_8086&DEV_B090` | OpenVINO `GPU` device |
| NPU | NPU 5 (NPU 5010), 50 TOPS INT8 peak | OpenVINO `NPU` device. 50 TOPS is **peak**, never report as achieved. |
| Memory | 16 GB LPDDR5X-7467, soldered, **unified across CPU/iGPU/NPU** | Weights + KV cache + iGPU/NPU working sets + OS share one pool. Every run must log peak committed and available memory. |
| Bandwidth | ~120 GB/s **derived, unverified** | Must be measured (M2.4) before use |
| Power | 15 W min / 25 W base / 55 W turbo, laptop chassis, battery | Thermal protocol is mandatory. Battery enables whole-device energy. |
| dGPU | none | Four local targets: `cpu-p`, `cpu-lpe`, `igpu`, `npu` |
| OS | Windows build 26200 | **RAPL via Linux powercap is unavailable.** See §3. |

**Platform-A-exclusive capability:** battery discharge gives a whole-device energy signal that Platform B (mains-only mini PC) cannot produce. Use it.

---

## 2. Repository layout

```
seam/
├── docs/
│   ├── SEAM_research_blueprint.md
│   └── PHASE_MINUS1_IMPLEMENTATION_SPEC.md
├── analysis/                       # existing probe artifacts — READ ONLY
│   ├── aipc-c1/MACHINE.md
│   ├── _c1_machine_probe.txt
│   └── _c1_drivers_probe.txt
├── seam/
│   ├── manifest.py                 # M1
│   ├── topology.py                 # M1
│   ├── telemetry/
│   │   ├── sampler.py              # unified async sampler
│   │   ├── energy_battery.py       # M2
│   │   ├── energy_rapl.py          # M2
│   │   ├── thermal.py              # M2
│   │   └── pdh.py                  # M2
│   ├── backends/
│   │   ├── base.py                 # LocalBackend protocol
│   │   ├── openvino_cpu.py         # M4
│   │   ├── openvino_igpu.py        # M4
│   │   ├── openvino_npu.py         # M4
│   │   └── cloud.py                # M3
│   ├── agent/
│   │   ├── harness.py              # M3 — fixed scaffold, model-swappable
│   │   ├── tools.py
│   │   └── trace.py
│   ├── bench/
│   │   ├── aa_test.py              # M3
│   │   ├── microbench.py           # M5
│   │   └── h1_pilot.py             # M6
│   └── analysis/
│       ├── load.py
│       ├── stats.py                # bootstrap CI, CV, Kendall τ
│       └── figures/
├── tools/lhm_bridge/               # C# RAPL bridge (M2)
├── configs/
│   ├── platforms/aipc-c1.yaml
│   ├── models/
│   ├── benchmarks/
│   └── sweeps/
├── raw/                            # WRITE-ONCE
├── derived/                        # regenerable
├── figures/                        # regenerable
├── tests/
├── AUDIT_LOG.md
└── AMENDMENTS.md
```

**Regeneration invariant:** `python -m seam.analysis.regenerate --all` rebuilds every file in `derived/` and `figures/` from `raw/` alone. CI asserts this produces no diff.

---

## 3. Telemetry design (the hard part — Windows)

Linux `powercap`/`/sys` RAPL does not exist here, and WSL2 cannot reach the NPU. **All measurement runs on native Windows.**

### 3.1 Three energy signals, deliberately redundant

**S1 — Battery discharge (whole device, ground truth-ish).**
WMI namespace `root\WMI`, class `BatteryStatus`: `DischargeRate` (mW), `RemainingCapacity` (mWh), `Voltage`. Also `Win32_Battery` for design capacity.

- Only valid **on battery**. Runs requiring S1 must assert AC is disconnected.
- Update granularity is EC-dependent and often 1–10 s and quantized. **Characterize this in M2.1** — measure the actual update period and quantization step before trusting it.
- Preferred estimator is *not* instantaneous rate but `ΔRemainingCapacity` across a window, which avoids EC smoothing artifacts.

**S2 — RAPL MSRs (SoC-domain attribution).**
`MSR_PKG_ENERGY_STATUS`, `MSR_PP0_ENERGY_STATUS` (cores), `MSR_PP1_ENERGY_STATUS` (uncore/graphics), `MSR_DRAM_ENERGY_STATUS` where present, scaled by `MSR_RAPL_POWER_UNIT`.

Requires a signed kernel driver on Windows. Implement `tools/lhm_bridge/` — a minimal C# service using **LibreHardwareMonitorLib** that exposes a localhost JSON endpoint polled from Python. Alternative: Intel PCM `pcm.exe -csv`. Pick one, pin its version, record it in the manifest.

- Handle 32-bit counter **wraparound** explicitly. This is the classic RAPL bug: counters roll over in tens of seconds under load. Accumulate deltas, detect rollover, never subtract raw values across long windows.
- Requires elevation. Fail loudly if not elevated.

**S3 — SRUM (sanity only).**
`powercfg /srumutil` for per-process energy attribution. Minute-granularity; use for cross-checks, never per-run.

### 3.2 The energy cross-validation protocol (implements P-1.10 / P0.4)

Goal: a calibrated SoC-energy estimator with a stated error, **without a wall meter**.

S1 includes display, SSD, WiFi, EC, and fans; S2 covers SoC domains only. So S1 > S2 always. The protocol:

1. **Quiesce.** Fixed power plan, fixed display brightness (record nits setting), WiFi state fixed, Windows Update paused, Defender real-time scan state recorded (and held constant — document whichever you choose), no background sync clients. Log every one of these in the manifest.
2. **Paired idle-load-idle design.** Measure idle discharge for $T_{idle}$, run load for $T_{load}$, measure idle again. The bracketing idles estimate the non-SoC baseline $P_{base}$.
3. Compute $E_{SoC}^{S1} = \int (P_{S1} - P_{base})\,dt$ over the load window.
4. Compare against $E^{S2} = \Delta$ RAPL package energy over the same window.
5. **Acceptance (AM-004, PRE-DATA, authorized by Z. Johnson):** fit the regression **separately for each execution target** (`cpu-p`, `cpu-lpe`, `igpu`, `npu`) — **not pooled**. Across ≥8 load levels spanning idle→turbo per target, require:
   - $R^2 \ge 0.95$;
   - slope $\in [1.0,\ 1.5]$ — slope $< 1.0$ is a **HARD FAILURE** (RAPL package is a strict subset of platform draw; the subset cannot grow faster than the whole);
   - intercept consistent with an independently measured idle baseline, validated by differencing two display-brightness levels;
   - report the **minimum resolvable energy difference** for that target.

   **Do not require agreement within a fixed percentage** — RAPL excludes display, SSD, WiFi, EC, fans, VRM, and possibly DRAM, so %-agreement with battery discharge is physically unachievable and would reward mis-attribution. Target-dependent slope is diagnostic: e.g. a higher slope under NPU-heavy load indicates RAPL missing NPU power.
6. Emit `derived/energy_calibration.json` with **per-target** slope, intercept, $R^2$, residual distribution, load levels used, and minimum resolvable energy difference. Every later energy claim cites this file and the target it was calibrated under.

If $R^2 < 0.95$ for a target, energy for that target is reported **with an explicit error band**, and any energy-based conclusion for it is downgraded to qualitative. Say so in the paper.

### 3.3 Thermal and throttle detection

- Package/core temperature via the LHM bridge.
- **Driver-free throttle proxy:** PDH counters `\Processor Information(_Total)\% of Maximum Frequency` and `\Processor Information(_Total)\Processor Frequency`. Sustained frequency depression is the operational throttle signal.
- If reachable through LHM, also read `IA32_THERM_STATUS` / `MSR_CORE_PERF_LIMIT_REASONS` for authoritative throttle and limit-reason bits. Treat as best-effort; the PDH proxy is the required path.
- **M2.3 must determine and freeze three constants** (blueprint §5.4): warm-up duration to steady state, throttle-residency exclusion threshold, and cooldown temperature ceiling. Write them to `configs/platforms/aipc-c1.yaml`. They are inputs to every subsequent run.

### 3.4 Engine utilization

- iGPU: PDH `\GPU Engine(*)\Utilization Percentage`, `\GPU Process Memory(*)\*`.
- NPU: **verify whether NPU engine PDH counters exist on build 26200.** Task Manager displays NPU utilization, but the counter set name and availability must be confirmed empirically. If absent, fall back to OpenVINO-reported inference timings plus S2 PP1-domain deltas, and record the limitation.
- Memory: `\Memory\Available MBytes`, `\Process(python)\Working Set - Private`, plus committed bytes. **Under 16 GB unified this is a first-class metric, not diagnostics.**

### 3.5 Timing

`time.perf_counter_ns()` (QPC-backed, sub-µs) for all durations. UTC ISO-8601 for correlation across signals. Never use `time.time()` for durations and never use `time.sleep()` inside a timed region — the Windows default timer resolution (~15.6 ms) will corrupt short measurements.

### 3.6 Unified sampler

`telemetry/sampler.py`: one background thread, configurable rate (default 1 Hz, 10 Hz when any temperature exceeds 70% of TjMax per §5.4), writing a newline-delimited JSON time series to `raw/<run_id>/samples.ndjson`. All signals share one clock. The sampler records its own overhead so §5.1's measurement-overhead term is quantified rather than assumed.

---

## 4. Core topology and affinity (`seam/topology.py`)

Distinguishing P-cores from LP-E cores is required for the `cpu-p` and `cpu-lpe` targets.

- Enumerate via `GetLogicalProcessorInformationEx(RelationProcessorCore)`; read `EfficiencyClass` per core.
- **Do not trust the EfficiencyClass ordering blindly.** Verify empirically: run a fixed single-thread integer+FP benchmark pinned to each logical CPU and cluster the results. The two clusters must separate cleanly and match the expected 4/4 split with the P-cluster faster. Persist the verified mapping to `configs/platforms/aipc-c1.yaml` and assert it on every run.
- Pin with `psutil.Process().cpu_affinity([...])`. For OpenVINO CPU inference also set `INFERENCE_NUM_THREADS` and `AFFINITY` properties explicitly; log both.
- Expose `topology.affinity_for(target)` returning the logical-CPU list for `cpu-p` (4 CPUs) and `cpu-lpe` (4 CPUs).

---

## 5. Inference backends (`seam/backends/`)

### 5.1 Protocol

```python
class LocalBackend(Protocol):
    target: str                      # cpu-p | cpu-lpe | igpu | npu
    def preflight(self, spec: ModelSpec) -> PreflightResult: ...
    def load(self, spec: ModelSpec) -> Handle: ...
    def prefill(self, h: Handle, tokens: int) -> PrefillStats: ...
    def decode(self, h: Handle, n_new: int) -> DecodeStats: ...
    def unload(self, h: Handle) -> None: ...
```

`preflight()` returns `SUPPORTED | UNSUPPORTED(reason) | DEGRADED(reason)` **without crashing.** Every sweep cell calls preflight first and records the verdict. An unsupported cell is a data point, not a failure.

### 5.2 Known-issue guards — implement as explicit assertions

These are real, filed OpenVINO issues on this hardware class. Encode them so they surface as clean diagnostics instead of mysterious crashes.

| Guard | Issue | Implementation |
|---|---|---|
| **NPU + INT8 weight-only IR crashes** with uncatchable `0xC0000005` at `generate()`; the pipeline silently accepts the IR at construction | openvino#35641 | Before constructing an NPU `LLMPipeline`, parse the IR's weight compression metadata and **assert INT4**. Refuse INT8 weight-only with a clear error. Do not attempt to catch the access violation — it is not catchable in-process. |
| **NPU dynamic-shape failure**: `to_shape was called on a dynamic shape` | openvino#34617 | Always set `MAX_PROMPT_LEN` and `NPUW_LLM_PREFILL_CHUNK_SIZE` (default 1024) explicitly; record both in the manifest. Never rely on defaults. |
| **Panther Lake iGPU** `CL_INVALID_WORK_GROUP_SIZE (-54)` on some models where Lunar/Meteor Lake succeed | openvino#34390 | Per-model GPU smoke test in `preflight()`. Classify as `UNSUPPORTED(cl_invalid_work_group_size)` rather than retry-looping. |

Pin the OpenVINO version (2026.0 or later — NPU 5010 on Panther Lake is validated on Windows 11 in that line) and record `openvino.__version__`, the NPU driver version, and the compiler version in every manifest.

### 5.3 Model set (`configs/models/`)

Under 16 GB unified, INT4-quantized ≈8B is the realistic ceiling and FP16 8B is out. Provide a capability ladder of at least four points, each in INT4 for NPU compatibility plus INT8/FP16 variants for CPU/iGPU where memory allows:

- ~0.5–1B (fast iteration, positive-control sensitivity)
- ~3–4B
- ~7–8B INT4 (the realistic deployment target)
- one long-context variant to stress KV growth under 16 GB

Each `ModelSpec` records name, revision SHA, quantization method and config, IR hash, and conversion command. Conversion is scripted and reproducible; never hand-converted.

---

## 6. Data schemas

### 6.1 Run manifest — `raw/<run_id>/manifest.json`

Implements blueprint §5.2. Add these Platform-A fields to the blueprint's schema:

```json
{
  "run_id": "uuid4",
  "spec_version": "1.0",
  "timestamp_utc": "...",
  "git_sha": "...", "git_dirty": false,
  "config_hash": "sha256 of fully resolved config",
  "elevated": true,
  "platform": {
    "id": "aipc-c1",
    "cpu": "Intel Core Ultra 5 325",
    "family": "Panther Lake",
    "topology": {"p_cpus": [...], "lpe_cpus": [...], "verified": true},
    "os_build": "26200",
    "provenance_artifacts": [
      {"path": "analysis/aipc-c1/MACHINE.md", "sha256": "..."},
      {"path": "analysis/_c1_machine_probe.txt", "sha256": "..."}
    ]
  },
  "drivers": {"npu": "...", "igpu": "...", "openvino": "...", "genai": "...", "lhm_bridge": "..."},
  "power_state": {
    "on_battery": true, "battery_pct_start": 92, "battery_pct_end": 84,
    "power_plan": "...", "display_brightness": 40,
    "defender_realtime": "enabled", "windows_update_paused": true
  },
  "thermal": {
    "ambient_c": 22.5, "warmup_s": 120, "cooldown_ceiling_c": 55,
    "throttle_residency_pct": 0.4, "throttle_threshold_pct": 5.0, "excluded": false
  },
  "target": "npu",
  "model": {"name": "...", "revision": "...", "quantization": "int4_sym_g128", "ir_sha256": "..."},
  "npu_config": {"MAX_PROMPT_LEN": 2048, "NPUW_LLM_PREFILL_CHUNK_SIZE": 1024},
  "workload": {"kind": "microbench|aa|h1_pilot", "benchmark": "...", "task_ids": [...], "seed": 1234, "n_repeats": 30},
  "condition_label": "A",
  "blinded_label": "cond_7f3a",
  "outputs": {"samples": "samples.ndjson", "steps": "steps.ndjson", "summary": "summary.json"},
  "integrity": {"self_check": "pass", "raw_sha256": "..."}
}
```

`condition_label` is written but **the analysis layer consumes only `blinded_label`** until unblinding (§7.3).

### 6.2 Step record — `raw/<run_id>/steps.ndjson`

One record per agent step. This is the substrate for H1.

```json
{
  "run_id": "...", "program_id": "...", "step_idx": 7,
  "step_type": "tool_call_synthesis",
  "assigned_target": "cloud", "model_ref": "...",
  "t_start_ns": 0, "t_end_ns": 0,
  "prompt_tokens": 3412, "completion_tokens": 118, "cached_prompt_tokens": 2900,
  "tool": {"name": "read_file", "duration_ns": 0, "result_bytes": 0, "error": null},
  "usd_cost": 0.0041,
  "privacy_class": "local_file_content",
  "terminated": false, "retry_of": null
}
```

### 6.3 Sample series — `raw/<run_id>/samples.ndjson`

```json
{"t_ns":0,"pkg_j":0.0,"pp0_j":0.0,"pp1_j":0.0,"dram_j":null,
 "batt_discharge_mw":18420,"batt_remaining_mwh":51230,
 "pkg_temp_c":78.2,"pct_max_freq":72.0,"cpu_freq_mhz":3100,
 "gpu_util_pct":4.1,"npu_util_pct":null,
 "mem_avail_mb":4210,"proc_ws_mb":6100,
 "sampler_overhead_us":180}
```

---

## 7. Milestones

Work strictly in order. Each has hard acceptance criteria; do not advance on a partial pass.

### M0 — Provenance repair (blueprint AF-001, AF-002)

1. Correct `analysis/aipc-c1/MACHINE.md` line 12: **not Lunar Lake — Panther Lake.**
2. Add the three discriminators inline as auditable evidence: SKU `Core Ultra 5 325` is a 3xx part → Core Ultra Series 3 → Panther Lake (Lunar Lake is 2xxV); graphics DID `B090` is Xe3 (Lunar Lake is `64A0`); core names Cougar Cove / Darkmont (Lunar Lake is Lion Cove / Skymont).
3. Add an explicit note: **the 4 P + 4 LP-E, 8C/8T topology does NOT discriminate** Panther Lake from Lunar Lake — Lunar Lake has the identical signature. State which evidence is load-bearing.
4. Flag whether "Cougar Cove / Darkmont" is a probe-reported field or a human inference. If inferred, mark it as non-independent evidence.
5. When a shell is available, re-run the probe, diff against committed artifacts, and record artifact SHA-256s for the manifest emitter.
6. Append both findings to `AUDIT_LOG.md` with the correction commit SHA.

**Accept:** MACHINE.md corrected with auditable evidence; `AUDIT_LOG.md` updated; artifact hashes committed.

### M1 — Manifest, topology, integrity

**Accept:**
- `seam.manifest.emit()` produces a schema-valid manifest; a JSON-schema test enforces it.
- Refuses to run on a dirty git tree unless `--allow-dirty` is passed, which is recorded in the manifest.
- `topology.py` verifies the P/LP-E split empirically (§4) and the verified mapping is committed.
- `pytest` green; `raw/` write-once enforced by a guard that fails on modification attempts.

### M2 — Telemetry

- **M2.1** Characterize S1: actual battery-counter update period and quantization step. Document both.
- **M2.2** LHM bridge with RAPL rollover handling; unit test that synthesizes a rollover and asserts correct accumulation.
- **M2.3** Thermal: determine and freeze warm-up duration, throttle threshold, cooldown ceiling. Include a sustained-load run characterizing whether 55 W turbo is sustainable and for how long.
- **M2.4** STREAM-class memory bandwidth benchmark. Report measured vs the ~120 GB/s derived figure. **Until this lands, no document may state a bandwidth number.**
- **M2.5** Energy cross-validation per §3.2 / AM-004, emitting `derived/energy_calibration.json` with **per-target** fits (`cpu-p`, `cpu-lpe`, `igpu`, `npu`): $R^2$, slope $\in [1.0,\ 1.5]$, intercept (brightness-differenced idle baseline), residuals, load levels, and minimum resolvable energy difference. Pooled regression is not acceptable.
- **M2.6** Sampler overhead characterization, including on LP-E cores.

**Accept:** per-target calibration $R^2 \ge 0.95$ with slope/intercept/residuals and min resolvable ΔE reported (AM-004); thermal constants committed to platform config; measured bandwidth recorded; overhead quantified.

### M3 — A/A test, variance baseline, cloud backend, agent harness

The gating milestone.

- **M3.1** `agent/harness.py`: a fixed agent scaffold where **only the model endpoint swaps.** Identical prompts, tools, stopping criteria, and retry logic across conditions. Emits step records per §6.2. Any per-model prompt tailoring invalidates H1 — forbid it.
- **M3.2** Cloud backend with **pinned dated model snapshots**, versioned pricing tables, and a token/cost ledger. Retries are logged as events, never silently swallowed.
- **M3.3** A/A negative control: run one configuration twice, labeled as two conditions, through the *entire* pipeline including analysis. The pipeline must report no significant difference.
- **M3.4** Positive control: a deliberately large contrast (largest vs smallest model) must register clearly.
- **M3.5** Variance baseline: $n \ge 20$ repeats on a fixed config; report CV for JCT, energy, total tokens, step count, task success. Emit `derived/noise_floor.json`.

**Accept (Gate −1, partial):** A/A reports no significant difference; positive control registers; `noise_floor.json` committed. **If A/A fails, stop and fix the harness. No comparison is valid until it passes.**

### M4 — Local backends

Implement `openvino_cpu` (both affinity variants), `openvino_igpu`, `openvino_npu` behind the §5.1 protocol, with all §5.2 guards.

**Accept:** for each of the four targets and every model in the ladder, `preflight()` returns a definite verdict without crashing; at least one model generates correct output on **each** target, or produces a documented `UNSUPPORTED` reason. **The NPU verdict is recorded regardless of outcome — this is the P-1.9 deliverable and a hard input to blueprint G0/R1.**

### M5 — Microbenchmark sweeps (S4, H7 groundwork)

Sweep dimensions: target × model × quantization × prompt length × generated tokens × batch (where applicable) × power cap (15/25/55 W) × AC/battery.

Metrics per cell: prefill tokens/s, decode tokens/s, TTFT, J/token (calibrated), peak memory, throttle residency, preflight verdict.

Order randomized within thermal blocks; cooldown enforced between runs; canary cell in every block.

**Accept:** crossover surfaces plotted for NPU vs iGPU vs CPU-P vs CPU-LPE with bootstrap CIs; every cell traceable to a manifest; all figures regenerate from `raw/` in one command. This is the Platform A half of the controlled contrast — Platform B replicates it later.

### M6 — H1 pilot (the decisive experiment)

Runs on cloud endpoints alone, so it does **not** block on M4/M5.

- Two benchmark families to start: a tool-calling suite (cheap, machine-checkable) and a small verified software-engineering subset (expensive, high value). Task lists **frozen and committed before collection.**
- Conditions: reference (all steps to the strongest model) versus per-step-type reassignment to a weaker model, one step type at a time (OFAT).
- $n \ge 30$ per cell, order randomized, day-blocked, canary in every block.
- Compute: Δ total tokens, Δ step count, Δ tool-call count and type distribution, Δ task success, behavioral divergence index, escalation cascade factor.
- **The decisive figure:** the trace-replay counterfactual. Take the reference trace, apply a partition policy, compute what a replay-based simulator would predict, and compare against what actually happened. This converts a methodological criticism into a measured quantity.
- Every effect is reported against `derived/noise_floor.json`. Effects smaller than 2× CV are reported as null.

**Accept:** H1 has a directional answer with bootstrap CIs separated from the noise floor, or an explicit statement that $n$ must increase. Result written to `AUDIT_LOG.md` and mapped to blueprint Gate G2.

---

## 8. Statistical and engineering standards

- **Bootstrap 95% CIs**, not standard error bars. Effect sizes alongside any p-value. ECDF or violin plots for heavy-tailed quantities — tool durations and JCT both are.
- **Pre-declared primary endpoints**; Benjamini–Hochberg on secondary comparisons.
- **Blinding:** analysis consumes `blinded_label`; a separate explicit `unblind` step joins labels. Analysis code must not import the condition mapping.
- **Discard policy (§5.3):** a run is discarded only for harness self-check failure, throttle residency above threshold, or API error. Every discard is logged with a reason and counted in the paper. Post-hoc discarding of inconvenient values is misconduct.
- Python 3.11+, type hints throughout, `ruff` + `mypy` in CI, `pytest` for all non-hardware logic with hardware calls mocked.
- Configs are YAML, fully resolved and hashed into the manifest. **No magic numbers in code.**
- Structured logging (JSON lines) alongside human-readable console output.

---

## 9. Prohibitions

1. No writes to `raw/` after run completion. No edits to `analysis/` probe artifacts.
2. No number in any figure, table, or document without a traceable run-manifest ID.
3. No hardcoded results in figure scripts. Figures read `derived/` only.
4. Do not cite **50 TOPS** as achieved NPU throughput, **~120 GB/s** as measured bandwidth, or **180 TOPS** as anything but a Platform B CPU+GPU+NPU aggregate.
5. No comparison before A/A passes and the noise floor is measured.
6. No silent retries, no silent exception swallowing, no silent fallback between targets. A fallback is an event that gets logged.
7. No per-model prompt tailoring in the agent harness. Only the endpoint may vary.
8. Do not tune worker-pool sizes with heuristics assuming more than 8 logical CPUs.
9. Do not "fix" a failing preflight by changing the model until the failure is recorded as a data point.
10. Do not skip a milestone's acceptance criteria to reach M6 faster. M6 is worthless without M3.

---

## 10. Open questions to resolve empirically (report, don't assume)

1. Do NPU engine PDH counters exist on build 26200? If not, what is the fallback and its error?
2. What is the real battery-counter update period and quantization step?
3. Is 55 W turbo sustainable in this chassis, and for how long before throttle?
4. Does the Windows `EfficiencyClass` ordering match the empirically measured P/LP-E split?
5. Which models in the ladder actually compile and run on NPU 5 via OpenVINO GenAI, and at what `MAX_PROMPT_LEN` ceiling?
6. Does the openvino#34390 iGPU work-group-size bug affect any model in the ladder on this Xe3 part?
7. Under 16 GB unified, at what context length does KV growth begin contending with weights, and what is the observable effect?
