# BLOCKED_ON_OPERATOR — 20-entry gpu_only BFCL probe

## Preconditions (same bar as `run_gpu_only_matrix.ps1`)

1. XPS on **AC**.
2. Close on the XPS: **Cursor**, **Chrome**, **Edge**, and other Tier-1 names
   (`Code`, firefox, brave, slack, Discord, Teams, Spotify, OUTLOOK, obsidian, docker desktop, …).
3. Confirm gate:

```powershell
cd C:\Users\zjohn\Projects\gnn-hls-accel
powershell -NoProfile -File tools\run_gpu_only_matrix.ps1 -DryRunGate
```

Must show Available MBytes ≥ 7000 and no Tier-1 refuse list.

## Run the probe (from Mac over SSH, preferred)

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; .\.venv-seam\Scripts\python.exe tools\bfcl_feasibility_probe.py --mode run_gpu --out derived\bfcl_feasibility"
```

Detached variant (survives SSH drop):

```bash
ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/spawn_detached.ps1 -CommandLine '.\\.venv-seam\\Scripts\\python.exe tools\\bfcl_feasibility_probe.py --mode run_gpu --out derived\\bfcl_feasibility' -LogPath derived\\bfcl_feasibility\\run_gpu.log"
```

## Outputs

- `derived/bfcl_feasibility/gpu_probe_report.json` — per-entry wall_s, tokens, AST `valid`, per-category counts
- Existing tokenize artifacts remain valid for prompt-format / cost sections

## Config locked for the probe

- IR pin `c1821f29332faa48871c7f16426a21443fbc701fa4e4c8a581a8c51ab7bf2cb2`
- `enable_thinking=False`
- `load_sequence=[GPU]`, `generate_device=GPU`
- `GenerationConfig.apply_chat_template=False`
- Prompt: **BFCL tools style** (divergence from timing arm is intentional and reported)
