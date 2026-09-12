# Environment changelog — Platform A host facts that affect measurement

Append-only. Each entry records a measured host behavior that launchers /
gates / watchdogs must treat as fact. Prefer citing a `run_id` when the
observation came from a sealed or session artifact.

---

## 2026-09-08 — No hard memory/position ceiling in C-1 range (AM-037)

**Host:** Platform A (16 GB unified). **Session:**
`83127e1b-9d6e-4103-bee6-2a63c00f479f` (`gpu_only_f16`, int4).

**Paging.** `available_mb_min` reached **0.0** with generate still
completing (`n=36750` r0; `n=44742` r0). Commit continued to grow
(~13.4 GB at n=44742). There is no Available-based hard stop under OS
paging; do not declare a memory ceiling from Available alone.

**RSS lock.** Process working-set maximum is
`SetProcessWorkingSetSizeEx` **12 GB** (`12884901888`). `peak_rss_bytes`
flattens near that lock above ~n=42,000 and is not a consumption measure
there. Use **`peak_commit_bytes`** for the additive memory model.

**Position.** `max_position_embeddings=40960` is **not** enforced at
inference; completed probes at **n=44742**.

**Launcher.** C-1 bisection that never observes a failure aborts with
`no_ceiling_found_in_range` (does not report `high` as a ceiling).

---

## 2026-09-01 — WorkloadsSessionHost cost, respawn, watchdog interval

**Host:** Platform A (Dell XPS 16 / Core Ultra 5 325).

**Cost.** `WorkloadsSessionHost` holds about **2.18 GB** working set while
resident. That alone can push Available below the 7,000 MB pre-run floor and
confound any long arm that assumed a single launch-time kill.

**Respawn.** After `Stop-Process`, WSH returns within about **4 minutes**
(X-2 cell 1 `91905556-3e51-4018-99f9-aaf421a31728`: start kill at
18:16:47Z with no host present; pid 6040 appeared ~4 min later and survived
the rest of the session). Earlier matrix notes of ~10–15 min are superseded
for watchdog sizing by this ~4 min observation.

**Binary / activation.** `WorkloadsSessionHost.exe` ships inside
`WindowsWorkload.Manager.1` (COM `OutOfProcessServer`
`Microsoft.Windows.Private.Workloads.SessionHost`), not inside the
`WindowsWorkload.EP.Intel.OpenVINO.*` Appx names the launchers remove. No
scheduled task or Win32 service named for WSH was found; respawn is
activation-driven, not a timer service.

**Watchdog interval.** A **300 s** poll interval is therefore **insufficient
even when the sibling process stays alive**: the host can be back for most
of each poll window. X-2 defaults to **60 s** after the spawn fix. Polling
remains a race against COM reactivation, not a durable off-switch.

**Spawn defect (fixed in `tools/run_x2_feasibility.py`).** The first X-2
watchdog used `subprocess.Popen` with
`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`. That sibling exited within
~1 s and wrote only the Python-side `watchdog_start_kill` line (zero poll /
kill events). Spawn A/B on this host: `DETACHED|NEW_GROUP` dead at 1 s;
`CREATE_NEW_PROCESS_GROUP` alone or flags=0 stay alive and poll;
`Start-Process -WindowStyle Hidden` works when the parent stays alive
(matrix orchestrator) but a short-lived helper that Start-Process-es and
exits can still lose the child under kill-on-job-close. X-2 now uses
`Popen` + `CREATE_NEW_PROCESS_GROUP` only, keeps the handle for the worker
lifetime, and refuses if the sibling exits in the first second. Do not
reintroduce `DETACHED_PROCESS`. Matrix reference:
`tools/run_delta_prefill_matrix.ps1` `Start-WshWatchdog` (10 events / 3
kills on a clean N-1 session).

**X-2 status.** Cell 1 (`cpu-p` × `NON_RESIDENT`, session `91905556-…`) is
**aborted** (`watchdog_failed_wsh_resident_2177mb`) — keep as methodology
evidence (guard reported healthy while sibling was dead; WSH ~2.18 GB for the
session). Re-runs `cb781dbf` / `9fdedb46` / `afd1aa21` / `0963168f` completed;
Phase 1 integrity **fails** seal gate on the two cpu-p cells (9 and 2 WSH
kill events respectively; upper-bound contaminated wall fraction ~6.6% /
~7.5%). gpu_only cells had zero WSH detections. Seals blocked until clean.
See `x2_phase1_integrity.json`, `x2_derived_table.json`, `x2_onset_analysis.json`.

**Durable removal.** `Remove-AppxPackage` of the OpenVINO workload packages
does not persist (packages return; WSH can still activate from Manager).
Options to stop needing a watchdog — **not applied**; see the 2026-09-01
dispatch report for blast radius. Requires an explicit human decision.
