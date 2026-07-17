# TurnTrace v2 — Box-arrival runbook (Strix Halo)

> Write-once, execute-later. Day one with the box is **execution only** — no design decisions.
> All local headline numbers remain blocked until this runbook completes with audit PASS.

## 0. Preconditions (done before unboxing)

- [ ] Pre-hardware phase P1 CPU dry-run tagged `v2-cpu-dryrun-pass`
- [ ] Rev B C1/C2 corpus collected; rev C cloud cells either complete or queued under a refreshed budget lock
- [ ] Harness subset locked in `PROTOCOL_NOTES.md`
- [ ] Rev C protocol lock and payload-manifest hash verified
- [x] Rev C C-P1 pairing/parity/cache-truth gates pass on the provisional mechanism cell (`make turntrace-v2-gate`)
- [ ] Rev C C-P2: ≥16K CPU model calibrated + G-BUDGET-WALL closed before long local suite
- [ ] This runbook reviewed; power mode choice pinned below

**Pinned power mode for headline runs:** `120W` (change only with a new protocol amendment + full D1 re-run).

**Pinned backends for L1:** record both; headline cells use the one that passes cache verification first:
1. llama.cpp **ROCm**
2. llama.cpp **Vulkan** (fallback / comparison)

**Cache-clear semantics (do not reuse the CPU dry-run latch):** P1's `/slots/?action=erase` → HTTP 501 latch is **CPU llama-server without `--slot-save-path` only**. On ROCm/Vulkan, re-run `verify_cache_behavior` and confirm cold samples are within ±25% of f(n) *before* trusting warm/cold cells. A different clear API (or a working slot erase) may be required — log the ack path in `boundary-cases.md`.

## 1. OS / drivers (day-one morning)

```bash
# On the Strix Halo box (Linux recommended; WSL2 only if bare metal blocked)
uname -a
rocm-smi || true
vulkaninfo --summary || true
# Install llama.cpp ROCm and Vulkan builds matching engine_version recorded in profiles.
# Place models under $TTV2_MODELS; binaries under $TTV2_BIN.
```

Log outputs into `apu_characterization/out/turntrace_v2/box_arrival/host_inventory.json`.

## 2. Thermal / power sanity

```bash
# Pin power mode BEFORE any calibration
# (vendor-specific; Framework / GMKtec — fill exact commands after first boot)
# Example placeholder:
#   sudo ryzenadj --stapm-limit=120000 --fast-limit=120000 --slow-limit=120000

# Confirm SoC temperature readable
cat /sys/class/hwmon/hwmon*/temp*_input 2>/dev/null | head
```

Abort and cool down if idle temp is abnormal or power mode flips mid-run.

## 3. C-D1 calibration — rev C models and full context range

The box's first measurement job is the rev C paired suite, superseding the
rev B `swebench_lite_layer1` cell list. Select a committed local model with a
context window that covers the suite (target calibration grid through 64K
where the model permits). Calibrate every chosen
`(model, quant, engine, hardware, power_mode)` tuple before either arm runs.

```bash
export APU_REPO_ROOT=...
export PYTHONPATH=$APU_REPO_ROOT
export TTV2_OUT=$APU_REPO_ROOT/apu_characterization/out/turntrace_v2/box_arrival

# Start llama-server (ROCm) for the committed rev C primary local model.
# Vulkan is the fallback/comparison backend, not a silent replacement.

python -m apu_characterization.turntrace_v2.cpu_dryrun \
  --out $TTV2_OUT/L1a_cal \
  --base-url http://127.0.0.1:8080 \
  --n-trajectories 0
# Prefer dedicated calibrate entry once split; until then use calibrate_live APIs:

python - <<'PY'
from pathlib import Path
from apu_characterization.turntrace_v2.engines import EngineIdentity
from apu_characterization.turntrace_v2.engines.llamacpp import LlamaCppServerEngine
from apu_characterization.turntrace_v2.calibrate_live import (
    calibrate_prefill, calibrate_decode, verify_cache_behavior,
)
ident = EngineIdentity(
    deployment_id="L1a", model_id="REV_C_PRIMARY", quantization="Q4_K_M",
    engine="llama.cpp", engine_version="ROCm-FILL", hardware="strix-halo",
    reasoning_mode="on", provisional=False,
)
eng = LlamaCppServerEngine(base_url="http://127.0.0.1:8080", identity=ident)
out = Path("apu_characterization/out/turntrace_v2/box_arrival/L1a")
pre = calibrate_prefill(eng, n_grid=(256,512,1024,2048,4096,8192,16384,32768,65536), reps=10, out_dir=out)
assert pre.acceptance_passed(), pre.to_dict()
calibrate_decode(eng, kv_depths=(0,8192,32768,65536), out_dir=out)
assert verify_cache_behavior(eng, pre, out_dir=out)["passed"]
print("L1a D1 OK")
PY
```

Repeat only for rev C deployment tuples frozen before the run.
**Gate:** R² ≥ 0.99 held-out on every (model, quant, engine, hardware, power_mode) tuple.
Also record the rev C f(n)-based total suite wall projection before collection.

## 4. Network baseline re-run (from the box's physical network)

```bash
# Provisional laptop baselines are INVALID for headline cloud attribution from the box.
export OPENAI_API_KEY=...   # from env only
python -m apu_characterization.turntrace_v2.network_probe \
  --endpoint-id C1 --n-probes 100 --tod-slot tod_utc_0_8 \
  --out apu_characterization/out/turntrace_v2/network_baselines_box
# Repeat for ≥3 TOD slots and for C2.
```

## 5. Rev C paired local suite — first box workload

```bash
# After C-D1 PASS:
# - TT-EDIT / TT-RET / TT-FAN / TT-DOC / TT-CHAIN
# - raw_python + langgraph
# - baseline_naive + orchestration_optimized
# - seeds 0..4, temperature=0
# - full context targets from protocol_turntrace_v2.json
# - Class I B-CACHE byte-identical pairs and required ablations on >=2 classes
# - every trajectory: pair_id + replay bundle + task_success
# - ideal-cache-simulated remains a post-hoc bound
```

Before accepting a batch:

1. G-CACHE-TRUTH verifies warm prefill ≈ f(new tokens) within the profile band.
2. G-PAIR verifies Class I byte hashes and Class II step-sequence/append discipline.
3. G-PARITY verifies exact paired task-success equality.
4. Generate C-D2 cards and C-D3 exchange-rate bands before any interpretation.

## 6. Validate + publishability

```bash
make turntrace-v2-gate
# Then project-specific validate once local artifacts exist
python -m apu_characterization.turntrace_v2.runner --synthetic-debug  # smoke only
```

## 7. Explicit non-actions on arrival day

- Do not start Layer 1 swap sweeps or let Layer 1 requirements alter rev C
- Do not change power mode mid-calibration
- Do not quote CPU dry-run or laptop network baselines as headline
- Do not invent cache remediation

## Fill-ins after first boot (only blanks allowed)

| Blank | Value |
|-------|-------|
| ROCm version | |
| Vulkan driver | |
| Primary model_id | |
| Small model_id (L2) | |
| Exact ryzenadj / powerctl command | |
| llama.cpp commit / release tag | |
