# Candidate studies — numbers that would make hardware a design decision

Working catalog. Not pre-registered. Nothing here enters a pitch or an abstract until it clears
the AUDIT gate (Appendix A.2 standing rule, AM-025).

---

## 0. What makes a number valuable here

A number lands with a DSE audience when it does one of four things. Ranked by how hard they are
to argue with:

1. **Shows non-monotonicity** — more hardware makes some objective worse. Kills "just buy the
   bigger part" and forces search.
2. **Shows rank inversion** — the ordering of designs depends on something outside the hardware.
   Means "better machine" is not a total order.
3. **Shows an input is endogenous** — a quantity you'd use to size the hardware is itself a
   function of the hardware. Kills open-loop sizing entirely.
4. **Shows a hard floor or cliff** — a configuration below which the workload is infeasible or
   economically irrational.

A number that only shows "this hardware is faster than that hardware" does none of these and
justifies a purchase, not a tool.

**Two directions, and the second is the underexplored one:**

- **Direction A — hardware changes what hybrid execution does.** The constraint claim.
- **Direction B — hybrid execution changes what hardware you should build.** The co-design claim.
  Direction B is where the boundary earns its keep, because every source in AUDIT-001 optimizes a
  local system in isolation.

---

## 1. Direction B — the umbrella thesis

> **A hybrid client is not a local-only client with some work removed. It is a different hardware
> design target.**

Four independent mechanisms, each pushing the optimal design point in a direction nobody has
measured. If two of the four hold, that is a paper by itself, and it is the strongest available
answer to "why does the boundary matter to a hardware person."

| | Mechanism | Design consequence |
|:--|:--|:--|
| CS-01 | Escalation **filters the workload** the local silicon sees | Different arithmetic intensity distribution → different balance point |
| CS-02 | Escalation **creates idle windows** on the local accelerator | Lower duty cycle → smaller accelerator is correct |
| CS-03 | Escalation **truncates KV lifetimes** | Different memory residency distribution → different hierarchy |
| CS-04 | Escalation **permits thermal recovery** | Higher sustainable peak envelope → different thermal design point |

---

## 2. The studies

### CS-01 — The workload is endogenous to the hardware ★★★

**Number:** the shift in the local workload's arithmetic-intensity distribution between local-only
and hybrid execution. *"Escalation removes the top X% of the intensity distribution and moves the
local mean by Y."*

**Why it matters.** Escalation is triggered by predicted latency; latency correlates with size;
so the steps that escalate are systematically the *large* ones. What remains local is a filtered
subset. **The hardware sees a different workload than the application generates** — and the filter
is set by the policy, which is set by the hardware.

This is selection bias in the workload, induced by the silicon. It means every workload
characterization in AUDIT-001 (Agent Memory, 2605.26297) characterizes the *unfiltered* workload,
which is not what a hybrid client's silicon experiences. You cannot size local hardware from
application workload statistics — you must size it from the post-escalation residual, which
depends on the thing you are trying to choose.

**This is criterion 3 in its purest form, and it is the formal argument that SEAM must exist.**
Open-loop sizing is not merely inaccurate here; it is ill-posed.

**Feasibility:** needs the agent harness and cloud backend. No second platform. No confinement.
**Audit:** required before any novelty claim. Adjacent to nothing found so far, which is
suspicious — search hard.

### CS-02 — Hybrid execution strands the accelerator ★★★

**Number:** local accelerator duty cycle, hybrid vs local-only, at matched task completion.
*"Hybrid execution reduces NPU utilization to X%."*

**Why it matters.** Every escalated step is a cloud round-trip during which the local accelerator
does nothing. If hybrid drops NPU duty cycle to a third, you have specified an accelerator you use
a third of the time — and **the correct NPU size for a hybrid client is smaller than for a
local-only client.** That is a direct BOM consequence of the boundary, in the units an architect
buys in.

Distinguish carefully from MORI: those are *tool-call* idle windows, created by the environment.
These are *escalation* windows, created by the partition policy — which is a design variable.

**Feasibility:** harness + cloud. Telemetry already planned.
**Audit:** required. MORI is close; the distinction must be stated precisely.

### CS-03 — Escalation truncates KV lifetimes ★★

**Number:** fraction of allocated KV discarded before reuse; residency lifetime distribution,
hybrid vs local-only.

**Why it matters.** MemExplorer designs memory for steadily growing residency. Under hybrid the
residency pattern is **punctuated** — grow, escalate, invalidate or hold. A memory hierarchy
designed for the first is wrong for the second. This is the concrete form of "hybrid is a
different design target" in the subsystem Callie's field cares most about.

**Feasibility:** harness. Couples to H11 (KV disposition), so it comes nearly free with S17.

### CS-04 — Hybrid runs cooler, so it can be specified hotter ★★

**Number:** throttle fraction and sustained package temperature, hybrid vs local-only, at matched
completion. *"Hybrid execution reduces time-in-throttle by X%, permitting a Y W higher sustained
envelope for the same thermal budget."*

**Why it matters.** Thermal is the binding constraint on sustained on-device inference
(2603.23640). If the partition policy creates recovery windows, **the thermal design point is a
function of the policy** — which is a co-design statement, not a characterization.

Survives the MORI objection: escalation gap duration is a cloud round-trip, far more predictable
than arbitrary tool latency.

**Feasibility:** harness + thermal instrumentation (M2.3). Runs in the axis regime, not the
confound regime.

### CS-05 — The co-design gain ★★★

**Number:** objective gap between jointly optimal *(h\*, π\*)* and sequentially optimal *h\** at
fixed vendor policy. *"Taking the routing policy as given costs one NPU per unit."*

**Why it matters.** **This is the DSE justification itself.** If joint co-design beats sequential
by a wide margin, the tool is necessary. If it doesn't, it isn't. Run it early precisely because
it can kill the project — that is what makes it worth running.

**Feasibility:** needs the surrogate, so it is late. But a two-point version (one alternative
policy, two hardware configs) is available much earlier and gives the sign.

### CS-06 — The economic floor ★★★

**Number:** the local configuration below which local-first loses to cloud-only on total cost of
ownership. *"Below X GB and Y W, on-device agentic execution is economically irrational for this
workload — you pay for the silicon and still pay the API."*

**Why it matters.** A hard floor (criterion 4), stated in money, immediately legible to industry
and to a committee. It also inverts nicely: above the floor, the exchange rate between silicon
dollars and API dollars becomes the sizing curve.

**Feasibility:** harness + cost ledger, which is already externally verified (11/11 exact).

### CS-07 — Required silicon as a function of the network ★★

**Number:** minimum local configuration meeting a target, as a function of RTT percentile.
*"At P95 RTT of 400 ms you need 2× the local silicon you need at 50 ms."*

**Why it matters.** A sizing rule with a *network* parameter is a genuinely cross-domain result
and it is unavailable to anyone without the boundary. Also the most defensible form of "hybrid
changes hardware requirements" — the causal path is short and undeniable.

**Feasibility:** harness + network shaping. Cheap to add once escalation works.

### CS-08 — Privacy sets a capability floor ★★

**Number:** the local capability floor imposed by a no-egress class. *"A no-PII policy requires X
GB and Y TOPS locally, independent of any performance target."*

**Why it matters.** Steps that cannot escalate set a hard floor that no amount of cloud budget
relieves. It is the cleanest example of a *non-performance* requirement driving silicon, and it is
the one industry asks about first.

### CS-09 — Accelerators cost context ★★★ (cheapest high-value study available)

**Number:** reduction in maximum usable context when the NPU or iGPU path is enabled, from unified
memory contention and driver reservations. *"Enabling the NPU costs X thousand tokens of context."*

**Why it matters.** Deeply counterintuitive and it appears in no datasheet. It says accelerators
have a **capacity price, not just an area price** — on a unified-memory client, using an
accelerator directly reduces how long a conversation can be. That is a real design tension between
two of the three channels, measurable on one machine.

**Feasibility: highest of anything here.** No agent harness, no cloud, no second platform, no
confinement mechanism. Platform A alone.

### CS-10 — Hardware-induced cascade amplification ★★

**Number:** cascade factor as a function of local capability. *"Each percentage point of local
step-failure rate costs N additional downstream steps."*

**Why it matters.** Crosses H4 with hardware. If weaker silicon raises failure rate and each
failure multiplies downstream work, then hardware shortfalls are **amplified, not linear** — the
cost of under-specifying silicon is superlinear. That is a strong argument for careful sizing.

### CS-11 — Concurrency capacity is policy-dependent ★★

**Number:** maximum concurrent agents at target QoS, local-only vs hybrid.

**Why it matters.** Under hybrid, concurrent agents either escalate together (network burst) or
stay local together (memory contention). The device's agent capacity is therefore a function of
the partition policy, not of the silicon alone. Extends H9 across the boundary.

### CS-12 — Rank inversion across policy ★★★

**Number:** Kendall's τ on hardware-configuration ordering across the deadline grid; the deadline
at which the ordering flips.

**Why it matters.** Criterion 2. *"Which machine is better"* has no answer independent of the
policy. For a DSE audience this is the cleanest possible statement that the space requires search.
This is H2 and it is already the blueprint's headline — listed here because it belongs in the
ranking.

### CS-13 — The escalation elasticity and its knee ★★

**Number:** ∂(local execution fraction)/∂(throughput), and the location of the knee.

**Why it matters.** Because escalation is a threshold, hardware investment should buy nothing,
then a great deal, then saturate. **Locating that knee is the sizing curve**, and its shape is the
economic content of the project. Directly feeds CS-06.

### CS-14 — The Pareto trade-off headline ★★★

**Number:** at identical tasks, seeds and policy, changing only the sustained power limit changes
cloud spend by X% and accuracy by Y points, **in opposite directions**.

**Why it matters.** Criterion 1, and the recommended first headline. Proves hardware moves the
objectives, that it moves them against each other, and therefore that the part cannot be chosen by
reasoning. Use **power cap** as the axis — quantization confounds model quality, core type is
blocked by the A0 failure.

**Feasibility:** harness + cloud. No confinement, no second platform.

### CS-15 — Memory versus compute at fixed budget ★★

**Number:** the optimal split of a fixed area/power budget between memory capacity and accelerator
width, and how that optimum moves with workload and network.

**Why it matters.** This is the OEM's actual question and it is stated in Callie's native units.
It is also the natural home for the elasticity results (CS-13) and the capacity findings.

### CS-16 — Quantization support as a silicon decision ★

**Number:** accuracy and throughput cost of INT4-only support versus INT4+INT8, at fixed target.

**Why it matters.** NPU × INT8 is infeasible on this stack, so precision support is a real
capability constraint with a measurable cost. Modest ceiling but very cheap.

### CS-17 — Cross-target energy per token at equal quality ★★

**Number:** joules per token by execution target and phase; whether race-to-idle on P-cores beats
LP-E cores.

**Why it matters.** Energy is one of the five objectives and the one most often asserted without
measurement. Race-to-idle inverting the naive "efficiency cores are efficient" expectation would
be a clean, quotable, hardware-native result.

### CS-18 — The HLS gating engine ★★

**Number:** routing decision latency in hardware versus software, and the resulting shift in the
amortization threshold *G*.

**Why it matters.** H12. Callie's home turf, and the differentiator no competing group can
replicate. Also the only place the project produces designed silicon rather than selected silicon.

### CS-19 — Open-loop sizing error ★★★

**Number:** size the hardware from the application's workload statistics, then measure what is
actually required under hybrid. Report the error. *"Sizing from application workload
characteristics overestimates required local memory by X%."*

**Why it matters.** The direct payoff of CS-01, stated as a number a designer feels immediately.
It converts an epistemological point ("the input is endogenous") into an engineering error bar.
Strongest possible framing: **"here is how wrong you are if you do it the way everyone currently
does it."**

### CS-20 — Cross-boundary phase splitting ☆

**Number:** the bound at which splitting prefill and decode *across the network* becomes viable.

**Why it matters.** Agent.xpu splits phases on-die. Splitting across the boundary requires shipping
KV state, so it is probably infeasible — but the *bound* is a number, and a measured negative
closes a direction that reviewers will otherwise ask about.

**Audit:** high collision risk. Search before investing.

---

## 3. Priority

**Run first — cheapest per unit of insight, no blocking dependencies:**

- **CS-09** (accelerators cost context) — Platform A only, no harness, no cloud. Runnable now.
- **CS-17** (energy per token by target) — instrument track, already scoped as M2.5.

**The headline for Callie — run as soon as the harness lands:**

- **CS-14** (Pareto trade-off, power-cap axis) — the number that proves hardware is a decision
  variable rather than a constraint.
- **CS-01 → CS-19** (endogenous workload → open-loop sizing error) — the strongest intellectual
  result available and the formal justification for the whole tool.

**The one that can kill the project, so run it early:**

- **CS-05** (co-design gain). If sequential sizing is nearly as good as joint, there is no tool
  here. Better to know in month two than month twelve.

**The umbrella paper:**

- **CS-01 through CS-04** together support *"a hybrid client is a different hardware design
  target."* Any two of the four carry it.

---

# HIGH-RISK TIER — bets that could break the field open or come back boring

The studies above argue that current *method* is biased. This tier argues that the industry is
**optimizing the wrong resource.** Higher ceiling, higher chance of a dull result. Each is
structured so the dull result is still worth having.

## CS-21 — The accelerator Amdahl ceiling ★★★★ *(top pick)*

**Number:** the maximum end-to-end agent speedup available from an *infinitely fast* accelerator.

**The claim, if it lands:**

> **AI PCs are marketed on TOPS. TOPS addresses the phase that isn't the bottleneck.**

**Why it's dangerous.** Agent wall time decomposes into prefill compute, decode compute, local
tool execution, tool wait, and orchestration overhead. An NPU touches the first two and nothing
else. Worse, decode is bandwidth-bound, so an NPU barely helps there either — it genuinely
accelerates only prefill.

Amdahl does the rest. If prefill is 15% of agent wall time, an **infinitely fast NPU delivers
1.18× end to end.** Not a slow NPU. Not a badly-scheduled one. Infinite. That is a hard ceiling on
an entire product category's headline feature, computed from a decomposition anyone can reproduce.

**Why it is robust to the thing that threatens E-FILTER.** The caching fork cuts both ways here
and both ways lead to the same place:

- **Cache holds** → prefill is small → decode dominates → decode is bandwidth-bound → the answer
  is **memory bandwidth**, not TOPS.
- **Cache evicts** → the step re-prefills constantly → prefill is large → but eviction happened
  because the machine ran out of **memory capacity**.

Whichever regime you land in, the binding resource is memory. Nobody sells an AI PC on memory
bandwidth. **Both roads lead to the same conclusion, which is rare and worth exploiting.**

**Experiment.** Instrument a local agent run with per-phase timing: prefill, decode, tool-local,
tool-wait, orchestration. Compute three ceilings — infinite prefill compute, infinite decode
compute, infinite memory bandwidth. Report all three, at several context lengths, cache on and
off.

**Output:** three numbers that bound what *any* accelerator can do for this workload. Not a
measurement of a part — a bound on the category.

**Feasibility:** very high. Local only. No cloud, no confinement mechanism, no second platform, no
NPU bring-up required — the point is that you compute the ceiling without needing the accelerator.
Shares instrumentation with E-FILTER; run them off the same logs.

**Risk:** if prefill turns out to dominate, the NPU story is fine and the result is ordinary. That
outcome is still publishable as "here is when the accelerator earns its place," and it still
produces the decomposition nobody has.

**Audit:** required. Amdahl analyses of LLM inference exist; agent-level decompositions including
tool wait are the part to verify.

## CS-22 — Standard DSE evaluation inverts the answer ★★★

**Number:** fraction of design pairs whose ranking flips between single-shot evaluation (standard
practice) and drift-aware sustained evaluation.

**The claim:** *"Conventional DSE methodology returns the wrong ordering on X% of design pairs for
this workload class."*

**Why it's dangerous.** This is an attack on DSE practice from inside DSE — Callie's home field.
Every tool in this space evaluates a design point once and treats the result as the point's value.
We have already established the objective drifts during evaluation (H8, H13). If drift is large
enough to invert rankings, then **every published DSE result on agentic workloads is
methodologically suspect**, including the ones we would otherwise cite approvingly.

**Experiment.** Take N design points. Evaluate each the standard way — one short measurement — and
again under sustained, thermally-settled, drift-aware measurement. Kendall τ between the two
orderings.

**Why it's a good bet:** the null is also useful. τ ≥ 0.9 means single-shot evaluation is safe
here, which is a methodological green light the field would use.

**Feasibility:** local only, no cloud. Needs thermal instrumentation (M2.3).

## CS-23 — The one-agent machine ★★★

**Number:** maximum concurrent agents at target QoS on 16 GB, at realistic agent context lengths.

**The claim:** *"A 16 GB AI PC runs exactly one agent."*

**Why it's dangerous.** The entire "your PC is an agent platform" narrative assumes plurality —
background agents, proactive monitoring, several assistants. At 144 KB/token, two agents at 32K
context is 9.4 GB of KV against a 12.5 GB budget before weights. If the honest answer is one, the
product category's premise is wrong.

**Risk:** partially occupied. 2603.04428 reports 3 agents at 8K on an M4 Pro with a 10.2 GB
budget. Our contribution would be realistic *agent* context lengths rather than 8K, and the QoS
threshold rather than mere fit. **Audit hard before claiming this one.**

## CS-24 — Privacy sets the floor, not performance ★★

**Number:** fraction of agent steps touching data a stated privacy policy forbids sending, and the
local capability floor that fraction implies.

**The claim:** *"On-device AI hardware requirements are set by what cannot leave, not by what is
slow."*

**Why it's dangerous.** It inverts the entire framing. Everyone sizes for latency and throughput.
If 40% of steps are egress-forbidden, that fraction must run locally at *any* speed, and the floor
is set by capability rather than performance. No amount of cloud budget relieves it.

**Risk:** partly definitional — the answer depends on the privacy policy assumed. Mitigate by
reporting a curve across policy strictness rather than a single number.

## CS-25 — Six ways to measure this wrong ★★

**Number:** the defect count and the magnitude of error each would have produced.

**The claim:** *"We attempted standard on-device LLM measurement practice and found six defects
that produce clean-looking wrong results."*

Already accruing as C9: `PCORE_ONLY` falling through while `ECORE_ONLY` binds, a corrupt IR that
loads and generates, battery counters with an 8% systematic between estimators, a charging taper
that made throughput appear to increase, CRLF making committed hashes platform-dependent, UTF-16LE
probes making three provenance tests vacuous.

**Why it matters:** methodology papers are cited by everyone who follows. Weak as a standalone
claim, strong as the credibility spine under a real finding.

---

# MICROARCHITECTURAL TIER — datapath consequences of the boundary

The dequantization finding works because it explains a number by naming a mechanism inside the
datapath. This tier looks for more of those, and asks specifically what hybrid execution does to
them.

## CS-26 — The balance mismatch: on unified memory, the NPU and the CPU are the same engine ★★★★★

**The arithmetic, from published specs and our own measured intensity:**

```
workload arithmetic intensity, INT4 batch-1 decode          ~4    FLOP/byte
CPU machine balance      (~300 GFLOP/s ÷ ~120 GB/s)         ~2.5  FLOP/byte
NPU machine balance      (50 TOPS      ÷ ~120 GB/s)        ~417   op/byte
```

Batch-1 decode has **zero weight reuse** — every weight byte is read once and used once. That is
not an implementation weakness; it is fixed by the algorithm and the batch size, and no datapath
can change it.

So the CPU sits almost exactly at the workload's operating point, and **the NPU is ~100× off**.
The NPU carries roughly 167× the CPU's compute and draws on **the same memory pool.** On a
bandwidth-bound workload, that compute is unusable.

**The prediction — sharp, falsifiable, and cheap:**

> **NPU and CPU decode throughput should be approximately equal**, because both are limited by the
> same memory and the workload cannot use the NPU's compute.

**Both outcomes are valuable.** If they match, the accelerator's compute is dead weight for agent
decode and the entire TOPS-based value proposition fails on this workload class. If the NPU wins
substantially, then its advantage is **not compute** — it is a private buffer, a better memory
path, or reduced contention, and identifying which is itself a microarchitectural finding nobody
has published.

**And here is where hybrid execution turns it lethal.** Escalation removes long-prefill steps —
the compute-bound ones. What stays local is decode, the zero-reuse bandwidth-bound regime:

> **Hybrid execution filters the local workload toward exactly the regime where the accelerator
> cannot help. The routing policy determines what fraction of your accelerator is dead silicon.**

That is a microarchitectural consequence of a software boundary, it is quantifiable as a curve
against the escalation deadline, and it is unavailable to anyone without both sides.

**Feasibility:** the arithmetic is available today. The CPU-vs-NPU comparison needs NPU bring-up
(INT4 only, `MAX_PROMPT_LEN` set) but no cloud, no confinement mechanism, no second platform.

**Caveat that must travel with it:** the ~120 GB/s denominator is *derived*, not measured — it is
in Appendix A as unverified pending I5 (STREAM). Every ratio here inherits that. Run STREAM before
the number leaves the lab.

## CS-27 — Decompose the 29% ★★★★

We know INT4 achieves 29% of the derived bandwidth ceiling. We do not know **why**, and the two
candidate mechanisms have opposite design implications.

**Mechanism A — dequantization on the critical path.** Unpacking INT4 consumes shuffle/permute
issue slots that are not doing MAC work. Fix: a datapath with native INT4 operands.

**Mechanism B — KV access pattern.** Paged KV attention is a strided gather. On LPDDR with limited
banks that thrashes DRAM rows, so *achieved* bandwidth during attention is far below achieved
bandwidth during weight streaming. Fix: KV layout, not compute.

**Experiment:** measure achieved bandwidth separately in the weight-dominated phase and the
KV-dominated phase, at several context lengths. If attention-phase bandwidth is much lower, the
loss is layout, not dequantization — and **the whole "quantize harder" strategy is aimed at the
wrong half of the traffic.**

**Why it's a headline:** it converts our existing number from an observation into a mechanism, and
it tells an architect which structure to change. Cheap, local-only, and it strengthens a result we
already have.

## CS-28 — Quantization and context contend ★★★

**Prediction:** the INT4/INT8 advantage **compresses toward 1× as context grows.**

Two mechanisms, separable:

- **Bandwidth** — weight traffic is fixed while KV traffic grows with context, so weight
  compression addresses a shrinking share of total traffic.
- **Port contention** — dequantization uses shuffle units, attention uses FMA; as attention grows
  they compete for issue slots.

Measure the ratio across a context sweep. Bandwidth predicts smooth decay tracking the traffic
mix; port contention predicts a knee where attention saturates the relevant ports. **The shape
distinguishes them.**

**Design consequence:** if the advantage decays, the optimal quantization level is a function of
context length — and under hybrid, context length is a function of the escalation policy. So
**the optimal weight format depends on the routing policy.**

**Feasibility:** highest here. One model, one target, a context sweep. Runnable now.

## CS-29 — The traffic mix flips under hybrid ★★★

**Number:** ratio of weight bytes to KV bytes per decoded token, local-only versus hybrid.

Long-context steps escalate, so a hybrid client runs **short-context** decode, where weight traffic
dominates. A local-only client runs the full distribution, where KV traffic eventually dominates.

**If the ratio flips, the memory subsystem's priorities flip with it** — weight compression and
weight-streaming bandwidth for the hybrid machine, KV capacity and KV layout for the local-only
one. Same workload, same target, opposite memory design.

That is CS-01's argument pushed down to the datapath, and it is the cleanest statement of "a
hybrid client is a different chip."

## CS-30 — The local machine should be a GEMV engine ★★★

Prefill is GEMM with reuse; decode is GEMV with none. NPUs are MAC arrays built for reuse-rich
dataflow — the structural assumption of a systolic array is operand reuse, which batch-1 decode
does not have.

If hybrid filters prefill away, **the local accelerator should be built for GEMV**: wide memory
ports, deep prefetch, minimal MAC area. That is close to the opposite of what is shipping.

**Why it is the FPGA project's real home.** This is where an HLS group can build the thing rather
than argue about it — a decode-shaped datapath, measured against the NPU on the same memory.
Stronger than a gating engine and far more central to the thesis.

---

## CS-32 — E-ATTRIB: the marginal value of silicon ★★★★★ *(CS-27 + CS-31 fused)*

Measuring the step floor and decomposing the 29% are the same measurement seen from two sides.
Fused, they stop producing numbers and start producing a **model** — and the model is the thing
SEAM needs anyway.

### The model

```
t_step  =  a                                   per-step fixed floor
        +  prompt_new / R_prefill              ingest of genuinely new tokens
        +  n_out × ( d0 + d1 × context )       per-token decode
                     ▲         ▲
                     │         └── KV streaming, grows with context
                     └── weight streaming + dequantization + per-token dispatch
```

Four parameters, and **each maps to a different hardware intervention**:

| Term | What buys it down | Responds to more silicon? |
|:--|:--|:--|
| `a` | kernel fusion, graph capture, lighter dispatch | **no** |
| `R_prefill` | compute — the only term an NPU truly helps | yes |
| `d0` | bandwidth, native INT4 operands, fewer launches | partly |
| `d1` | bandwidth, KV layout, KV quantization | yes |

Comparing INT4 against INT8 splits `d0` further: weight streaming halves while dequantization
rises, so the difference isolates the two. That is CS-27's decomposition, obtained as a
coefficient rather than as a separate study.

### Design — and the one trick that makes it identifiable

Factorial sweep over **context × new-prompt × output × quantization**. The essential move:
**context length and new-prompt length must be varied independently**, which a real agent trajectory
cannot do because context is just accumulated prompt. Use synthetic prompts with a warmed cache —
set a long resident context, then issue a short new prompt. That decouples `d1 × context` from
`prompt_new / R_prefill`, and without it the model is unidentifiable.

Fit on synthetic microbenchmarks. **Validate on real agent steps.** Report held-out error.

### Three claims, ranked

**1. Which hardware upgrade pays is set by a number in your software config.**

The sensitivity vector ∂t/∂(each resource) **rotates** as the escalation deadline moves. Loose
deadline → long steps stay local → `d1 × context` dominates → buy bandwidth. Tight deadline → only
short steps stay local → `a` dominates → bandwidth buys nothing.

> *Tighten the latency budget by two seconds and memory bandwidth stops being the thing to buy.*

A software policy parameter determining a silicon procurement decision, through a measured
mechanism. That is the strongest form of the co-design claim available in this project.

**2. Most of an agent step may not be inference.** If `a` is large relative to median step time,
then tokens-per-second is the wrong metric for agentic work and every benchmark in the category
measures the wrong quantity.

**3. Our own router is misspecified, and we found it before we ran it.** `policy.decide()` uses
`prompt/R_prefill + n_out/R_decode` — **no constant term.** If `a` is material, every routing
decision on a short step is biased rather than noisy. The fix is one term, and reporting the defect
alongside the correction is worth more than either.

### Why this is not a side study

`h*(workload, target)` requires knowing the marginal value of each hardware coordinate. **That is
literally what this measures.** E-ATTRIB is the surrogate's hardware model — the thing SEAM has to
build regardless — designed so its intermediate results are independently publishable.

### Risk

If `a` is negligible and the coefficients are unsurprising, there is no headline; you still have a
validated hardware model and the surrogate needs it. Asymmetric in the right direction.

**Feasibility:** highest of any leading candidate. Synthetic microbenchmarks, Platform A only, no
cloud, no confinement mechanism, no second platform. The validation half rides on E-FILTER's logs.

**Audit:** analytical LLM latency models exist (SweetSpot 2602.05695 and others) but are
datacenter, single-shot, and carry no agent-step floor. The rotation-with-policy claim needs the
boundary and is unavailable to them. Verify before speaking.

---

## 4. Gates

Every study above producing a novelty claim passes AUDIT before it is spoken aloud. CS-01, CS-02,
CS-03 and CS-20 are the ones most likely to collide — the on-device agentic characterization
literature is moving fast and AUDIT-001 found eight overlaps in a single session.

Pre-register the predicted sign and the materiality threshold before running. A predicted result
is a finding; the same result recognized afterward is a curve fit.
