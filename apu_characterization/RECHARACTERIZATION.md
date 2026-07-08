# Recharacterization runbook (verifiable path)

Ordered steps after `VERIFIABLE_DATA.md` policy. **Do not cite scripted/mock runs.**

## Prerequisites

- WSL2 Linux (resolution self-test must PASS)
- `OPENAI_API_KEY` in PowerShell session (rotate if ever pasted in chat)
- Git clean tree for publishable artifacts (or `--allow-dirty` for dry runs only)

## Step 0 — One-time WSL bootstrap

From PowerShell (repo root):

```powershell
wsl.exe bash --noprofile --norc /mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/run_wsl_bootstrap.sh
```

Uses `uv` (no sudo). Creates `.venv-wsl` with py-spy, LangGraph, deps.

Verify:

```powershell
wsl.exe bash --noprofile --norc -c "export PATH=/usr/bin:/bin:$HOME/.local/bin; cd /mnt/c/Users/zjohn/Projects/gnn-hls-accel && . .venv-wsl/bin/activate && python -m apu_characterization.tests.test_resolution"
```

## Step 1 — Phase A3: LH-01 profile + py-spy (OpenAI)

Confirms ORCH reconcile is harness-class work before v2 replication.

```powershell
$env:OPENAI_API_KEY = "sk-..."
.\apu_characterization\run_profile_lh01_wsl.ps1
```

**Outputs:**

| File | Purpose |
|------|---------|
| `out/profile_lh-01_s0.json` | Timer attribution (must be `backend: openai`) |
| `out/pyspy_lh01.speedscope.json` | Profiler stacks |
| `out/pyspy_lh01_buckets.md` | Bucket table |
| `out/ATTRIBUTION_VERDICT.md` | (a)/(b)/(c) verdict vs 15 pp cross-check |

**Gate:** verdict must use live OpenAI profile; scripted profile is invalid.

**py-spy notes:** If you see `Ns behind in sampling`, reduce rate (script default `PYSPY_RATE=20`).
WSL may print `No child process (os error 10)` after writing speedscope; run
`bash apu_characterization/run_profile_lh01_finish.sh` to bucketize + verdict.

## Step 2 — Phase B validation (local, no API)

```powershell
py -3 -m apu_characterization.tests.test_instr
py -3 -m apu_characterization.tests.test_reconcile_worker
py -3 apu_characterization/tools/validate_publishable.py apu_characterization/out/replication_remote_search.json
```

On WSL after bootstrap, same tests run automatically before replication.

## Step 3 — Phase C: v2 replication (OpenAI, ~1 hour)

```powershell
$env:OPENAI_API_KEY = "sk-..."
.\apu_characterization\run_linux_replication_v2.ps1
# or with uncommitted policy/docs changes:
.\apu_characterization\run_linux_replication_v2.ps1 -AllowDirty
```

**Outputs:**

| File | Purpose |
|------|---------|
| `out/replication_remote_search_v2.json` | v2 medians/IQR, RESIDUAL gate |
| `out/replication_remote_search_v2.md` | Human report |
| `out/replication_v1_v2_migration.md` | v1→v2 mass migration table |

**Gates (every session, audit):**

- `audit.pass` and `publishable_ok`
- `backend == openai`
- `RESIDUAL_UNATTRIBUTED` below 15% per session (instr v2)
- Git clean (unless explicit allow-dirty)

Validate:

```powershell
py -3 apu_characterization/tools/validate_publishable.py apu_characterization/out/replication_remote_search_v2.json
```

## Step 4 — Refresh v1 (no OpenAI, optional)

After code changes to ORCH split logic on existing v1 JSON:

```powershell
py -3 -m apu_characterization.experiments.replication_batch --refresh-only
```

## Step 5 — Phase D: v3 replication (thread-identity, measured)

```powershell
$env:OPENAI_API_KEY = "sk-..."
.\apu_characterization\run_linux_replication_v3.ps1 -AllowDirty
```

Artifact: `replication_remote_search_v3.json`. Quote harness headlines from **measured** provenance tier only.

Smoke (no OpenAI, Linux):

```bash
bash apu_characterization/run_v3_smoke_wsl.sh
```

## Step 6 — Concurrency sweep (blocked until Step 5 PASS)

Only after v2 replication audit PASS and ATTRIBUTION_VERDICT confirmed on OpenAI LH-01.

## Current status

| Step | Status |
|------|--------|
| v1 publishable baseline | DONE — `replication_remote_search.json` |
| WSL bootstrap (uv venv) | DONE — `.venv-wsl` + py-spy 0.4.2 |
| Phase A3 OpenAI profile | **Pending** — needs `OPENAI_API_KEY` |
| Phase C v2 replication | **Pending** — needs `OPENAI_API_KEY` |

## Quick reference

```powershell
# Bootstrap once
wsl.exe bash --noprofile --norc apu_characterization/run_wsl_bootstrap.sh

# Phase A3
$env:OPENAI_API_KEY = "sk-..."
.\apu_characterization\run_profile_lh01_wsl.ps1

# Phase C
.\apu_characterization\run_linux_replication_v2.ps1
```
