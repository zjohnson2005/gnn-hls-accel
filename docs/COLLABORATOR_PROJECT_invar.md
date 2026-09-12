# INVAR — Are routing advantages a property of the policy, or of the machine?

**Working title only. The name is yours to change — so is the framing.**

An independent project proposal. This is not a component of SEAM and does not depend on SEAM's
results, data, or schedule. What the two share is measurement methodology, which is free to copy.

---

## 1. The question

At least ten published systems route agent steps between a local model and a cloud model — HERA,
HybridFlow, PAAC, PRISM, IslandRun, MSAO, EWSJF, ConfigSpec, R2V-Agent, Minions. Each reports an
advantage over its baselines.

No two were evaluated on the same hardware. Most do not report the hardware in enough detail to
reproduce. None reports device energy. None tests whether its advantage survives a change of
machine.

So:

> **Is "this router is better" a statement about the router, or about the laptop it was
> benchmarked on?**

Nobody knows. That is not a gap in a niche — it is an uncontrolled variable running through an
entire active subfield.

## 2. Why the crowding is the opportunity

A tenth routing policy entering this field competes with nine incumbents. A paper showing that
the nine cannot be compared to each other *needs* there to be nine. The density of the field is
what makes the critique load-bearing rather than pedantic.

This is also why the project is worth doing now rather than later: the subfield is still
accumulating policies, and the correction is most valuable before the next twenty arrive.

## 3. Hypotheses

| | Claim | Yields |
|:--|:--|:--|
| **R1** | Published routing work does not report evaluation hardware in enough detail to reproduce, and does not report energy. | Audit table. No experiments required. |
| **R2** | The ranking of policies by a given objective **changes across execution targets**. | The headline. Kendall τ across targets. |
| **R3** | Ranking instability across *hardware* exceeds instability across *workload* within a fixed target. | Sharper: hardware is a larger confound than the variable people already control for. |
| **R4** | Transfer failure is **asymmetric in kind**, not just in magnitude. | The mechanism. See below. |
| **R5** | No policy is Pareto-dominant across all five objectives on any single target. | If true, "best router" is malformed as a question. |

**R4 is the scientific core.** A policy tuned on fast local silicon keeps more work local, because
local execution is cheap there. Move it to slower silicon and those steps miss their deadlines —
it fails on **latency**. A policy tuned on slow silicon escalates aggressively. Move it to fast
silicon and it escalates work it no longer needed to — it fails on **cost**.

The two directions do not degrade by different amounts. They break *different objectives*. That
is a directional, mechanistic prediction, and it is what separates this from a benchmark sweep.

## 4. Phases, and what each yields on its own

**Phase 0 — the reporting audit** *(no hardware, ~2 weeks)*
For every candidate paper: hardware stated? reproducible? code available? objectives reported?
energy measured? policy hyperparameters given? Produces the R1 table.

*Yields regardless of everything downstream.* Also satisfies the documented-search requirement
before any absence claim is made in an abstract.

**Phase 1 — common substrate** *(no special hardware)*
Wrap or reimplement each policy behind one interface: same workload, same model endpoints, same
telemetry. Original author code wherever it exists.

**Phase 2 — cross-target sweep** *(needs hardware)*
Every policy × every execution target × workload set, five objectives measured.

**Phase 3 — analysis**
Rank correlation across targets (R2), variance decomposition hardware-vs-workload (R3), the
directional asymmetry test (R4), Pareto analysis per target (R5).

**Phase 4 — the constructive ending** *(optional, only if R2 holds)*
If rankings invert, the fix is a **hardware-conditional policy selector**: detect the machine,
choose the policy. This is where you build a router — and it arrives as the *conclusion of a
critique* rather than as a tenth entry into a crowded field. Much stronger position.

## 5. The fidelity gate — non-negotiable

A reimplementation that underperforms its paper is worthless as evidence and unfair to the
authors. Before any policy enters the ranking analysis it must reproduce its own paper's headline
result on that paper's own reported setup, within a stated tolerance.

A policy that fails reproduction is reported as **NOT REPRODUCED** in the audit table and
**excluded** from the ranking analysis. It is never silently dropped, and never included with bad
numbers. Contact the authors before declaring failure.

Irreproducibility is itself a Phase 0 result. It is not a setback.

## 6. Pre-registration

Declare R2–R5, the comparison protocol, the tolerance, and the analysis before running Phase 2.

If the rankings turn out to be stable, that is a real finding — routing advantages are
hardware-robust — and it is only publishable as a finding if it was predicted in advance. Without
pre-registration a null looks like a failed project.

## 7. Scope

**In:** published policies, common substrate, cross-target measurement, five objectives, the
asymmetry test, and the selector if R2 holds.

**Out:** designing a novel routing policy as the *starting* contribution; anything requiring
SEAM's surrogate; anything on SEAM's critical path.

## 8. Relationship to SEAM

Independent, and deliberately so. Zach's project asks how hardware should be chosen at design
time. This asks whether the existing evaluation literature controlled for hardware at all. Same
underlying insight, opposite directions — one constructive, one critical. Separate papers,
separate framings, separate first authors.

**What transfers (free, no dependency):** the isolation invariant, confinement verification with
per-core delta utilization against an idle baseline, the thermal dual-regime rule, bootstrap CIs
and the effect-size discipline, manifest and provenance practice.

**What does not transfer:** π*, the surrogate, SEAM's measured anchors, the blueprint.

**Interface:** results, not code. If the two projects are ever editing the same file, the split
has failed.

**One real constraint:** Phase 2 needs quiesced exclusive access to a machine, and thermally
settled measurement cannot be shared. Either schedule around the second platform's arrival, or
use different silicon entirely — the ranking-inversion claim is *stronger* if it holds on
machines outside our lab.

## 9. Risks

| Risk | Response |
|:--|:--|
| Reimplementation is heavy and the fidelity gate is strict | Phase 0 yields regardless; prefer original code; N can shrink to the reproducible subset without killing the claim |
| Rankings prove stable | Pre-registered null, still publishable, and it strengthens the transferability argument |
| Hardware contention | Phase 2 scheduling, or foreign silicon |
| Some policies are not reimplementable at all | That is an R1 result, reported as such |

## 10. Ownership

First authorship, the name, the framing, the venue, and the decision to run Phase 4 are all his.
Zach is a co-author at most. A project that is not genuinely his will not get the aggression it
needs.
