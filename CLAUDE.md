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
Deadlines (Task BJ, 2026-10-23; registry section 7): data freeze Sun Nov 22, draft to Dr. Hao
about Dec 1, ISPASS 2027 submission-ready Dec 11 (CFP not posted). Paper plan of record: registry
section 0 ("Not the KV Cache: Memory Tiers Set the Context Ceiling of LLM Agents on Consumer AI PCs").

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
10. PLAN LOCK (2026-10-23, docs/PLAN_LOCK_2026-10-23.md): no new cells, arms, predictions,
   thresholds, title or thesis changes. Only red flags R1-R10 trigger re-evaluation: on one, park the
   current cell safely, change nothing, report it FIRST under "RED FLAG" with run_ids; Zach decides.
   Every closeout report starts with R1-R10 as PASS / RED FLAG / NOT YET MEASURED. Accuracy-only
   wording fixes are allowed and logged in AUDIT_LOG.md.

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
  theoretical (LITERATURE). Our unit per WMI 2026-10-16: 8 x 2 GiB,
  configured 7467 MT/s (rated 9600; record d67beb19); bandwidth unmeasured
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

As of 2026-10-23 (Task BN, PLAN LOCK). Plan of record: docs/EXPERIMENT_REGISTRY.md. Read it at
session start; update it in the same commit as the work. Never delete a row.

- 2026-10-15 (Task AQ): thesis docs/THESIS.md; papers and evidence map
  docs/PAPER_*_ABSTRACT.md, docs/PAPER_EVIDENCE_MAP.md; literature sweep
  docs/literature/2026-10-15/ (wording rules in docs/RELATED_SEARCHES.md).
  ISPASS flags: 9,750 is HELD (cite 10,000 c2246b1f); the ~46,000 combined
  limit and the C2 23-25x headline are MEASURED (Zach), data location/run_id pending; not yet in this repo
  (corrected 2026-10-16, Task AS: measured by us, not Rithwik side); check
  the baseline against 10,000; SEM-IMPL is built but has no sealed run here,
  RET-0/RET-1 are blocked here; "Arrow Lake" vs our Panther Lake.
- 2026-10-16 (Task AS): DEMO-2 redesigned before any run against the true
  runtime default (docs/amendments/DEMO2_AMEND_2026-10-16_TRUE_DEFAULT.md):
  arms A true default (primary control; invalid if SDPA fallback or KV not
  i8), B device-only tuned, C full tuned, D ecosystem 4096 (XPS only);
  material-win threshold and pivot rule into the registered SEARCH phase
  (DEMO2_SEARCH_PHASE_2026-10-16.md); second pin DEMO2_HELDOUT_60_B
  (long_context half; base half by rule R1, below) for one
  confirmation run. APPROVED by Zach 2026-10-16 (APPROVALS_2026-10-16.md):
  amendment, SEARCH, pilots; ceiling $275; P7 spend approved, P5 not yet;
  R1 base half, full pin DEMO2_HELDOUT_60_B sha256 9dfa9280 (reserved).
  Pilots P0-P9 registered (DEMO2_PILOTS_2026-10-16.md),
  harness built, all flags default off; nothing run. Tuned values come
  from the pilots via an arm-spec addendum before any held-out run.
- KV default on 2026.2.1 is i8 by source (not u4), NOT YET MEASURED on the
  hosts: pilot P0 (tools/kv_compiled_readback.ps1 -Mode all). The
  2026-10-15 9:22 PM ET P0 attempt timed out on both hosts.
- Task AT 2026-10-16: XPS pin restored, be91e69d backed up, P9 read-only
  done (d67beb19). P0 and later pilots NOT RUN: XPS had Chrome, Edge and
  Claude desktop open (STOP rule). T2S pin is the CRLF 8b0844ef form.
- XPS window 2026-10-19 (Task AW, all $0, no -CacheDir):
  - P0b PASSED (640ec474): arm A valid on the XPS.
  - P9 drift +1.52% (687bbb9f): no warm-up rule.
  - P6/P1 BASE_30 (39c1c131): local pass 3/30, the same 3 entries as DEMO-1 V1.
  - P1: lever exists (65% non-tool-call). Median 91 generated tokens per
    turn, not 130-255.
  - LONGCTX_30 841b84e4 hung after 14/30. It stopped after the load for
    entry 123, with the GPU idle and about 0.8 cores busy, not paging. It is
    recorded UNSEALED in derived/demo2_pilots/hung_841b84e4/. The cause is
    not identified; the native generate is the one unbounded call.
  - Per-turn watchdog built (-TurnWatchdogS, default off).
  - -CacheDir breaks arm A (3a03221e: compiled KV 'dynamic'); do not use it.
  - Next: P8-u4, then arm A LONGCTX entries 15-30 with the watchdog
    (py-spy 0.4.2 standalone, approved). Then P3, with an added
    true-default resident-limit cell first, then P4 (run_window_20261020.sh;
    Task AX).
  - cf3555d5's 20,000 is a plain-LLMPipeline (latency scheduler) limit, not
    a bare-SchedulerConfig one. The DERIVED effect of a higher A limit is in
    docs/amendments/DRAFT_DEMO2_ARM_SPEC_ADDENDUM.md (pending Zach).
- XPS window 2026-10-20 (Task AY, $0):
  - P8-u4 sealed: BASE_30 1f3a261a, LONGCTX 1-14 162a9b5c.
  - Arm A LONGCTX 15-30 24c1abc0 hung again at entry 123 turn 0, this time
    from a fresh worker. The watchdog stopped it at 1,800 s; it is recorded
    UNSEALED in derived/demo2_pilots/hung_24c1abc0/.
  - py-spy: the stall is an OpenCL enqueue waiting on a GPU sync object,
    with no error. Regime: "silent device stall"
    (analysis/demo2_pilots/AY/GPU_HANG_ENTRY123.md).
  - P8 so far: u4 23/44 silent vs i8 22/44 (keep_u4 false, not final).
  - Harness additions, all default off:
    - run_h1_hybrid --skip-entries/--skip-hang-record (a hung entry counts
      as a local fail);
    - --sched-exploratory/--sched-dynamic-split-fuse (P10 only);
    - run_decode_match --uncold-uptime-deviation (T2S).
  - Added pilot P10-HANG123 (registered; entry-123 isolation matrix).
  - Next: window 2 (run_window_w2.sh), window 3 (run_window_w3.sh), then
    P3_FROM=1 and P4.
  - T2S block: run_window_t2s.sh.
- 2026-10-20 windows 2-3 and T2S block (Task AZ, $0; analysis/demo2_pilots/AZ/):
  - P3 cell 0 a5d19dcc: true-default XPS resident limit 18,000 (first fail 18,500).
  - P6 complete: NO_CHANGE (0 of 60 in the band). Arm A valid on the T2S
    (P0a record 5e190568, P0b 03632ad3).
  - T2S: P8 keep_u4 false (27/59 vs 26/59); P4 no prompt lookup (not
    byte-identical); P9 no warm-up; P2 model holds, u4 gain 1.08.
  - Entry 123 "stalled 4 of 4 times on 2 devices" (+ 027a07b7 P10 C1, bbdd1c0d
    T2S): overstated, corrected in Task BB. P11-HANG-REGIME registered, not approved;
    --step-log and tools/repro_hang123.py built.
  - Config audit: derived/audit/CONFIG_PROVENANCE.md. The cited limits are
    plain pipeline + KV property; DEMO-1 is REPLACED_SCHEDULER; the XPS driver
    went 8622 -> 8724 -> 8860.
  - "Hybrid studies inherit Ollama's default" withdrawn
    (docs/literature/2026-10-20/).
- 2026-10-21 (Task BA): the XPS is off AC (unavailable); window 3's resume
  stopped (XPS not back within 45 min). T2S-only hang window ready:
  ~/seam_closeout_1013/xps/run_window_t2s_hang.sh (P11 + added P10-T2S,
  registered docs/amendments/DEMO2_PILOT_P10_T2S_2026-10-21.md and
  DEMO2_PILOT_P11_VARIANTS_2026-10-21.md; stop by 10:00 PM ET Oct 25).
  Arm D label decided (DRAFT addendum section 5). Zach pushed the AZ and BA
  commits (origin 9d67c18) before the 2026-10-21 T2S window.
- 2026-10-21 (Task BB, analysis/demo2_pilots/BB/): T2S window 12:09 PM ET: L1 9b4cdefb completed;
  L2 8af10211 turn 0 step 1 = 87,392 tokens on the model's own path, steps still progressing when the
  600 s per-turn watchdog fired. Entry-123 "4 of 4 stalls" withdrawn: 841b84e4 STALL, 24c1abc0 /
  027a07b7 / bbdd1c0d UNKNOWN, 8af10211 over budget while progressing. 43 local generates above
  Qwen3-4B's 40,960 positions (8 runs); GenAI enforces no limit by default; "context held" is not
  valid above 40,960. Stall watchdog (--stall-watchdog-s) built. P11-B registered; T2S script
  run_window_t2s_hang.sh now runs P11-B; X0-XPS queued (run_window_xps_x0.sh).
- 2026-10-21 (Task BC, analysis/demo2_pilots/BC/): P11-B T2S: entry 123 is a context-overrun loop
  (X0 cddcd9fd 21 steps to 98,165 tokens, 26 min, no stall; random tokens loop above 65k, not at <= 40,960);
  a 40,960 cap converts it (e66a2a89). Repo facts: hybrid Qwen3-4B; thinking off by template; IR rt_info
  AWQ True / scale_estimation False (card says True); max_new_tokens 512 everywhere; a5d19dcc 18,500 =
  OpenCL event error in turn 2. Registered before any held-out run: revised arms
  (docs/amendments/DEMO2_ARMS_REVISED_2026-10-21.md; predictions: revised C not a material $ win vs A on
  either host) and per-device profiles + T2S ladder R0-R6 (DEMO2_PER_DEVICE_2026-10-21.md). L1 ran: K 1,024
  h70t30. Harness: --retention-k/-shape/-age-mask/-cloud-raw, demo2_ladder_l1/l4, pins DEMO2_CONFIRM_200 /
  DEMO2_GROWTH_10. Scripts run_window_t2s_ladder.sh / run_window_xps_ladder.sh. XPS X0 d0dd5a37 pending.
- 2026-10-21 (Task BE, approved 9:45 PM ET): DEMO-2 primary = $ at iso-quality by offline replay
  (docs/amendments/DEMO2_ISO_QUALITY_2026-10-21.md; tools/demo2_iso_quality_replay.py): local-only passive
  logs per arm vs ONE shared cloud-only log. Arm A resident; shared corrections in every arm (resident
  pipeline + tool-set warm-up, caching ephemeral, cloud retention K 1,024). Arm P device-provisioned
  (XPS 8B INT4, P' 4B INT8 by rule; T2S 8B INT8). Calibration pin DEMO2_CALIB_30. Freeze Fri Oct 23 noon
  (TASK_BF_PROMPT.md). Scripts download_models_{xps,t2s}.sh, run_queue_{t2s,xps}_be.sh;
  schedule docs/DEMO2_SPRINT_2026-10-22.md.
- 2026-10-22 (Task BF0 part A, approved ~1:15 PM ET): pre-freeze rules
  docs/amendments/DEMO2_PREFREEZE_2026-10-22.md: cache-aware cloud price (refuse missing cache
  fields); ONLY confirmatory test = P vs A dC_iso, T2S then XPS; everything else secondary; -inf
  draws kept; P' rule (pass / decode p5 / TTFT vs cal_a1); hang at its turn; splice primary +
  re-run / cold-handoff sensitivities; analytic frontier; held-out cloud cap rule; Sunday rule;
  freeze Fri Oct 23 12:00 PM ET hard ceiling. Predictions DEMO2_BF0_PREDICTIONS.json.
  Part B: cache-aware CostGuard + replay repricing; replay per PF (analytic frontier, `family`);
  runner --rebuild-on-error, DEMO2_HELDOUT_60 refused without --heldout-after-freeze; queue scripts
  ~/seam_closeout_1013/xps/run_queue_{t2s,xps}_be_v2.sh + park_untracked_v2.ps1 (v1 unchanged).
- 2026-10-22 ~8 PM ET (Task BF): DEMO-2 FROZEN, docs/amendments/DEMO2_FREEZE_2026-10-23.md (freeze head =
  its commit). T2S B 16,384 (R1 5a6583aa); XPS 8,192 (dd2ecf51). P' selected on the XPS (PF 6 (a): cal_p
  f511af02 3 vs cal_a1 7cf9b18d 4 local passes) -> PSPEC Qwen3-4B-int8-ov.yaml. A/A 0/30 discordant on both
  hosts, d_usd 0.0, d_lat 0.0045 T2S / 0.0471 XPS. cal_cloud a403befe $2.45 -> held-out cap $20. Replay
  scorer bug (BFCL checker name reuse) fixed in 24f9ed9 before any value. Records
  derived/demo2_pilots/windows_20261022/. Next: Zach pushes, then held-out on both hosts (FROM=30).
- 2026-10-22 ~10:30 PM ET (Task BH, approved "ok register everything new"; APPROVALS_2026-10-23.md):
  no held-out record exists. DEMO-2 amendment docs/amendments/DEMO2_AMEND_2026-10-23_OBJECTIVES.md:
  P/C vs I-4K equal on both hosts is NOT a bug (I-4K reference has no host input; BF0 unchanged);
  F2 non-dollar family (silent overrun [by construction, outside Holm], wall per entry,
  time-to-failure, hang/loop) x (A vs P, A vs C), m = 6 per host, Holm, NOT gated on the $ primary;
  tools/demo2_f2_objectives.py; predictions DEMO2_BH_F2_PREDICTIONS.json (P slower than A on both
  hosts; C faster on the XPS only). Separate experiment CTXKV-E1E2 registered
  (docs/registrations/CTXKV_E1E2_2026-10-23.md, derived/ctxkv/): E1 context default by memory tier,
  E2 KV precision / flash attention; AMD/T2S arms pending Rithwik; 200-task pin PENDING; E1 cloud cap
  $20 not yet approved. Held-out EXPECT_HEAD = the last BH commit (freeze note still in tree).
- 2026-10-23 (Task BJ; priority override ~10:45 AM ET: Tue Oct 27 meeting needs the new headline measured):
  - Part A: docs/amendments/DEMO2_AMEND_2026-10-23b_PPRIME.md, XPS P' rows (P' vs R-full / I-4K / C,
    each 1.5% DERIVED; DEMO2_BJ_PPRIME_PREDICTIONS.json). Guard re-checked: no held-out record.
    Held-out EXPECT_HEAD = 72e499f. Schedule: the T2S held-out runs first; the XPS held-out is
    deferred until after Oct 27 (fixed sequence T2S -> XPS unchanged).
  - Registry rebuilt (sections 0-8: plan of record, machine windows, F1-F10 map, tracks, drops with
    reasons, timeline to the Nov 22 freeze). Every old row was kept verbatim.
  - CC registration docs/registrations/CC_CONTEXT_CEILING_2026-10-23.md, predictions
    derived/cc/CC_PREDICTIONS.json.
    - CC-PRECHECK: the sealed XPS limits read back the requested KV and failed in the uncapped turn-1
      prefill (turn 2 = 183 tokens). So F1 wording is "non-KV term in the uncapped prefill" until
      CC-MECH reports. T2S limits are TTFT-bound, not memory.
    - Runner options (default off): run_resident_limit --cc-cell / --points / --gpu-mem-stats /
      --compiled-readback; memory sidecar tools/cc_mem_sidecar.ps1.
    - Queues: ~/seam_closeout_1013/xps/run_queue_{t2s,xps}_cc.sh. The T2S queue waits for the
      held-out queue. CC-CLIFF-T2S is blocked.
  - Monday prompt: ~/seam_closeout_1013/papers_20261015/TASK_BK_MEETING27.md.
  - CC-XRT-T2S and E2-T2S are CONDITIONAL on Rithwik's written OK.
- 2026-10-23 ~11:50 AM ET (Task BL, before any CC launch): amendment
  docs/registrations/CC_AMEND_2026-10-23b.md (A1-A18), predictions derived/cc/CC_BL_PREDICTIONS.json.
  - MIXED 64*T is retired for the sealed limits. H-act (a = 96,768 B per token) vs H-quad is decided
    by f16 / u4 at c256 and c1024. The primary 63,319 and the gate >= 40,000 are unchanged.
  - Grid to 110,000 at 1,000; child timeout 3,600 s; censored timeouts; every row L_mem / L_valid;
    10 Hz in-child trace.
  - New cells:
    - T2S: CC-CONC (i)-(iv), CC-WINDOW, A14 read-only record first;
    - XPS: CC-TTFT, CC-GROW, CC-VALID (Qwen3-4B-Instruct-2507 INT4, Mac export, spec pin pending);
    - CONDITIONAL: CC-RT, A15 slider (Rithwik), A16, A18.
  - Queues ~/seam_closeout_1013/xps/run_queue_{t2s,xps}_cc_v2.sh. The BJ CC scripts are superseded.
  - Corrections:
    - cf3555d5 compiled i8;
    - the NPU caps ran on the T2S;
    - 44,742 = 83127e1b, unsealed.
- 2026-10-23 ~12:25 PM ET (Task BM, before any CC launch): amendment
  docs/registrations/CC_AMEND_2026-10-23c.md (A19-A36, Context Roofline validation cells),
  predictions derived/cc/CC_BM_PREDICTIONS.json.
  - Held-out tests of the fitted law:
    - A20 allocator-measured a (93-98 KB/token);
    - A21 8-bit (i8) rebisect, 20,921-21,486;
    - A22 / A29 GPU-shared and CPU balloons;
    - A23 grow at 1K / 2K / 4K;
    - A24 TTFT law;
    - A25 XPS slider (Zach);
    - A33 cache_size test.
  - Logging: A19 DXGI budget record and in-child trace; A31 rejects compiled != requested KV;
    A32 failure taxonomy.
  - Source read (genai 2026.2.1.0): the budget assertion runs only with an explicit cache_size,
    so it does not explain the sealed limits.
  - Queues ~/seam_closeout_1013/xps/run_queue_{t2s,xps}_cc_v3.sh (the v2 scripts are superseded).
  - Not scripted: A26 battery pass and A27 (gates need AC); A28; A15/A16/A35 and A30-active on the
    T2S (Rithwik).
- 2026-10-23 ~12:35 PM ET (Task BN): PLAN LOCK, docs/PLAN_LOCK_2026-10-23.md.
  - Title: "Beyond the KV Cache: A Context Roofline for LLM Agents on Consumer AI PCs".
  - Thesis, experiment set, schedule and red flags R1-R10 are locked (rule 10).
- 2026-10-23 afternoon (Task BO, parallel Mac work, local commits only):
  - Second model Qwen3-8B registered (CC_AMEND_2026-10-23d_MODEL2.md; predictions CC_M2_PREDICTIONS.json;
    queue run_queue_xps_m2.sh after the v3 queue). The PLAN_LOCK addendum adds it.
  - Nov 6 gate wording reconciled; FLEET-FRONTIER registered (TraceLab pinned, results after Nov 6).
  - Tools: tools/figs/fig1-7, tools/redflags.py, tools/queue_status.py.
  - T2S A19 record: R6 PASS (48,634 = 65,018 - 16,384 MiB); the OpenCL device total is 33.6 GiB.
  - Retro: the sealed 8B points sit 22-26% under the law (analysis/cc/retro_8b.md).
- 2026-10-23 ~4:25-4:45 PM ET (Task BP): canary-arming fix docs/amendments/CC_FIX_2026-10-23e_CANARY.md
  (CC series and one-point cells calibrate before the first probe); grow + balloon rows re-queued in
  run_queue_xps_cc_v3b.sh. R1 RED FLAG (8-bit 19,750 < 19,900; window B shift shared with u4), R6 PASS
  (XPS Intel override 57%), balloon cells refused by the 7,000 MB floor (Zach decides);
  analysis/cc/bp_xps_first_data_20261023.md. DEMO-2 T2S resume note DEMO2_RESUME_2026-10-23c_T2S_HELDOUT.md.
- 2026-10-23 ~5:10-5:30 PM ET (Task BQ): R1 "Keep going" (logged in PLAN_LOCK red-flag log); balloon-gate
  option (a) approved and built (--balloon-floor-credit, CC-BAL only, docs/amendments/CC_BALLOON_GATE_2026-10-23f.md);
  v3b runs balloon rows last with BALLOONS=1. u4 L* unchanged by a 1 GiB balloon (d6616dfd vs 598e882d).
- Spend: DEMO-2 ceiling $275 (raised 2026-10-16 from $150; arms $108.35 /
  $216.70 at 1 / 2 replicates + pilot caps $54.81). P7 approved (caps
  $27.54); P5 needs a separate OK after P7.
- XPS queue (registry section 7): pin restore, back up be91e69d, P0 both
  hosts, remaining pilots, arm spec, DEMO-2 rehearsals, held-out cells,
  H1-CPU (amendment 3 awaiting approval), P1 B=20 A0, rest. T2S block
  Oct 19-25 pending Rithwik. Oct 26 showing: arms D and A, SEARCH plan next.
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
- DEMO-2: prereg registered (derived/h1_hybrid/demo2/DEMO2_PREREG_v1.json),
  amended 2026-10-16 (true default); not run; pilot P0 next.
