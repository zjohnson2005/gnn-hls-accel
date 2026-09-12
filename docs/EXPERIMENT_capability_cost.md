# E-CAP — the accelerator that costs you money

**Pre-registration draft. The project's single focus.** SEAM takes a back seat; this is the headline
experiment and everything else waits.

---

## 0. The claim

> **On unified memory, enabling an accelerator reserves memory that context needs. The accelerator
> makes some steps faster and other steps impossible. When the impossible ones escalate, the
> accelerator bought to reduce cloud spend increases it.**

Three properties make this worth the project's whole attention:

**It is mechanistically forced, not speculative.** Unified memory is one pool. A backend that
allocates from it leaves less for KV cache. That is arithmetic, not a hypothesis — only the
magnitude is open.

**It inverts the premise of on-device acceleration.** The industry case for an NPU is that local
work displaces cloud work. If the NPU's memory footprint forces long-context steps off-device, it
does the opposite.

**It is invisible without all three of this project's capabilities.** Unified memory needs a client;
accumulating context needs agent semantics; "impossible locally" only has a *price* if there is a
paid alternative. Every colliding paper has at most two.

## 1. Conflict audit — recorded per the Appendix A.2 standing rule

Searched 2026-08-04. **Five collisions, none fatal, each stated with its expansion.**

| Prior work | What it has | Why it does not close this |
|:--|:--|:--|
| [2511.22334](https://arxiv.org/pdf/2511.22334) — CPU/GPU/NPU edge backend comparison | All three backends, sequence-length effects, EDP | Measures **degradation at a given length**, not the **ceiling each backend permits**. No cloud, so exceeding a ceiling has no price. |
| [HeteroMosaic 2607.12839](https://arxiv.org/html/2607.12839v3) | Heterogeneous roofline, joint schedule + device allocation, unified-memory **contention** | Contention is interference *while running*. This is **reservation** — memory taken before any work, permanently lowering the ceiling. |
| KV-cache memory literature (KVQuant, KVDrive, and others) | Extensive context-versus-batch analysis | Datacenter, fixed GPU, batch-size framing. Not *which accelerator is enabled on a unified-memory client*. |
| Context-offloading frameworks (LangChain DeepAgents, Strands) | Offload tool results past a token threshold | Software workarounds that **prove the constraint binds**. None measures how the hardware target choice moves the boundary they route around. |
| [2607.05475](https://arxiv.org/abs/2607.05475) vs [2511.22334](https://arxiv.org/pdf/2511.22334) | CPUs beat NPUs on decode / NPUs dominate on EDP | **The literature contradicts itself.** Two 2026 papers, opposite conclusions. That disagreement is an opening, not an obstacle — it implies workload dependence, which is a crossover claim nobody has stated cleanly. |

**Not found in any search:** maximum usable context measured **as a function of which accelerator is
enabled**, and the cloud-spend consequence of that difference. Four searches is weak evidence of
absence; extend before any absence claim reaches a slide.

## 2. What gets measured

For each target configuration `S ⊆ {cpu-p, cpu-lpe, igpu, npu}`:

**2.1 — The capability frontier.** Binary-search the maximum context that completes, per
configuration. Report the ceiling, the failure mode at the boundary, and the memory reserved by
enabling each backend before any inference runs.

This is **memory-safe by construction** — the procedure is designed to find where it fails, so
failure is the measurement rather than a lost run. That is why this experiment can proceed on a
machine that has blocked ten agent pilots.

**2.2 — The speed frontier.** `R_prefill` and `R_decode` per target, across a prompt-length sweep.
Also `J/token`, since energy is where the literature disagrees.

**2.3 — Reservation attribution.** When a backend is enabled, where does the memory go? Weight
duplication, driver allocation, or activation buffers. **If weights are copied rather than shared,
the reservation could be gigabytes**; if zero-copy holds on unified memory, it could be negligible.
Nobody publishes this and the answer determines whether the effect is large or nil.

## 3. The replay

Over sealed trajectories with per-step context and token counts:

```
infeasible(step, S)  =  context(step) > max_context(S)
too_slow(step, S)    =  min over feasible targets of t_pred > D
escalated(step, S)   =  infeasible ∨ too_slow
cloud_spend(S)       =  Σ price(escalated steps)
```

**Decompose escalation into necessity and choice.** Escalation-by-necessity is the new quantity —
it exists only because capability is finite, and it is invariant to the deadline. No routing policy
can recover it.

## 4. Pre-registered predictions

| | Prediction | Falsified if |
|:--|:--|:--|
| **P1** | Enabling an accelerator measurably reduces maximum usable context | reduction < 5% with CI excluding 15% |
| **P2** | **For at least one target, capability loss exceeds speed gain, so cloud spend *increases* when the accelerator is enabled** | cloud spend falls or is unchanged for every target |
| **P3** | The sign of ΔCloud-spend depends on the workload's context growth rate | sign invariant across workload profiles |
| **P4** | Escalation-by-necessity is a material fraction of all escalation at realistic context | < 5% of escalations are capability-forced |
| **P5** | The NPU/CPU throughput ordering is workload-dependent, reconciling 2607.05475 and 2511.22334 | one target wins across every step type and length |

**P2 is the headline.** P3 is the DSE justification — a sign that flips with workload cannot be
reasoned to and must be searched. P5 is free: the two papers disagree, and a proper crossover
measurement explains why.

## 5. Why each outcome is worth having

**P2 holds** → *"the accelerator you bought to cut cloud spend increases it."* Inverts the on-device
acceleration premise, quantified, with a mechanism.

**P2 fails, P1 holds** → accelerators cost context but the speed gain dominates. Still novel — the
capability/speed trade is measured for the first time, and the crossover point is a design number.

**P1 fails** → reservation is negligible on this stack, zero-copy holds, and the whole line is dead
in a day for the price of a binary search. **Cheap to kill, which is why it goes first.**

## 6. Cost

iGPU and NPU bring-up — M4, currently partial with neither path exercised. Three documented defects
to handle rather than rediscover:

- NPU + INT8 weight-only IR: accepted at construction, uncatchable `0xC0000005` at `generate()`
  (openvino#35641). Assert INT4 first.
- NPU dynamic shapes (openvino#34617): set `MAX_PROMPT_LEN` and `NPUW_LLM_PREFILL_CHUNK_SIZE`
  explicitly, record both.
- Panther Lake iGPU `CL_INVALID_WORK_GROUP_SIZE` (openvino#34390): per-model smoke test, classify
  `UNSUPPORTED`, never retry-loop.

`preflight()` returns `SUPPORTED | UNSUPPORTED(reason) | DEGRADED(reason)` without crashing. **An
unsupported target is a data point** — and on the capability frontier, an unsupported target is
precisely the finding.

Everything after bring-up is microbenchmarks and offline replay. No agent trajectories on the
laptop, no memory wall.

## 7. What this does not claim

Not a scheduling contribution — HeteroMosaic and Agent.xpu own that. Not a KV-cache optimization —
that literature is deep and settled. Not a routing policy.

**It is a statement about what a target set costs**, made possible by having a priced alternative to
local execution. That is the one thing none of the colliding work has.
