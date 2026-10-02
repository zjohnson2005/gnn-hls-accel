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

## Two workspaces, one origin

Work happens in two places: Cursor on the XPS repo (when the XPS is
reachable) and Claude Code in this Mac clone (when it is not, or to spread
usage). Both push to the same origin. To avoid divergence:

- Start every session with `git pull --ff-only`; end it with commit + push.
- Never have both workspaces editing at the same time. Before handing off,
  push and say which commit is current.
- If a pull is not fast-forward, stop and report; never force-push and
  never resolve by discarding the other workspace's commits.
- Cursor on the XPS must never be open during an XPS measurement.

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

## Current state (keep this section updated)

- Key sealed results: placement 21.4x (GPU 10000 vs CPU 468 tokens;
  c2246b1f, 7f232f86); resident-session limits f16/u8/u4 = 15000/20000/
  26500 (553b3a5c, cf3555d5, e4a22dac); warm turn-2 at 12k f16 0.639 s vs
  u8 1.003 s vs u4 0.946 s (72776603, 1587d2f4, dd2b0779); int8 decodes
  ~30-34% slower than int4 (180dfbb9); P0-v2 exchange rate ac4e5472
  (warm TTA GPU 2.47/3.26 s, CPU 9.29/11.17 s at 4k/6k).
- P1 budget-quality (amendments 1-7 on record): A0 8a529053 = 23/200
  in budget. A1-unbounded 385cd4f6 = no gain. A4-as-implemented 3b4d8207
  = 2/100 (no greedy fallback; greedy thinking). Next: A4 fix
  (greedy-first + sampled thinking) + budget sweep B = 10/20/30 s; A5
  feedback-retry; A2, A3, bounded A1.
- T2S window: Fri Oct 2 1 am ET to Tue Oct 6; back to Rithwik Wed.
