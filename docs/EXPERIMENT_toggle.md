# E-TOGGLE — hardware state as a routing action

**Pre-registration draft. The project's single focus.** Supersedes `EXPERIMENT_capability_cost.md`
and `EXPERIMENT_net_target_value.md`.

---

## 0. The claim

On unified memory, compute and context draw from **one pool**. A backend that is enabled reserves
memory whether or not it is executing. Therefore:

> **Enabling an accelerator is spending context. Disabling it is buying context.**
>
> **The routing action space includes hardware state, not just target assignment.**

And the policy consequence, which no static configuration achieves:

> **Enable the accelerator early in a trajectory for speed. Disable it late for capacity. The
> optimal hardware configuration changes within a single agent session, deterministically, as
> context accumulates.**

Every router in the surveyed literature assigns *work to targets*. **None changes the target set at
runtime to convert compute into capacity.** That is the gap.

## 1. Novelty audit — 12 queries, 2026-08-04

Recorded per the Appendix A.2 standing rule. **Realm-by-realm.**

### Speed — closed

| Work | Covers |
|:--|:--|
| [HeteroMosaic 2607.12839](https://arxiv.org/html/2607.12839v3) | heterogeneous roofline, joint schedule + device allocation, unified-memory contention, DVFS, 3 platforms |
| [Agent.xpu 2506.24045](https://arxiv.org/html/2506.24045) | NPU/iGPU affinity, prefill/decode disaggregation, client SoC |
| [HeteroLLM 2501.14794](https://arxiv.org/html/2501.14794v1), [BIDENT 2606.05271](https://arxiv.org/html/2606.05271) | heterogeneous accelerator mapping on mobile SoCs |
| MORI, IdleSpec, SPORK | idle-window exploitation, speculative planning |
| AHASD, collaborative speculative inference | heterogeneous and cross-boundary speculative decoding |
| [Latency prediction for NPU 2606.18042](https://arxiv.org/pdf/2606.18042) | per-target latency modelling |
| Shared-memory contention literature | **two units concurrently reach ~60 GB/s of a 68 GB/s SoC maximum**; bandwidth-bound operators gain little from added compute |

**Verdict: do not enter.** The speed argument for heterogeneity is measured and bounded by groups
with better hardware access.

### Cost — headline occupied

| Work | Covers |
|:--|:--|
| Practitioner hybrid-routing analyses, [2509.18101](https://arxiv.org/html/2509.18101v1) | **60–80% cloud-spend reduction**, break-even economics — all assuming discrete or large dedicated memory |
| MAUI-era offloading literature | offload-to-save-energy, settled since ~2010 |
| [Permission Denied 2608.02670](https://arxiv.org/html/2608.02670) | policy-graded agent evaluation: 18.3 pt success loss, **167.3% cost inflation** under strict egress |

**Verdict:** the main claim is a blog post. The optimal-subset framing is open but derivative of the
capability finding.

### Capability — open

| Work | Why it does not close this |
|:--|:--|
| [KAIROS 2604.16682](https://arxiv.org/pdf/2604.16682) | *closest hit* — context outgrowing drain into a thrashing regime. But **serving-side**, attributed to frequency-induced compute bottlenecks, not to backend memory reservation, and no toggling |
| [2511.22334](https://arxiv.org/pdf/2511.22334) | CPU/GPU/NPU comparison; measures **degradation at a length**, never the **ceiling a backend permits** |
| [Quant.npu 2605.20295](https://arxiv.org/html/2605.20295v1) | NPU quantization constraints documented; the **routing consequence** of INT4-only is not |
| KV-cache literature (KVQuant, KVDrive, Oaken) | datacenter, fixed GPU, batch-size framing |
| Context-offloading frameworks | move context *out*; never free a backend to make room |
| Contention literature | measures interference during concurrent execution; never proposes **disabling** a unit for capacity |

**Not found in any query:** maximum usable context measured as a function of which backend is
enabled; backend disablement as a capacity action; a routing policy with hardware state in its
action space.

Twelve queries is stronger evidence than this project has previously had, but still not proof.
Extend before any absence claim reaches a slide.

## 2. Measurements

**2.1 — The capability frontier.** Binary-search maximum context that completes, for each backend
configuration `S ⊆ {cpu-p, cpu-lpe, igpu, npu}`. Report the ceiling and the failure mode at the
boundary.

**Memory-safe by construction** — the procedure finds where it fails, so failure is the
measurement. This is why it proceeds on a machine that has blocked ten agent pilots.

**2.2 — Reservation attribution.** Where does the memory go when a backend is enabled — weight
duplication, driver allocation, or activation buffers? **If weights are copied rather than shared,
reservation could be gigabytes; if zero-copy holds on unified memory, negligible.** This single
answer decides whether the effect is large or nil, and it is not published.

**2.3 — The switching cost.** Time to unload a backend and **verify the memory is actually
reclaimed**, and to reload and re-warm it. Model load measured 3.1 s previously; reclamation may be
slower or incomplete.

This determines the *granularity* at which toggling is a viable action — per step, per phase, or
per session. It is the parameter that makes the policy implementable or not.

**2.4 — The speed frontier.** `R_prefill`, `R_decode`, `J/token` per configuration.

## 3. The policy comparison

Three policies over sealed trajectories with per-step context:

```
ALWAYS-ON    all backends enabled for the whole trajectory
ALWAYS-OFF   cpu-p only
TOGGLE       enable accelerators while context < threshold, disable above it
```

Report for each: steps completed locally, steps escalated by **necessity** (context exceeds ceiling)
versus by **choice** (too slow), total cloud spend, p95 latency, energy.

**Escalation-by-necessity is the quantity the toggle policy exists to reduce.** It is invariant to
the deadline; no latency-based router can touch it.

## 4. Pre-registered predictions

| | Prediction | Falsified if |
|:--|:--|:--|
| **P1** | Enabling a backend measurably reduces maximum usable context | reduction < 5%, CI excluding 15% |
| **P2** | Switching cost is small enough to permit at least **per-phase** toggling | reclamation exceeds 30 s or is incomplete |
| **P3** | **TOGGLE strictly dominates both static policies** — fewer necessity-escalations than ALWAYS-ON, lower latency than ALWAYS-OFF | TOGGLE is dominated by, or equal to, some static policy |
| **P4** | The toggle threshold is computable in advance from `max_context(S)` and the context growth curve | the empirical optimum diverges from the computed one beyond CI |
| **P5** | Cloud spend under ALWAYS-ON exceeds ALWAYS-OFF for context-heavy workloads | ALWAYS-ON is cheaper at every context profile |

**P3 is the headline.** A policy that changes hardware state beating both static configurations is
the entire claim — it means the action space everyone uses is incomplete.

**P4 makes it a design rule rather than a search result.** If the threshold is computable, it ships
as a lookup, and the DSE tool emits it.

**P5 is the provocative one:** the accelerator increases cloud spend.

## 5. Every outcome is worth having

**P3 holds** → *"a hybrid router should be able to turn hardware off; disabling an accelerator is a
routing action."* A new action in the routing action space, with a hardware mechanism and a
computable rule.

**P3 fails, P1 holds** → backends cost context but toggling cannot exploit it, most likely because
switching is too slow. **The switching cost then becomes the finding**: *"the capacity gain exists
but is unreachable at agent timescales,"* which is a concrete argument for runtime support that does
not exist.

**P1 fails** → reservation is negligible, zero-copy holds, and the line dies in a day for the cost
of a binary search. **The cheapest test is the decisive one**, which is the property every previous
direction lacked.

## 6. Cost

iGPU and NPU bring-up — M4, partial with neither path exercised. Three documented defects to handle
rather than rediscover: NPU + INT8 IR (openvino#35641 — assert INT4 first), NPU dynamic shapes
(openvino#34617 — set `MAX_PROMPT_LEN` and chunk size explicitly), Panther Lake iGPU
`CL_INVALID_WORK_GROUP_SIZE` (openvino#34390 — per-model smoke test).

`preflight()` returns `SUPPORTED | UNSUPPORTED(reason) | DEGRADED(reason)` without crashing. **On a
capability frontier an unsupported target is the finding.**

After bring-up: microbenchmarks and offline replay. No agent trajectories on the laptop.

## 7. What this does not claim

Not a scheduling contribution — HeteroMosaic, Agent.xpu, HeteroLLM and BIDENT own that, and the
shared-bandwidth contention literature already bounds it. Not that local inference saves money,
which is a blog post. Not a KV-cache optimization.

**It claims the routing action space is incomplete, and that on unified memory the missing action is
turning hardware off.**
