# E-NET — the optimal target set is a strict subset

**Pre-registration draft. The project's single focus.** Supersedes `EXPERIMENT_capability_cost.md`,
which measured only the cost channel.

---

## 0. The question this answers

> **How does optimizing hardware targets benefit hybrid execution routing policy?**

Through two channels that pull in opposite directions on unified memory:

```
positive   more local targets → more work stays local  → LESS cloud spend
negative   more local targets → less memory for context → forced escalation → MORE cloud spend
net        an interior optimum
```

**Optimizing the target set means finding the subset where the savings channel dominates the
capability channel. That subset is not "all of them," and which subset it is depends on the
workload.** The router's target set becomes a decision variable rather than an inventory.

## 1. The prior number this pushes against

The positive channel is **not** a research claim. Practitioner analyses put hybrid routing at
**60–80% cloud-spend reduction**, with break-even calculators for local hardware widely published.

But every one of those analyses assumes an **RTX 5090 with 32 GB dedicated VRAM**, a Jetson AGX
Orin, or an M4 Max — **memory separate from, or vastly larger than, the context budget.**

```
discrete / large memory    accelerator memory ⊥ context memory    savings are pure
unified memory             accelerator memory ∩ context memory    savings compete with capability
```

> **The 60–80% figure assumes the accelerator has its own memory. Every AI PC is unified. On
> unified memory the accelerator takes memory from context, forcing long-context steps back to the
> cloud — so the savings shrink, and past some point they invert.**

That is a claim with an established number to contradict, a mechanism that says exactly when it
breaks, and a regime covering the entire product category the industry is selling.

## 2. Conflict audit — recorded per the Appendix A.2 standing rule

Searched 2026-08-04, six queries. **Six collisions, each stated with its expansion.**

| Prior work | What it has | Why it does not close this |
|:--|:--|:--|
| Practitioner hybrid-routing analyses; [2509.18101](https://arxiv.org/html/2509.18101v1) on-prem break-even | 60–80% cloud savings, break-even economics | **Discrete or large dedicated memory.** The capability channel does not exist on their hardware. |
| [HeteroMosaic 2607.12839](https://arxiv.org/html/2607.12839v3) | Heterogeneous roofline, joint schedule + allocation, unified-memory **contention** | Contention *during* execution. This is **reservation** — memory taken before work begins, lowering the ceiling. And no cloud, so no price on infeasibility. |
| [2511.22334](https://arxiv.org/pdf/2511.22334) | CPU/GPU/NPU edge comparison, sequence-length effects | Measures **degradation at a length**, not the **ceiling each backend permits**. No cloud. |
| [Agent.xpu 2506.24045](https://arxiv.org/abs/2506.24045) | NPU/iGPU affinity, prefill/decode split, client SoC | All work must stay local. Cannot ask whether a target is worth its memory when escalation exists. |
| KV-cache memory literature | Deep context-versus-batch analysis | Datacenter, fixed GPU, batch framing. Not *which backend is enabled on a shared pool*. |
| Context-offloading frameworks (DeepAgents, Strands) | Offload tool results past a token threshold | Software workarounds that **prove the constraint binds.** None measures how the hardware target choice moves the boundary. |

**Not found:** maximum usable context measured as a function of which accelerator is enabled, and
the cloud-spend consequence. Six queries is weak evidence of absence — extend before any absence
claim reaches a slide.

**Also noted:** [2607.05475](https://arxiv.org/abs/2607.05475) finds CPUs beat NPUs on decode while
[2511.22334](https://arxiv.org/pdf/2511.22334) finds NPUs dominate on EDP. The literature
contradicts itself, which implies workload dependence and is an opening rather than an obstacle.

## 3. Measurements

For each target configuration `S ⊆ {cpu-p, cpu-lpe, igpu, npu}`:

**3.1 Capability frontier.** Binary-search maximum context that completes, per configuration.
Report the ceiling, the failure mode at the boundary, and **memory reserved by enabling each backend
before any inference runs.**

Memory-safe by construction — the procedure finds where it fails, so failure is the measurement.
That is why this can proceed on a machine that has blocked ten agent pilots.

**3.2 Reservation attribution.** Where does the memory go — weight duplication, driver allocation,
or activation buffers? **If weights are copied rather than shared, reservation could be gigabytes;
if zero-copy holds, negligible.** This single answer determines whether the effect is large or nil,
and nobody publishes it.

**3.3 Speed frontier.** `R_prefill`, `R_decode`, `J/token` per target across a prompt-length sweep.

## 4. The replay

Over sealed trajectories with per-step context and token counts:

```
infeasible(step, S) = context(step) > max_context(S)
too_slow(step, S)   = min over feasible targets of t_pred > D
cloud_spend(S)      = Σ price(infeasible) + Σ price(too_slow)
```

**Escalation decomposes into necessity and choice.** Necessity is the new quantity — it exists only
because capability is finite, it is invariant to the deadline, and no routing policy recovers it.

Evaluate `cloud_spend(S)` over **every subset** and report the argmin.

## 5. Pre-registered predictions

| | Prediction | Falsified if |
|:--|:--|:--|
| **P1** | Enabling a backend measurably reduces maximum usable context | reduction < 5%, CI excluding 15% |
| **P2** | `cloud_spend(S)` is **not monotone decreasing** in \|S\| — adding a target past some point raises it | monotone decreasing across all subsets |
| **P3** | **The argmin is a strict subset of all available targets** | the full set is optimal |
| **P4** | Savings from adding a local target on unified memory are materially below the 60–80% reported for dedicated-memory setups | savings within that band |
| **P5** | The argmin depends on the workload's context growth rate | invariant across workload profiles |

**P3 is the headline** — it is the direct answer to "how does optimizing targets benefit routing."
**P4 engages the established number.** **P5 is the DSE justification**: an optimum that moves with
workload cannot be reasoned to and must be searched.

## 6. Every outcome is worth having

**P3 holds** → *"the optimal target set is a strict subset; routing over all available hardware is
not optimal."* A routing-policy result driven by hardware, in a regime nobody has measured.

**P3 fails, P1 holds** → accelerators cost context but the speed gain always dominates. The
capability/speed trade is still measured for the first time, and the crossover is a design number.

**P1 fails** → reservation is negligible, zero-copy holds, and the line dies in a day for the price
of a binary search. **Cheap to kill, which is why it goes first.**

## 7. Cost

iGPU and NPU bring-up — M4, partial with neither exercised. Three documented defects to handle
rather than rediscover: NPU + INT8 IR (openvino#35641, assert INT4 first), NPU dynamic shapes
(openvino#34617, set `MAX_PROMPT_LEN` and chunk size explicitly), Panther Lake iGPU
`CL_INVALID_WORK_GROUP_SIZE` (openvino#34390, per-model smoke test).

`preflight()` returns `SUPPORTED | UNSUPPORTED(reason) | DEGRADED(reason)` without crashing. **On a
capability frontier, an unsupported target is the finding.**

Everything after bring-up is microbenchmarks and offline replay. No agent trajectories on the
laptop.

## 8. What this does not claim

Not a scheduling contribution — HeteroMosaic and Agent.xpu own that. Not a KV-cache optimization.
Not that local inference saves money, which is established.

**It claims that on unified memory the target set has an interior optimum, and that using all
available hardware is not it.** That requires a priced alternative to local execution, which none of
the colliding work has.
