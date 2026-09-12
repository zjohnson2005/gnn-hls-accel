# BLOCKED_ON_OPERATOR — 20-entry multi_turn gpu_only probe (DISPATCH A3)

## Preconditions (same bar as `run_gpu_only_matrix.ps1`)

1. XPS on **AC**.
2. Close on the XPS: **Cursor**, **Chrome**, **Edge**, and other Tier-1 names.
3. Confirm gate:

```powershell
cd C:\Users\zjohn\Projects\gnn-hls-accel
powershell -NoProfile -File tools\run_gpu_only_matrix.ps1 -DryRunGate
```

Must show Available MBytes ≥ 7000 and no Tier-1 refuse list.

## Already done (no GPU)

```powershell
.\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py --mode multi_turn_gold_selftest --out derived\bfcl_feasibility
```

Gold selftest artifact: `derived/bfcl_feasibility/multi_turn_gold_selftest.json` (**20/20 valid**).

## Run the 20-entry multi-turn GPU probe (from Mac over SSH, preferred)

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; .\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py --mode run_gpu_multi_turn --out derived\bfcl_feasibility"
```

Detached variant (survives SSH drop / Cursor exit):

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/spawn_detached.ps1 -CommandLine '.\\.venv-seam\\Scripts\\python.exe tools\\bfcl_feasibility_probe.py --mode run_gpu_multi_turn --out derived\\bfcl_feasibility' -LogPath derived\\bfcl_feasibility\\run_gpu_multi_turn.log"
```

## Outputs

- `multi_turn_gold_selftest.json` — gold path (done)
- `multi_turn_probe_entries.json` — selected 20 entries
- `multi_turn_gpu_probe_report.json` — correct/n, wall-clock, token dists, context growth
- `multi_turn_gpu_probe_partial.json` — incremental per-entry (if killed mid-run)

## Config locked

- IR pin `c1821f29332faa48871c7f16426a21443fbc701fa4e4c8a581a8c51ab7bf2cb2`
- `enable_thinking=False`
- `load_sequence=[GPU]`, `generate_device=GPU`
- `GenerationConfig.apply_chat_template=False`
- Prompt: BFCL tools style + multi-turn agent loop (tool responses fed back)
- Scorer: `multi_turn_checker` via `apu_characterization/cap01/bfcl_cap01_multi_turn_checker.py`
