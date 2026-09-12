# Proposal — the target-set reframe, and what it does to the blueprint

**Status: proposal. Not authorized, not pre-registered.** This restructures the project's central
object. It is written to be argued with.

---

## 1. The reframe

The blueprint currently models the decision as a **partition**: local or cloud, one boundary, one
local option. Every routing paper in §3 does the same, and it is why the field is crowded.

**Collapse the boundary.** The cloud is not the other side of a wall — it is one element of a
target set, with a network coordinate, a price, and a privacy class:

```
𝒯 = { cpu-p, cpu-lpe, igpu, npu, cloud }
```

Each target carries: `R_prefill`, `R_decode`, `J/token`, `memory_reserved`, `max_prompt_len`,
`price`, `privacy_class`, `feasible(model, quant)`.

The policy π stops being a binary threshold and becomes an **assignment** `step → 𝒯`, subject to a
feasibility mask that varies per step.

**Positioning consequence, and it is generous rather than dismissive:**

> The routing literature solves the projection **N = 1 local target**. Agent.xpu and the on-SoC
> schedulers solve the projection **no network target**. Neither is wrong; each is a lower-
> dimensional slice. The general problem is the one that exists on shipping hardware, and it
> requires agent semantics, per-target hardware measurement, and a network boundary simultaneously.

That is the cleanest separation this project has, and it does not depend on anyone having missed
anything.

## 2. The BOM question becomes an ablation

If 𝒯 is a set, targets can be **removed** and the frontier recomputed.

```
value(t) = frontier(𝒯) − frontier(𝒯 \ {t})
```

> **Ablating the NPU costs X% of cloud spend at matched p95 latency. That is what an NPU is worth
> for agentic workloads, measured rather than assumed.**

The same ablation runs for the iGPU, the LP-E cluster, and memory tiers. **This is the procurement
question stated as an experiment** — and it makes routing policy and silicon composition the same
decision viewed at two timescales.

That equivalence is the co-design thesis in its strongest form and it should become the project's
headline framing.

## 3. The risky claim: heterogeneity may be over-provisioned

Targets are not free. Each costs die area, and on unified memory each costs **context** when used.
So there is an optimal heterogeneity level and it may be below what ships.

Compose with the hybrid effect: escalated steps leave every local target idle during the cloud
round-trip. **The accelerator is selected rarely and stranded often.**

> **The NPU is selected for X% of agent steps and idle for Y% of wall time. Effective utilization is
> Z%.**

If Z is single digits, that is a fully quantified claim about a product category sold on TOPS. High
risk — if the NPU turns out to win frequently, the claim inverts into "heterogeneity pays," which is
also publishable and also useful.

## 4. Each channel generates a target experiment

The three channels stop being a narrative device and become an experimental program.

### Capacity → **E-SHRINK**: the feasible set contracts within a trajectory

Accelerators reserve unified memory; the NPU declares `MAX_PROMPT_LEN` at compile time. As context
grows, targets do not get slower — **they become infeasible.**

Measure the feasible set as a function of step index. Report which target drops out, at what
context, and for which reason: speed, static shape limit, or memory reservation.

This is the capacity channel expressed in routing terms, and it is binary rather than graded — the
strongest form the capacity claim can take.

### Throughput → **E-CROSS**: the crossover surface is the routing table

Which target wins depends on the step's arithmetic intensity — prefill-heavy work wants compute,
decode-heavy work wants bandwidth.

C10 stops being a characterization and becomes the **lookup structure a target-aware policy
consumes.** Measure the crossover over (arithmetic intensity × target), then verify that real agent
steps land where their measured intensity predicts.

### Drift → **E-THERMAL-CROSS**: the crossover moves as the device heats

The sharp one. **Accelerators and CPUs throttle differently.** If the NPU's sustained throughput
degrades faster than the CPU's under load, the crossover point moves during a session.

> Thermal drift does not merely slow the device. **It changes which silicon you should be using.**

Measure the crossover surface at cold, warm, and thermally-saturated states. If it moves, H8 becomes
much stronger: the non-stationarity is not a performance decay, it is a **change in the optimal
design point** — which is precisely what makes a static DSE answer wrong.

### The composition

> **There is no static optimal execution target. The right unit changes within a single agent
> session for three independent reasons: the workload's arithmetic intensity, the context it has
> accumulated, and the heat it has generated.**

Three channels, one falsifiable claim, expressed as a decision an OEM must make.

## 5. Blueprint impact

### §2 — the formal object

`π` changes from a binary threshold to an assignment `step → 𝒯` with a per-step feasibility mask.
The "partition" language is retained for continuity but redefined: a partition is the induced
2-colouring of a target assignment, i.e. a projection of the real decision.

`𝒯` itself becomes a **hardware coordinate** — which targets exist is a BOM choice, and the design
space includes subsets of 𝒯.

### §5 — new hypotheses

| | Claim |
|:--|:--|
| **H14** | *False escalation.* A material fraction of binary-routing escalations are avoidable on a local target the policy does not consider. |
| **H15** | *Ablation value.* Removing a target from 𝒯 costs measurable cloud spend at matched latency; the value differs per target and per workload. |
| **H16** | *Feasible-set contraction.* The feasible target set shrinks monotonically within a trajectory, and at least one target becomes infeasible before the context cap. |
| **H17** | *Thermal crossover migration.* The arithmetic-intensity crossover between targets moves measurably between cold and thermally-saturated states. |
| **H18** | *Objective disagreement.* Latency-optimal and energy-optimal targets disagree on a material fraction of steps. |

H18 is what makes it a frontier rather than a ranking. H17 is the highest-risk and highest-value.

### §9 — ledger

- **C13** — target-aware routing beats binary local/cloud, with the false-escalation mechanism
- **C14** — per-target ablation values: the BOM answer, measured
- **C10** is promoted from characterization to the routing policy's lookup structure
- **C6**, the sizing rule, changes shape: from *"how much of coordinate X"* to *"which targets should
  exist, and how large"* — closer to the question an OEM actually asks

### §11 — studies

E-TARGET (already drafted), E-ABLATE, E-SHRINK, E-CROSS, E-THERMAL-CROSS, and E-UTIL (accelerator
effective utilization under hybrid).

### The pitch line

> **Routing policy and silicon composition are the same design problem at different timescales.**

## 6. Why this is available now

None of it requires long agent trajectories on the laptop.

```
per-target table       microbenchmarks, short prompts, memory-safe
trajectories           already sealed (1a0166b9, 51 steps with token counts)
ablations & crossings  offline replay over the target table
thermal crossover      sustained microbenchmarks, no agent harness
```

The blocker is iGPU and NPU bring-up — M4, currently partial with neither path exercised. Bounded
backend work with three documented defects to handle rather than rediscover.

## 7. Risks

**The composition may be occupied.** The pieces exist separately. Search specifically for N-way local
target selection *with* a cloud escalation option, feasibility varying within a trajectory, and
thermal-dependent target crossover. Record in Appendix A.2 before any absence claim.

**The accelerators may simply lose.** [2607.05475](https://arxiv.org/abs/2607.05475) reports CPUs
beating NPUs on memory-bound decode. If they lose everywhere, H14 goes to zero — but prefill is
where the NPU should win, and prefill is where binary routing escalates, so the mechanism should
survive.

**One target may dominate.** Then 𝒯 collapses to a point, there is no frontier, and the honest
finding is that target-aware routing is not worth building. That is a clean negative and it saves
the field the effort.
