# XPS gate-coverage audit (read-only)

Date 2026-10-12. Registry row XPS-HYGIENE. This audit changes no status and
no seal. Every number below is read from a sealed tree, from the tracked
unsealed sibling of the same run_id (marked "sibling"), or from git.

## Question

Until f713edc, tools/launch_boot1.ps1 called Invoke-CellPreamble with
-SkipGateFile for kinds det, warm, decode, resident, exchange and p1, so
Invoke-BootGates (seam.measurement_gates, gate JSON under derived/_gate_probes)
did not run for those cells. seam/measurement_gates.py had no process-name
check; the tier-1 names (chrome.exe, cursor.exe, code.exe, msedge.exe, ...)
were only in seam/isolation.py. What was enforced for the sealed runs
launched on that path?

## Answer in one paragraph

The launcher skipped the gate file, but every runner on the skip path ran
the same gates itself and refused on failure:
- tools/boot4_session.py require_gates() for warm, decode and resident;
- tools/exchange_rate_session.py for exchange;
- tools/run_p1_quality.py for p1, importing require_gates from boot4_session;
- tools/run_det_probe.py _run_gates() for det, which runs the
  seam.measurement_gates CLI and checks its exit code.

Each of these calls evaluate_measurement_gates with defaults: no skip_uptime,
no skip_host_probes. So every run below was refused-unless-passed on five
gates at session start: AC, processor AC 100/100, free memory >= 7000 MB,
uptime <= 7200 s, and onset. Each plan.json (gates.json for DET) records all
five passed, with the observed values.

The only gap is the tier-1 process check. No code at any of these HEADs
looked for browsers or editors by name, and the per-cell
environment_start/peak snapshots record tier-2 names only
(seam/telemetry/host_environment.py). So no sealed tree can show that tier-1
processes were absent.

## Enforcement by commit (identical at every HEAD below)

| layer | enforced at launch | source |
|---|---|---|
| launcher | WSH kill (Clear-WorkloadsSessionHost), machine lock, clean tree (Assert-BootTree, from 7b90a21), AC battery status (Assert-BootAc, from 7b90a21) | tools/launch_boot1.ps1 |
| launcher | Invoke-BootGates: SKIPPED for det (from 94bb43d), warm and decode (from 7de3f6f), and resident, exchange and p1 (as each kind was added) | -SkipGateFile |
| runner | ac, processor_ac, available_mb >= 7000, uptime <= 7200, onset; SystemExit on any failure | require_gates / _run_gates |
| runner | tier-1 process names: NOT CHECKED (added in f713edc) | seam/measurement_gates.py |
| in run | drift canary must arm (C=3 calibration) and aborts on trip (FAIL_CANARY_DRIFT); not in DET-PROBE | docs/CANARY_PROTOCOL.md |

The gates are read once, at session start, before any model load. The
7000 MB floor is a pre-run floor (configs/delta_n.yaml
isolation.pre_run_available_mb_min). It is not re-checked at canaries.

## Per run

HEAD: DET-PROBE plan.json records git_head (tree CLEAN). No other tree
records a HEAD. For those, HEAD is the last origin commit before
started_utc (or the first canary utc for P1, whose plan has no
started_utc). It is marked "inf". This does not change the result: the gate
code above did not change across 7fd174d..f713edc~1. require_gates existed
in each runner before its first sealed run (boot4_session 0e8aa5a,
exchange_rate_session 435a8e3, run_p1_quality b97dde7).

| run | id / kind | start UTC | HEAD | gate free MB / uptime s | canary: armed, n, max abs drift t1 / t2 (threshold t1 / t2) | free MB at canary start (bold = below 7000) | class |
|---|---|---|---|---|---|---|---|
| cb9773be | DET-PROBE u8 / det | after 2026-09-24 03:17 (HEAD time) | 7fd174d (recorded) | 9759 / 951 | none | none recorded | GATED (5); tier-1 UNVERIFIABLE |
| c46d9c94 | DET-PROBE f16 / det | after 2026-09-25 01:06 (HEAD time) | 7b90a21 (recorded) | 11175 / 1453 | none | none recorded | GATED (5); tier-1 UNVERIFIABLE |
| e9264a0a | WARM-KV f16 attempt / warm (status failed; sealed record, not cited) | 2026-09-29 22:02 | 4bc56e0 inf | 9823 / 357 | armed, 3 (calibration only) | **6915**, 7146, 9599 | GATED (5); tier-1 CANARY-GUARDED ONLY |
| 72776603 | WARM-KV f16 / warm | 2026-09-30 16:22 | 7471516 inf | 9515 / 147 | armed, 5, 0.033 / 0.029 (0.077 / 0.270) | **6581, 6180, 6965, 6939**, 8820 | GATED (5); tier-1 CANARY-GUARDED ONLY |
| 1587d2f4 | WARM-KV u8 / warm | 2026-09-30 16:26 | 7471516 inf | 12079 / 392 | armed, 5, 0.015 / 0.007 (0.077 / 0.164) | 8859-9947 | GATED (5); tier-1 CANARY-GUARDED ONLY |
| dd2b0779 | WARM-KV u4 / warm | 2026-09-30 16:30 | 7471516 inf | 12657 / 625 | armed, 5, 0.009 / 0.006 (0.077 / 0.164) | 9034-9518 | GATED (5); tier-1 CANARY-GUARDED ONLY |
| 180dfbb9 | DECODE-MATCH / decode | 2026-09-30 16:34 | 7471516 inf | 12322 / 898 | armed, 6, 0.022 / 0.070 (0.173 / 0.164) | 8951-9434 | GATED (5); tier-1 CANARY-GUARDED ONLY |
| 553b3a5c | RESIDENT-LIMIT f16 / resident | 2026-09-30 18:01 | 4e50885 inf | 10236 / 115 | armed, 9, 0.054 / 0.129 (0.096 / 0.805) | 7227, **6461**, 7073, 8764-10062 | GATED (5); tier-1 CANARY-GUARDED ONLY |
| cf3555d5 | RESIDENT-LIMIT u8 / resident | 2026-09-30 19:03 | 4e50885 inf | 11942 / 3869 | armed, 10, 0.051 / 0.095 (0.085 / 0.164) | 8688-9052 | GATED (5); tier-1 CANARY-GUARDED ONLY |
| e4a22dac | RESIDENT-LIMIT u4 / resident | 2026-10-01 00:12 | 435a8e3 inf | 9544 / 115 | armed, 9, 0.028 / 0.090 (0.077 / 0.413) | 7218, then **6528-6773** (8 of 9) | GATED (5); tier-1 CANARY-GUARDED ONLY |
| d4f66bbc | P0 v1 / exchange (partial; superseded by ac4e5472, EXCHANGE_RATE_AMENDMENT.json; not cited) | 2026-10-01 00:22 | 435a8e3 inf | 10097 / 710 | armed, 6, 0.044 / 0.158 (0.077 / 0.164) | 7239, **6799**, 7087-7596 | GATED (5); tier-1 CANARY-GUARDED ONLY |
| ac4e5472 | P0-v2 / exchange | 2026-10-01 01:53 | 9c70e2c inf | 9563 / 116 | armed, 6, 0.058 / 0.112 (0.077 / 0.855) | 7318, **6536, 6767, 6440**, 7270, 7314 | GATED (5); tier-1 CANARY-GUARDED ONLY |
| 8a529053 | P1 A0 / p1 | 2026-10-01 18:59 | 127db99 inf | 9419 / 92 | armed, 8, 0.032 / 0.257 (0.096 / 0.325) | **6640**, 7111, **3948-4627** (c2-c7) | GATED (5); tier-1 CANARY-GUARDED ONLY |
| 385cd4f6 | P1 A1 [:100] / p1 | 2026-10-01 20:57 | ec7e203 inf | 9121 / 365 | armed, 7, 0.032 / 0.093 (0.077 / 0.205) | **6846, 6421, 3524-4321** (all 7) | GATED (5); tier-1 CANARY-GUARDED ONLY |
| 3b4d8207 | P1 A4 [:100] / p1 | 2026-10-02 00:11 | 3e36455 inf | 9206 / 250 | armed, 9, 0.016 / 0.167 (0.077 / 0.257) | **6970, 6586, 3811-4815** (all 9) | GATED (5); tier-1 CANARY-GUARDED ONLY |

No canary tripped in any run. Isolation evidence:
- Tier-1 processes: none recorded in any run; the code did not record them.
- Tier-2 processes and process_count are in the P1 canary records
  (work/canaries/canary.*.json) and in the siblings' work/ records for the
  others.
- process_count at canary start: 216-231 in 8a529053, 385cd4f6 and
  3b4d8207, against 245-267 in VOID c42328c7 (Chrome and Cursor open).
  Other sessions reach 244-248 at some canaries (72776603, e4a22dac,
  ac4e5472; all launched at uptime 115-147 s). So the count corroborates but does not prove absence.

Out of scope: older sealed delta_prefill trees (41e419bd, 48779b5a,
9f38eb15, a784f5ec, d5c98342) came from August launchers, before
launch_boot1.ps1 existed (94bb43d, 2026-09-23). Ceiling and control cells
(c2246b1f, 7f232f86, 69234ed5, a427233b) took the non-skip path, so
Invoke-BootGates ran. They also had no tier-1 check before f713edc; that is
the same gap, but not this question.

## Free memory below 7000 MB

The 7000 MB floor is read once, before any model load. All 15 gate reads
pass (9121-12657 MB). Canary-start readings below 7000 MB appear in 11
runs, bolded above. Most come from pipelines held during the run:
- in P1, canaries 2 onward run while the arm pipeline is resident
  (3524-4815 MB);
- in RESIDENT-LIMIT and P0, the session keeps its model loaded.

These are not gate violations under the rule as written. The one
pre-pipeline case is 8a529053 canary 0: 6640 MB at uptime 111 s, 20 s
after the gate read 9419 MB at uptime 92 s, with the arm pipeline not yet
loaded ("calibrate with the arm pipeline released", 127db99). Free memory
fell 2.8 GB in 20 s of early boot. A single pre-run read does not bound
free memory during the run; only the canary does.

## Do p1 launches now enforce the memory floor and uptime?

Yes, but in the runner, not the launcher. At f713edc the p1 cell in
tools/launch_boot1.ps1 runs these in order:
1. Assert-T2sOwnedWorkers.
2. Assert-BootAc (battery status).
3. Assert-BootTier1 (python -m seam.measurement_gates --tier1-only).
4. Assert-BootTree.
5. Invoke-CellPreamble -SkipGateFile. Invoke-BootGates still does not run,
   so there is no derived/_gate_probes file.

Then tools/run_p1_quality.py:718 calls require_gates(), which calls
evaluate_measurement_gates(ROOT) with defaults. That now refuses on:
- AC and processor AC;
- available_mb >= 7000 and uptime <= 7200;
- onset;
- the new tier1_processes gate. Since f713edc it runs whenever host probes
  are on, so tier-1 is checked twice.

The result is written to plan.json "gates". The calibrate-only path
(run_p1_quality.py:858) skips require_gates only under SEAM_REHEARSAL=1.

## Proposed limitations paragraph

Before 2026-10-12, no XPS launch checked by name for operator-controlled
contending processes (browsers, editors). The DET-PROBE, WARM-KV,
DECODE-MATCH, RESIDENT-LIMIT, P0-v2 and P1 sessions were gated at start on
AC power, processor AC state, free memory (>= 7000 MB) and uptime
(<= 7200 s). Every timed session ran with an armed two-sided drift canary.
None tripped: maximum turn-1 drift was 5.8% against per-session thresholds
of 7.7-17.3%. A resident browser or editor that slowed prefill by more than
the threshold would have aborted the session; a smaller slowdown would not
be detected. DET-PROBE has no canary; it measures output identity, not
timing. One session from this period (c42328c7) was voided when a browser
and an editor were found running, and is not cited. Since f713edc, every
launch refuses if a tier-1 process is resident.
