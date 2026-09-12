# Cursor dispatch — C2f: baseline the canary, scope it per-endpoint, run

Track: `agent`. Attrib frozen. Everything in C2b–C2e not restated here still stands.

---

## Where `ede96981` got to

**The run sealed. Integrity OK.** Three consecutive write-path failures — circular reference,
UnicodeEncodeError, schema rejection — are fixed.

```
task      ratio   paging_adm   canary settled
C2T13     5.98       no            4.69
C2T19     8.04       no             —
C2T10     8.34      yes             —
C2T20     1.45      yes             —
C2T14     7.12       no            0.23
                  median ratio 7.12 ≥ 3.0
```

Clearance withheld on two non-paging invalidations: canary drift 4.69 and 0.23 against a 0.15
threshold.

## 1. Explain the 4.69 before deciding anything about it

A settled drift of 4.69 means the canary ran roughly **5.7× slower** after the block than before and
stayed slow through the settle. That is not a threshold miss, it is an event.

**C2T13 is first in execution order, and the earlier free-memory series rose across tasks**
(1846 → 2085 → 2300 → 2382 → 2303 MB). The first task runs on the least-settled machine.

Test it directly: **add a discard-first warm-up task** — run one full task, discard its record
entirely, then begin timing. If C2T13-position drift disappears, the cause is startup settling and
the fix is permanent. If it persists, something else is happening and it must be found before the
full run.

Report the drift by execution position across the pilot, not only by task ID. Position is the
variable under test.

## 2. Baseline the canary — the 0.15 threshold was never derived

The paging gate has a proper baseline: `e6bae93f`, idle p95 plus margin, recorded in the manifest
with `baseline_run_id`. **The canary threshold does not. 0.15 was asserted, not measured.**

Before the next pilot, characterize the canary's own variability:

1. Machine quiesced, machine lock held, no inference workload.
2. Run the canary ≥30 times back to back, with the same spacing it would have inside a run.
3. Report the drift distribution between consecutive pairs: median, p95, max, fraction above 0.15.

**Then set the threshold at canary p95 plus a stated margin**, and record `canary_gate` in the
manifest with `baseline_run_id`, `idle_p95`, `margin`, `threshold` and the justification — exactly
as `paging_gate` does.

If the canary's own p95 drift is near 0.15, the threshold was sitting on the noise floor and every
block was a coin flip. If it is near 0.01, then 4.69 is unambiguous and §1 matters more.

**Do not choose the threshold to make the pilot pass.** Derive it, record it, apply it.

## 3. Scope canary drift per-endpoint — with the principle stated

```
peak resident KV  =  context × 73,728
context           =  token count in the transcript
transcript        =  deterministic given prompts and fixed sampling
```

**Machine speed does not change which tokens are produced.** A block that ran 5.7× slower generates
an identical transcript, so envelope endpoints are unaffected. Canary drift contaminates
`t_actual`, `actual_wall_s`, `deadline_overrun` — the same set paging contaminates, for the same
reason.

Two gates have now been scoped after they blocked, so the principle is recorded explicitly:

> **A gate governs the endpoints whose values its quantity can causally affect, and no others.**
> Membership is decided by the causal path, not by whether the gate is inconvenient.

**This argument has a precondition that must be verified, not assumed.** If the harness contains any
wall-clock timeout that truncates generation, then a slow block *does* change token production and
the entire argument collapses.

**Audit the harness for wall-clock timeouts on the generation path and report what you find.** If
one exists, canary drift is fatal to envelope endpoints too and this section is withdrawn.

Assuming none: tag each block `canary_admissible: bool` with its drift value, and apply it per
endpoint exactly as `paging_admissible` is applied — envelope over all blocks, timing over
admissible only, admissible fraction stated beside every number.

## 4. Re-pilot

≥5 tasks plus the discarded warm-up. Pass conditions:

- median per-task context ratio ≥ 3.0
- the run seals — now demonstrated, keep it
- **zero invalidations that causally affect the primary endpoint**, given §3's audit result
- canary drift reported by execution position

## 5. Then the full run

As C2b §6: deadline grid derived from the measured `t_pred` distribution with ≥8 points spanning its
range, amendment withdrawing the pre-registered 8 s deadline, corrected proxy per AM-027, paging and
canary gates scoped per endpoint, cloud backend that raises, P1–P6 at materiality 1.2×, and the
computed ceiling `C_max/C_min` reported alongside the measured over-provisioning.

## Report, in order

1. **Wall-clock timeout audit.** This decides whether §3 stands or is withdrawn.
2. Canary noise-floor distribution and the derived threshold, with its manifest record.
3. Re-pilot with the discarded warm-up: drift by execution position, admissibility per block, seal
   result.
4. Then the full run, with the admissible fraction beside every timing-derived number.

## Standing constraints

Machine lock every timed block, detached launch. No commit, push, raw mutation, cloud call, or
credential load. Thresholds are derived from baselines and recorded — never chosen to make a run
pass. Every number carries its run_id per AM-027(b).
