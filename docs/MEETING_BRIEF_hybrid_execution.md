# SEAM — Meeting Brief

**Silicon-aware Exploration of Agentic Model partitioning**
Zach Johnson · Sharc Lab, Georgia Tech · 2026-08-03

---

## 1. The question

Intel, Qualcomm, and AMD are all putting NPUs into laptops so AI agents can run locally. Which
means Dell has to decide whether the next XPS ships with 16 or 32 GB, and how much NPU to pay
for. That is an annual bill-of-materials decision with real cost, made per product line, and
there is no method behind it.

> **Given an agentic workload and a target operating point, what local silicon is required —
> and which routing policy goes with it?**

Everyone in this area treats hardware as a speed knob. It is three separate things: what is
**possible**, what gets **chosen**, and what it **costs** — and the third moves during the
session.

---

## 2. Three channels

### 2.1 Capacity — what is possible

Platform A has one **16 GB LPDDR5X pool, soldered, shared between CPU, iGPU and NPU.** Weights,
KV cache, runtime, and every accelerator's working set draw from it.

Weights set a coarse ceiling:

| | |
|---|---|
| 4B INT4 | ~2.3 GB — our verified IR, measured |
| 8B INT4 | ~4.5 GB |
| 8B FP16 | ~16 GB — the entire machine, before the OS |
| 14B FP16 | ~28 GB — does not exist here |

But the part that gets skipped is the **KV cache**, and it is where agents differ from chat. Read
back from the device rather than from the config — the config's declared `f16` is wrong, and using
it would double every figure below:

```
2 (K,V) × 36 layers × 8 KV heads × 128 dim × 1 byte (u8) = 73,728 B/token
```

```
  8K context  →  0.60 GB
 32K context  →  2.42 GB    approaching the INT4 weights
 40K context  →  3.02 GB    the model's ceiling — max_position_embeddings = 40,960
```

Note the third line. **128K is not a large number here, it is an unreachable one** — the position
limit binds before memory does, so on this model capacity is bounded by the architecture rather
than by the machine. That changes which constraint you design against.

Context **accumulates** through an agent trajectory — every tool output, every intermediate
result, every retry stays in the window. A fifty-step agent routinely reaches 32–64K. So
agentic workloads hit the memory wall along an axis chat workloads never touch.

The budget, worked:

```
4B INT4 weights      2.6 GB   observed, peak RSS minus resident KV
32K KV cache         2.4 GB   73,728 B/token, device readback
OS + background      4.5 GB
runtime              ~1 GB
                    ───────
                    10.5 GB  of 16 GB
```

Push to 64K context, add a second agent (weights shared, KV is not), or route a step to the iGPU
— which allocates its own working set from the same pool — and it does not fit. **On unified
memory, choosing a faster target costs you context length.** No published model of hybrid
execution includes that.

Platform B has 64 GB. An 8B at full precision, a 128K context, four concurrent agents all exist
there and none exist here.

> **Capacity does not change which policy is best. It changes which policies exist.**

Binary, easy to demonstrate, and it needs no argument about behavior or thermals.

### 2.2 Throughput and accelerator balance — what gets chosen

> **Provenance status, 2026-08-04.** The sealed contrast is run `5eb09eba` — a randomized,
> interleaved 10-block INT4 run giving **15.801 and 8.401 tok/s, ratio 1.881×**. Interleaving is
> good, so the *contrast* is not a session artifact. But confinement classification returned
> UNCLEAR on all of A1–A6 and `adopted_mechanism` is null, so **we cannot yet assert the two arms
> ran on the core clusters we labelled them with.** Figures previously quoted as 15.1 and 7.4 have
> no traceable sealed source and are withdrawn. Everything below is the argument this contrast
> would support **once confinement validates** — it is not yet a result.

The provisional contrast is **1.881× between two conditions intended as P-core and LP-E.**

That is larger than it should be. Decode is textbook memory-bandwidth-bound, and both clusters
sit behind the *same memory controller*, so the ratio should be near 1.0.

The second signal points the same way, with a heavier caveat. Our model is ~2.6 GB, and at this
machine's **derived** bandwidth the ceiling would be about 52 tok/s — derived from
LPDDR5X-7467 × 128-bit, which Appendix A still lists as unverified pending STREAM. Against that
denominator we are well under a third of the roof. **Do not quote a percentage until STREAM
lands**; a ratio whose denominator is a datasheet is not a measurement.

The explanation is quantization:

```
FP16   2 FLOPs / 2 bytes    =  1 FLOP/byte    below machine balance → memory-bound
INT4   2 FLOPs / 0.5 byte   =  4 FLOPs/byte   above it → compute-bound
INT4 + dequantization       ≈ 10 FLOPs/byte
```

INT4 shrinks the memory side without touching compute, and dequantization *adds* compute. On a
client CPU with balance ≈ 2.5 FLOP/byte, INT4 decode lands solidly on the compute side.

**"Decode is memory-bound" is an FP16 datacenter heuristic.** It was formed on unquantized
models with HBM and does not transfer to INT4 on client silicon. Which matters, because the
received on-device rule — *prefill on the NPU, decode on the CPU* — rests on it.

**H7** extends this. Hold the NPU **constant** — same generation, same TOPS bin, same driver
stack — and widen the iGPU 3× across our two platforms. Prediction: the region where NPU beats
iGPU **contracts**, but *only in the compute-bound region*; where bandwidth binds, both platforms
share one memory controller and the boundary should not move.

And an asymmetry worth noting: Platform B has 3× the iGPU compute but only ~1.13× the bandwidth,
so its **machine balance point is ~2.65× higher.** The same workload can be compute-bound on one
platform and memory-bound on the other. That is H2's mechanism stated precisely — not "the
numbers differ," but *"the binding constraint differs."*

### 2.3 Thermal, memory and power — what it costs, and it moves

Three independent mechanisms produce the same symptom: the optimal partition drifts **within a
single session.**

**H8 — thermal.** Under sustained load the chassis heats, clocks drop, local steps slow, more
steps miss the deadline, the partition drifts toward cloud. Every routing paper assumes device
capability is constant.

**H13 — memory.** Context accumulates, KV grows, pressure rises, prefix caching fails,
re-prefill cost rises, local steps slow. Same symptom, different cause.

**Roofline drift.** KV traffic is FP16 and grows; weight traffic is INT4 and is fixed. Beyond
~16K context KV dominates the memory bill, arithmetic intensity falls, and the workload becomes
memory-bound again — which should *compress the 1.881× ratio toward 1*. This one changes **which
target wins**, not just what it costs.

They are separable, because their drivers differ:

```
thermal   → elapsed time under load
memory    → context length
roofline  → context length, but changes the target ranking
```

**H10 — power source.** On battery the binding budget is **joules, not seconds**, and the
direction inverts: under a latency budget you escalate to go *faster*; under an energy budget you
escalate to *conserve*. A policy tuned for one is wrong for the other. Platform A exclusive.

---

## 3. The multiplier — and it is not ours

Everything above compounds, because the workload is not fixed. Move a step to the weaker local
model and the agent produces longer output, retries more, calls different tools, takes more
turns, sometimes fails.

**None of that is our finding, and the brief should say so plainly.**

- Minions documents the behavioral difference; it is why they built a second protocol.
- Off-policy evaluation for LLM agents is an active area — ADWM learns a world model to
  estimate a new policy's value from offline trajectories; Causal Agent Replay intervenes on a
  step and re-executes to attribute failures.
- Output-length prediction is a mature subfield in serving (SSJF, TRAIL, entropy-guided,
  uncertainty-aware).
- Resource-allocation frameworks for agentic workflows already *"assume access to estimates of
  single-attempt success probability and expected generation length for each subtask–model
  pair."*
- **R2V-Agent** routes SLM↔LLM per step with a calibrated failure-risk estimator, motivated
  explicitly by *"compounding local errors"* making pre-execution routing brittle.

What none of them condition on is **hardware.** Every result above is a function of *(subtask,
model)*. Ours is a function of *(subtask, model, silicon)* — and hardware is what determines
which model handles which step.

So the compounding is a **known amplifier on an unmeasured axis**, and the practical consequence
is that we assemble our behavioral surrogate from this prior art rather than inventing it.

---

## 4. Why it is open

Not because anyone erred. It falls between two communities.

The agent-evaluation and routing people know the workload responds and have machinery for it —
world models, length predictors, risk-calibrated routers. But those are ML papers; hardware is
not in their frame and their venues do not require reporting it.

The architecture people know how to explore hardware design spaces and do not study agents.

> **The tools exist on both sides. Nobody has aimed them at silicon.**

---

## 5. What SEAM is

A **design-time** DSE framework, not a router. That distinction is the whole design, so it is
worth stating precisely rather than as a slogan.

### Design-time versus runtime

| | Runtime router | SEAM |
|:--|:--|:--|
| **Question** | given this query and this machine, where do I send it? | given this workload and this target, what machine should exist? |
| **Hardware** | a fixed constraint | the decision variable |
| **Consumer** | the serving stack | the person specifying the BOM |
| **When** | inside the request | before the part is chosen |
| **Judged on** | regret against an oracle decision | **rank preservation** across designs |

The last row is the one that matters technically and I will come back to it. A router that is
5% off on every decision is a bad router. A design-time tool that is 5% off on every design but
orders them correctly is a **correct** tool — the answer it emits is *which configuration*, not
*what number*. That lowers the accuracy bar from "simulate an agent faithfully" — which nobody
can do — to "preserve an ordering," which is achievable and is what L4 measures.

### The loop, and why it has no closed form

```
     hardware  h  ──determines──▶  which policies π are viable
         ▲                                    │
         │                                    ▼
   what silicon                     policy determines what
   the workload needs                  the agent does
         ▲                                    │
         └──────────  agent behavior  ◀───────┘
```

This is a fixed point: *h* is chosen for a behavior that only materializes once *h* is chosen.
It admits no closed form for three reasons, and each is a place a simpler method breaks.

**Φ is empirical.** The behavioral response operator `G' = Φ(G, h, π, w, n, c_p, θ(t))` has no
analytic form — it is a property of a trained model's response to latency-shaped context, not of
a circuit. Nothing about the silicon lets you write it down.

**Φ is discontinuous.** Escalation is a threshold. A 3% throughput change moves zero steps across
the boundary until it moves many. Gradient methods have nothing to hold onto near the knee, which
is exactly where the design decision lives.

**Φ is non-stationary.** θ(t) and c(t) evolve *during* the evaluation, so the objective you
measure depends on when in the trajectory you measured it. A fixed point over a moving surface
is not a fixed point in the usual sense — it is the reason a single-number benchmark of this
space is not just imprecise but ill-posed.

So it gets searched.

### The design space

The three channels above are the narrative. This is the object being searched.

| Class | Coordinates |
|:------------------|:-------------------------------------------------------------------|
| **Local hardware** $h$ | execution target {LP-E cores, P-cores, iGPU, NPU} + cloud · power cap {15/25/55 W} · power source {battery, mains} · quantization {INT4, INT8, FP16} · memory capacity · platform |
| **Partition policy** $\pi$ | escalation semantics {predictive, preemptive} · per-step deadline · KV disposition on escalation {discard, retain, transfer} · decision granularity {step, phase, session} · **decision location** {software, HLS gating engine} |
| **Workload** $w$ | reasoning mode {on, off} · concurrent agents {1,2,4,8} · model capability rung · benchmark family |
| **Environment** | network regime · privacy constraint |

Two coordinates are **not** decision variables — they are states that *evolve during evaluation*:

```
θ(t)   thermal state        driven by elapsed time under load        → H8
c(t)   context length       driven by trajectory progress            → H13
```

Every DSE formulation in this space assumes a static design point. Admitting these makes the
objective surface **non-stationary within a single evaluation**, which is the formal content of
H8 and H13 and the reason no fixed policy can be optimal.

### The feasible set is discovered, not given

In classical DSE the feasible region comes from a datasheet. Here it does not. Two constraints
are already measured rather than documented:

- **NPU × {INT8, FP16} is infeasible.** An INT8 weight-only IR is accepted at pipeline
  construction and then dies with an uncatchable `0xC0000005` at `generate()` (openvino#35641).
  Nothing in the spec sheet says the NPU is INT4-only for this path.
- **Platform A × {32, 64 GB} is infeasible.** Memory is soldered at 16 GB, which is a
  *capacity-channel* constraint, not a performance one.

Those two alone take the hardware space from 432 points to 240 — a **44% prune** that no
datasheet predicts. More will appear: iGPU `CL_INVALID_WORK_GROUP_SIZE` on Panther Lake is
model-specific (openvino#34390), and `MAX_PROMPT_LEN` caps the NPU path at a length that has to
be found by trying. Mapping this boundary is contribution C10, and it is the unglamorous half of
what makes the tool usable — a search over an assumed-rectangular space returns configurations
that cannot be built.

### Why it cannot be enumerated

```
hardware   4 targets × 3 caps × 2 sources × 3 quant × 3 memory × 2 platforms  =    432
policy     2 semantics × 6 deadlines × 3 KV × 3 granularity × 2 locations     =    216
workload   2 reasoning × 4 concurrency × 3 rungs × 4 benchmarks               =     96
environ.   3 network regimes × 2 privacy regimes                              =      6
                                                                        ─────────────
                                                                          5.4 × 10⁷
```

One evaluation is an *agent trajectory* — minutes of wall time and real cloud tokens, not a
kernel launch. At four minutes each, exhaustive enumeration is roughly **400 years of serial
machine time**, and the deadline axis is discretized generously in that count.

A large measured study is O(10³) trajectories. So the surrogate is asked to extrapolate about
**10⁴–10⁵×** beyond what it has seen. Stating that ratio out loud is the honest version of the
central technical risk, and it is why fidelity accounting (C8) is a first-class result rather
than an appendix.

### How it is searched

The expensive object is not the search — it is the measurement. That inverts the usual DSE
burden, where evaluation is cheap simulation and the algorithm is the contribution.

```
measured anchors        O(10³) real trajectories on real silicon
        │
        ▼
surrogate ──┬── hardware model    R_prefill(T, target, quant, cap), R_decode(…)   measured
            ├── behavior model Φ̂  output length · success probability · tool calls
            ├── cost model        token accounting + prompt-cache economics
            └── energy model      per-target power × time, RAPL + battery cross-checked
        │
        ▼
frontier                exhaustive over the pruned feasible set — cheap once Φ̂ exists
```

Once Φ̂ is in hand the frontier is cheap, so the algorithmic question is not *how to search* but
**what to measure** — an adaptive design-of-experiments problem over the anchor set. That is
where the real budget goes.

**Φ̂ is adopted, not invented.** Its components are published: output-length prediction is a
mature subfield, and single-attempt success probability is already assumed available by the
allocation frameworks (§3). We take them and add the one argument nobody supplies — the silicon.
Building our own would be a worse paper *and* a worse tool.

### Objectives — five, simultaneously

```
task accuracy · cloud dollar cost · latency (JCT) · device energy · privacy leakage
```

Across the ~24 works in the positioning audit, **none carries more than three**. The split is
clean and structural: the tools with accuracy have no hardware, and the tools with hardware have
no accuracy. QEIL v2 gets closest — energy, quality, latency on real edge silicon — but has no
cloud boundary, no dollar cost, and no agent semantics. MALBO has the multi-objective search
machinery and zero hardware.

Same shape on execution targets: **four on-die targets plus cloud**, against two in the nearest
work — Agent.xpu covers NPU and iGPU, HeRo a mobile SoC. Neither carries an accuracy objective or
a cost boundary.

*(Both counts are bounded to the audited set in Appendix A. Neither is a claim about all
literature — see the standing rule on absence claims.)*

### What comes out

Five-objective Pareto fronts per network and privacy regime, the sensitivity of that frontier to
each hardware coordinate, and the artifact an OEM actually wants: a **silicon sizing rule**
*h\*(workload, target)* — the minimum local configuration reaching a stated operating point.

The form of that answer, which is the thing to show in the talk:

```
WORKLOAD   4-step research agent · reasoning off · 1 session
TARGET     p95 step ≤ 8 s · ≤ $0.02/session cloud · ≥ 90% of all-cloud accuracy

h*   memory      32 GB          REQUIRED      16 GB caps usable context below
                                              the trajectory's working set
     NPU         NOT REQUIRED   ← the money    workload sits below the balance
                                              point; INT4 on P-cores holds the deadline
     sustained   25 W           SUFFICIENT    55 W buys single-digit % for 2.2× power
     quant       INT4           REQUIRED      INT8 misses the deadline outright
```

**Illustrative form only — not one cell is a measured result.** The point is the shape of the
output. "The NPU is not required for this workload" is a per-unit BOM decision at fleet scale,
and it is a *result*, not a disappointment. The inverse — a workload that needs the NPU and does
not need 32 GB — is equally useful and equally unavailable today.

### How it gets used

What SEAM actually builds is one object: a surrogate over **(h, π, w, env) → five objectives**,
plus the feasible set. Every use is a query against it, distinguished only by which coordinates
are pinned and which are free. The workload is always pinned — SEAM never tells you *what* to
run, only what to run it on and how to split it.

| Query | Pinned | Free | Who asks | Returns |
|:--|:--|:--|:--|:--|
| **Co-design** *(primary)* | *w*, env, target | *h*, *π* | silicon architect, OEM | the pair (*h\**, *π\**) |
| **Deployment** | *h*, *w*, env | *π* | framework shipping on known devices | *π\** for that machine |
| **Procurement** | *π*, *w*, env | *h* | buyer with a fixed software stack | minimum viable *h\** |
| **Qualification** | *h*, *π*, *w*, env | — | "will this run on my laptop?" | feasible / infeasible, and which channel binds |
| **Attribution** | *w*, env | — | architect allocating area and power | ∂frontier/∂*h* per coordinate |

**The primary mode is joint, and that is forced by the loop.** Asking for *h\** at a fixed policy
answers the wrong question, because the policy you would run on better silicon is not the policy
you are holding fixed — size the machine against a policy tuned for a slower one and you buy
hardware whose headroom the policy never spends. The reverse fails the same way. Single-direction
queries are the degenerate cases you fall back to when reality has already pinned something for
you; the full query returns a **pair**.

**The deployable artifact is π\*(h), not π\*.** An agent framework shipping to a fleet of
heterogeneous client machines cannot use a single policy. What it can use is a table: detect the
machine at install time, look up the policy. That table is a function from silicon to policy,
which is exactly what the surrogate emits when you sweep the deployment query across *h*. It is
also the most direct product consumption path for this work, and it does not exist today because
nobody has conditioned a routing policy on silicon.

**Attribution is the most interesting query scientifically** and the one the list above is easiest
to miss. It does not ask what to buy — it asks what the next dollar, watt, or square millimetre
buys. An architect with a fixed budget deciding between more unified memory and a wider NPU is
asking for the elasticity of the frontier along each hardware coordinate, and our three channels
predict those elasticities point in *different directions for different workloads*: memory
dominates near the capacity cliff, the accelerator dominates above the balance point, and neither
matters in the region where the thermal envelope binds first.

A worked query, in the form it would actually be issued:

```
QUERY    free  h, π          pinned  w, env, target
─────────────────────────────────────────────────────────────────
w        personal research assistant · 4–8 steps · reasoning off
env      home broadband · no privacy constraint
target   p95 step ≤ 8 s · ≥ 90% of all-cloud accuracy · ≤ $0.02/session

RETURNS  h*   the minimum feasible configuration
         π*   the policy that makes h* meet the target
         ∂    what the next increment of each coordinate buys
         ⊥    which channel binds — and it is rarely the one expected
```

### What would falsify the whole framework

If *h\** turns out to be constant — the same configuration wins across every workload, target,
and regime — then the frontier is insensitive to silicon, the sizing rule is trivial, and the
correct advice is to buy the cheapest part that runs the model. No tool needed.

That is a real possible outcome and it is worth saying in the meeting before someone else does.
It is also directly testable early: it is the null of H3, and S1's partition-shift measurement is
the first place it could appear.

### The experimental vehicle

A **deadline-aware local-first policy**: attempt each step locally, escalate if predicted latency
exceeds a per-step deadline. Silicon enters through exactly one channel:

```
t_pred = prompt_tokens / R_prefill(T)  +  n_out_pred / R_decode(T)
```

**Why this policy, when better ones exist.** It is chosen for *identifiability, not performance* —
and the difference is the point. A confidence-based or learned router would escalate better and
would be a worse instrument, because silicon would enter through several channels at once and no
measured shift could be attributed to any one of them. Here silicon enters through exactly two
scalars, `R_prefill` and `R_decode`, and the policy is a threshold on a quantity those two
scalars determine analytically. That buys the rescaling check below, which a smarter policy
would forfeit.

The vehicle is a measuring instrument. Being unsophisticated is a design property.

**Isolation invariant:** between two arms *only* `R_prefill` and `R_decode` may differ — same
tasks, seeds, prompts, step types, predicted lengths, deadline, confinement mechanism, reasoning
mode. Enforced in code, with tests that fail on violation.

**The design is self-checking.** If the invariant holds, the escalation curves satisfy a
pre-registered relationship:

```
escalation_rate_lpe(D)  ≈  escalation_rate_p(D · R_p/R_lpe)
```

The same curve, horizontally rescaled by the measured throughput ratio. Failure to collapse means
something other than compute speed is driving the partition — one test that catches affinity
leakage, thermal confounds, predictor bugs, and invariant violations together.

Pre-registering it is what makes it worth anything. Declared after the fact it is a curve fit;
declared before, a failure to collapse is informative rather than embarrassing, and gets reported
either way.

**What the vehicle does and does not establish.** It establishes that the partition shifts with
silicon under a policy where silicon enters analytically, that the shift has the predicted
functional form, and — through the escalation-rate change — that the cost and accuracy
consequences are measurable rather than assumed.

It does **not** establish the magnitude of that shift for an arbitrary policy. A confidence-based
router will have a different sensitivity to `R_decode`, possibly a much weaker one. Closing that
gap is the job of the DSE tool and the surrogate, not of this experiment, and conflating the two
is the mistake I most want to avoid making in the paper. The vehicle proves the mechanism exists
and is well-behaved; the tool is what generalizes it.

---

## 6. Hypotheses

Thirteen, each pre-registered with a falsification criterion before measurement.

| ID | Claim | Status |
|:------|:--------------------------------------------------------|:---------------------|
| **H2** | optimal partition shifts with local silicon — *headline* | pre-registered |
| **H7** | NPU held constant, iGPU 3× wider → crossover contracts, compute-bound region only | needs Platform B |
| **H8** | partition is time-varying within a session (thermal) | instrumentation in progress |
| **H13** | partition is time-varying within a session (memory) | new; separable from H8 |
| **H9** | partition depends on concurrent agent count | needs multi-agent harness |
| **H10** | battery vs mains inverts the tradeoff direction | telemetry characterized |
| **H11** | KV disposition at escalation materially matters | pending |
| **H3** | a granularity exists below which routing overhead exceeds benefit | pending |
| **H12** | a hardware gating engine moves the H3 bound | needs FPGA |
| **H4** | a failed local step costs more than its own re-execution | pending |
| **H1** | workload responds to model assignment — *calibration, not a contribution* | threshold set |
| **H5** | the behavioral surrogate generalizes to unseen configurations | assembled from prior art |
| **H6** | the tool ranks design points as reality does | the metric that matters |

**H2 in one sentence:** *the same accelerator becomes the wrong choice purely because of what
sits next to it.*

---

## 7. Validation

Four levels, in increasing difficulty. Only the last determines whether the tool is useful.

| | Validates | Metric |
|:----|:------------------------------------------------|:-----------------------------|
| **L1** | each component model against measurement | held-out MAPE |
| **L2** | end-to-end open-loop (replay; behavior given) | JCT, throughput error |
| **L3** | end-to-end closed-loop (behavior predicted) | JCT + step count + success |
| **L4** | **rank preservation** on held-out design points | Kendall τ, top-*k* overlap |

**H5 is validated held-out by configuration, never by random split** — random splits leak, and
the whole claim is about generalizing to configurations never observed. That validation question
is distinct from "does my length predictor work on held-out prompts," and it is the part the
prior art does not answer.

**Honest fidelity accounting:** report error decomposed by which terms were *given* versus
*predicted*, under both L2 and L3. Methodological contribution and a quiet clarification of what
a replay-based error number describes.

---

## 8. Why this lab

**Every competitor is software** — routers, simulators, cost models, world models. None has
custom silicon in the loop, because nobody else has an HLS group, a fast RTL-accurate simulator,
and a client machine with an external PCIe port on one bench.

**H12** turns the cost of the routing decision from a number we *model* into one we **measure**:

- design the routing/gating datapath in **HLS**
- simulate with **OmniSim** (Sarkar & Hao, MICRO'26)
- validate against a **real FPGA over OCuLink** on Platform B
- report OmniSim-vs-FPGA error, which underwrites every hypothetical-silicon claim in the paper

Second advantage, easy to undersell: everyone else models the device side **analytically** —
roofline, TOPS, a latency table. We measure it, and where measurement is impossible we simulate
at RTL accuracy.

And it keeps the work inside the lab's identity: DSE of a new and commercially hot design space.

---

## 9. What is already measured

Zero partition experiments have run. The instrument work has produced an accruing contribution
that is the easiest one to defend.

**Real numbers in hand:** KV geometry read back from the device at 73,728 B/token, u8 — the
config's declared `f16` is wrong and would have doubled every capacity figure; 4B INT4 IR verified
byte-exact against the publisher's SHA-256; cloud round-trip 1.2–5.4 s; cost model validated
against 11 real API calls with zero arithmetic mismatches; escalation-disabled runs verified by
readback with 0/51 escalations and 51/51 replay reproduction at rel_tol 1e-9.

**Provisional, not yet adoptable:** the 1.881× core-cluster contrast (run `5eb09eba`, interleaved
and randomized, but confinement UNCLEAR on A1–A6). Any throughput percentage against the 52 tok/s
roof, because that denominator is derived and STREAM has not run.

**Client-platform measurement pathologies — each produces a clean-looking wrong result:**

| Finding | Consequence if unnoticed |
|:----------------------------------------|:-------------------------------------------|
| Windows battery telemetry is **time-cadenced at ~19 s**, with an **8% systematic** between the two available energy estimators and **−13% SoC drift** | Edge-energy numbers carry 8–13% of uncharacterized slop |
| OpenVINO `PCORE_ONLY` does not bind on this silicon; default placement is P-cores regardless of thread count | Both arms of a P-vs-E comparison run on the same cores; the result is a clean-looking null |
| A **corrupt model file that loads and generates** — 110 MB oversized | A complete, plausible, wrong throughput ratio and partition verdict |
| A credential leak-scanner **silently skipping** on the one machine where it mattered | A test that passes vacuously is worse than no test |
| A **~30% tokenizer difference** across the local/cloud boundary | Would fake behavioral divergence, biased *toward* our own hypothesis |

Every reported number traces to a sealed run manifest. 300+ tests, $0.15 spent of $50.

---

## 10. Positioning

**Motivating.** Rainone et al. (Qualcomm), arXiv 2605.30102 — the hybrid design space is
"complex and poorly understood," handled by "ad hoc decisions." GT+Intel, arXiv 2511.00739 —
CPU-side work is 50–90% of agentic latency.

**Agent evaluation and counterfactual machinery — we consume this, we do not compete with it.**
ADWM (2606.05558) learns a world model of the *environment* and executes the agent for real;
our surrogate models the *agent* and the environment is cheap for us, so the two are
complementary rather than substitutable. Causal Agent Replay (2606.08275) intervenes and
re-executes for failure attribution — its point-of-commitment rule for stochastic run-forward is
directly borrowable for our counterfactual measurement.

**Behavioral estimation.** Output-length prediction (SSJF, TRAIL, entropy-guided,
uncertainty-aware) is mature. Resource allocation for agentic workflows (2605.06110) assumes
access to success probability and expected length per subtask–model pair. We assemble from these.

**Routers — inputs to our search space.** HERA, HybridFlow, PAAC, IslandRun, Agent.xpu, HeRo,
and **R2V-Agent** (2605.16604), which is closest to our premise: step-level SLM↔LLM routing
motivated by compounding local errors. SEAM is design-time; these are run-time; **we consume
them as candidate policies.**

**Serving simulators.** AgentServeSim (2606.09613), LLMServingSim 2.0, Vidur, TokenSim,
LLMCompass — all datacenter, all same-model scheduling policies, for which trace replay is
*valid*. The boundary is worth drawing: replay works for policies that permute fixed work, not
for policies that determine what the work is.

**Adjacent.** Asgar/Nguyen/Katti (2507.19635) and Gimlet Labs — same shape, datacenter side,
academically staked and commercially occupied, which is why our scope boundary excludes it.
QEIL v2 (2602.06057) — closest lane, weak execution.

**Precedent, stated honestly.** Hardware-aware NAS with accuracy surrogates; the Neurosurgeon →
SPINN lineage. **Our novelty is the hardware axis, not the machinery.**

---

## 11. Risks

**The behavioral claim is fully occupied.** Confirmed by search: phenomenon, framing, surrogate
components, and the compounding observation are all published. We claim none of it.

**H2 might be false.** The partition might be robust to silicon within the range we can test.
Pre-registered falsification criterion; the null is publishable and would simplify the field.

**The window is roughly a year.** Intel's CTO co-authored the datacenter version, Gimlet is
commercializing it, QEIL v2 is extending toward consumer edge. Mitigation: preprint on the first
defensible contribution.

**Instrument defects are still arriving.** About a dozen, rate not yet declining. Each is a
contribution, but time to first partition result is uncertain.

---

## 12. Questions to expect

**"Isn't this off-policy evaluation? That's a known problem."**
> Yes, and we cite it. ADWM models the *environment* and runs the agent for real; our bottleneck
> is the opposite — local inference is expensive, the environment is cheap. Different side of the
> loop. And neither has hardware as a variable, which is our contribution.

**"Doesn't R2V-Agent already do step-level local/cloud routing?"**
> It does, and it's the closest work to our premise. It's also a router — run-time, on fixed
> hardware. We're design-time, and R2V is a candidate policy inside our search space. Our
> question is which machine you should build so R2V has a good operating point available.

**"Isn't this Neurosurgeon for LLMs?"**
> Neurosurgeon splits a fixed computation graph at a layer boundary. Our granularity is the step,
> not the layer — you can't split autoregressive decode across a network without a round trip per
> token — and the graph changes shape depending on where it runs.

**"Why not the datacenter?"**
> Academically staked and commercially occupied. The client side is open, and it's where the
> hardware question is interesting because the silicon is constrained.

**"You have one laptop."**
> Second platform in 2–4 weeks, and the contrast is deliberately *controlled*: same NPU
> generation and driver stack, iGPU width 3×, cores 2×, memory 4×. Cleaner than cross-generation,
> which would confound IP change with capacity.

**"How much does this cost?"**
> $0.15 spent against a $50 budget. The constraints are machine time and instrument correctness,
> not money.

---

## 13. What I need from this meeting

1. **Direction sign-off** — hybrid execution DSE with hardware as the decision variable.
   Explicitly *not* the earlier agent-orchestration-accelerator framing, which the routing
   overhead numbers do not support at request granularity.
2. **FPGA resource for the H12 path** — a board with OCuLink, plus guidance on OmniSim for this
   datapath style. The single biggest differentiator and the one thing I cannot do alone.
3. **Platform B logistics** — the EVO-T2 routes through GTech before reaching me.
4. **Industry contact interest** — Intel and Qualcomm both need the sizing answer and neither has
   published a method. AMD has already built a Ryzen AI integration for Minions, which says the
   local-cost side is where vendor interest sits.
5. **Collaboration shape** — the behavioral-calibration track is parallelizable and mostly
   assembly from prior art. Should a student own it?
6. **Venue thinking** — contributions accumulate in a ledger rather than aiming at one date;
   ICCAD, DAC, MLSys and FCCM fit different subsets.

---

## Appendix — Platform and figures

| Item | Value |
|:--------------------|:------------------------------------------------------------------|
| Platform A | Core Ultra 5 325 (Panther Lake, 18A): 4 P + 4 LP-E, 8C/8T; Xe3 iGPU 4 cores; NPU 5 @ 50 TOPS INT8 peak; 16 GB LPDDR5X unified |
| Platform B | Core Ultra X7 358H: 16 cores; Arc B390 12 Xe3 cores; NPU 5; 64 GB; OCuLink |
| Controlled contrast | NPU held constant; iGPU 3×, cores 2×, memory 4×, bandwidth 1.13× |
| Objectives | 5 — accuracy, $, latency, energy, privacy |
| Hypotheses | 13, pre-registered with falsification criteria |
| Spent to date | $0.15 of $50 · 300+ tests · every number traces to a sealed manifest |

**Key figures:** S5 policy ranking vs hardware configuration (*headline*) · S10 silicon sizing
rule (*industry-facing*) · S12 HLS gating engine and OmniSim-vs-FPGA error (*differentiator*) ·
S14 escalation rate vs elapsed session time (*thermal non-stationarity*) · capacity feasibility
map (*cheapest, runnable now*).

**Peak or derived — never cite as measured:** 50 TOPS (peak INT8), ~120 GB/s (derived from
LPDDR5X-7467 on a 128-bit bus), 180 TOPS (Platform B CPU+GPU+NPU aggregate), 1.38× topology
separation ratio (interpreter-bound clustering discriminant, not a performance figure).
