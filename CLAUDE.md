# SEAM / gnn-hls-accel - working rules for Claude Code

This repo is a measurement study: how hardware configuration (placement,
residency, KV precision, weight precision, model tier, retention, routing)
changes hybrid device<->cloud agent execution on consumer AI PCs.
Paper 1 (with Rithwik Sharma, SHARC Lab, Georgia Tech): characterization.
Paper 2: design-space search over the same axes.
Deadlines: draft to Dr. Hao Nov 2, data freeze Nov 16, ISPASS in December.

## Where things run

- This clone (Mac): code, analysis, preregistrations, tests that do not need
  a GPU. Push to origin; measurement hosts pull from origin.
- XPS 16 (platform aipc-c1): `ssh zjohn@100.101.81.6`,
  repo `C:\Users\zjohn\Projects\gnn-hls-accel`. 16 GB unified, Arc iGPU,
  Windows 11 Home (no RDP). Default shell over ssh is PowerShell.
- EVO-T2S (platform evo-t2): `ssh zach@100.72.40.24`,
  repo `C:\Users\zach\Projects\gnn-hls-accel`. 64 GB unified, Arc B390.
  Shared with Rithwik: his queue watchdog is the scheduled task
  `APU-QueueWatchdog`, log `C:\apu\ovn\watchdog.log`. Never modify his
  task or files without his written OK. Clock is US Pacific.
- ssh one-liners: wrap the remote PowerShell in SINGLE quotes so zsh does
  not expand `$`. Inside, use double quotes. Do not use `''` inside WQL
  filters; filter with Where-Object instead.

## One workspace (Cursor retired 2026-10-14)

Claude Code in this Mac clone is the only editing workspace. The
measurement hosts (XPS, T2S) only pull from origin; nothing is edited,
committed or pushed from them.

- Start every session with `git pull --ff-only`; end it with commit + push.
- If a pull is not fast-forward, stop and report; never force-push and
  never resolve by discarding commits.
- Cursor and Claude (desktop app or Claude Code) must never be open on the
  XPS or the T2S. The tier-1 gate refuses `cursor.exe` and `claude.exe`
  (seam/isolation.py), but a CLI session may not show up under either
  name, so do not rely on the gate for this.
- `.cursor/rules/seam.mdc` is retired; this file is authoritative.

## Non-negotiable rules

1. Every number cited carries a run_id. A figure whose sealed run cannot be
   named is withdrawn, not caveated (`derived/WITHDRAWN.md`).
2. Predictions are written and committed BEFORE the run they predict.
   Runners must not read prereg/amendment files (a test asserts this).
   Never edit a committed prediction; add a new amendment file instead.
3. Thresholds are derived from measured baselines and recorded with the
   derivation. Never choose or loosen a threshold to make a run pass. When a
   gate blocks a run, sequence around it; never shrink the comparison.
4. Sealed run trees are immutable. Never edit, move, or delete files inside
   a directory that contains `.sealed` (a pre-commit hook enforces this).
   Notes about a run go in analysis files or `derived/VOIDS/`, never inside
   the run directory.
5. No measurement launches from a dirty tree. Commit and push first; the
   measurement host must `git pull --ff-only` to the pushed commit.
6. Never edit code on a measurement host. All code changes happen here,
   are committed, pushed, then pulled.
7. Source files in tools/, tests/, seam/ are ASCII only (hook enforced).
8. Do not revive withdrawn directions. Search before any "first" or novelty
   claim and log the search in docs/RELATED_SEARCHES.md.
9. Concise, plain language in reports. State errors plainly.

## Number prohibitions and analysis integrity

Ported from `.cursor/rules/seam.mdc` (retired 2026-10-14), wording kept.

Governing docs (re-read the relevant section before implementing):
`docs/SEAM_research_blueprint.md`, `docs/PHASE_MINUS1_IMPLEMENTATION_SPEC.md`,
`docs/hybrid_execution_dse_positioning.md`, `AMENDMENTS.md`, `AUDIT_LOG.md`.

Platform A (aipc-c1), fixed facts:
- Dell XPS 16 DA16260, Intel Core Ultra 5 325 (**Panther Lake**, not Lunar Lake)
- 4 P + 4 LP-E, **8 logical CPUs, no SMT**, Xe3 iGPU, NPU 5, 16 GB LPDDR5X
  unified, no dGPU
- Windows build 26200; never size worker pools by heuristic / `cpu_count()`

Number prohibitions:
- Never report **50 TOPS** as achieved NPU throughput (peak INT8 only)
- Never state **~120 GB/s** bandwidth until M2.4 measures it (unverified)
- **180 TOPS** is Platform B aggregate only - never as Platform A or NPU-alone
- Figures read only from `derived/`
- Never cite `topology.measured.cluster_separation_ratio` (~1.38x from
  `python_intfp_v1`) as a P-core vs LP-E-core **performance** figure - it is
  an interpreter-bound clustering discriminant only. Representative
  throughput comes from M5 microbenchmarks.
- `raw/` payloads are committed while under the AM-014 ceiling (100 MB in
  `configs/repo.yaml`); above that, external archive + `raw/MANIFEST.sha256`

Integrity:
- `raw/` is **write-once**. Never edit `analysis/` except documented AF-001
- No comparison before A/A + noise floor (`derived/noise_floor.json`)
- Analysis consumes `blinded_label`, never `condition_label`
- Discard policy: log in `AUDIT_LOG.md`; no silent discards
- **No silent retries, exception swallowing, or execution-target fallbacks**
  (log as events)
- **No per-model prompt tailoring** - invalidates H1
- Configs YAML, hashed into manifests; no magic numbers in code

Tooling:
- Python **3.11+**, full type hints, **ruff + mypy** clean, **pytest** for
  non-hardware logic

Milestone gates:
- M1 is **ACCEPTED** (`a3d2323`, citing `fb5cd2d5`). Topology mapping is
  committed.
- Do **not** start M2 telemetry / LHM / RAPL until the governance pass lands
  elevation requirements in the Phase -1 spec and a battery-pinned profile
  is defined
- Work M0->M1->M2->... in order; show evidence before advancing
- From M2 onward, agreement and acceptance criteria are **pre-registered
  before data collection** for that milestone (M1 AM-012/AM-013 are the
  worked example of the cost)
- Amendments to pre-registered gates require `AMENDMENTS.md` + owner
  authorization (see AM-004)

## Measurement hygiene (why runs refuse)

- Cold window: launch within the first minutes after a reboot; the uptime
  gate is 7200 s (provisional). WorkloadsSessionHost is killable right
  after boot and becomes kill-denied (session 0, svchost) after ~1 h; the
  gate kills it and refuses if the kill fails.
- XPS: on AC, charge >= 80%, no chrome/msedge/Cursor/Code running, free
  memory >= 7000 MB. Never run an editor or browser on a host during a
  measurement.
- Drift canary (docs/CANARY_PROTOCOL.md): must arm or the run refuses;
  two-sided; thresholds = max(2 x early drift, pooled healthy floor).
- Smokes must exercise every probe/arm path; rehearse new sequences via
  `tools/spawn_detached.ps1` (WMI child, same context as a real launch)
  until the log ends REHEARSAL_COMPLETE. A passing dry-run only proves
  plumbing.
- Known driver behavior: after CL_OUT_OF_RESOURCES the child can hang;
  the harness reaps it 30 s after its result file is written
  (HUNG_AFTER_RESULT).
- T2S: no reboots unless Tailscale unattended mode is confirmed (otherwise
  access is lost at the login screen). Use -NoRebootDeviation, which is
  recorded in the seal, and the f16 control cell first.

## How a measurement session goes

1. Code + prereg/amendment committed and pushed (clean tree).
2. Host: pull, preflight smokes (P1: tools/launch_p1_preflight.ps1).
3. Reboot (XPS), wait ~3 min, gated launch with `-Detach` (refuses unless
   AC, charge, no tier-1 processes).
4. Poll every 2 min; do not touch the host until the summary says complete.
5. Closeout: seal/verify, score every registered prediction (HIT/MISS by
   the prereg's own definition), record verdicts, commit, push.

Always ask the human before: rebooting a host, launching a measurement,
spending cloud money (H1/R0/P3 runs need explicit spend approval), or
touching the T2S watchdog.

## Task reports (standing rule)

At the end of every task, write the final report and nothing else. It is
ASCII markdown under 150 lines covering: what changed, commits in order,
registry rows touched, test results, open issues, and exact host commands.
Write it to `_agent_reports/<UTC yyyymmddThhmmZ>_<slug>.md` and overwrite
`_agent_reports/LATEST.md` with the same text. In the terminal, print only
the report path and a 3-line summary. `_agent_reports/` is gitignored.

## Current state (keep this section updated)

As of 2026-10-14. Plan of record: docs/EXPERIMENT_REGISTRY.md. Read it at
session start; update it in the same commit as the work. Never delete a row.

- Key sealed results: placement 21.4x (GPU 10000 vs CPU 468 tokens;
  c2246b1f, 7f232f86); resident-session limits f16/u8/u4 = 15000/20000/
  26500 (553b3a5c, cf3555d5, e4a22dac); warm turn-2 at 12k f16 0.639 s vs
  u8 1.003 s vs u4 0.946 s (72776603, 1587d2f4, dd2b0779); int8 decodes
  ~30-34% slower than int4 (180dfbb9); P0-v2 exchange rate ac4e5472
  (warm TTA GPU 2.47/3.26 s, CPU 9.29/11.17 s at 4k/6k).
- DEMO-1 (prereg v2, scored, analysis/demo1/):
  - XPS V1 f7343708: MATCH x3.
  - XPS V4 a678926e: MISS x3 (local 0.673, $0.184/task, 9 escalations).
  - T2S V1 b026f3fd: MATCH x3.
  - T2S V3 a4284ab0: MISS x3 (local 0.891, $0.0958/task, 5 escalations).
  - T2S V4 30caa847: MATCH x3 (local 0.982, $0.0129/task). f7de976b is
    cited for local share only: its cloud cost was not measured.
  - The trigger stays step 0 of each user turn; a per-step trigger is row
    PER-STEP-SLO.
  - V5 not run (addendum rule).
  - V5-CAL (a178e9c5, e1ed06b4): delta prefill at D ~8.5k is slower than a
    cold prefill of the full prompt on the XPS.
- NPU:
  - F1 verdict FA (natstop_f1_b172b287). NPU-1-CW planned.
  - NPU-INT8 1024 (1e79daa3: TOOLCHAIN_CAP 960) and 4096 (63d35555:
    LATENCY 2048) are recorded, not citable: their content check ran before
    the fix (d300223).
  - 2048: REFUSED twice (0fd9cd8c, 4f6a9102) plus VOID e8a27848. 8192:
    REFUSED (evidence not yet sealed).
  - The next guarded NPU session runs under amendment 2026-10-14 (canary
    state, 3367974).
  - Canary diagnosis: analysis/canary/CANARY_DRIFT_20261014.md.
- P1 budget-quality:
  - Sealed A0 8a529053: 23/200 in budget.
  - Sweep B=10 (CROSSING_B10_20261014.json): A0 bdc32a87 14 vs A4
    a766bd0b + 78dbf4c3 13. No crossing; floor and close fraction MISS.
  - Next: B=20, per amendment 9.
- T2S window 1 ended 2026-10-14; window 2 is Oct 19-25. The T2S is not
  rebooted (UNCOLD_UPTIME deviation).
- DEMO-1 cloud spend so far: about $4.40 (V4 XPS $2.77, V3 T2S $1.44,
  V4 T2S rerun $0.19, pings).
