# Cursor dispatch — measurement isolation, then ΔN

Track: `agent`. Do this before `CURSOR_PROMPT_delta_n.md`.

---

## The problem

Ten pilots have been blocked or contaminated by contention on a personal machine. Every attempt so
far has tried to **eliminate** noise — quiesce gates, closing applications, refusing runs. That is
unwinnable on a laptop that is also a workstation.

Three mechanisms change it structurally. Implement all three, verify each, then measure.

## 1. Reserve cores from the OS — not process affinity

**Process affinity constrains our process. It does nothing to stop Windows from scheduling other
work onto the same cores.** That is why quiesce keeps refusing.

Windows exposes **SetRTCores** through the WindowsIoT CSP, which prevents interrupts *and* tasks
from being scheduled on reserved cores. [ReservedCpuSets](https://github.com/valleyofdoom/ReservedCpuSets)
wraps it.

**Target configuration:** reserve CPUs 0–3 (P-cores) for measurement, leave 4–7 (LP-E) to Windows.
OpenVINO already defaults to P-core placement, so the workload lands on the reserved set and
everything else is pushed off.

Requirements:

- **Verify it took effect**, do not assume. After applying, run a 4-process CPU burn and confirm
  from per-core utilization that the burn does **not** land on 0–3.
- **Record the reserved set in every manifest.** It changes the machine's configuration, so every
  measurement under it is of a modified machine and must say so.
- **Document the restore procedure** and record the pre-change state before applying.
- Report whether reservation survives reboot, and whether it must be reapplied.

If SetRTCores is unavailable or ineffective on this build, report that and fall back to §2 alone —
do not substitute plain process affinity and call it isolation.

## 2. Interleave so interference is shared

[Duet Benchmarking (2001.05811)](https://arxiv.org/pdf/2001.05811): *"Randomized interleaving of
workloads avoids bias by equalizing the probability of interference for all workloads."*

Two model instances will not fit in 16 GB, so apply the principle at the finest feasible
granularity instead:

**Alternate configurations rung by rung, in randomized order. Never all of A, then all of B.**

For the ΔN ladder that means: at each context size, measure config A, config B and config A′ in
randomized order before advancing to the next rung. Drift and interference then affect all arms
equally, and the comparison survives even when absolute values do not.

This directly addresses the unexplained 1.98×, which was a **between-run** difference. Interleaved
within a run it would have been shared.

Record `arm_sequence_index` and `rung_index` on every block so order effects are testable
afterward.

## 3. Lock the model's working set

Phase 3 attempted `SetProcessWorkingSetSize` and received Win32 error 6 — `ERROR_INVALID_HANDLE`,
which is a code defect rather than a privilege wall.

Retry with a handle from `GetCurrentProcess()` and `SE_INC_WORKING_SET_NAME` enabled. Use
`QUOTA_LIMITS_HARDWS_MIN_ENABLE` so the minimum is enforced rather than advisory.

**If it takes, the OS cannot trim the 2.6 GB model out from under a run** — attacking the paging
problem at its source instead of detecting it afterward.

Report whether it was granted, and measure hard page-read rate during generation with and without
it. That difference is worth recording regardless of the ΔN outcome.

## 4. Verification before any measurement

Report all four, with evidence:

1. Reserved CPU set applied, **verified by burn test** showing no foreign work on 0–3.
2. Working-set lock granted or denied, with the page-read difference either way.
3. Interleaving implemented, with a sample sequence showing randomized arm order within a rung.
4. A repeat of the earlier contention probe under isolation: run the same fixed config twice,
   20 minutes apart, and report the throughput ratio. **The 1.98× is the benchmark to beat.**

Item 4 is the acceptance test. If the ratio is near 1.0 under isolation, the machine is finally a
measurement instrument.

## 5. Then run ΔN

Proceed to `CURSOR_PROMPT_delta_n.md` unchanged, with §2's interleaving applied to its ladder and
§1's reserved set recorded in the manifest.

## Not in scope

No changes to security software. No disabling of Windows AI services beyond the existing quiesce
control. The `AMENDMENTS.md` / blueprint §14 dual-definition collision is resolved
(AMENDMENTS-side content reissued as AM-033 / AM-034; Blueprint retains AM-025 / AM-027).

## Standing constraints

Machine lock every timed block, canary either side, detached launch. No commit, push, raw mutation,
cloud call, or credential load. Every number carries its run_id. Record the pre-change system state
before applying §1 or §3, and include the restore procedure in the report.
