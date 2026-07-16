# TurnTrace v2 — Box-arrival runbook (Strix Halo)

> Write-once, execute-later. Day one with the box is **execution only** — no design decisions.
> All local headline numbers remain blocked until this runbook completes with audit PASS.

## 0. Preconditions (done before unboxing)

- [ ] Pre-hardware phase P1 CPU dry-run tagged `v2-cpu-dryrun-pass`
- [ ] C1/C2 corpus cells collected (or queued) per P2
- [ ] Harness subset locked in `PROTOCOL_NOTES.md`
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

## 3. D1 calibration (local) — both backends × committed models × reasoning on/off

```bash
export APU_REPO_ROOT=...
export PYTHONPATH=$APU_REPO_ROOT
export TTV2_OUT=$APU_REPO_ROOT/apu_characterization/out/turntrace_v2/box_arrival

# Start llama-server (ROCm) for primary local model — reasoning ON → deployment L1a
# Start second server or flag for reasoning OFF → L1b
# Small model → L2

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
    deployment_id="L1a", model_id="PRIMARY", quantization="Q4_K_M",
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

Repeat for L1b (reasoning off), L2 (small model), and Vulkan backend variants.  
**Gate:** R² ≥ 0.99 held-out on every (model, quant, engine, hardware, power_mode) tuple.

## 4. Network baseline re-run (from the box's physical network)

```bash
# Provisional laptop baselines are INVALID for headline cloud attribution from the box.
export OPENAI_API_KEY=...   # from env only
python -m apu_characterization.turntrace_v2.network_probe \
  --endpoint-id C1 --n-probes 100 --tod-slot tod_utc_0_8 \
  --out apu_characterization/out/turntrace_v2/network_baselines_box
# Repeat for ≥3 TOD slots and for C2.
```

## 5. Local corpus cells (L1a / L1b / L2)

```bash
# After D1 PASS, collect ≥10 trajectories per (workload × harness × deployment × cache-mode)
# Primary workload: swebench_lite_layer1 (same subset as C1/C2)
# Every headline trajectory: replay bundle + task_success
# Cache modes: engine-default, cache-disabled; ideal-cache-simulated is post-hoc
```

## 6. Validate + publishability

```bash
make turntrace-v2-gate
# Then project-specific validate once local artifacts exist
python -m apu_characterization.turntrace_v2.runner --synthetic-debug  # smoke only
```

## 7. Explicit non-actions on arrival day

- Do not start Layer 1 swap sweeps
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
