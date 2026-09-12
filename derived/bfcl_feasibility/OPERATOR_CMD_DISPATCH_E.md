# BLOCKED_ON_OPERATOR — DISPATCH E (KV precision + NPU load)

## Gate status (captured this session)

- AC: Online (`BatteryStatus=2`, SoC 100%)
- DryRunGate: **REFUSED**
  - Tier-1 resident: Cursor (~2.1 GiB private), chrome (~1.7 GiB)
  - Available MBytes **~6188–6243** < floor **7000**
- Offline inventory completed: attention-window + `KV_CACHE_PRECISION` Core smoke
- Accuracy matrix + NPU load: **not run** (no invented scores / no fake `isolation_mode`)

## Preconditions (same bar as `run_gpu_only_matrix.ps1`)

1. XPS on **AC**.
2. Close on the XPS: **Cursor**, **Chrome**, **Edge**, and other Tier-1 names.
3. Confirm gate:

```powershell
cd C:\Users\zjohn\Projects\gnn-hls-accel
powershell -NoProfile -File tools\run_gpu_only_matrix.ps1 -DryRunGate
```

Must show Available MBytes ≥ 7000 and no Tier-1 refuse list.

## 1) KV precision quality (gpu_only, ~gates 5 h ladder)

Exact property: `KV_CACHE_PRECISION` (`openvino.Type` f16 / u8 / u4).
20 AST entries: 10 `simple_python` + 10 `parallel`. No prompt tuning.

Preferred (Mac → detached SSH):

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/spawn_detached.ps1 -CommandLine '.\\.venv-seam\\Scripts\\python.exe tools\\bfcl_feasibility_probe.py --mode run_gpu_kv_precision --out derived\\bfcl_feasibility' -LogPath derived\\bfcl_feasibility\\run_gpu_kv_precision.log"
```

Foreground:

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; .\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py --mode run_gpu_kv_precision --out derived\bfcl_feasibility"
```

Artifact: `derived/bfcl_feasibility/kv_precision_gpu_probe_report.json`

Decision rule (after numbers exist):
- u4 collapses → u4 dead; only u8 gets a ladder (if u8 holds)
- u8 and u4 both collapse → precision axis dies
- f16 is the quality reference arm

## 2) NPU feasibility (~15 min)

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/spawn_detached.ps1 -CommandLine '.\\.venv-seam\\Scripts\\python.exe tools\\bfcl_feasibility_probe.py --mode run_npu_load --out derived\\bfcl_feasibility' -LogPath derived\\bfcl_feasibility\\run_npu_load.log"
```

Uses `load_sequence=[NPU]` with `MAX_PROMPT_LEN` / `NPUW_LLM_MAX_PROMPT_LEN` ∈ {512,1024,2048,4096} and `NPUW_LLM_PREFILL_CHUNK_SIZE=1024`.

Artifact: `derived/bfcl_feasibility/npu_load_probe_report.json`

## Already runnable offline (no clean-host needed)

```powershell
.\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py --mode attention_window_inventory --out derived\bfcl_feasibility
.\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py --mode kv_precision_property_smoke --out derived\bfcl_feasibility
```
