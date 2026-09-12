# E-TARGET — target-aware routing versus binary local/cloud

**Pre-registration draft.** Not yet authorized. Predictions and thresholds freeze before the first
replay.

---

## 0. The claim

Every routing system in the positioning table decides **local or cloud** — one local option, one
boundary. A client SoC has **four on-die targets plus cloud**, each with different throughput,
energy, memory footprint, and *feasibility*.

> **Binary routing collapses a frontier to a point. It escalates work that a local target it does
> not consider could have handled.**

Three claims, in increasing strength:

**T1 — False escalation.** A measurable fraction of binary-routing escalations are avoidable: the
step meets its deadline on some local target other than the default.

**T2 — Target-aware routing dominates.** At equal latency, N-way routing reduces cloud spend
materially, with no accuracy cost — the work runs locally on the same model, just on different
silicon.

**T3 — The optimal target changes mid-trajectory.** Context growth crosses the NPU's statically
declared `MAX_PROMPT_LEN`, and accelerator use consumes unified memory that context also needs. So
the feasible target set **shrinks as the trajectory progresses**, and any static assignment is wrong
by construction.

T3 is the non-stationarity claim of H8, driven by a deterministic architectural boundary rather than
by stochastic thermal drift — which makes the crossing point computable in advance rather than
merely observed.

## 1. Why this is available while E-FILTER is blocked

```
per-target R_prefill, R_decode, J/token, memory   ← microbenchmarks, short prompts, memory-safe
per-step token counts from real trajectories      ← already sealed: 1a0166b9, 51 steps
the N-way routing counterfactual                  ← offline replay, no machine time
```

No long agent trajectories on the laptop. The memory wall that has blocked ten pilots does not
enter, because the expensive object is a per-target throughput table, not a trajectory.

## 2. What must be measured — the target table

For each target in {`cpu-p`, `cpu-lpe`, `igpu`, `npu`} and the cloud:

| Quantity | Notes |
|:--|:--|
| `R_prefill(target)` | tok/s, measured across a prompt-length sweep — it may not be constant |
| `R_decode(target)` | tok/s, at short context |
| `J_per_token(target)` | prefill and decode separately |
| `memory_footprint(target)` | **including memory the accelerator reserves from the unified pool** |
| `max_prompt_len(target)` | NPU: statically declared. Others: measured feasibility limit |
| `feasible(target, model, quant)` | INT4/INT8/FP16 support; NPU is INT4-only on this stack |

**The memory column is not incidental.** Using an accelerator reduces the context length available
to the same workload. That is the coupling that makes this a design-space problem rather than a
scheduling one.

**Known defects to handle, not rediscover:**

- NPU + INT8 weight-only IR: accepted at construction, then uncatchable `0xC0000005` at
  `generate()` (openvino#35641). Assert INT4 before constructing an NPU pipeline.
- NPU dynamic shapes (openvino#34617): set `MAX_PROMPT_LEN` and `NPUW_LLM_PREFILL_CHUNK_SIZE`
  explicitly; record both.
- Panther Lake iGPU `CL_INVALID_WORK_GROUP_SIZE` on models that work on Lunar/Meteor Lake
  (openvino#34390). Per-model smoke test; classify `UNSUPPORTED`, never retry-loop.

`preflight()` returns `SUPPORTED | UNSUPPORTED(reason) | DEGRADED(reason)` without crashing. **An
unsupported cell is a data point.**

## 3. The replay

Over sealed trajectories with per-step `prompt_tokens` and `n_out_pred`:

```
BINARY     assigned = cpu-p if t_pred(cpu-p) ≤ D else cloud
N-WAY      feasible = { t : t_pred(t) ≤ D and feasible(t, step) }
           assigned = argmin over feasible of chosen objective, else cloud
```

Run N-way under three objectives separately — **latency**, **energy**, **cloud cost** — because they
will not agree, and their disagreement is the frontier binary routing collapses.

Sweep `D` over the same derived grid E-FILTER uses.

## 4. Endpoints

```
T1   false_escalation_rate(D) = |escalated_binary ∩ feasible_locally_elsewhere| / |escalated_binary|
T2   Δcloud_spend(D) at matched p95 latency ;  Δenergy ;  Δlatency at matched spend
T3   feasible target set as a function of step index — the shrinkage curve
     the context at which each target drops out, and why (speed, MAX_PROMPT_LEN, or memory)
```

Plus the crossover surface: **which target wins as a function of the step's prefill:decode ratio.**
That is C10, obtained as a by-product.

## 5. Pre-registered predictions

| | Prediction | Falsified if |
|:--|:--|:--|
| **P-T1** | `false_escalation_rate ≥ 15%` at the material deadline | < 5% with CI excluding 15% |
| **P-T2** | N-way cuts cloud spend ≥ 20% at matched p95 latency | < 10%, CI excluding 20% |
| **P-T3** | The feasible target set shrinks monotonically with step index, and ≥1 target drops out mid-trajectory | the set is invariant across the trajectory |
| **P-T4** | Latency-optimal and energy-optimal targets disagree on ≥20% of steps | they agree on >95% |
| **P-T5** | Enabling an accelerator measurably reduces maximum usable context | no measurable reduction |

P-T4 is the one that makes it a *frontier* rather than a ranking. P-T5 is the coupling that makes it
a DSE problem — if using the NPU costs context, then target choice and capacity are not separable.

## 6. What would make this uninteresting

**If one target dominates everywhere**, N-way collapses back to binary with a different default and
there is no frontier. Report it plainly — that is a clean negative and it saves the field the
effort of building target-aware routers.

**If the NPU and iGPU are simply slower than CPU-P on this workload**, T1 goes to zero. Published
work already reports CPUs outperforming NPUs on memory-bound decode
([2607.05475](https://arxiv.org/abs/2607.05475)), so this is a live possibility for the *decode*
side. The prefill side is where the NPU should win, and prefill is where binary routing escalates.

## 7. Positioning

**Agent.xpu (2506.24045)** schedules across NPU and iGPU on a fixed SoC with **no cloud**, so
everything must work locally and it optimizes throughput under that constraint.

With a boundary the problem inverts: you can be **selective**. Use an accelerator only where it is
clearly better and escalate the rest. The alternative to "run on the NPU" is not "run on the iGPU" —
it is **"do not run locally at all."** That changes which local target is correct, and it is a
question a system without a cloud fallback structurally cannot ask.

State this explicitly in related work. It is the cleanest separation the project has.

## 8. Audit before claiming

Search specifically for: N-way local target selection **with** a cloud escalation option in agent
routing; target-aware routing where the feasible set varies within a trajectory; and any prior
report of accelerator memory reservation reducing usable context. Record in Appendix A.2 per the
standing rule.

The individual pieces exist — Agent.xpu for on-die scheduling, the router literature for the
boundary. **The composition is the claim.** Verify nobody has composed them before saying so.

## 9. Cost

iGPU and NPU bring-up — M4 is partial with neither path exercised. Backend integration with three
known defects, all documented above. Microbenchmarks are short-prompt and memory-safe.

The trajectories already exist. The replay is offline and free.
