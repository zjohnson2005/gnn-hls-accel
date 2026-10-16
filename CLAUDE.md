# SEAM / gnn-hls-accel - working rules for Claude Code

This repo measures hardware configuration as a design space for local and
hybrid device<->cloud agent execution on consumer AI PCs (docs/THESIS.md).
Three papers and one demo:
1. ISPASS combined paper with Rithwik Sharma (SHARC Lab, Georgia Tech),
   "Where the operating limit comes from" (docs/PAPER_ISPASS_ABSTRACT.md).
   Zach: configuration (Intel, OpenVINO); Rithwik: retention and the
   NVIDIA/llama.cpp side. **This is the current priority.**
2. Paper 2, after ISPASS: "Provisioning and routing when failure is
   unobservable" (docs/PAPER2_ABSTRACT.md).
3. ERN, Zach's configuration DSE that feeds Paper 2
   (docs/PAPER_ERN_ABSTRACT.md; numbers dated 2026-09-07, to refresh).
4. DEMO, shown Oct 26: DEMO-1 done; DEMO-2 (default vs tuned configuration
   in a real hybrid) registered, rehearsals pending.
Evidence per paper: docs/PAPER_EVIDENCE_MAP.md.
Deadlines: draft to Dr. Hao Nov 2, data freeze Nov 16, ISPASS in December.

## Thesis and decision rules

Thesis: docs/THESIS.md (registered by
docs/amendments/THESIS_AMEND_2026-10-15.md). Every future experiment:
1. names the configuration axis it moves on fixed hardware;
2. reports every objective it measures (latency, memory cost, quality,
   context held), and cloud $ for hybrid cells;
3. uses the default configuration run as a real hybrid as its control,
   never an all-cloud or all-local run;
4. treats a hardware change as a yardstick only;
5. treats limits, canaries and gates as infrastructure;
6. takes its priority from the papers: ISPASS first, then Paper 2 and ERN,
   with DEMO-2 in time for Oct 26.
Wording forced by the 2026-10-15 literature sweep is in docs/THESIS.md and
docs/RELATED_SEARCHES.md (e.g. "configuration-aware", never "hardware-aware
routing"; rank reversal only with the model fixed).

## Where things run

- This clone (Mac): code, analysis, preregistrations, tests that do not need
  a GPU. Push to origin; measurement hosts pull from origin.
- XPS 16 (platform aipc-c1): `ssh zjohn@100.101.81.6`,
  repo `C:\Users\zjohn\Projects\gnn-hls-accel`. 16 GB unified, Arc iGPU,
  Windows 11 Home (no RDP). Default shell over ssh is PowerShell.
- EVO-T2S (platform evo-t2): `ssh zach@100.72.40.24`,
  repo `C:\Users\zach\Projects\gnn-hls-accel`. 64 GB unified, Arc B390
  (12 Xe3 cores, 16 MB L2; LITERATURE: Wikipedia, Chips and Cheese).
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
- 4 P + 4 LP-E, **8 logical CPUs, no SMT**, Xe3 iGPU ("Intel(R) Graphics",
  4 Xe3 cores; not an Arc B390), NPU 5, 16 GB LPDDR5X unified, no dGPU
- Memory per Notebookcheck: LPDDR5X-7467 on a 128-bit bus, about 119.5 GB/s
  theoretical (LITERATURE; our unit's memory speed is unconfirmed, pilot P9)
- Windows build 26200; never size worker pools by heuristic / `cpu_count()`

Number prohibitions:
- Never report **50 TOPS** as achieved NPU throughput (peak INT8 only)
- Never state **~120 GB/s** bandwidth until M2.4 measures it (unverified).
  The figure may appear only as "theoretical, per <source>, unmeasured"
  (e.g. 119.5 GB/s per Notebookcheck), never as achieved bandwidth
- **180 TOPS** is Platform B aggregate only - never as Platform A or NPU-alone
- Figures read only from `derived/`
- Never cite `topology.measured.cluster_separation_ratio` (~1.38x from
  `python_intfp_v1`) as a P-core vs LP-E-core **performance** figure - it is
  an interpreter-bound clustering discriminant only. Representative
  throughput comes from M5 microbenchmarks.
- `raw/` payloads are committed while under the AM-014 ceiling (100 MB in
  `configs/repo.yaml`); above that, external archive + `raw/MANIFEST.sha256`

Integrity:
- `raw/` is **write-once**. Never edit a committed file under `analysis/`;
  add a new file instead (AF-001 remains the documented exception).
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

As of 2026-10-15. Plan of record: docs/EXPERIMENT_REGISTRY.md. Read it at
session start; update it in the same commit as the work. Never delete a row.

- 2026-10-15 (Task AQ): thesis docs/THESIS.md; papers and evidence map
  docs/PAPER_*_ABSTRACT.md, docs/PAPER_EVIDENCE_MAP.md; literature sweep
  docs/literature/2026-10-15/ (wording rules in docs/RELATED_SEARCHES.md).
  ISPASS flags: 9,750 is HELD (cite 10,000 c2246b1f); the ~46,000 combined
  limit and the C2 23-25x headline are MEASURED (Zach), data location/run_id pending; not yet in this repo
  (corrected 2026-10-16, Task AS: measured by us, not Rithwik side); check
  the baseline against 10,000; SEM-IMPL is built but has no sealed run here,
  RET-0/RET-1 are blocked here; "Arrow Lake" vs our Panther Lake.
- Open before DEMO-2 rehearsals: KV-DEFAULT-READBACK (2026.2.1 source:
  the default compiles i8 on a PA model, not u4 - corrected 2026-10-16;
  confirm on both hosts, tools/kv_compiled_readback.ps1) and the PREFIX-CACHE-AUDIT
  control decision (NON_RESIDENT passes a bare SchedulerConfig: prefix
  caching off and struct-default batch tokens, not the runtime default).
  Draft addendum in _agent_reports/drafts/ (not committed).
- XPS queue: pin restore, back up be91e69d, DEMO-2 2-entry rehearsals,
  D-X, T-X, H1-CPU (draft amendment 3 first), P1 B=20 A0, rest.
- Sealed $0 analyses: analysis/aq_20261015/ (silent failures 122/141
  non-escalated under emission in d482c621; DEMO-1 spend 100% step-0 TTFT;
  no router beats matched-rate random escalation on BASE_30).

- Key sealed results: placement 21.4x (GPU 10000 vs CPU 468 tokens;
  c2246b1f, 7f232f86); resident-session limits f16/u8/u4 = 15000/20000/
  26500 (553b3a5c, cf3555d5, e4a22dac); warm turn-2 at 12k f16 0.639 s vs
  u8 1.003 s vs u4 0.946 s (72776603, 1587d2f4, dd2b0779); int8 decodes
  ~30-34% slower than int4 (180dfbb9); P0-v2 exchange rate ac4e5472
  (warm TTA GPU 2.47/3.26 s, CPU 9.29/11.17 s at 4k/6k).
- DEMO-1 (prereg v2, scored, analysis/demo1/):
  - XPS V1 f7343708: MATCH x3.
  - XPS V2 CPU 1acc8c58: local 0.0 and 30 escalations MATCH, $/task 0.297
    MISS (band 0.320-0.347); 22/30 hybrid passes vs V1's 3/30
    (descriptive).
  - XPS V3 (71d33f7a + ab88f47f, one cell): MISS x3 (local 0.673, $0.308/task,
    9 escalations). All v2 V cells are done.
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
  - Citable limits (all post-reboot): 1024 -> 960 (faa14a31),
    2048 -> 1984 (9acabbf7, 2ffbd61c), 4096 -> 4032 TOOLCHAIN_CAP
    (2972e8c4). P-INT8-d (decode < 1.0 tok/s) misses at every post-reboot
    setting (1.03-1.08).
  - Guarded NPU sessions run under amendment 2026-10-14b (canary cell in a
    child process). Reading rule: 2048 C-confirmed, 4096 inconclusive
    (child +3.3%); in-process dip recurred in both. Transition record off.
  - 8192: REFUSED twice, drift question unanswered. 3b36e9e4: t1 drift.
    c759d72f: canary CL_OUT_OF_RESOURCES (OTHER), then a teardown crash
    0xC0000409. 16384 load-only done (8850e64a).
  - NPU timings are about 2x faster after the 2026-10-14 reboot; split
    every NPU timing comparison pre/post reboot.
  - Canary diagnosis: analysis/canary/CANARY_DRIFT_20261014.md.
- P1 budget-quality:
  - Sealed A0 8a529053: 23/200 in budget.
  - Sweep B=10 (CROSSING_B10_20261014.json): A0 bdc32a87 14 vs A4
    a766bd0b + 78dbf4c3 13. No crossing; floor and close fraction MISS.
  - Next: B=20, per amendment 9.
- T2S window 1 ended 2026-10-14; window 2 requested Oct 19-25 (Windows
  Update pause pending Rithwik; Tailscale unattended likely works, needs his
  confirmation before any deliberate reboot; Dr. Hao meeting Oct 29). The T2S runs
  with the UNCOLD_UPTIME deviation (no reboot before sessions). Windows
  Update rebooted it at 08:29 AM ET 2026-10-14 (event 1074, MoUsoCoreWorker
  then TrustedInstaller, Upgrade (Planned)); same pattern 2026-09-21. ssh
  came back with no user logged in (tailscaled runs as a service at boot).
- DEMO-1 cloud spend total: about $17.92 (V4 XPS $2.77, V3 T2S $1.44,
  V4 T2S rerun $0.19, V2 XPS $8.90, V3 XPS $4.62, pings).
- Knob-vs-upgrade table: analysis/demo1/KNOB_VS_UPGRADE_20261014b.json
  (placement, upgrade, retention rows).
- DEMO-2: prereg registered (derived/h1_hybrid/demo2/DEMO2_PREREG_v1.json);
  not run; host rehearsals next.
