# SEAM — Research Blueprint

**Silicon-aware Exploration of Agentic Model partitioning**

Sharc Lab, Georgia Institute of Technology
Version 1.0 — July 29, 2026
Status: **binding protocol.** Deviations require a dated amendment entry in §14, not a silent edit.

---

## 0. How to use this document

This is a pre-registration and execution protocol, not a proposal. Three rules:

1. **§4 hypotheses and §5 audit standards are committed before data collection.** Once Phase 1 begins, hypotheses may be added but not silently revised. Amendments go in §14 with a date and a reason.
2. **Gates in §11 are hard.** A failed gate triggers the declared response, not a workaround. The scientific value of this project depends on the gates being real.
3. **Any number that appears in a paper must trace to a run manifest ID** (§5.2). No number enters a figure without a reproducible provenance chain.

---

## 1. Thesis

### 1.1 The claim

Existing design-space exploration for agentic AI serving assumes **agent behavior is invariant to the serving decision.** Simulators replay recorded traces: prompt content, generated-token counts, tool durations, and turn structure are treated as inputs. This assumption is defensible for datacenter serving, where policies change *when* work runs but not *what* work is produced.

It is false for hybrid execution. When a step moves from a frontier cloud model to a local small model, the agent produces different output lengths, retries differently, calls different tools, takes a different number of turns, and may fail where it previously succeeded. The workload is a *function of* the configuration.

SEAM is a design-time, hardware-aware, accuracy-aware DSE framework for hybrid client↔cloud agentic execution that (a) models this behavioral coupling explicitly, and (b) treats local silicon configuration as a decision variable rather than an experimental constant.

### 1.2 Formal problem statement

Let an agentic program be a dynamically-unfolding DAG $G$ whose nodes are *steps* $s \in S$, each with a type $\tau(s) \in \mathcal{T}$ (plan, tool-call synthesis, tool-result summarization, code generation, verification, final response, …).

Decision variables:

| Symbol | Space | Meaning |
|---|---|---|
| $h$ | $\mathcal{H}$ | Local hardware configuration: NPU throughput/precision, on-chip SRAM, memory capacity, memory bandwidth, power cap, optional custom datapath parameters |
| $\pi$ | $\Pi$ | Partition/routing policy mapping step types (or steps) to execution targets |
| $n$ | $\mathcal{N}$ | Network regime: RTT, bandwidth, jitter, availability |
| $c$ | $\mathcal{C}$ | Privacy constraint: which step payload classes may cross the trust boundary |

Execution targets $\mathcal{D} = \{$LP-E cores, P-cores, Xe3 iGPU, NPU, [FPGA via OCuLink], cloud endpoint(s)$\}$.

**The coupling that defines this work.** The realized program is not $G$ but
$$G' = \Phi(G, h, \pi, n, c)$$
where $\Phi$ is the *behavioral response operator*. All prior tools assume $\Phi = \mathrm{id}$.

Objective vector, all evaluated on $G'$:
$$\mathbf{f} = \big(\underbrace{A}_{\text{task success}},\ \underbrace{\$}_{\text{cloud cost}},\ \underbrace{L}_{\text{JCT}},\ \underbrace{E}_{\text{device energy}},\ \underbrace{P}_{\text{privacy leakage}}\big)$$

Goal: recover the Pareto set $\mathcal{P} \subseteq \mathcal{H} \times \Pi$ under regimes $(n, c)$, and extract from it an interpretable **silicon sizing rule** $h^*(W, \mathbf{f}^{\text{target}})$.

### 1.3 Scope boundaries — non-negotiable

**In scope:** client device ↔ cloud. Single-device local execution. Design-time exploration.

**Out of scope, permanently:** datacenter/cluster infrastructure, multi-tenant serving, cluster TCO. This is not a preference. The datacenter framing is academically staked (Asgar, Nguyen & Katti, arXiv 2507.19635) and commercially occupied (Gimlet Labs). Any drift toward it converts a defensible contribution into an unfavourable comparison.

**Deliberately deferred:** distributed multi-device edge orchestration; federated/multi-user; training.

---

## 2. Positioning (condensed; full collision map in `hybrid_execution_dse_positioning.md`)

| Prior work | What it establishes | What SEAM adds |
|---|---|---|
| Rainone et al., *When Cloud Agents Meet Device Agents* (2605.30102) | Hybrid device+cloud MAS design space is real and currently navigated ad hoc | Automated search; hardware as variable; validated cost model |
| AgentServeSim (2606.09613) | Program-centric agent serving simulation; 6% JCT error under trace replay | Client side; closed-loop behavior; accuracy/cost/energy/privacy objectives; non-profilable silicon |
| LLMServingSim 2.0, Vidur, TokenSim, LLMCompass | Hardware DSE machinery for LLM serving | Agent program semantics; trust boundary; behavioral coupling |
| HERA, HybridFlow, PAAC, PRISM, IslandRun, HeRo, Agent.xpu | Runtime routing/partition policies on fixed hardware | SEAM consumes these as candidate $\pi$; does not compete with them |
| MALBO (2511.11788) | MOBO over agent team composition (accuracy, cost) | Hardware in the loop; five objectives; energy and latency from measurement |
| QEIL v2 (2602.06057) | Multi-objective edge allocation with quality, energy, latency | Genuinely agentic workloads; honest client hardware; hardware as variable; $ and privacy |
| Asgar/Nguyen/Katti (2507.19635) | Cost-model-driven heterogeneous agent placement, TCO | Client scope; calibrated rather than roofline; validated rather than preliminary |
| HW-NAS accuracy surrogates; Neurosurgeon lineage | Methodological precedent — this is *why* the approach is sound | New scope, not new machinery. Claim scope, not invention. |

**Relationship to routers, stated once, precisely:** SEAM is design-time; routers are run-time. SEAM's output is a hardware configuration plus a policy envelope; a router's output is a per-request decision. SEAM takes published routers as inputs to its search space. The contribution is making explicit the hardware–policy coupling that the routing literature holds constant.

---

## 3. Platform

**Primary measurement platform.** GMKtec EVO-T2, Intel Core Ultra X7 358H (Panther Lake, Intel 18A), 16 cores (4P / 8E / 4LP), Intel NPU 5, Arc B390 iGPU (12 Xe3 cores @ up to 2.5 GHz), 64 GB LPDDR5X-8533, dual M.2 (PCIe 5.0 + 4.0), OCuLink.

**Facts requiring week-1 verification — do not cite until measured:**

- Peak memory bandwidth. LPDDR5X-8533 on a 128-bit bus derives to ≈136 GB/s; **treat as unverified** until confirmed by STREAM-class microbenchmark.
- NPU-only TOPS. The platform's advertised 180 TOPS is a CPU+GPU+NPU aggregate. **Never cite 180 TOPS as NPU capability.** Measure achieved NPU throughput directly.
- NPU power telemetry. Whether NPU 5 exposes per-domain power via level-zero sysman / powercap is unconfirmed. If unavailable, energy attribution must fall back to package-level differencing with an explicit error model.
- OpenVINO / NPU driver support for target model architectures and quantizations.
- OCuLink FPGA attach: enumeration, DMA bandwidth, driver stack.

**Secondary platform (required, for external validity).** One additional client-class device with a different vendor's NPU or a different memory configuration. Without a second platform, every result is single-platform and reviewers will discount it. Identify by week 4; a laptop with Core Ultra series 2, a Ryzen AI part, or an Apple silicon machine all qualify.

**FPGA (Phase 3b).** Board attached over OCuLink for the custom-datapath design point and for OmniSim cross-validation.

**Cloud endpoints.** Minimum two providers, **pinned to dated model snapshots.** Frontier models are silently updated; an unpinned endpoint invalidates longitudinal comparison. Record snapshot ID and access date on every call.

---

## 4. Pre-registered hypotheses

Each hypothesis states a predicted direction, a falsification criterion, and the consequence of falsification. Committed to git before Phase 1 data collection.

### H1 — Behavioral non-invariance (load-bearing)

**Statement.** For a fixed agent task, the realized execution differs materially between local-model and cloud-model step assignment.

**Predicted.** Median relative difference $\ge 20\%$ in at least two of: total generated tokens, step count, distinct tool invocations.

**Falsified if.** All three metrics show median relative difference $< 5\%$ with 95% bootstrap CI excluding 20%.

**Consequence of falsification.** Claim A (closed-loop simulation) collapses. Descope SEAM to open-loop DSE and *publish the null result* — "trace replay is adequate for hybrid agentic DSE" is a genuine, useful finding that saves the field effort. Do not quietly reframe.

### H2 — Silicon-dependent optimum (headline result)

**Statement.** The Pareto-optimal partition policy changes as a function of local hardware configuration.

**Predicted.** There exist $h_1, h_2 \in \mathcal{H}$ and target region such that $\arg\max$ policy differs, i.e. rank inversion in the policy ordering.

**Falsified if.** Policy ranking is invariant (Kendall's $\tau \ge 0.9$) across the full swept $\mathcal{H}$.

**Consequence.** H2 falsified means hardware genuinely doesn't matter for policy choice — which would validate the entire routing literature's implicit assumption and is publishable as such, but SEAM's premise weakens to sizing-only.

### H3 — Routing amortization bound

**Statement.** There exists a step-granularity threshold $G$ below which per-step routing decision overhead exceeds the benefit of finer partitioning, and $G$ depends on local compute throughput and network RTT.

**Predicted.** $G$ is identifiable and monotone in RTT.

**Falsified if.** No crossover exists within the achievable parameter range (i.e., software routing overhead is negligible everywhere tested).

**Consequence.** Publishable either way. If falsified, this is the honest negative result that closes the "hardware routing accelerator" direction — including the earlier orchestration-engine concept — and that is a service to the field.

### H4 — Escalation cascade

**Statement.** A failed or low-quality local step costs more than its own re-execution because it induces additional downstream steps.

**Predicted.** Cascade factor $> 1.5$ (extra steps per local failure).

**Falsified if.** Cascade factor $\le 1.1$.

### H5 — Behavioral surrogate validity

**Statement.** $\Phi$ can be approximated by a surrogate $\hat{\Phi}$ that generalizes to held-out configurations.

**Predicted.** Held-out prediction: token count and step count within 15% MAPE; task success within 10 percentage points.

**Falsified if.** Held-out error exceeds 30% MAPE.

**Consequence.** H5 falsified means closed-loop simulation is not credible with available data. Report as a limitation of the approach and fall back to bounded interval prediction rather than point estimates.

### H7 — NPU/iGPU crossover shift under constant NPU (added 2026-07-29)

**Statement.** With NPU capability held constant (NPU 5, 50 TOPS on both platforms) and iGPU width varying 3× (4 → 12 Xe3 cores), the operating region in which the NPU outperforms the iGPU contracts on the wider-iGPU platform.

**Predicted.** The crossover boundary in (sequence length × batch size × model size) space shifts monotonically against the NPU on Platform B.

**Falsified if.** The crossover boundary is invariant across platforms within bootstrap CI.

**Why it matters.** This is a mechanistic, falsifiable prediction rather than a measurement report, and it is only testable *because* the NPU is held constant. If confirmed, it is direct evidence for H2 with a clean causal attribution: the same accelerator becomes the wrong choice purely because of what sits next to it. That sentence is the paper's thesis in miniature.

### H6 — Rank preservation (the metric that actually matters)

**Statement.** SEAM ranks design points in the same order as measured reality.

**Predicted.** Kendall's $\tau \ge 0.8$ between simulated and measured ordering on a held-out design subset.

**Falsified if.** $\tau < 0.6$. A DSE tool that cannot rank is not a DSE tool.

---

## 5. Audit and data-integrity standard

This section is the difference between a paper that survives review and one that doesn't. It applies to every phase.

### 5.1 Threats this standard exists to neutralize

| Threat | Why it is severe here | Control |
|---|---|---|
| **Thermal throttling** | A small-chassis mini PC under sustained CPU+iGPU+NPU load will throttle. Throttling silently corrupts latency *and* energy, and correlates with condition (heavier configs throttle more), producing systematic bias, not noise. | §5.4 thermal protocol. Mandatory. |
| **LLM nondeterminism** | Identical inputs yield different outputs even at temperature 0 under batching. Any comparison without a variance baseline is uninterpretable. | §5.5 A/A testing and variance-first ordering |
| **Cloud API drift** | Frontier endpoints change without notice; a result from week 3 may not reproduce in week 12. | Pinned dated snapshots; weekly canary (§5.6) |
| **Measurement overhead** | Instrumentation can perturb the thing measured, especially on LP-E cores. | Overhead characterization run; report as error term |
| **Multiple comparisons** | The design grid has hundreds of cells; some will look significant by chance. | Pre-declared primary endpoints; Benjamini–Hochberg on secondary |
| **Selection bias in benchmarks** | Cherry-picked tasks make any policy look good. | Frozen task list, committed before Phase 2 |
| **Analysis drift** | Analysis choices made after seeing data. | Analysis scripts committed before unblinding |

### 5.2 Run manifest (mandatory, machine-generated)

Every experimental run emits an immutable manifest. No manifest, no data.

```yaml
run_id: <uuid>
timestamp_utc: <iso8601>
git_sha: <commit of harness>
config_hash: <sha256 of resolved config>
platform:
  host_id, cpu_model, microcode, bios_version
  npu_driver_version, openvino_version, gpu_driver_version
  kernel, os_build
  power_profile, cpu_governor, power_cap_w
thermal:
  ambient_c_start, ambient_c_end
  pkg_temp_series_path, throttle_events: <count>
models:
  local: {name, revision_sha, quantization, runtime, precision}
  cloud: {provider, model_snapshot_id, access_date, pricing_table_version}
workload:
  benchmark, task_ids: [...], seed, n_repeats
policy: {name, version, params}
network: {regime_name, measured_rtt_ms_p50/p95, measured_bw_mbps, shaping_rule}
outputs:
  raw_log_path, energy_trace_path, token_ledger_path
integrity:
  raw_sha256, harness_self_check: pass|fail
```

### 5.3 Data handling

- **Raw is immutable.** Write-once directory, checksummed, never edited. All derived artifacts regenerable from raw by a single command. **Retention (AM-014, PRE-DATA w.r.t. M2):** `raw/` payloads **ARE committed to git** while total payload size remains under a declared ceiling of **100 MB** (`configs/repo.yaml` → `raw_retention.ceiling_mb`). Above that ceiling, payloads move to an externally archived, separately checksummed bundle, and `raw/MANIFEST.sha256` — the committed index of run directories and seal hashes — becomes the authoritative in-repo audit record. At M1 scale committing raw costs almost nothing and buys off-host verification (commit `503a845`); at M2/`samples.ndjson` and M5 sweep scale the ceiling is pre-declared so the transition is not ad hoc. §5.3 immutability is enforced by `seam/rawstore.py` in both regimes. Supersedes a draft blanket "do not commit `raw/`" ruling that never took effect (identifier AM-011 is deliberately unused in the repo amendments log).
- **Three-tier layout.** `raw/` → `derived/` → `figures/`. A figure must name the derived tables it consumes; a derived table must name the run IDs it consumes.
- **No manual data entry, ever.** Numbers reach papers through scripts.
- **Discard policy declared in advance.** A run is discarded only for: harness self-check failure, throttle events exceeding the §5.4 threshold, or API error. Discards are logged with reason and counted in the paper. Post-hoc discarding for being an inconvenient value is misconduct.

### 5.4 Thermal protocol (mandatory)

1. Fixed ambient, logged. Record chassis orientation and any added cooling.
2. **Warm-up to steady state** before measurement; discard the transient. Determine warm-up duration empirically in Phase 0 and fix it.
3. **Inter-run cooldown** to a fixed package temperature ceiling before the next run begins.
4. Log package/core temperature and throttle-residency counters at ≥1 Hz throughout.
5. **A run with throttle residency above the Phase-0-determined threshold is flagged and excluded from primary analysis, and reported in a throttling table.** Do not claim zero throttling; measure it and report it.
6. Randomize condition order within a block so thermal drift cannot align with condition.

### 5.5 Variance before comparison, and A/A testing

**Ordering rule: no comparison is run before its noise floor is measured.**

- **A/A (negative control).** Run the *same* configuration twice, labeled as two different conditions, through the full pipeline including analysis. The pipeline must report no significant difference. If it reports one, the harness or analysis is broken — fix it before any A/B. Repeat A/A at the start of each phase.
- **Positive control.** A configuration with a known-large effect (e.g. 8B vs 0.5B local model) must register clearly. If it doesn't, sensitivity is insufficient.
- **Variance characterization.** For each metric, estimate run-to-run CV with $n \ge 20$ repeats on a fixed config. Report CV in the paper. Any claimed effect smaller than $2\times$ CV is reported as null.
- **Sample sizing.** Pilot to estimate variance, then power analysis for the smallest effect worth detecting. Declare $n$ per cell before collection. Default floor: $n = 30$ per cell for behavioral metrics, $n = 20$ for hardware microbenchmarks.
- **Reporting.** Bootstrap 95% CIs, not standard error bars. Effect sizes, not just p-values. Distributions (violin/ECDF) for anything with heavy tails — tool durations and JCT both are.

### 5.6 Weekly integrity ritual (Fridays, non-negotiable)

1. Re-run the **canary experiment** — one fixed config, fixed task set. Compare to the reference distribution. Drift beyond CI is an incident: investigate before continuing.
2. Re-run A/A.
3. Verify raw checksums.
4. Regenerate all figures from raw end-to-end; diff against committed figures.
5. Log the week's discards with reasons.
6. Append to `AUDIT_LOG.md`: canary result, drift verdict, incidents, discards, amendments.

### 5.7 Artifact standard

Target artifact-evaluation "reusable." Single-command environment setup, pinned dependencies, seeds recorded, expected runtimes documented, a small-scale mode that reproduces headline figures in under an hour, and a documented path for someone with different hardware.

---

## 6. Phase 0 — Instrumentation and platform bring-up (Weeks 1–2)

**Purpose.** Establish that the platform and harness can produce trustworthy numbers. Nothing scientific happens until this passes.

### 6.1 Tasks

| ID | Task | Output |
|---|---|---|
| P0.1 | NPU bring-up: get a candidate local model executing on NPU 5 via OpenVINO. Record achieved prefill/decode throughput. | Feasibility verdict + throughput table |
| P0.2 | iGPU and CPU execution paths for the same model set | Throughput table per target |
| P0.3 | Energy harness: RAPL package/core/uncore/DRAM via powercap; NPU and iGPU domains if exposed | Energy sampling library |
| P0.4 | **External power validation**: compare harness-reported energy against a wall-socket meter over sustained load | Agreement figure + error model |
| P0.5 | Thermal harness: temperature and throttle-residency logging; determine warm-up duration and throttle threshold | Thermal protocol constants |
| P0.6 | Latency and token ledger: monotonic timing, prompt/completion token accounting, cost accounting from dated pricing tables | Ledger schema |
| P0.7 | Network characterization and shaping: measure real RTT/bandwidth/jitter to each cloud endpoint across a day; build `tc`/netem regimes | Network regime definitions |
| P0.8 | Measurement overhead characterization | Overhead error term |
| P0.9 | Run-manifest emitter and integrity self-check | Harness |
| P0.10 | A/A + positive control + variance baseline | Noise floor table |
| P0.11 | OCuLink FPGA enumeration and DMA bandwidth (can slip to Phase 3b) | Feasibility verdict |

### 6.2 Numbers Phase 0 must produce

- Achieved tokens/s (prefill, decode) per (model, quantization, target ∈ {LP-E, P-core, iGPU, NPU}) — a matrix, not a single number
- Measured peak memory bandwidth (STREAM-class)
- Joules per 1k tokens per target
- Harness energy vs wall meter: agreement %
- Warm-up duration to steady state; throttle onset time under sustained load
- Run-to-run CV for JCT, energy, token count, task success
- Cloud RTT p50/p95/p99 per endpoint, and diurnal variation
- Instrumentation overhead as % of measured latency

**Gate 0 must pass before Phase 1.** See §11.

---

## 7. Phase 1 — Workload characterization (Weeks 3–4)

**Purpose.** Establish, in numbers, what agentic workloads actually consist of on a client device, and where the time, energy, money, and privacy exposure go. This is the empirical foundation for every later model and the source of the paper's motivation figures.

### 7.1 Benchmark suite (frozen before collection; committed to git)

Five families, chosen for structural diversity rather than popularity:

1. **Software engineering** — SWE-bench Verified subset (long horizon, heavy tool use, verifiable success)
2. **Function/tool calling** — BFCL v4 (short horizon, high step count, machine-checkable)
3. **Retrieval-augmented QA** — a RAG agent over a local corpus (privacy-relevant: local file content)
4. **Web/computer-use agent** — highly variable tool latency, external nondeterminism
5. **Long-horizon planner** — deep dependency chains, wide branching

For each: fixed task ID list, fixed seeds, fixed harness version. **Task lists are frozen and published.** No task is added or removed after Phase 2 begins.

### 7.2 Step-type taxonomy

Define and publish an operational taxonomy with an inter-rater reliability check. Proposed types: `plan`, `tool_call_synthesis`, `tool_result_summarize`, `code_generate`, `code_repair`, `verify`, `reflect`, `final_response`.

**Reliability requirement.** Two annotators independently label ≥200 steps; report Cohen's $\kappa$. Target $\kappa \ge 0.75$. If lower, the taxonomy is not operational — revise it before it becomes a load-bearing abstraction. Automated classification (rules or a classifier) is then validated against the human labels and its error rate reported.

### 7.3 Measurements per program

- Step count: mean, median, p95, max, full ECDF
- Per step: prompt tokens, completion tokens, tool type, tool wall duration
- **Wall-time decomposition**: local compute / cloud inference (network + queue + generate) / tool execution / orchestration and framework overhead / idle. This decomposition is the client-side analogue of the GT–Intel CPU-centric result and it is what determines whether any hardware acceleration of coordination is worth pursuing.
- **Energy decomposition** over the same categories
- Prefix reuse rate $\eta$ across consecutive steps
- DAG structure: critical path length, mean/max parallelism width, dynamic branching factor, fraction of steps whose existence depends on a prior step's content
- **Privacy sensitivity classification** per step payload: does it contain local file content, PII, credentials, or proprietary context? Publish the classifier and its validation.
- Cost: dollars per completed task at current pinned pricing

### 7.4 Deliverable

`characterization_report.md` + committed derived tables + figures. This is also the motivation section of the paper.

---

## 8. Phase 2 — Behavioral response characterization (Weeks 5–8)

**Purpose.** Measure $\Phi$. This is the scientific core and the novel contribution. It either validates or kills the project's central premise.

### 8.1 Design

**Factors.**
- Step-type assignment: for each step type $\tau$, assign {local, cloud}, holding all other types at cloud reference
- Local model ladder: ≥4 points spanning capability (e.g. ~1B, ~4B, ~8B, ~8B-INT4) — capability *and* quantization
- Cloud reference: pinned frontier snapshot
- Task families: all five from §7.1

**Design choice.** Full factorial over all step types is combinatorially infeasible. Use:
1. **One-factor-at-a-time (OFAT)** across step types to establish main effects and identify the sensitive types
2. **Full factorial** restricted to the 3 most sensitive types identified by OFAT, to capture interactions
3. **Reference and all-local corners** as anchors

Randomize execution order across the full grid. Block by day to absorb API drift; include the canary in every block.

$n \ge 30$ per cell, adjusted upward by the Phase 0 power analysis.

### 8.2 Response metrics

| Metric | Definition | Why |
|---|---|---|
| $\Delta$ tokens | Relative change in total generated tokens | Direct driver of latency, energy, and cost |
| $\Delta$ steps | Relative change in realized step count | The term trace replay fixes |
| $\Delta$ tool calls | Change in count and type distribution | Control-flow divergence |
| $\Delta$ success | Change in task success rate | The objective nobody models |
| **Behavioral divergence index** | Normalized edit distance between realized DAG and reference DAG | Single scalar for "how different was the run" |
| **Escalation cascade factor** | Extra downstream steps induced per local step failure | Tests H4; explains why local failures are expensive |
| **Capability elasticity** | $\partial(\text{steps}) / \partial(\text{model capability})$ | Quotable derived quantity; feeds the surrogate |

### 8.3 The decisive analysis

Report, per step type, the distribution of $\Delta$ tokens / $\Delta$ steps / $\Delta$ success with bootstrap CIs, alongside the Phase 0 noise floor on the same axes. **H1 is evaluated only against the measured noise floor.** A visually large shift that falls inside run-to-run variance is null.

Then: quantify the error a trace-replay simulator would incur. Take the reference trace, apply a partition policy, and compute what replay would predict versus what actually happened. **This figure is the paper's central argument.** It converts a methodological criticism into a measured quantity.

### 8.4 Gate 2 decision point (Week 8)

This is the project's fork. See §11.

---

## 9. Phase 3 — Cost-model calibration (Weeks 7–10, overlaps Phase 2)

### 9.1 Phase 3a — Measured hardware characterization

Microbenchmark sweeps producing calibrated performance and energy models:

- Prefill throughput vs sequence length, per (model, quantization, target)
- Decode throughput vs batch size and context length
- Memory footprint and KV cache growth
- Energy per token, per target, at multiple power caps
- **Crossover surfaces**: the (sequence length, batch, model size) regions where NPU beats iGPU beats CPU. These curves are a contribution in their own right — nobody has published them for Panther Lake.
- Power-cap sweep: performance and energy vs cap, to expose the thermal/energy design axis
- Contention: what happens when NPU and iGPU run concurrently (the realistic agentic case)

Model form: piecewise/regression fits with reported residuals. **Every fitted model reports held-out error.** No unvalidated analytical model enters SEAM.

### 9.2 Phase 3b — Non-existent silicon (the Sharc Lab differentiator)

For hardware configurations that cannot be profiled because they do not exist:

1. Design the candidate device-side datapath in HLS — including the routing/gating engine that Claim H3 evaluates
2. Simulate with **OmniSim / LightningSim** for fast, RTL-accurate latency
3. **Validate the simulation against a real FPGA over OCuLink** — measured, not asserted
4. Report OmniSim-vs-FPGA error explicitly; this number is the credibility of every hypothetical-silicon result in the paper

This is the capability no competitor has: AgentServeSim's profile-based operator model structurally cannot evaluate silicon that does not exist.

### 9.3 Network and cost models

- Empirical RTT/bandwidth/jitter distributions per endpoint, with diurnal variation
- Defined regimes: `datacenter-adjacent`, `residential-broadband`, `mobile`, `degraded`, `offline`
- Dollar cost from dated pricing tables, versioned in the repo
- Device amortization model for TCO comparisons — **secondary, not a headline** (vendor white papers already cover the economics; leading with TCO reads as known)

### 9.4 Privacy leakage model

The weakest-defined objective; treat it with corresponding care.

- Operational definition: leakage = volume and sensitivity-weighted count of payload classes crossing the trust boundary
- Sensitivity classes defined and published; classifier validated against human labels with reported agreement
- **Explicitly report what this metric does not capture** (inference attacks, aggregation risk, provider-side retention). Overclaiming here is the fastest way to lose a security-literate reviewer.
- If the classifier cannot be validated to acceptable agreement, demote privacy from an objective to a *hard constraint* (feasible / infeasible) and say so.

---

## 10. Phase 4 — SEAM construction and validation (Weeks 9–14)

### 10.1 Architecture

```
 ┌──────────────────────────────────────────────────────────┐
 │ Frontend: agent program → step-typed dynamic DAG          │
 └──────────────────────────┬───────────────────────────────┘
                            ▼
 ┌──────────────────────────────────────────────────────────┐
 │ Closed-loop discrete-event executor                       │
 │  at each step: consult Φ̂ → mutate remaining DAG           │
 └───┬───────────┬──────────────┬──────────────┬────────────┘
     ▼           ▼              ▼              ▼
 ┌────────┐ ┌─────────┐ ┌────────────┐ ┌──────────────┐
 │  Φ̂     │ │Hardware │ │  Network   │ │ Privacy /    │
 │behav.  │ │perf+    │ │  model     │ │ cost models  │
 │surrogate│ │energy   │ │            │ │              │
 │(Ph. 2) │ │(Ph. 3a/b)│ │  (Ph. 3c)  │ │  (Ph. 3d)    │
 └────────┘ └─────────┘ └────────────┘ └──────────────┘
                            ▼
 ┌──────────────────────────────────────────────────────────┐
 │ Multi-objective search: qEHVI MOBO over H × Π            │
 │ baselines: random, grid, NSGA-II, expert-hand            │
 └──────────────────────────┬───────────────────────────────┘
                            ▼
 ┌──────────────────────────────────────────────────────────┐
 │ Outputs: Pareto fronts · sensitivity · silicon sizing rule│
 └──────────────────────────────────────────────────────────┘
```

### 10.2 The behavioral surrogate $\hat{\Phi}$

Trained on Phase 2 data. Predicts, conditioned on (step type, assigned model, context state): completion-token distribution, continuation/termination probability, tool-type distribution, step success probability.

**Requirements.**
- Predict *distributions*, not point values — the variance is the phenomenon
- Held-out validation by **configuration**, not by random split. Random splits leak; you must predict configurations never seen.
- Report calibration (reliability diagrams for success prediction), not just accuracy
- Where H5 confidence is insufficient, propagate uncertainty and emit **interval-valued** objectives rather than false precision

### 10.3 Four-level validation ladder

| Level | What is validated | Metric | Why it matters |
|---|---|---|---|
| L1 | Each component model against measurement | Held-out MAPE per model | Prevents compensating errors |
| L2 | End-to-end **open-loop** (replay, behavior given) | JCT/throughput error | Apples-to-apples with AgentServeSim's claim |
| L3 | End-to-end **closed-loop** (behavior predicted) | JCT + step count + success error | The novel claim; nobody has reported this |
| L4 | **Rank preservation** on held-out design points | Kendall's $\tau$, top-$k$ overlap | The only metric that determines whether the tool is useful |

**Honest fidelity accounting (a contribution in itself).** Report error decomposed by which terms were *given* versus *predicted*, under both L2 and L3. This makes explicit what a "6% error" headline conceals, and it establishes SEAM as the credible instrument in the subfield. Frame it as a methodological standard, not an attack.

### 10.4 Search evaluation

Compare MOBO against random search, grid, NSGA-II, and a hand-tuned expert baseline. Metrics: hypervolume vs evaluation budget (with CIs over repeated seeds), and evaluations-to-target-Pareto-point. The claim is sample efficiency versus ad hoc exploration — the status quo Rainone et al. named in print — not superiority over specialized routers.

---

## 11. Gates — hard decision points

Each gate has a measurable criterion and a pre-committed response. **A failed gate triggers the declared response.** The purpose of writing them now is to remove the temptation to rationalize later.

| Gate | Week | Criterion | If PASS | If FAIL |
|---|---|---|---|---|
| **G0 — Platform** | 2 | A local model runs on NPU 5 at usable throughput; **energy cross-validation passes the §16.8 three-part criterion** (on Platform B a wall meter substitutes for battery discharge as the whole-system signal — note it measures AC input including PSU conversion loss, so it is likewise a superset of RAPL and the same physics applies); A/A shows no false positive; CV known for all primary metrics | Proceed to Phase 1 | If NPU only: drop NPU, reframe local targets as CPU+iGPU, continue. If harness fails: **stop all science**, fix instrumentation. No exceptions. |
| **G1 — Characterization** | 4 | Wall-time and energy decompositions complete with CIs; taxonomy $\kappa \ge 0.75$; frozen benchmark list committed | Proceed to Phase 2 | Revise taxonomy or narrow benchmark families; do not proceed on an unreliable taxonomy |
| **G2 — H1 / behavioral non-invariance** | 8 | $\ge 20\%$ median divergence in $\ge 2$ metrics, CI-separated from noise floor | **Full SEAM.** Closed-loop is justified; this is the flagship path | $< 5\%$: publish the null, descope to open-loop DSE. Between 5–20%: descope to token/step-count surrogate only; drop success prediction |
| **G3 — Surrogate validity (H5)** | 12 | Held-out (by configuration) MAPE $\le 15\%$ tokens/steps; success within 10 pp | Closed-loop results are quotable as point estimates | 15–30%: emit intervals, not points; state limitation prominently. $>30\%$: report as negative result on surrogate feasibility |
| **G4 — Rank preservation (H6)** | 14 | Kendall's $\tau \ge 0.8$ on held-out design points | Tool is validated; write the DSE studies | $0.6 \le \tau < 0.8$: publish as preliminary, restrict claims to coarse regions. $\tau < 0.6$: **do not publish as a DSE tool.** Publish characterization + behavioral finding only |
| **G5 — Submission** | 15 | All figures regenerate from raw; audit log complete; no unexplained discards; every number traces to a manifest | Submit | Delay to next venue. **Do not submit unreproducible results.** |

---

## 12. Studies and figure plan

Each study maps to a hypothesis and a figure. Numbered so drafts can reference them.

| Study | Tests | Figure | Claim it supports |
|---|---|---|---|
| S1 | H1 | Divergence distributions per step type vs noise floor | Behavior is not invariant |
| S2 | H1 | Trace-replay prediction error under policy change | Existing simulators are structurally invalid here — **central argument** |
| S3 | §7.3 | Wall-time and energy decomposition on client hardware | Motivation; also determines whether coordination acceleration is worth pursuing |
| S4 | Phase 3a | NPU/iGPU/CPU crossover surfaces on Panther Lake | Standalone contribution; nobody has published these |
| S5 | H2 | Policy ranking vs hardware configuration (rank-inversion heatmap) | **Headline**: fixed routing policies are overfit to one device |
| S6 | H3 | Amortization threshold $G$ vs local throughput and RTT | The bound; publishable either direction |
| S7 | H4 | Cascade factor by step type | Explains the cost structure of local failure |
| S8 | H5, L1–L4 | Validation ladder, error decomposed by given-vs-predicted | Credibility; methodological contribution |
| S9 | — | 5-objective Pareto fronts per network/privacy regime | The tool's product |
| S10 | — | Silicon sizing rule: minimum $h$ for a target operating point | The actionable industry-facing result |
| S11 | — | Search efficiency vs random/grid/NSGA-II/hand | Justifies MOBO |
| S12 | H3, Phase 3b | HLS gating-engine design point; OmniSim-vs-FPGA error | Sharc Lab differentiator; evaluates silicon that cannot be profiled |
| S13 | — | Second-platform replication of S1 and S5 | External validity — without this, everything is single-platform |

---

## 13. Publication strategy — and the honest recommendation

### 13.1 The scope problem

Today is July 29, 2026. MLSys 2027 closes **Oct 30** (13 weeks); DAC 2027 abstract **Nov 11**, paper **Nov 18** (16 weeks); ICCAD 2027 ≈ **April 2027**; FCCM 2027 ≈ Nov–Dec 2026 (confirm).

Phases 0–4 as specified are approximately 14 weeks of work **if nothing goes wrong**, for one student, including building a validated behavioral surrogate and an FPGA cross-validation. That is not a realistic single-submission schedule. Compressing it produces exactly the thin, roofline-grade evaluation this project is positioned to criticize — which would be self-defeating.

### 13.2 Recommended: two papers

**Paper 1 — "Agent behavior is not invariant to the serving decision"** (characterization + behavioral response). Phases 0–2 plus S1, S2, S3, S4, and a second-platform replication. Target **DAC 2027 (Nov 18)** or **MLSys 2027 (Oct 30)** if Phase 2 runs clean.

This is a complete, self-contained paper with a sharp, falsifiable, useful claim. It invalidates a methodological assumption held across ~10 recent papers, it is measurement-driven, and it does not depend on the tool existing. It also stakes the claim publicly and fast, which matters given the ~12-month window.

**Paper 2 — SEAM** (the tool). Phases 3b, 4, plus S5–S13. Target **ICCAD 2027 (April)** or **MLSys 2028**, with an arXiv preprint and public code as soon as G4 passes.

**Why this is better, not just safer.** Paper 1 is the *citation* for Paper 2's premise. Publishing the characterization first means SEAM arrives with its foundational assumption already peer-reviewed, which is a much stronger position than asserting both at once in a compressed evaluation.

### 13.3 Alternative: single submission

Possible only if G2 passes decisively by week 8 and the surrogate proves easy. Requires dropping S12 (FPGA/OmniSim) and S13 (second platform). Dropping S13 is a serious external-validity concession. **Not recommended.**

### 13.4 Preprint and code timing

arXiv preprint of Paper 1 at week 10 regardless of venue decision. Code and traces public at preprint. The field moves monthly; a staked public claim is worth more than a polished private one.

---

## 14. Risk register and amendment log

### 14.1 Risks

| # | Risk | P | Impact | Mitigation | Owner action |
|---|---|---|---|---|---|
| R1 | Intel NPU stack cannot run target models at usable throughput | Med-High | Blocks NPU as a target | **De-risk in week 1.** Fallback: CPU+iGPU only, reframed | G0 |
| R2 | H1 falsified — behavior barely shifts | Med | Kills flagship claim | Pre-committed null publication path | G2 |
| R3 | Surrogate doesn't generalize | Med-High | Closed-loop not quotable | Interval-valued outputs; report as limitation | G3 |
| R4 | Thermal throttling corrupts measurements | **High** | Systematic bias, not noise | §5.4 protocol, mandatory | G0 |
| R5 | Cloud API drift mid-study | High | Longitudinal invalidity | Pinned snapshots, daily canary, blocked design | Weekly ritual |
| R6 | Single-platform criticism | High | Reviewer rejection | Second platform by week 4 — treat as required, not optional | G1 |
| R7 | Scope creep into datacenter | Med | Unfavourable comparison to Gimlet/Asgar | §1.3 is a hard boundary | Every review |
| R8 | Competing publication appears | Med-High | Novelty loss | Week-10 preprint | Fixed date |
| R9 | OCuLink FPGA path costs more than budgeted | Med | Loses the differentiator | Defer to Paper 2; not on Paper 1's critical path | Phase 3b |
| R10 | Privacy metric not defensible | Med | Objective must be dropped | Pre-declared demotion to hard constraint | §9.4 |
| R11 | Multiple-comparison false positives | Med | Retracted claims | Pre-declared primary endpoints, BH correction | §5.1 |
| R12 | Student time / coursework collision | High | Schedule slip | Two-paper split absorbs this | §13.2 |

### 14.2 Amendment log

Every deviation from this protocol is recorded here with date, what changed, why, and whether it was decided before or after seeing relevant data. **Post-hoc amendments are permitted but must be labeled as such.**

| Date | Section | Change | Reason | Pre/post data |
|---|---|---|---|---|
| 2026-07-29 | — | v1.0 committed | Initial pre-registration | Pre |
| 2026-07-29 | §3, §16 | Added Phase −1. Dell XPS 16 promoted from stopgap to **Platform A**, satisfying the §3 second-platform requirement and R6. Phase −1 inserted ahead of Phase 0. | EVO-T2 not yet in hand; H1 is platform-independent and can be resolved early. Sequencing improvement, not a concession. | Pre |
| 2026-07-29 | §4, §16.1 | **Retracted the two-generation NPU axis.** It rested on a false premise: Platform A was assumed Meteor Lake, but hardware probe artifacts identify it as **Panther Lake, Core Ultra 5 325** — the same generation as the EVO-T2. Replaced with a *controlled-contrast* axis (NPU held constant, iGPU width / memory capacity / thread count / thermal envelope varying). Added **H7**. | Corrected platform identification. The controlled contrast is a stronger design than the cross-generation one, which would have confounded NPU IP, driver stack, process node, and capacity simultaneously. | Pre |
| 2026-07-29 | §11 (G0), §16.8 (Gate −1) | **AM-004 — RESOLVED, authorized by Z. Johnson.** Replaced "RAPL and battery agree within 15%" (and the parallel "wall meter within 10%" in G0) with a three-part physical criterion: (a) linearity $R^2 \ge 0.95$ across ≥8 load levels; (b) slope $\in [1.0, 1.5]$, **slope < 1.0 a hard failure**; (c) intercept consistent with an independently measured idle platform baseline. Regressions fit **per execution target**. Adds a reported minimum resolvable energy difference. | The original criterion was physically unsatisfiable. RAPL package energy is a strict subset of platform draw, and the excluded terms — display, SSD, WiFi, EC, fans, VRM losses, possibly DRAM — are large. At idle the signals differ by roughly 3–5×; only near maximum load does the gap approach 15%. The criterion was satisfiable at one operating point only, and reachable elsewhere only by mis-attributing platform baseline power into the SoC term. The replacement tests what the gate intended (instrument trustworthiness) and adds a slope<1 sanity check the original lacked. | **Pre** — no energy data collected |
| 2026-07-29 | §16 | **AM-002 — RESOLVED.** Renumbered duplicated §16 subsections. The 2026-07-29 platform-correction amendment introduced a second §16.1–§16.3, colliding with the existing Tier sections. Now: 16.1 Platform A, 16.2 controlled-contrast axis, 16.3 consequences, 16.4 Tier 1, 16.5 Tier 2, 16.6 Tier 3, 16.7 ordering, 16.8 Gate −1, 16.9 topology/power-pinning note. | Document defect introduced by the amending author; cross-references were ambiguous. | Pre |
| 2026-07-30 | §5.3 | **AM-014 — RESOLVED (PRE-DATA w.r.t. M2), authorized by Z. Johnson.** Threshold-based `raw/` retention. Payloads **ARE committed to git** while under a declared **100 MB** ceiling; above it, payloads move to an externally archived, separately checksummed bundle and `raw/MANIFEST.sha256` becomes the authoritative in-repo audit index. Ceiling declared in `configs/repo.yaml` and enforced by `seam/raw_retention.py`. §5.3 immutability remains enforced by `seam/rawstore.py` in both regimes. **Renumber:** an earlier draft of this amendment was numbered AM-011; that identifier is deliberately unused in `AMENDMENTS.md` (collision with a prior unused slot), so the amendment is issued as AM-014. The draft blanket "raw/ is NOT committed to git" ruling is **superseded before it ever took effect** — commit `503a845` correctly committed M1 sealed runs (~0.09 MB) for off-host verification. | At M1 scale committing raw is cheap and valuable; at M2 (1–10 Hz `samples.ndjson`) and M5 (hundreds of runs) it is not. Declaring the ceiling now makes the transition a pre-registered rule rather than an ad hoc reaction. | **Pre** w.r.t. M2 |
| 2026-07-29 | Appendix B | **Audit finding AF-001** logged: `analysis/aipc-c1/MACHINE.md` line 12 mislabels the platform "(Lunar Lake)." Because MACHINE.md is the provenance source for run manifests (§5.2), the error would propagate into every manifest's platform identity. Caught before data collection. | Provenance integrity | Pre |

---

## 15. Immediate next actions (week 1)

1. Commit this document to the repo. Tag `blueprint-v1.0`. This is the pre-registration timestamp.
2. **P0.1 first, before anything else** — attempt NPU bring-up. This single result determines the project's shape and is the highest-variance unknown.
3. Order/borrow: wall-socket power meter, second client platform, FPGA board with OCuLink cable.
4. Stand up the repo skeleton: `raw/`, `derived/`, `figures/`, `harness/`, `configs/`, `AUDIT_LOG.md`, `AMENDMENTS.md`.
5. Freeze and commit the benchmark task lists (§7.1).
6. Take §1, §4, §11, and §13.2 to Callie. The two decisions that need her input: the two-paper split, and whether the FPGA/OmniSim path belongs in Paper 1 or Paper 2.

---

## 16. Phase −1 — Pre-platform work on the XPS 16 (starts immediately)

### 16.1 Platform A: Dell XPS 16 DA16260, Core Ultra 5 325 (Panther Lake)

**Confirmed configuration** (source: committed hardware probe artifacts, `analysis/aipc-c1/MACHINE.md`, `analysis/_c1_machine_probe.txt`, `analysis/_c1_drivers_probe.txt`, `apu_characterization/out/setup.json`, recorded 2026-07-28; OS build 26200. **Recorded, not live** — see AF-002):

- **CPU:** Intel Core Ultra 5 325, Panther Lake. 4 Cougar Cove P-cores (2.1 / 4.5 GHz) + 4 Darkmont LP-E cores (1.6 / 3.4 GHz). **8C/8T, no SMT.** 12 MB L3. Compute tile Intel 18A; GPU tile Intel 3.
- **iGPU:** Intel Xe3, **4 cores** (PCI `VEN_8086&DEV_B090`)
- **NPU:** NPU 5, **50 TOPS INT8**
- **Memory:** 16 GB LPDDR5X-7467, soldered, 8 × 2 GiB banks, **unified with iGPU and NPU**. Not upgradeable.
- **Power:** 15 W min / 25 W base / **55 W max turbo**, in a 16″ laptop chassis, with a battery
- **No discrete GPU.**

Local execution targets: {LP-E cores, P-cores, Xe3 iGPU, NPU 5} — four, plus cloud. Five-way partition space, as planned.

### 16.2 The controlled-contrast axis (replaces the retracted cross-generation axis)

Both platforms are Panther Lake with NPU 5. That removes the two-generation NPU comparison, and **replaces it with a better-controlled experiment.**

| Axis | Platform A (U5 325) | Platform B (X7 358H) | Ratio |
|---|---|---|---|
| **NPU** | NPU 5, 50 TOPS | NPU 5, ~50 TOPS | **≈1× — held constant** |
| iGPU width | 4 Xe3 cores | 12 Xe3 cores (Arc B390) | **3×** |
| CPU threads | 8 | 16 cores | **2×** |
| Memory capacity | 16 GB | 64 GB | **4×** |
| Memory bandwidth | ~120 GB/s (derived) | ~136 GB/s (derived) | 1.13× |
| Sustained power / thermal | 55 W peak, laptop, battery-capable | mini PC, mains | — |

**Why this is stronger than what it replaces.** A cross-generation comparison would have confounded NPU IP revision, driver stack, process node, iGPU architecture, and memory capacity simultaneously — no effect could be attributed. Here the NPU is *held constant in both capability and driver stack*, while everything around it varies by 2–4×. Any observed flip in the optimal partition must be attributable to capacity, bandwidth, iGPU width, or thermal envelope. **This is now the primary H2 experiment**, and it is a controlled contrast rather than a generational anecdote.

**Second consequence: Phase −1 work is ~fully transferable.** Same generation means the same OpenVINO build, NPU driver, and level-zero stack. NPU bring-up on Platform A *is* NPU bring-up for Platform B. R1 (NPU stack risk) drops from Med-High to Low-Med once P-1.9 passes.

**Third: the platforms map onto real market segments.** 16 GB unified is the *volume* AI PC configuration; 64 GB is the headroom configuration. So S10's silicon sizing rule answers the question OEMs are actually asking — **is 16 GB sufficient for agentic workloads, or is 32/64 GB required?** Frame S10 this way.

**Platform A exclusives** (Platform B cannot produce these):
- Battery vs. mains operation as a design axis — DVFS and power-cap behavior differ, and battery energy is the objective users actually feel
- Two independent energy signals (RAPL *and* battery discharge), which cross-validate each other and let P0.4 proceed **without a wall meter**
- The hard thermal case: 55 W turbo in a laptop chassis. A §5.4 protocol proven here transfers upward safely.
- The *constrained* regime: 8 threads and 16 GB unified. Given that the GT–Intel CPU-centric result found CPU-side tool processing dominating agentic latency, an 8-thread part is where that bottleneck bites hardest — which makes Platform A the more informative platform for S3, not the weaker one.

### 16.3 Consequences to propagate

1. **8 threads, not 16.** Any manifest, budget, or model assuming thread-parallel CPU throughput must be revised. Concurrency defaults in the harness need re-tuning.
2. **No dGPU target.** Remove it from P-1.12's target set.
3. **16 GB unified is a hard constraint.** Weights, KV cache, iGPU/NPU working sets, OS, and framework share one pool. INT4-quantized ~8B is the realistic ceiling; FP16 8B is out. Long contexts will contend with weights — measure the contention, don't assume it away.
4. **~120 GB/s is derived, not measured.** LPDDR5X-7467 on a 128-bit bus. Confirm by STREAM-class benchmark before it appears anywhere.
5. **Never cite 50 TOPS as achieved throughput.** It is a peak INT8 figure. Measure achieved tokens/s.

### 16.4 Tier 1 — fully executable now, zero dependence on the EVO-T2

| ID | Task | Serves | Notes |
|---|---|---|---|
| P-1.1 | **H1 pilot: behavioral response via model-capability contrast** | H1, H4, S1, S2, S7 | **Highest priority.** H1 asks whether agent behavior changes when model capability changes. That is a property of *models*, not of silicon. Run it with cloud endpoints at differing capability plus local models on the XPS. **The project's load-bearing hypothesis can be resolved before the AI PC ships.** |
| P-1.2 | Harness: run-manifest emitter, token ledger, cost accounting, integrity self-check | §5.2 | Platform-independent |
| P-1.3 | A/A negative control, positive control, variance baseline | §5.5, G0 | Must precede every comparison |
| P-1.4 | Analysis pipeline: `raw/` → `derived/` → `figures/`, one-command regeneration | §5.3, G5 | Build before there is data to be tempted by |
| P-1.5 | Freeze benchmark task lists; build annotation tooling; run the step-type taxonomy $\kappa$ study | §7.1, §7.2, G1 | Needs a second annotator — recruit now |
| P-1.6 | Phase 1 workload characterization, cloud-side | §7.3, S3 | Step counts, token distributions, tool durations, DAG structure, prefix reuse, privacy classification. Only the *local* energy split waits. |
| P-1.7 | Audit the six unread papers (HERA, HybridFlow, PAAC, PRISM, IslandRun, HeRo); write the differentiation table | Appendix A, related work | Cheap, removes a known blind spot |
| P-1.8 | Network characterization from the actual deployment network | §9.3 | Diurnal RTT/bandwidth/jitter per endpoint |

### 16.5 Tier 2 — Platform A measurements with lasting value

| ID | Task | Serves | Notes |
|---|---|---|---|
| P-1.9 | **NPU 5 bring-up via OpenVINO** | G0 / R1 | Same NPU generation as Platform B, so this result transfers directly. Outcome is a hard input to whether NPU stays a target. |
| P-1.10 | Energy harness: RAPL domains + battery discharge, cross-validated | P0.3, P0.4, G0 | The two-signal validation described in §16.2 — no wall meter needed |
| P-1.11 | Thermal harness and protocol constants: warm-up duration, throttle threshold, cooldown ceiling. Characterize 55 W turbo sustainability in the laptop chassis. | §5.4, G0 | Developed on the hard case |
| P-1.12 | Crossover surfaces: prefill/decode throughput and J/token per (model, quantization, target ∈ {LP-E, P, Xe3 iGPU, NPU 5}) | S4, H7, Phase 3a | Platform A half of the controlled contrast. **No dGPU.** |
| P-1.13 | Power-cap sweep (15/25/55 W), battery-vs-mains, and memory-pressure sweep under 16 GB unified | H2 first signal, Platform A exclusive | Usable hardware axes without new silicon |
| P-1.15 | Memory contention study: weights + KV cache + iGPU/NPU working set within 16 GB unified, as context length grows | §16.3(3) | The binding constraint on Platform A; likely a headline limitation figure |
| P-1.14 | Measurement-overhead characterization | §5.1 | Especially on LP-E cores |

### 16.6 Tier 3 — genuinely blocked until the EVO-T2 arrives

- Panther Lake / NPU 5 throughput, energy, and bandwidth figures
- The cross-generation H2 experiment (needs both halves)
- OCuLink FPGA attach, the HLS datapath, and OmniSim cross-validation (S12, Phase 3b)
- Any claim about 18A silicon

### 16.7 Phase −1 ordering

1. **P-1.9 (NPU bring-up) and P-1.2/P-1.3 (harness + A/A) in parallel, first.** One resolves the largest technical unknown; the other is a prerequisite for all measurement.
2. **P-1.1 (H1 pilot) immediately after A/A passes.** Nothing else in the program matters if H1 fails, and it is cheap to test.
3. P-1.5, P-1.6, P-1.7 run continuously alongside.
4. Tier 2 measurements as the harness stabilizes.

### 16.8 Gate −1 (before Phase 0 / EVO-T2 arrival)

| Criterion | Response if failed |
|---|---|
| A/A passes; per-metric CV known | Stop; fix harness. No comparison is valid without this. |
| **Energy cross-validation passes the three-part criterion** (AM-004): per-execution-target regression of baseline-corrected battery energy on RAPL energy across ≥8 load levels gives (a) $R^2 \ge 0.95$, (b) slope $\in [1.0, 1.5]$, (c) intercept consistent with an independently measured idle platform baseline. Minimum resolvable energy difference reported per target. | **Slope < 1.0 on any target: hard failure** — a subset cannot grow faster than the whole, so a signal is broken. Stop and fix. $R^2 < 0.95$: report energy with an explicit error band and downgrade all energy-based conclusions to qualitative. **Target-dependent slope divergence:** treat as a RAPL domain-coverage gap, document which domains are uncounted, and do not report energy for the affected target without stating the omission. |
| H1 pilot yields a directional answer with CIs separated from the noise floor | If inconclusive, increase $n$ before expanding scope — do not proceed to build on an unresolved premise |
| NPU verdict recorded (works / doesn't / with what caveats) | Feeds G0 and R1 directly |
| Benchmark lists frozen and committed; taxonomy $\kappa \ge 0.75$ | Revise taxonomy before it becomes load-bearing |
| **Topology mapping committed from a pinned (AC) session** | See §16.9 |

### 16.9 Note on the topology verification and power pinning

The Phase −1 harness correctly refused to commit a P/LP-E mapping measured in an unpinned (battery) session. Two observations for whoever closes this out:

1. **The mapping and the evidence have different power sensitivity.** Which logical CPUs are P versus LP-E is a static hardware property. The *separation ratio* used to verify it is not — it depends on power plan, thermal headroom, and DVFS state. So a battery-session result is weaker evidence, not a different answer.
2. **Therefore the AC re-run has a predictable direction.** On AC with greater thermal and power headroom, P-cores have more turbo room than LP-E cores, so the separation ratio should come out **larger** than the 1.309× observed on battery. If the AC run yields a *smaller* ratio, something is wrong — with the pinning, the thermal state, or the kernel — and it must be investigated before the mapping is committed. Record this as a directional prediction before running, so the confirmation is meaningful rather than post-hoc.

**Configuration facts: resolved.** See §16.1. Remaining action: correct AF-001 and re-verify AF-002 when the shell backend is restored.

---

## Appendix B — Audit findings log

Per §5, integrity findings are logged, not silently fixed. Each entry records what was found, its blast radius, and the corrective action.

### AF-001 — Platform mislabel in the provenance document

**Found:** 2026-07-29, before data collection. `analysis/aipc-c1/MACHINE.md` line 12 labels the platform "(Lunar Lake)." The platform is Panther Lake (Core Ultra 5 325).

**Blast radius:** MACHINE.md is the provenance source for the `platform` block of every run manifest (§5.2). Uncorrected, every manifest inherits a wrong platform identity, and any figure caption or paper claim derived from manifests would misattribute the silicon generation. This is precisely the failure class §5 exists to catch.

**Evidence for Panther Lake:** (a) SKU numbering — `Core Ultra 5 325` is a 3xx part, i.e. Core Ultra Series 3 = Panther Lake; Lunar Lake parts are 2xxV. (b) Graphics device ID `VEN_8086&DEV_B090` is in the Xe3 range; Lunar Lake's is `64A0` (Xe2). (c) Core names Cougar Cove / Darkmont are Panther Lake; Lunar Lake is Lion Cove / Skymont.

**Provenance-hygiene note:** the 4 P + 4 LP-E, 8C/8T topology **does not discriminate** between the two — Lunar Lake has the identical 4+4/8T signature (4 Lion Cove + 4 Skymont). The SKU number and the graphics DID carry the argument; the topology does not. Also confirm whether "Cougar Cove / Darkmont" is a field reported by the probe or an inference added during identification — if the latter, it cannot serve as independent evidence. Keep the discriminating evidence explicit in MACHINE.md so the identification is auditable rather than asserted.

**Action:** correct line 12; add the three discriminators as inline evidence; record the correction commit SHA here.

### AF-002 — Probe artifacts are recorded, not live

**Found:** 2026-07-29. Shell backend unavailable this session, so §16.1 rests on artifacts recorded 2026-07-28 rather than a live probe. Internal agreement across four artifacts and consistency with the reported OS build (26200) make them credible.

**Blast radius:** low but non-zero. Driver and firmware versions in particular can change between recording and measurement, and §5.2 requires those in every manifest.

**Action:** on shell restoration, re-run the probe, diff against the committed artifacts, and record the probe-artifact SHA-256 values in the manifest emitter so every run pins the exact provenance snapshot it relied on.

---

## Appendix A — Unverified assumptions

Every item here must be confirmed by measurement before it appears in a paper. Flagged so they cannot silently become "facts."

| Assumption | Status | Resolved by |
|---|---|---|
| Platform B ≈136 GB/s peak memory bandwidth (derived from LPDDR5X-8533, 128-bit) | **Unverified** | P0 STREAM benchmark |
| Platform A ≈120 GB/s peak memory bandwidth (derived from LPDDR5X-7467, 128-bit) | **Unverified** | P-1 STREAM benchmark |
| Platform B NPU 5 is the same ~50 TOPS bin as Platform A (the X7 358H's 180 TOPS is a CPU+GPU+NPU aggregate) | **Unverified — load-bearing for H7's "NPU held constant" claim** | Vendor spec confirmation + P0.1 measurement |
| NPU 5 standalone achieved throughput (50 TOPS is peak INT8, not achieved) | **Unverified** | P-1.9 / P0.1 |
| NPU per-domain power telemetry exists | **Unverified** | P0.3 |
| OpenVINO supports target models/quantizations on NPU 5 | **Unverified** | P0.1 |
| OCuLink FPGA attach is practical | **Unverified** | P0.11 |
| OmniSim applies to the intended datapath style | **Unverified** | Consult Rishov/Callie |
| Routing overhead is ~5% of response time at request granularity | From practitioner analysis, **not peer-reviewed** | S6 |
| HERA / HybridFlow / PAAC / PRISM / IslandRun / HeRo evaluation quality | **Abstracts only — not audited** | Read before related-work is written |
