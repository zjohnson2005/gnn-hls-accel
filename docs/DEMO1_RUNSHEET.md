# DEMO-1 v2 run sheet (and H1-CPU amendment 2 boots)

Governing files (the runner reads none of them):
- derived/h1_hybrid/demo1/DEMO_PREREG_v2.json, sha256
  7317baab93330a7f3c0987f4fc80878779107d6f620dba0a2b7d2cfe6271c4ac
- derived/h1_hybrid/H1_CPU_AMEND_2.json
- docs/DEMO1_DESIGN.md

Every launch needs Zach's OK. Every XPS launch also needs a reboot first,
which also needs Zach's OK. Spend caps come from the prereg. The $55 reserve
needs Zach.

## Hosts
- XPS (aipc-c1): `ssh zjohn@100.101.81.6`, repo `C:\Users\zjohn\Projects\gnn-hls-accel`.
  - Before each XPS cell: reboot, wait about 3 min, then launch. The uptime
    gate is 7200 s.
  - Nothing else may run: no Chrome, Edge, Cursor or Code.
- EVO-T2S (evo-t2): `ssh zach@100.72.40.24`, repo `C:\Users\zach\Projects\gnn-hls-accel`.
  - No reboot. `-T2S` skips only the uptime gate (recorded as UNCOLD_UPTIME).
  - Rithwik's watchdog must be idle.
- launch_h1.ps1 runs these in the foreground: gates (including tier-1),
  the canary opening and a lifecycle smoke. It then spawns the worker
  detached and exits.

## Preflight (booleans and versions only; run before each host session)
XPS:
```
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; git log --oneline -1; "api_key_user=" + [bool][Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY","User"); "api_key_machine=" + [bool][Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY","Machine"); "api_key_session=" + [bool]$env:ANTHROPIC_API_KEY; .\.venv-seam\Scripts\python.exe -m pip show anthropic transformers bfcl-eval openvino-genai | Select-String "^(Name|Version):"; .\.venv-seam\Scripts\python.exe -c "import anthropic, transformers, bfcl_eval; print(1)"; "ir_4b=" + (Test-Path models\Qwen3-4B-int4-ov\openvino_model.bin); "pins=" + (Test-Path derived\h1_hybrid\demo1\DEMO1_PAIRED_15.json)'
```
T2S (also checks the watchdog and the 4B IR on that host):
```
ssh zach@100.72.40.24 'cd C:\Users\zach\Projects\gnn-hls-accel; git pull --ff-only; git log --oneline -1; "api_key_user=" + [bool][Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY","User"); "api_key_machine=" + [bool][Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY","Machine"); "api_key_session=" + [bool]$env:ANTHROPIC_API_KEY; .\.venv-seam\Scripts\python.exe -m pip show anthropic transformers bfcl-eval openvino-genai | Select-String "^(Name|Version):"; .\.venv-seam\Scripts\python.exe -c "import anthropic, transformers, bfcl_eval; print(1)"; "ir_4b=" + (Test-Path models\Qwen3-4B-int4-ov\openvino_model.bin); .\.venv-seam\Scripts\python.exe tools\t2s_queue_watchdog.py launch-check --log C:\apu\ovn\watchdog.log --running-json "[]"'
```
What to expect:
- At least one api_key_* is True. The detached worker needs the User or
  Machine variable, because a WMI child does not inherit the ssh session.
- The import line prints 1, ir_4b=True, and the watchdog prints
  watchdog_launch_ok.

## Cells (prereg run order: V1, V2, V4, V3)
Estimated wall time includes about 600 s of launch overhead (gates, canary,
smoke). The estimate uses the sealed cold-prefill curves at each turn's gold
n_ctx, plus 3.5-9 s of decode per step and 6.5 s per cloud turn
(d482c621). It is an estimate, not a registered value.

Common flags for every DEMO-1 cell: `-Policy slo_escalate -Residency NON_RESIDENT -Entries <pin>`.
`-MaxUsd` is the per-config cap from the prereg. These are single-policy
runs, so `-SessionMaxUsd` does not apply.

| # | cell | host | extra flags | -MaxUsd | estimate (s) | fits 7200 s |
|---|---|---|---|---|---|---|
| 1 | V1 | XPS GPU | | 5 | 2,205 | yes |
| 2 | V1 | T2S 4B | -T2S | 5 | 1,720 | yes |
| 3 | V2 | XPS CPU | -Placement cpu-p | 15 | 5,140 | yes |
| 4 | V4 | XPS GPU | -ObsMaskK 1024 | 20 | 2,016 | yes |
| 5 | V4 | T2S 4B | -T2S -ObsMaskK 1024 | 10 | 1,560 | yes |
| 6a | V3 | XPS GPU | -EntryOffset 0 -EntryCount 8 | 24 | 4,038 | yes |
| 6b | V3 | XPS GPU | -EntryOffset 8 -EntryCount 7 | 21 | 3,690 | yes |
| 7 | V3 | T2S 4B | -T2S | 45 | 2,689 | yes |

V3 XPS is chunked. As one launch it is about 7,128 s (0.99 window), because
each entry pays one cold local attempt at about 34k tokens; 2b3316b6
measured 94.6 s at 32k. The two chunk caps add to the prereg's $45, split by
entry count.

Launch commands (dry run: the same command plus ` -DryRun`. That runs the
gates report-only and the logic-only canary, and spawns nothing):
```
# 1 V1 XPS GPU (after reboot)
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Policy slo_escalate -Residency NON_RESIDENT -Entries derived\h1_hybrid\demo1\DEMO1_BASE_30.json -MaxUsd 5'
# 2 V1 T2S 4B
ssh zach@100.72.40.24 'cd C:\Users\zach\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -T2S -Policy slo_escalate -Residency NON_RESIDENT -Entries derived\h1_hybrid\demo1\DEMO1_BASE_30.json -MaxUsd 5'
# 3 V2 XPS CPU (after reboot)
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Policy slo_escalate -Placement cpu-p -Residency NON_RESIDENT -Entries derived\h1_hybrid\demo1\DEMO1_BASE_30.json -MaxUsd 15'
# 4 V4 XPS GPU (after reboot)
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Policy slo_escalate -Residency NON_RESIDENT -ObsMaskK 1024 -Entries derived\h1_hybrid\demo1\DEMO1_PAIRED_15.json -MaxUsd 20'
# 5 V4 T2S 4B
ssh zach@100.72.40.24 'cd C:\Users\zach\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -T2S -Policy slo_escalate -Residency NON_RESIDENT -ObsMaskK 1024 -Entries derived\h1_hybrid\demo1\DEMO1_PAIRED_15.json -MaxUsd 10'
# 6a V3 XPS GPU, chunk 1 (after reboot)
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Policy slo_escalate -Residency NON_RESIDENT -Entries derived\h1_hybrid\demo1\DEMO1_PAIRED_15.json -EntryOffset 0 -EntryCount 8 -MaxUsd 24'
# 6b V3 XPS GPU, chunk 2 (after reboot)
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Policy slo_escalate -Residency NON_RESIDENT -Entries derived\h1_hybrid\demo1\DEMO1_PAIRED_15.json -EntryOffset 8 -EntryCount 7 -MaxUsd 21'
# 7 V3 T2S 4B
ssh zach@100.72.40.24 'cd C:\Users\zach\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -T2S -Policy slo_escalate -Residency NON_RESIDENT -Entries derived\h1_hybrid\demo1\DEMO1_PAIRED_15.json -MaxUsd 45'
```
Where to look and what to look for:
- launch_h1 prints `session_id (run_id)`, `artifact_dir` and `launch_log`.
- Log: `derived\h1_hybrid\_launches\h1_slo_escalate_<yyyyMMdd_HHmmss>.log`.
- Artifact: `derived\h1_hybrid\slo_escalate_<run_id>\` (plan.json, summary.json,
  turn_ledger.json, entry_quality.json, obs_mask_ledger.json for V4, .sealed).
- Launch evidence (since 2026-10-13): `derived\h1_hybrid\_launches\<run_id>\`
  holds the gate JSON (`gates_<stamp>.json`) and the opening canary
  (`canary_opening\opening_plan.json`, `canary_opening\canaries\`). It is
  gitignored, so the worker's clean-tree check passes. The worker records each
  file's path, size and sha256 in plan.json `git.launch_evidence`. The shared
  `derived\h1_hybrid\_canary_opening\` (d482c621) and `derived\_gate_probes\`
  are no longer written by a live launch_h1.
- Cloud ping (since 2026-10-13): before the spawn, launch_h1 sends one
  max_tokens 8 request through the worker's own client and model id
  (tools/cloud_ping.py) and refuses the spawn if it fails. The record is
  `_launches\<run_id>\cloud_ping.json` (model, SDK and python versions, HTTP
  status, error class, latency, cost; no key). -DryRun pings too unless
  -NoCloudPing.
- On a dead cloud turn or a cloud-dead abort the artifact also holds
  `cloud_dead_events.json`: the guard events and each request's ok, error
  (redacted), error class, HTTP status, request id, model, tokens and
  latency. It is inside the sealed tree.
- In-worker ping (since 2026-10-13): the detached worker repeats the same ping
  from its own process before the first entry and writes
  `cloud_ping_worker.json` into the artifact (sealed); plan.json
  `cloud_ping_worker` says it ran and passed. If it fails, the run ends with
  status `refused_cloud_ping`, no entry runs, $0, and the dir is sealed as a
  record. Skipped when no selected policy reaches the cloud (local_only).
- Done when the log ends with the runner's JSON block `{"ok": true, "summary": ...}`
  containing `"status": "complete"`, and the artifact has `.sealed`.
- Poll:
  `ssh <host> 'Get-Content -Tail 20 <repo>\derived\h1_hybrid\_launches\h1_slo_escalate_<stamp>.log'`.
  Do not touch the host until it is complete.

## V5 cells (DEMO-1 amendment 2026-10-13c; XPS, each after a cold reboot)
Caps $15 each come from the $55 reserve: need Zach's written OK first.
Predictions: analysis/demo1/V5_PREDICTIONS.json (all 15 entries indeterminate
from sealed data; upper bound: 15/15 escalate, local share 0.164).
```
# V5a RESIDENT u8
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Policy slo_escalate -Residency RESIDENT -Kv u8 -ObsMaskK 1024 -Entries derived\h1_hybrid\demo1\DEMO1_PAIRED_15.json -MaxUsd 15'
# V5b RESIDENT u4
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Policy slo_escalate -Residency RESIDENT -Kv u4 -ObsMaskK 1024 -Entries derived\h1_hybrid\demo1\DEMO1_PAIRED_15.json -MaxUsd 15'
```
Dry runs: append -DryRun (one cloud ping under $0.001 unless -NoCloudPing).
Log `h1_slo_escalate_<stamp>.log`; artifact `slo_escalate_<run_id>\`; plan.json
arm_config.kv must read u8 / u4.

## H1-CPU amendment 2 boots (XPS, all after a reboot; RESIDENT as registered)
```
# boot 1
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Policy slo_escalate -Placement cpu-p -EntryOffset 0 -EntryCount 67 -MaxUsd 21.25'
# boot 2
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Policy slo_escalate -Placement cpu-p -EntryOffset 67 -EntryCount 67 -MaxUsd 24.8'
# boot 3
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Policy slo_escalate -Placement cpu-p -EntryOffset 134 -EntryCount 66 -MaxUsd 25.98'
# boot 4
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Interleaved -InterleavedPolicies emission_escalate,full_signal_bounceback,local_only -Placement cpu-p -Entries derived\h1_hybrid\demo1\DEMO1_BASE_30.json -EntryOffset 0 -EntryCount 15 -PolicyCapUsd emission_escalate=1.8,full_signal_bounceback=1.52,local_only=0 -SessionMaxUsd 3.32'
# boot 5
ssh zjohn@100.101.81.6 'cd C:\Users\zjohn\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_h1.ps1 -Interleaved -InterleavedPolicies emission_escalate,full_signal_bounceback,local_only -Placement cpu-p -Entries derived\h1_hybrid\demo1\DEMO1_BASE_30.json -EntryOffset 15 -EntryCount 15 -PolicyCapUsd emission_escalate=1.2,full_signal_bounceback=0.48,local_only=0 -SessionMaxUsd 1.68'
```
Logs, artifacts and estimates:
- Boots 1-3 log to `h1_slo_escalate_<stamp>.log`, artifact `slo_escalate_<run_id>\`,
  each about 6,300 s (estimate).
- Boots 4-5 log to `h1_interleaved_<stamp>.log`, artifact `interleaved_<run_id>\`
  with `policies\<arm>\`, each about 5,200 s (estimate).
- The completion line is the same as for the DEMO-1 cells.
- Caps per boot: H1_CPU_AMEND_2.json per_boot_caps_usd (total $77.03).

## Closeout, per run (Mac side unless marked host)
1. Host listing. Set `<run>` to the artifact dir name, e.g. `slo_escalate_<run_id>`:
```
ssh <host> 'cd <repo>\derived\h1_hybrid; $r="<run>"; $base=(Resolve-Path $r).Path; Get-ChildItem -Recurse -File $r | ForEach-Object { "{0}|{1}|{2}|{3}|{4}" -f $r, $_.FullName.Substring($base.Length+1).Replace("\","/"), $_.Length, (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower(), $_.LastWriteTimeUtc.ToString("o") }' > ~/seam_closeout/H1_SOURCE_MANIFEST_<date>_<run>.txt
```
2. Copy: `scp -r <host>:"<repo>/derived/h1_hybrid/<run>" ~/seam_closeout/h1/`.
   Compare every file's sha256 with the listing. Also copy the launch evidence:
   `scp -r <host>:"<repo>/derived/h1_hybrid/_launches/<run_id>" ~/seam_closeout/h1/launch_<run_id>/`,
   and check each file against plan.json `git.launch_evidence.files[].sha256`.
3. Seal check. The run seals itself in-run (`.sealed`). Copy the dir into
   derived/h1_hybrid/ and run `python tools/seal_verify.py derived/h1_hybrid/<run>`.
   Expect MATCH. Add `-text` for the dir in .gitattributes if any file has
   CRLF endings.
4. Commit the run dir and the listing, score against DEMO_PREREG_v2.json (or
   H1_CPU_AMEND_2.json), update the registry, and push. Commit the launch
   evidence at `derived/h1_hybrid/_launches/<run_id>/` with a .gitignore
   exception (`!derived/h1_hybrid/_launches/<run_id>/` and `/**`) and `-text`,
   as for the natstop launch dirs; its hashes are already fixed by the plan.
5. Host: verify against origin, move, pull. It moves only if every file matches:
```
ssh <host> 'cd <repo>; git fetch -q origin; $d="derived/h1_hybrid/<run>"; $files=@(Get-ChildItem -Recurse -File $d); $bad=0; foreach ($f in $files) { $p=$f.FullName.Substring((Resolve-Path .).Path.Length+1).Replace("\","/"); if ((git hash-object -- $p) -ne (git rev-parse "origin/main:$p")) { $bad++; "DIFF $p" } }; "files=$($files.Count) diff=$bad"; if ($bad -eq 0) { $dst="<backup dir>"; New-Item -ItemType Directory -Force $dst | Out-Null; Move-Item $d $dst; git pull --ff-only; git status --short } else { "NOT MOVED" }'
```
Backup dirs:
- XPS: `C:\Users\zjohn\gnn_backup_demo1\run_dirs\` (new).
- T2S: `C:\Users\zach\gnn_backup_20260929\run_dirs_demo1\`.
   The launch evidence dir stays on the host (it is ignored there); after the
   commit and pull it is tracked and matches origin.

## One-time host cleanup before the first launch after 2026-10-13
The refused launches T2S 199f3f7d and XPS 16e8ec3f left each host dirty: the
tracked `derived\h1_hybrid\_canary_opening\canaries\canary.0.json` and
`opening_plan.json` are modified, and `derived\_gate_probes\gates_<stamp>.json`
is untracked. launch_h1 refuses a dirty tree, so keep a copy, then restore.
Look at the status first; run only with Zach's OK. Example, T2S:
```
ssh zach@100.72.40.24 'cd C:\Users\zach\Projects\gnn-hls-accel; git status --short; $dst="C:\Users\zach\gnn_backup_20260929\refused_h1_199f3f7d"; New-Item -ItemType Directory -Force $dst | Out-Null; Copy-Item -Recurse derived\h1_hybrid\_canary_opening $dst; Get-ChildItem derived\_gate_probes\gates_20261013_*.json | Move-Item -Destination $dst; git checkout -- derived/h1_hybrid/_canary_opening; git pull --ff-only; git status --short'
```
XPS: the same with `C:\Users\zjohn\...` and `refused_h1_16e8ec3f` under
`C:\Users\zjohn\gnn_backup_demo1\`. Before moving, check that the gates
files listed are the ones from these refused launches.

## Tier-1 process gate (f713edc) on both hosts
launch_h1.ps1 runs the full measurement gate set, tier-1 included, before
any spawn:
- tools/launch_h1.ps1:407 dot-sources tools/_run_measurement_gates.ps1.
- tools/launch_h1.ps1:412 calls Invoke-SeamMeasurementGates. On the T2S it
  adds only -SkipUptime. Live launches pass -ProbeDir (the run's launch dir).
- tools/_run_measurement_gates.ps1:50 runs `python -m seam.measurement_gates --json`.
  It refuses at :83 on a non-zero exit.
- seam/measurement_gates.py:639 `_main` calls evaluate_measurement_gates
  without skip_host_probes.
- :520 appends the tier1_processes gate.
- :534 counts it as a refusal; :654 returns 1.
- tests/test_h1_t2s.py checks this path.
On the T2S, a resident Chrome, Edge, Cursor or Code refuses the launch.
