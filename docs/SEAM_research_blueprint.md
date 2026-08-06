# SEAM — Research Blueprint

**Silicon-aware Exploration of Agentic Model partitioning**

Sharc Lab, Georgia Institute of Technology
Version 2.0 — 2026-08-02
Supersedes v1.0 (2026-07-29). Status: **binding protocol.**

---

## 0. Operating mode

**This is the most important section. It governs every other.**

v1.0 was organized around shipping a defensible paper by a conference deadline. That produced
a timeline, a deadline-motivated two-paper split, staged experiments, and gates that partly
asked "can we finish in time." All of it is withdrawn.

### 0.1 The four standing rules

**R1 — Timing is not a constraint.** No decision is made to save time. Schedule appears in
this document only as *sequencing* — what unblocks what — never as a reason to reduce, stage,
defer, or simplify. There is no deadline. No scope is "too expensive."

**R2 — The claim strengthens monotonically.** Every change must add an axis, tighten a bound,
remove a confound, or extend coverage. A change trading claim strength for any other benefit
is rejected. Scope moves in one direction.

**R3 — Maximize contribution yield per session.** The objective is the number and value of
measurements and contributions produced. Each session should end with a recorded measurement,
a resolved finding, or a strengthened arm — obtained *within* the protocol, never by relaxing
it. Rigor is not traded against yield; the audit standard in §6 is what makes a measurement
worth having at all.

**R4 — Protect the main line.** Arms are added only if additive (§1.2 filter). An arm that
would displace the main line is recorded as a future direction and not started. Expansive
thinking is required; drift is not.

### 0.2 What this forbids

Proposing a reduced version of an experiment. Staged calibration where full calibration is
possible. Deferring an arm because it is slow. Splitting papers to hit dates. Choosing a
weaker instrument because a stronger one takes longer. Any sentence of the form "given the
time available, we could instead…"

### 0.3 What replaces the forcing function

A deadline is a crude forcing function, but it is one. Removing it creates a real risk (§13,
K2) that the instrument becomes the work. Two mechanisms replace it:

- **The contribution ledger (§9).** Contributions are recorded as obtained. The ledger, not a
  calendar, measures progress.
- **The yield queue (§8.3).** At any moment there is a defined highest-yield available
  measurement. Work proceeds from the queue, not down a schedule.

---

## 1. Thesis and main line

### 1.1 The claim

Existing design-space exploration for agentic AI serving assumes **agent behavior is invariant
to the serving decision.** Simulators replay recorded traces: prompt content, generated-token
counts, tool durations, and turn structure are inputs. That assumption is defensible for
datacenter serving, where policy changes *when* work runs but not *what* work is produced.

It is false for hybrid execution. Moving a step from a frontier cloud model to a local small
model changes output lengths, retry behavior, which tools are called, how many turns occur,
and whether the task succeeds. The workload is a *function of* the configuration.

SEAM is a design-time, hardware-aware, accuracy-aware DSE framework for hybrid client↔cloud
agentic execution that (a) models this behavioral coupling explicitly, (b) treats local
silicon configuration as a decision variable rather than an experimental constant, and (c)
admits a **time-varying** device state, which no prior DSE formulation does.

### 1.2 The main line, and the filter that protects it

**Main line question.** *Does local silicon configuration change the optimal device↔cloud
partition for agentic workloads, and if so, what silicon is required to reach a target
operating point?*

A chain of five results:

1. **Behavior responds to capability** (H1) — the premise
2. **The optimal partition shifts with silicon** (H2, H7, H8, H9, H10) — the headline
3. **The routing amortization bound** (H3, H12) — when coordination cost binds
4. **The tool is trustworthy** (H5, H6) — SEAM validated
5. **The silicon sizing rule** (S10) — the actionable output

**Additive/displacing filter.** A proposed arm is **additive** if it varies a coordinate of
the §2 design space *and* feeds one of the five results above. It is **displacing** if it
requires a different workload class, a different thesis, or answers a question outside that
chain.

Additive arms are added without hesitation and without regard to cost. Displacing directions
go in §12.4 and are **not started**, however attractive.

Worked example: *reasoning mode* varies a workload coordinate and feeds H2 → additive, now a
required two-arm axis. *Speculative decoding* is a different hybrid execution mechanism rather
than a point in the routing design space → displacing, recorded as a future paper, not started.

### 1.3 Scope boundary

**In scope:** client device ↔ cloud. Single-device local execution. Design-time exploration.

**Permanently out of scope:** datacenter/cluster infrastructure, multi-tenant serving, cluster
TCO. Academically staked (Asgar, Nguyen & Katti, arXiv 2507.19635) and commercially occupied
(Gimlet Labs). This is a positioning requirement, and the one boundary R2 does not override.

---

## 2. Formal problem statement

Let an agentic program be a dynamically-unfolding DAG $G$ whose nodes are *steps* $s$, each
with type $\tau(s)$ (plan, tool-call synthesis, tool-result summarization, code generation,
code repair, verification, reflection, final response).

### 2.1 Decision variables

**Local hardware configuration** $h \in \mathcal{H}$:

| Coordinate | Domain | Note |
|---|---|---|
| execution target | {cpu-lpe, cpu-p, igpu, npu, fpga-gate} | 5-way |
| power cap | {15, 25, 55} W | |
| power source | {battery, mains} | **Platform A exclusive** |
| quantization | {INT4, INT8, FP16} | capacity × throughput |
| available memory | induced pressure below 16 GB; 64 GB on B | |
| platform | {A: 16 GB / 4×Xe3 / 8T, B: 64 GB / 12×Xe3 / 16C} | NPU held constant |

**Partition policy** $\pi \in \Pi$:

| Coordinate | Domain |
|---|---|
| escalation semantics | {predictive, preemptive} |
| per-step deadline $D$ | continuous; grid derived per arm (§7.4) |
| KV residency on escalation | {discard, retain, transfer} |
| granularity | {step, phase, session} |

**Workload configuration** $w \in \mathcal{W}$:

| Coordinate | Domain |
|---|---|
| reasoning mode | {off, on} |
| concurrency $c$ | {1, 2, 4, 8} concurrent agents |
| model capability rung | within-family ladder (~0.6B / 4B / 8B) |
| benchmark family | five families (§7.2) |

**Environment:** network regime $n \in \mathcal{N}$; privacy constraint $c_p \in \mathcal{C}$.

### 2.2 The time-varying coordinate

Device thermal state $\theta(t)$ is **not a decision variable.** It is a state that evolves
during evaluation and modulates achievable throughput:

$$R_{\text{decode}} = R_{\text{decode}}(h, \theta(t))$$

Every prior DSE formulation in this space treats the design point as static. Admitting
$\theta(t)$ makes the objective surface non-stationary *within a single evaluation*, which is
the formal content of H8 and the reason no static policy can be optimal.

### 2.3 The behavioral coupling

The realized program is not $G$ but
$$G' = \Phi(G, h, \pi, w, n, c_p, \theta)$$
where $\Phi$ is the **behavioral response operator**. All prior tools assume $\Phi = \mathrm{id}$.

### 2.4 Objectives

All evaluated on $G'$:
$$\mathbf{f} = \big(A_{\text{accuracy}},\ \$_{\text{cloud}},\ L_{\text{JCT}},\ E_{\text{device}},\ P_{\text{leakage}}\big)$$

**Goal.** Recover the Pareto set $\mathcal{P} \subseteq \mathcal{H} \times \Pi \times \mathcal{W}$
under regimes $(n, c_p, \theta)$, and extract an interpretable **silicon sizing rule**
$h^*(W, \mathbf{f}^{\text{target}})$.

---

## 3. Positioning

| Prior work | Establishes | SEAM adds |
|---|---|---|
| Rainone et al., *When Cloud Agents Meet Device Agents* (2605.30102) | Hybrid device+cloud design space real, navigated ad hoc | Automated search; hardware as variable; validated cost model; time-varying state |
| AgentServeSim (2606.09613) | Program-centric agent serving simulation; 6% JCT error under trace replay | Client side; closed-loop behavior; five objectives; non-profilable silicon; non-stationarity |
| LLMServingSim 2.0, Vidur, TokenSim, LLMCompass | Hardware DSE machinery for LLM serving | Agent program semantics; trust boundary; behavioral coupling |
| HERA, HybridFlow, PAAC, PRISM, IslandRun, HeRo, Agent.xpu | Runtime routing policies on fixed hardware | Consumed as candidate $\pi$; not competitors |
| MALBO (2511.11788) | MOBO over agent team composition | Hardware in the loop; five objectives; measured energy |
| QEIL v2 (2602.06057) | Multi-objective edge allocation including quality | Genuinely agentic workloads; honest client hardware; hardware as variable; characterized instruments |
| Asgar/Nguyen/Katti (2507.19635) | Cost-model-driven heterogeneous placement | Client scope; calibrated not roofline; validated not preliminary |
| HW-NAS accuracy surrogates; Neurosurgeon lineage | Methodological precedent | New scope, not new machinery. Claim scope. |

**Relationship to routers, stated once.** SEAM is design-time; routers are run-time. SEAM emits
a hardware configuration plus a policy envelope; a router emits a per-request decision. SEAM
consumes published routers as inputs. The contribution is making explicit the hardware–policy
coupling the routing literature holds constant.

---

## 4. Platforms

**Platform A — Dell XPS 16 DA16260, Intel Core Ultra 5 325 (Panther Lake).**
4 Cougar Cove P + 4 Darkmont LP-E (8C/8T, no SMT), 12 MB L3, Intel 18A compute tile. Xe3 iGPU,
4 cores (`VEN_8086&DEV_B090`). NPU 5, 50 TOPS INT8 peak. 16 GB LPDDR5X-7467, soldered, unified
across CPU/iGPU/NPU. 15/25/55 W. Battery. No discrete GPU.

**Platform B — GMKtec EVO-T2, Intel Core Ultra X7 358H (Panther Lake).**
16 cores (4P+8E+4LP). Arc B390, 12 Xe3 cores. NPU 5. 64 GB LPDDR5X-8533. Mains only. OCuLink →
external FPGA.

**The controlled contrast.** NPU held constant (same generation, same driver stack) while iGPU
width varies 3×, threads 2×, memory capacity 4×, and thermal envelope differs. Any partition
flip is attributable to capacity, bandwidth, iGPU width, or thermals — not to generational IP
change. Cleaner than a cross-generation comparison, which would confound all of those at once.

**Platform A exclusives** (B cannot produce these): battery-vs-mains as a partition axis; two
independent energy signals (RAPL and battery discharge) that cross-validate without a wall
meter; the hard thermal case (55 W turbo in a laptop chassis), the ideal substrate for H8.

**Never cite as measured:** 50 TOPS (peak INT8), ~120 GB/s (derived, LPDDR5X-7467 × 128-bit),
180 TOPS (Platform B CPU+GPU+NPU aggregate), 1.38× cluster separation ratio (interpreter-bound
clustering discriminant, not a performance ratio).

---

## 5. Pre-registered hypotheses

Each states a predicted direction, a falsification criterion, and a consequence. **Under R1 no
consequence is ever "reduce scope."** A falsified hypothesis redirects investigation and is
itself a publishable result.

### H1 — Behavioral non-invariance (premise)

For a fixed task, realized execution differs between local and cloud step assignment.

*Predicted:* median relative difference ≥ 20% in ≥2 of {generated characters/bytes, step count,
distinct tool invocations}. Metrics must be **tokenizer-independent** (§6.8).

*Falsified if:* all three < 5% with 95% bootstrap CI excluding 20%, **in every step type**.

**Stratification (AM-025).** Divergence is not uniform across step types — a tool-call formatting
step is near-deterministic while a planning step is high-entropy. A statistic pooled over steps
therefore measures the *step mixture of the benchmark*, not the phenomenon, and fails in both
directions: a real effect concentrated in planning steps is diluted below the falsification floor
by a majority of low-variance formatting steps, or an effect present in one type is reported as
general. Report per-step-type effects as **primary**; the pooled figure is secondary and is never
the basis for falsification. Same requirement on H2 (a single policy ranking over a mixture is a
weighted average of possibly opposing rankings) and H5 (pooled MAPE conceals *which* step types
the surrogate cannot predict, which is exactly what a surrogate consumer needs).

*Consequence:* publish the null — "trace replay is adequate for hybrid agentic DSE" is a genuine
finding that saves the field effort. Then investigate *why*: capability gap too small, workload
too structured, ladder too narrow? Widen the ladder and re-test. Do not descope.

### H2 — Silicon-dependent optimum (headline)

The Pareto-optimal partition policy changes as a function of local hardware configuration.

*Predicted:* rank inversion in policy ordering across $\mathcal{H}$.
*Falsified if:* Kendall's $\tau \ge 0.9$ across the full swept space.
*Consequence:* falsification would validate the routing literature's implicit assumption — a
major result in itself. Investigate which coordinate is responsible.

### H3 — Routing amortization bound

There exists a step-granularity threshold $G$ below which per-step routing decision overhead
exceeds the benefit of finer partitioning; $G$ depends on local throughput and network RTT.

*Predicted:* $G$ identifiable and monotone in RTT.
*Falsified if:* no crossover in the achievable range.
*Consequence:* publishable either way. See H12 — the bound becomes *measured* rather than
modeled once the hardware gating engine exists.

### H4 — Escalation cascade

A failed or low-quality local step costs more than its own re-execution because it induces
additional downstream steps.

*Predicted:* cascade factor > 1.5.
*Falsified if:* ≤ 1.1.
*Vehicle:* preemptive escalation semantics — abandoned local work is a cascade cost by
construction.

### H5 — Behavioral surrogate validity

$\Phi$ admits a surrogate $\hat{\Phi}$ generalizing to held-out configurations.

*Predicted:* held-out (by configuration, never random split) token and step count within 15%
MAPE; task success within 10 pp.
*Falsified if:* > 30% MAPE.
*Consequence:* emit interval-valued objectives rather than point estimates; report as a
limitation of the approach.

### H6 — Rank preservation (the metric that matters)

SEAM ranks design points in the order measured reality does.

*Predicted:* Kendall's $\tau \ge 0.8$ on held-out design points.
*Falsified if:* $\tau < 0.6$. A DSE tool that cannot rank is not a DSE tool.

### H7 — NPU/iGPU crossover shift under constant NPU

With NPU capability held constant (NPU 5, 50 TOPS both platforms) and iGPU width varying 3×
(4 → 12 Xe3 cores), the region where NPU outperforms iGPU contracts on the wider-iGPU platform.

*Predicted:* crossover boundary shifts monotonically against the NPU on Platform B.
*Falsified if:* boundary invariant within bootstrap CI.
*Why it matters:* mechanistic and falsifiable, and only testable *because* the NPU is held
constant. "The same accelerator becomes the wrong choice purely because of what sits next to it"
is the thesis in miniature.

### H8 — Thermal non-stationarity (added v2.0)

Device thermal state evolves under sustained agentic load, degrading throughput, so the optimal
partition is **time-varying within a single session**. No static policy is optimal.

*Predicted:* under a **fixed** deadline policy, escalation rate drifts monotonically upward over
a sustained session, attributable to thermal degradation rather than workload drift.

*Falsified if:* escalation rate is stationary within CI over a session long enough to reach
thermal steady state, on the platform with the tightest thermal envelope.

*Why this is the strongest new arm:* every routing and partitioning paper in §3 implicitly
assumes constant device capability. If capability is time-varying and the partition depends on
it, no fixed policy can be optimal and the DSE framing becomes *more* necessary. It also
reframes §6.4 — thermal state ceases to be a confound to exclude and becomes an axis to
measure. Same instrumentation, dramatically more value.

*Control requirement:* workload drift must be excluded as an alternative explanation. Randomize
or hold task order fixed, and show the drift tracks package temperature and frequency rather
than task position.

### H9 — Concurrency shifts the partition (added v2.0)

The optimal partition depends on the number of concurrent agents sharing the device.

*Predicted:* escalation rate and the Pareto frontier shift materially across $c \in \{1,2,4,8\}$,
with 16 GB unified memory binding earlier than compute.
*Falsified if:* frontiers coincide within CI across $c$.
*Why:* real deployments run several agents. Unexplored, and it makes the unified-memory
constraint bite where it is most realistic.

### H10 — Power source shifts the partition (added v2.0)

The optimal partition differs on battery versus mains.

*Predicted:* on battery, DVFS and power limits reduce local throughput, shifting the escalation
curve; the energy objective additionally reweights the frontier.
*Falsified if:* curves coincide within CI after controlling for thermal state.
*Platform A exclusive.*

### H11 — Cross-boundary KV residency (added v2.0)

The disposition of local KV state on escalation (discard / retain / transfer) materially affects
JCT and memory pressure.

*Predicted:* retain dominates at short tool gaps, discard at long, with a crossover determined
by available memory.
*Falsified if:* no measurable difference across policies.
*Why:* InferCept/Continuum's question at the device↔cloud boundary, which nobody has studied and
AgentServeSim structurally cannot model.

### H12 — Hardware gating changes the bound (added v2.0)

A custom HLS routing/gating engine moves the H3 amortization threshold $G$ measurably.

*Predicted:* hardware decision latency is lower than software by a margin that shifts $G$ by a
reportable factor.
*Falsified if:* $G$ unchanged within CI — which would mean routing overhead never binds, closing
the hardware-acceleration direction with a measured answer rather than an assumed one.

*Why this is the differentiator:* every paper in §3 is software. Nobody else has an HLS group,
OmniSim, and OCuLink on the same bench. H3 becomes a bound *measured against silicon we
designed*, and the OmniSim-vs-FPGA error quantifies the fidelity of every hypothetical-silicon
claim in the paper.

---

## 6. Audit and data-integrity standard

Unchanged in substance from v1.0 and **not subject to R1 or R2** — rigor is the precondition for
a measurement being worth having, never a cost to be traded.

### 6.1 Threats

| Threat | Why severe here | Control |
|---|---|---|
| Thermal throttling | Correlates with condition → systematic bias, not noise | §6.4. **Under H8 also an axis** |
| LLM nondeterminism | Identical inputs differ even at temperature 0 | §6.5 variance-first ordering |
| Cloud API drift | Weights pinned, serving infrastructure documented as mutable | Pinned snapshot + daily canary |
| Self-certifying provenance | Hashing what you received proves nothing about what you should have received | §6.7 |
| Concurrency on shared paths | Two writers produced a corrupt 2.26 GB IR that still loaded | §6.6 |
| Measurement overhead | Instrumentation perturbs the measured, especially on LP-E | Characterized, reported as error term |
| Multiple comparisons | Hundreds of cells | Pre-declared primary endpoints; Benjamini–Hochberg on secondary |
| Benchmark selection bias | Cherry-picking flatters any policy | Frozen task lists, committed pre-collection |
| Analysis drift | Choices made after seeing data | Analysis committed before unblinding |

### 6.2 Run manifest

Every run emits an immutable manifest. No manifest, no data. Required: run identity; git state;
config hash; platform and topology with verified P/LP-E mapping; driver versions; power state
(source, charging, SoC, pinned profile); thermal (ambient, warm-up, throttle residency,
exclusion verdict, **regime: confound or axis**); target; **confinement mechanism**; model spec
with per-file verification method; **reasoning mode**; workload; policy; network; condition and
blinded labels; outputs; integrity self-check.

### 6.3 Data handling

Raw is immutable, write-once, checksummed. All derived artifacts regenerable from raw by one
command. Three tiers: `raw/` → `derived/` → `figures/`. No manual data entry. Discard only for
harness self-check failure, throttle residency above threshold (confound regime only), or API
error — every discard logged with reason and counted in the paper. Post-hoc discarding of
inconvenient values is misconduct.

**Retention (AM-014):** `raw/` payloads committed while total size is under the ceiling in
`configs/repo.yaml`; above it, payloads move to an externally checksummed archive and
`raw/MANIFEST.sha256` becomes the in-repo audit index.

### 6.4 Thermal protocol — and its dual role

Fixed ambient, logged. Warm-up to steady state, duration determined empirically and frozen.
Inter-run cooldown to a fixed ceiling. Temperature and throttle-residency logged ≥1 Hz. Runs
above threshold flagged, excluded from primary analysis, reported in a throttling table.
Condition order randomized within blocks so thermal drift cannot align with condition.

**Dual role under H8.** The above governs experiments where thermal state is a *confound*. H8
experiments deliberately do not exclude throttling — they measure it. Every run declares which
regime it belongs to, and the two are **never pooled**.

### 6.5 Variance before comparison

**No comparison runs before its noise floor is measured.**

A/A negative control: same configuration twice, labeled as two conditions, through the entire
pipeline including analysis. Must report no difference; if it does, the harness is broken.
Repeated at the start of each phase. Positive control: a known-large contrast must register.
Variance characterization: CV with $n \ge 20$ on a fixed config, reported in the paper. Any
effect below 2× CV is reported as null. Bootstrap 95% CIs, effect sizes, distributions for
heavy-tailed quantities.

### 6.6 Mutual exclusion

Two concurrent writers produced a corrupt 2.26 GB IR that still loaded and would have yielded a
complete, plausible, wrong result. Any operation writing a shared path — downloads,
`AUDIT_LOG.md`, config writes, `raw/` seals — takes a lockfile. Parallel agents are assigned
disjoint tracks (§8.2) and do not write outside them.

### 6.7 External verification of external artifacts

**Provenance that self-certifies proves nothing.** Hashing what you received records a fact about
your disk, not about the artifact.

Every externally sourced artifact is verified against an external authority before it can produce
provenance. Model weights: per-file SHA-256 against the publisher's `lfs.oid`, **not size alone**
— size catches overlap-append but not a misaligned resume splice landing at the correct length.
Governing documents: hash against a recorded expected value. The per-file verification *method*
is recorded, so a size-only-verified file is visibly weaker provenance than a hash-verified one.

### 6.8 Cross-boundary measurement confounds

Two artifacts masquerade as behavioral divergence across the local/cloud boundary. Both bias
toward the hypothesis, which is the dangerous direction.

**Tokenizer.** Claude 4.7+ uses a tokenizer producing ~30% more tokens for identical text.
Therefore **Δ tokens must not be a primary behavioral metric.** Primary behavioral metrics are
tokenizer-independent: generated characters or bytes, or all outputs re-tokenized under one
declared reference tokenizer. Native token counts are retained for cost accounting only, where
they are correct by definition.

**Reasoning mode.** Declared explicitly on both sides per arm, recorded in every manifest, never
inherited as a default on one side only. Discriminate on **non-empty thinking content**, never
marker presence — Qwen3's `enable_thinking=false` pre-fills an empty `<think></think>` pair into
the prompt, so the marker is present by construction. Verify both directions.

### 6.9 Weekly integrity ritual

Re-run the canary against its reference distribution; drift beyond CI is an incident. Re-run A/A.
Verify raw checksums. Regenerate all figures from raw end-to-end and diff. Log discards. Append
to `AUDIT_LOG.md`.

### 6.10 Artifact standard

Target artifact-evaluation "reusable": one-command setup, pinned dependencies, recorded seeds,
documented runtimes, a small-scale mode reproducing headline figures in under an hour, and a
documented path for different hardware.

---

## 7. The measurement program

Organized by dependency, not by date. Each block states what it produces and what it unblocks.

### 7.1 Instrument (I)

| ID | Produces | Unblocks |
|---|---|---|
| I1 | Manifest, topology, integrity, raw store | everything |
| I2 | S1 battery characterization | energy on A |
| I3 | RAPL bridge + elevation preflight | energy on both platforms |
| I4 | Thermal constants **and** H8 thermal-state instrumentation | H8; §6.4 both regimes |
| I5 | Memory bandwidth (STREAM-class) | capacity/bandwidth claims |
| I6 | **Full per-target energy cross-validation** — ≥8 load levels × 4 targets, anchored, randomized order, multi-cycle blocked design with repeated anchor | all energy objectives |
| I7 | Confinement mechanism verification, symmetric across arms | every target comparison |
| I8 | Network regime characterization + shaping | $\mathcal{N}$ sweeps |

**I6 note.** Multi-cycle is the design, not a fallback. Randomize load-level order within cycle —
the measured −13% SoC drift in reported discharge would otherwise load onto the slope. Include a
common anchor level in every cycle and treat cross-cycle comparability as a measured question.

### 7.2 Workload (W)

Five frozen benchmark families, committed before collection: software engineering (verifiable),
function/tool calling (machine-checkable), retrieval-augmented QA (privacy-relevant),
web/computer-use (variable tool latency), long-horizon planning (deep dependency chains).

Step-type taxonomy published with inter-rater reliability; Cohen's $\kappa \ge 0.75$ before the
taxonomy becomes load-bearing.

Per-program: step count distribution; per-step prompt/completion tokens, tool type and duration;
wall-time decomposition (local compute / cloud inference / tool execution / orchestration /
idle); energy decomposition over the same categories; prefix reuse $\eta$; DAG structure
(critical path, parallelism width, dynamic branching factor); privacy sensitivity classification;
cost per completed task.

### 7.3 Behavioral response (B)

Measures $\Phi$. The scientific core.

OFAT across step types to identify sensitive types, then full factorial on the sensitive subset,
with reference and all-local corners as anchors. Randomized order, day-blocked, canary in every
block, $n \ge 30$ per cell adjusted by power analysis.

Response metrics: Δ characters/bytes (tokenizer-independent), Δ step count, Δ tool-call
distribution, Δ success, behavioral divergence index (normalized DAG edit distance), escalation
cascade factor, capability elasticity $\partial(\text{steps})/\partial(\text{capability})$.

**The decisive analysis:** take the reference trace, apply a partition policy, compute what a
trace-replay simulator would predict, compare to what actually happened. This converts a
methodological criticism into a measured quantity and is the paper's central argument.

### 7.4 Partition experiments (P)

The main-line series. Deadline-aware local-first policy; escalation when predicted local latency
exceeds $D$.

**Predictive semantics:**
$t_{\text{pred}} = \text{prompt}/R_{\text{prefill}} + n_{\text{out}}^{\text{pred}}/R_{\text{decode}}$,
with $n_{\text{out}}^{\text{pred}}$ the per-step-type median measured per arm, frozen, identical
across targets. **Isolation invariant:** between arms only $R_{\text{prefill}}$ and
$R_{\text{decode}}$ differ — enforced in code, with confinement mechanism and reasoning mode
joined to the invariant.

**Deadline grid:** derived from measured $t_{\text{pred}}$ distributions; ≥4 absolute values
spanning the union of both targets' transition regions. **Identical across targets within an
arm** — per-target quantile deadlines would destroy the rescaling test, the strongest internal
check available.

**Pre-registered rescaling prediction, per arm:**
$$\text{escalation\_rate}_{\text{lpe}}(D) \approx \text{escalation\_rate}_{\text{p}}(D \cdot R_p/R_{\text{lpe}})$$
Failure to collapse indicates something other than compute speed is driving the partition, and
catches affinity leakage, thermal confounds, and predictor bugs in one test.

**Preemptive semantics** run as a second axis: start locally, abandon at deadline, pay
local_partial + cloud_full. H4's vehicle.

Axes swept: execution target (5-way) × deadline × reasoning mode (2) × escalation semantics (2)
× concurrency (4) × power source (2, A only) × power cap (3) × quantization × platform (2) ×
network regime × KV residency (3).

### 7.5 Hardware design point (H)

HLS routing/gating engine, simulated in OmniSim, validated against a real FPGA over OCuLink,
integrated as a fifth execution target. Produces H12 and the OmniSim-vs-FPGA fidelity figure that
underwrites every hypothetical-silicon claim in the paper.

### 7.6 Tool (T)

Closed-loop discrete-event executor consulting $\hat{\Phi}$ at each step; calibrated hardware,
network, privacy and cost models; MOBO (qEHVI) over the joint space with random/grid/NSGA-II/
expert baselines.

**Four-level validation ladder:** L1 component-wise against measurement; L2 end-to-end open-loop
(replay, behavior given) — apples-to-apples with AgentServeSim's claim; L3 end-to-end closed-loop
(behavior predicted) — the novel claim; L4 **rank preservation** on held-out design points, the
only metric determining whether the tool is useful.

**Honest fidelity accounting:** report error decomposed by which terms were *given* versus
*predicted*, under both L2 and L3. A methodological contribution and a polite, devastating
critique of headline error numbers obtained under replay.

---

## 8. Execution model

### 8.1 Dependency graph

```
I1 ─┬─► I2 ─► I3 ─► I4 ─► I6 ────────────► energy objectives
    │                └─► H8 instrumentation
    ├─► I7 ─────────────────────────────► all target comparisons
    ├─► I5, I8
    ├─► W ──► B ──► T
    └─► P (needs I7 + W + local backends)
                    └─► H (needs Platform B + OCuLink)
```

### 8.2 Tracks

Three tracks proceed in parallel and do not contend. Each agent is assigned exactly one and does
not write outside it.

- **Instrument** — I2 … I8
- **Agent** — W, B, T (cloud-bound; the long calendar pole regardless of deadline pressure)
- **Local execution / hardware** — backends, P, H

### 8.3 The yield queue

At any moment the next work item is the highest-yield *available* measurement, judged by: does it
produce a result on the main line; does it unblock more than one downstream item; does it
strengthen a claim already made. The queue is re-derived at the start of each session from
`seam_status()`, never assumed from the last session.

**A session ending without a recorded measurement, resolved finding, or strengthened arm should
be explained in `AUDIT_LOG.md`** — not as blame, but as a signal that queue ordering or the
instrument needs attention.

---

## 9. Contribution ledger

Replaces v1.0's deadline-driven paper split. Contributions are recorded as obtained; papers are
assembled when a set is strong enough.

| # | Contribution | Status |
|---|---|---|
| C1 | Agent behavior is not invariant to the serving decision (H1) | pending |
| C2 | Trace-replay simulators structurally invalid for hybrid partitioning — measured error | pending |
| C3 | The optimal partition shifts with local silicon (H2, H7) | pending |
| C4 | The optimal partition is time-varying within a session (H8) | pending |
| C5 | Routing amortization bound, measured against custom silicon (H3, H12) | pending |
| C6 | Silicon sizing rule for on-device agents (S10) | pending |
| C7 | SEAM: validated closed-loop DSE framework (H5, H6) | pending |
| C8 | Honest fidelity accounting as a methodological standard | pending |
| C9 | Client-platform measurement pathologies | **accruing** |
| C10 | NPU/iGPU/CPU crossover surfaces on Panther Lake | pending |
| C11 | Concurrency and power-source effects on partition (H9, H10) | pending |
| C12 | Cross-boundary KV residency (H11) | pending |

**C9 detail** (already accruing, and worth more than it appears): battery-counter
characterization — time-cadenced ~19 s updates with an 8% systematic between rate and capacity
estimators and −13% SoC-dependent drift; OpenVINO `PCORE_ONLY` silently falling through to all
cores on Panther Lake while `ECORE_ONLY` binds; a corrupt IR that loads and generates; a
credential leak-scan silently skipping on precisely the machine where it matters; UTF-16LE probe
artifacts making three provenance tests vacuous; CRLF making committed artifact hashes
platform-dependent.

Each is a defect a competitor would have shipped. QEIL v2 reports energy from hardware counters
with no characterization; anyone measuring P-versus-LP-E on Panther Lake with OpenVINO has
leaking affinity and does not know it. These are documented instances of measurements that would
look clean and be wrong.

---

## 10. Gates

Purely scientific. **No gate response is ever "reduce scope."**

| Gate | Criterion | If unmet |
|---|---|---|
| **G-instrument** | Energy signals pass §10.1; A/A shows no false positive; CV known for all primary metrics; confinement verified symmetric | Stop measurement, fix instrumentation. No exceptions. |
| **G-provenance** | Every externally sourced artifact hash-verified against external authority | No artifact without verified provenance enters an experiment |
| **G-behavior (H1)** | Divergence CI-separated from noise floor, in tokenizer-independent units | Publish the null; investigate cause; widen the capability ladder and re-test |
| **G-surrogate (H5)** | Held-out-by-configuration MAPE within threshold | Emit intervals not points; report as approach limitation |
| **G-rank (H6)** | Kendall's $\tau \ge 0.8$ on held-out design points | Do not publish as a DSE tool; publish characterization and behavioral results |
| **G-publication** | Every figure regenerates from raw; audit log complete; no unexplained discards; every number traces to a manifest | Do not submit. Fix reproducibility. |

### 10.1 Energy cross-validation criterion (AM-004)

Per execution target, regress baseline-corrected whole-device energy on RAPL across ≥8 load
levels: (a) $R^2 \ge 0.95$; (b) slope $\in [1.0, 1.5]$, with **slope < 1.0 a hard failure** since
a subset cannot grow faster than the whole; (c) intercept consistent with an independently
measured idle baseline. Report minimum resolvable energy difference per target.
**Target-dependent slope divergence indicates a RAPL domain-coverage gap** — critical for the NPU,
and it must be surfaced rather than pooled away.

---

## 11. Studies and figures

| Study | Tests | Claim |
|---|---|---|
| S1 | H1 | Divergence distributions vs noise floor |
| S2 | H1 | Trace-replay prediction error under policy change — **central argument** |
| S3 | §7.2 | Wall-time and energy decomposition on client hardware |
| S4 | I6 | NPU/iGPU/CPU crossover surfaces, both platforms |
| S5 | H2 | Policy ranking vs hardware configuration — **headline** |
| S6 | H3 | Amortization threshold vs throughput and RTT |
| S7 | H4 | Cascade factor by step type, preemptive semantics |
| S8 | H5, L1–L4 | Validation ladder, error decomposed given-vs-predicted |
| S9 | — | Five-objective Pareto fronts per regime |
| S10 | — | Silicon sizing rule — the industry-facing result |
| S11 | — | Search efficiency vs random/grid/NSGA-II/expert |
| S12 | H12 | HLS gating engine; OmniSim-vs-FPGA error — **the differentiator** |
| S13 | — | Cross-platform replication of S1 and S5 |
| S14 | H8 | Escalation rate vs elapsed session time under fixed policy — **non-stationarity** |
| S15 | H9 | Partition vs concurrency; memory-binding onset |
| S16 | H10 | Battery vs mains frontiers |
| S17 | H11 | KV residency policy vs tool-gap duration |

**Stratification (AM-025).** S1, S2, S5 and S8 report **per-step-type** results as primary, pooled
as secondary. S7 already does this and is the template. The cost is sample size — sufficient steps
of each type per cell — which is accepted under R1. Stratify only where step type can plausibly
moderate the effect; S16 (power source) and S3 (energy decomposition) pool.

**Step-type taxonomy.** Declared and frozen before S1, recorded in every manifest. Assignment is
made from the agent's own control flow, never inferred post hoc from output, so it cannot be
contaminated by the behavior being measured.

---

## 12. Publication and positioning

### 12.1 Claim staking

The competitive window is independent of the working schedule. Katti at Intel, Gimlet Labs
commercializing, QEIL v2 already extending the heterogeneous-agentic idea to consumer edge
hardware. **Preprint as soon as any §9 contribution is defensible**, independent of eventual
venue. Public code and traces with the preprint.

### 12.2 Assembly

Papers are assembled from the ledger when a set is strong, not at a date. Natural groupings:
C1+C2+C9 (behavior and measurement validity); C3+C4+C10+C11 (silicon dependence); C5+C12+C6
(bound, hardware, sizing); C7+C8 (the tool). Groupings, not commitments.

### 12.3 Venues

ICCAD, DAC, MLSys, FCCM, ASPLOS as they arise. Venue selection follows the contribution set,
never the reverse.

### 12.4 Recorded future directions — not started

Displacing rather than additive under R4. Recorded so they are not lost, and not begun.

- **Speculative decoding as a hybrid mode** (local draft, cloud verify). A different execution
  mechanism rather than a point in the routing design space. Feasible — OpenVINO GenAI supports
  it on NPU. Strongest available direction change; its own paper.
- Distributed multi-device edge orchestration.
- Federated / multi-user settings.
- Training-time considerations.

---

## 13. Risk register

Schedule risk removed under R1. What remains:

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| K1 | Competing publication closes the window | High | §12.1 preprint on first defensible contribution |
| K2 | **Loss of forcing function** — instrument becomes the work | **High** | §0.3 ledger + yield queue; §8.3 session accountability |
| K3 | Scope dilution — arms displace the main line | Medium-High | §1.2 filter, applied explicitly to every proposal |
| K4 | Instrument-defect arrival rate not declining | Medium | Each defect is C9 material; track the rate and investigate if it does not fall |
| K5 | Surrogate does not generalize | Medium-High | Interval-valued outputs; reported as approach limitation |
| K6 | Cross-cycle comparability in multi-cycle energy design | Medium | Repeated anchor level per cycle; cycle effect modeled, not assumed |
| K7 | Platform B delay | Low | ~85% of the program runs on A; B is generalization |
| K8 | Concurrency corruption on shared paths | Medium | §6.6 mutual exclusion, after two occurrences |
| K9 | Network fault selectivity affects the cloud track | Medium | Probe every dependent endpoint with contemporaneous controls before it matters |

---

## 14. Amendment log

Every divergence recorded with date, reason, and a **PRE-DATA / POST-DATA** label relative to the
affected measurement. Post-hoc amendments permitted but must be labeled. Identifiers never reused.

| Date | Section | Change | Reason | Pre/post |
|---|---|---|---|---|
| 2026-08-02 | all | **v2.0.** Operating mode replaced (§0): timing removed as a constraint; monotonic claim strengthening; yield maximization; main-line protection filter. Timeline replaced by dependency graph and yield queue. Deadline-driven paper split replaced by contribution ledger. Staged energy calibration withdrawn — full per-target multi-cycle design reinstated. Preemptive escalation, four local targets, both reasoning arms, and the HLS gating engine moved in scope. Added H8 (thermal non-stationarity), H9 (concurrency), H10 (power source), H11 (KV residency), H12 (hardware gating). Added §2.2 time-varying state, §6.6 mutual exclusion, §6.7 external verification, §6.8 cross-boundary confounds. Gates rewritten to remove every "reduce scope" response. | Directive: no time constraint; aggressive and expansive; impact and arm count must only increase; main line protected. | Pre, w.r.t. every hypothesis |

| 2026-08-03 | Appendix A.2, §5, §7.3, §11 | **AM-025 — the absence-claim rule and the step-type stratification correction.** (a) Standing rule: no absence claim enters any external artifact without a documented search recorded in Appendix A.2. (b) AUDIT-001 recorded; proposed H14 (step type selects execution target), H15 (tool mix drives θ(t)/c(t)), and the capacity→intensity coupling are all **withdrawn before pre-registration** as occupied or contradicted. (c) **Stratification correction:** H1, H2 and H5 currently pool behavioral metrics across step types, which makes each a measurement of the benchmark's step mixture rather than of the phenomenon. All three, and studies S1/S2/S5/S8, report **per-step-type** effects as primary with the pooled statistic demoted to secondary. H1's falsification criterion applies per type; a pooled median cannot falsify a type-specific effect. | Three prior absence claims collapsed under searches that should have preceded them. The pooling defect is a validity error independent of novelty; Agent Memory (2606.06448) is precedent for phase-aware attribution. | **Pre**, w.r.t. H1/H2/H5 and S1/S2/S5/S8 |

| 2026-08-04 | §7.3, Appendix A.2, §9 | **AM-027 — router proxy correction, and the narrative-provenance failure.** (a) **Authorized:** the router's prompt-token proxy changes from `chars // 4` to `chars // 4 + 621`, where 621 is the measured fixed chat-template scaffold. Measured bias falls from **−77.4% to −1.03%**; slope 0.9594, R² 0.9983, residual SD 11.93 tok, intercept 637.1 → 41.3. The scaffold constant is per-model and per-template and must be re-measured, not inherited, whenever either changes. Applies to all runs after this amendment; prior runs keep the uncorrected proxy and report the filter boundary as an interval. (b) **C9 entry — numbers without provenance.** Decode figures of 15.1 and 7.4 tok/s circulated through the meeting brief, the opening pitch, a collaborator meeting, and a drafted external email. A provenance audit found **no sealed run producing either value**, and **no INT8 arm exists at all** — the nearest sealed artifact is `5eb09eba`, an interleaved INT4 P-core/LP-E contrast at 15.801/8.401 (1.881×) whose confinement classification returned UNCLEAR on A1–A6. The quantization framing built on those numbers is withdrawn entirely. | The proxy defect was quantified by B3 and is a one-constant fix with a large effect on filter placement. The provenance failure is the pin-and-seal discipline holding inside `raw/` and `derived/` while failing completely in the narrative layer, where no gate exists. | **Pre**, w.r.t. every run after this date |

**AM-027(b) standing rule — the narrative gate.** No quantitative claim enters a brief, pitch,
slide, email, or paper without a **run_id** attached at the point of use. A number whose run_id
cannot be named is withdrawn, not caveated. This extends AM-009's pin discipline from governing
documents to external communications, which is where it was missing.

Prior v1.0 amendments AM-001 … AM-024 remain in force and are recorded in `AMENDMENTS.md`.

---

## Appendix A — Unverified assumptions

Confirmed by measurement before appearing in any paper.

| Assumption | Status | Resolved by |
|---|---|---|
| Platform A ≈120 GB/s peak bandwidth (derived, LPDDR5X-7467 × 128-bit) | **Unverified** | I5 |
| Platform B ≈136 GB/s (derived, LPDDR5X-8533 × 128-bit) | **Unverified** | I5 on B |
| Platform B NPU is the same ~50 TOPS bin as A | **Unverified — load-bearing for H7's "NPU held constant"** | Vendor confirmation + measurement |
| NPU 5 achieved throughput (50 TOPS is peak INT8) | **Unverified** | Local backend bring-up |
| OpenVINO `PCORE_ONLY` fall-through: defect or configuration | **Under investigation** | A2 with `ENABLE_CPU_PINNING=YES` |
| NPU engine PDH counters exist on build 26200 | **Unverified** | I3 |
| RAPL covers NPU power domains | **Unverified — determines whether NPU energy is reportable at all** | I6 per-target slopes |
| OCuLink FPGA attach is practical | **Unverified** | H block |
| `api.anthropic.com` handshake reliability on this network | **Unverified** | Probe with contemporaneous controls |
| Routing overhead ≈5% of response time at request granularity | Practitioner analysis, **not peer-reviewed** | S6 |
| HERA / HybridFlow / PAAC / PRISM / IslandRun / HeRo evaluation quality | **Abstracts only — not audited** | Before related work is written |

---

## Appendix A.2 — Literature audits behind absence claims

**Standing rule (AM-025).** No absence claim — "nobody has done X," "this has not been
measured," "this is unexplored" — enters a pitch, a brief, an abstract, or a paper without a
documented search recorded here. Three prior instances of an absence claim surviving into a
draft and then collapsing under a search that should have been run first.

Each entry records the date, what was searched, what was found, and the verdict on the claim
that motivated the search.

### AUDIT-001 — Workload composition as a hardware axis (2026-08-03)

**Motivating claim (proposed H14/H15, PRE-DATA):** that agent step type determines the optimal
execution target, and that tool mix determines the device state trajectories θ(t) and c(t).

**Searched:** Agent.xpu granularity; tool-gap characterization scope; agent step-type taxonomies
with hardware measurements; duty cycle as emergent vs imposed; workload-composition-driven
hardware sizing; capacity-forced re-prefill on constrained devices.

| Finding | Source | Effect |
|---|---|---|
| Prefill/decode **operator-accelerator affinity** on client SoC; elastic operator binding; stage-divergent batching. Granularity is operator, stage, and **flow criticality** (reactive vs proactive) — *not* step semantics. | Agent.xpu, [2506.24045](https://arxiv.org/abs/2506.24045) | Physics of phase→target is published. Step-semantic parameterization is not, but the gap is narrow. |
| Memory-system + NPU co-design DSE that **balances throughput and power between prefilling and decoding devices** for agentic workloads. SRAM/HBM/LPDDR/GDDR/HBF. Microsoft Research. | MemExplorer, [2604.16007](https://arxiv.org/abs/2604.16007) | **Most dangerous paper for the sizing framing.** Datacenter/multi-device NPU, two objectives, no cloud boundary, no accuracy. |
| First systems characterization of agent memory; taxonomy on four axes; **phase-aware profiling attributing cost to construction, retrieval, generation**; ten systems, two suites. | Agent Memory, [2606.06448](https://arxiv.org/abs/2606.06448) | Step-type cost attribution is published. Precedent *for* stratification, not against it. |
| Tool-type characterization: which tool types dominate, which contribute most latency, failure rates, **how tool intent shifts** (early read/explore → later execute/write). Also: with prefix caching, agent execution is **decode-dominated**, not long-prompt. | Agentic AI Workload Characteristics, [2605.26297](https://arxiv.org/html/2605.26297v1) | Tool-type characterization and trajectory phase shift are published. The decode-dominance finding **contradicts** the assumed prefill-heavy step types. |
| Idle durations **highly heterogeneous within a trajectory** (>10× range, long tail dominates total idle). Tool latency volatility "largely stems from factors external to the agent runtime — network jitter, backend load, queuing, rate limiting." | MORI, [2606.00866](https://arxiv.org/html/2606.00866) | **Actively undermines H15.** If gap length is externally dominated, tool mix does not cleanly determine duty cycle. |
| Sustained-load thermal characterization on mobile/NPU/GPU; one-second inter-iteration gap does not permit thermal recovery; duty-cycling or external cooling required for interactive use. | [2603.23640](https://arxiv.org/html/2603.23640v2) | Adjacent to H8. Duty cycle treated as an **imposed** operating condition. |
| Edge KV budget forces eviction → **full re-prefill** (M4 Pro, 10.2 GB budget, 3 agents at 8K FP16, 15.7 s re-prefill at 4K). Solved with persistent Q4 KV cache. | [2603.04428](https://arxiv.org/html/2603.04428v1) | The capacity → eviction → re-prefill loop on client silicon is **published with numbers**. |
| KV cache TTL across tool gaps in multi-turn agent scheduling. | Continuum, [2511.02230](https://arxiv.org/pdf/2511.02230) | Already cited under H11. |

**Verdicts.**

- **H14 as proposed (step type selects target): DO NOT PRE-REGISTER.** Phase→target affinity is
  published (Agent.xpu); prefill/decode balance as a sizing variable is published (MemExplorer);
  the workload-side composition shift is published (2605.26297).
- **H15 as proposed (tool mix drives θ(t), c(t)): DO NOT PRE-REGISTER.** MORI's own
  characterization contradicts the mechanism — gap length is dominated by factors external to the
  agent. A weaker form survives (local tools have no network variance, so a local-tool-heavy
  agent has a predictable duty cycle) but it is not worth a hypothesis slot on current evidence.
- **Capacity → arithmetic-intensity coupling: DO NOT PRE-REGISTER.** Occupied by 2603.04428.
- **Stratification correction: PROCEED.** Not a novelty question. Pooling behavioral metrics
  across step types makes H1/H2/H5 measure the benchmark's step mixture rather than the
  phenomenon. Agent Memory's phase-aware attribution is precedent for doing it.

**Strategic finding.** The on-device agentic *characterization* layer is being built out rapidly
by well-resourced groups. SEAM should stop attempting to own it and cite it. Every source above
optimizes or characterizes a **local system in isolation**; not one admits a cloud boundary. Once
a step may escalate, the sizing question changes in kind — "is this NPU large enough" becomes
"large enough for what fraction, given that the remainder escalates, at what accuracy and dollar
cost." That question is untouched by all eight findings and is where SEAM's claim now lives.

**Positioning consequence.** §3 and the positioning document are missing an entire cluster
(on-device agentic characterization and memory co-design). Six of the sources above appear in
neither. This must be closed before related work is written; a reviewer who knows this literature
would otherwise read SEAM as unaware of it.
