# E-FILTER — the escalation filter study

**Pre-registration draft.** Produces the number behind "the steps that justify the silicon are the
steps that leave." Not yet authorized; predictions and thresholds must be frozen before the first
run.

Implements CS-01 and CS-19.

---

## 1. Question

When an agent runs hybrid rather than local-only, escalation removes a **non-random subset** of
steps from the local machine. Escalation triggers on predicted latency, and predicted latency
tracks size, so the removed steps should be the large ones.

> Does the resource envelope the local silicon actually experiences differ materially from the
> envelope a local-only benchmark would report — and in which direction?

If the answer is "yes, and the benchmark is higher," then sizing silicon from local-only
benchmarks systematically over-specifies, and open-loop sizing is not merely inaccurate but
structurally biased.

## 2. Design — two stages, and the gap between them is a second result

### Stage 1 — the counterfactual filter (no cloud, no second arm)

Run the workload **local-only**, fully instrumented. For every step record the inputs to the
latency predictor. Then apply the escalation rule *offline*, at every deadline in a grid, to
identify which steps **would have** escalated. Compute the resource envelope of the surviving
steps.

One trajectory per task. No cloud spend. No second arm. No confinement mechanism. No second
platform. The entire headline number comes from replaying one log against a rule.

**Stage 1 is knowingly a trace-replay estimate, and trace replay is invalid for policies that
change what work exists.** That is not a defect of the design — it is the null model. Stage 1
assumes the trajectory would be unchanged. It would not be.

### Stage 2 — the realized measurement

Run both arms live:

- **Arm L** — escalation disabled, everything local
- **Arm H** — deadline-aware local-first at deadline *D*, escalated steps served by cloud

Measure the realized local envelope in each. Trajectories will fork after the first escalation, so
this is a **distributional** comparison across tasks, not a paired step-by-step one.

**The gap between Stage 1's counterfactual and Stage 2's realized number is the measured error of
trace-replay reasoning in this setting** — which is contribution C2, obtained as a by-product.

## 3. Instrumentation — the actionable core

Per step, log:

```
step_index, step_type
prompt_tokens_total          # full context presented
prompt_tokens_new            # tokens actually processed this step (post-cache)
cache_hit_tokens             # reused
output_tokens
kv_bytes_resident_before / _after
peak_process_rss
t_pred_prefill, t_pred_decode, t_pred_total
t_actual
execution_target, quantization, power_cap
cache_evicted (bool), evicted_bytes
```

`prompt_tokens_new` versus `prompt_tokens_total` is the single most important pair in this log.
See §6.

## 4. Envelope metrics

Reported per task, then aggregated:

| Metric | Drives |
|:--|:--|
| **peak resident KV bytes** | memory capacity — the headline BOM number |
| **peak local context (tokens)** | same, in legible units |
| **max single-step prefill tokens** | peak compute burst |
| **P95 sustained decode demand** | throughput requirement |
| **peak total footprint** (weights + KV + activations) | the 12.5 GB budget |
| **arithmetic intensity distribution** of surviving steps | memory-vs-compute balance |

Primary endpoint: **peak resident KV bytes, unfiltered versus filtered**, as a function of deadline.

Report the ratio with a bootstrap CI over tasks. **Never report a single max** — peaks are
extreme-value statistics. Use per-task peaks and their distribution, plus P95 of per-step context
as the stable companion statistic.

## 5. Analysis

The output is not one number, it is a **curve**: local resource envelope as a function of
escalation deadline. The headline point is the deadline meeting a stated latency target.

```
over_provisioning(D) = envelope_localonly / envelope_filtered(D)
```

That curve is directly a design artifact — it says how much local silicon each millisecond of
latency budget buys back.

## 6. The caching fork — declare before running

The mechanism assumes escalation selects on *context length*. Whether it does depends on which
term dominates the predictor:

```
t_pred = prompt_tokens_new / R_prefill  +  n_out_pred / R_decode
```

**If prefix caching holds**, `prompt_tokens_new` is small, decode dominates, and escalation selects
on **predicted output length** — not context. Context keeps growing locally and the memory claim
weakens. The over-provisioning would then appear in **throughput and compute**, not capacity.

**If the cache is evicted** — which is the realistic case on a 12.5 GB budget at long context —
the step re-prefills, `prompt_tokens_new` jumps to the full context, prefill dominates
overwhelmingly, and escalation selects hard on context. The memory claim holds strongly.

Both regimes are real and they occur in the *same trajectory*: cached early, evicted late. So the
prediction is that **the filter changes character as the trajectory progresses — output-length
selective early, context selective late.** Which means it bites hardest exactly where memory
pressure is highest.

**Do not bet the study on the memory dimension.** The primary claim is that the envelope differs;
*which dimension it differs in* is itself a finding, and it is determined by the caching regime.
Log `cache_evicted` and `prompt_tokens_new` on every step or the result is uninterpretable.

## 7. Pre-registered predictions

Freeze before the first run.

| | Prediction | Falsified if |
|:--|:--|:--|
| **P1** | The filtered envelope is **lower** than unfiltered on at least one primary dimension | filtered ≥ unfiltered, or ratio < 1.2× on every dimension |
| **P2** | At a deadline meeting a p95 8 s step target, peak local KV falls by **≥ 2×** | < 1.2× with the CI excluding 2× |
| **P3** | Surviving steps have **lower** mean arithmetic intensity — the local workload becomes more decode-dominated | no shift, or a shift upward |
| **P4** | Filter selectivity shifts from output-length-driven to context-driven as context grows | selectivity constant across step index |
| **P5** | Stage 1 **overestimates** the Stage 2 envelope reduction, because escalated steps change the downstream trajectory | Stage 1 within noise of Stage 2, or underestimates |

Materiality threshold: a ratio below **1.2×** is reported as null.

## 8. Held constant

Same tasks, seeds, prompts, model, quantization, execution target, power cap, thermal regime
(warmed to steady state, cooled between runs, randomized order), and step-type taxonomy. Between
Arm L and Arm H **only the escalation policy differs.**

Analysis consumes `blinded_label`. Results stratified by step type per AM-025.

## 9. Failure modes

**Escalation doesn't correlate with size.** Then P1 fails and the mechanism is wrong — a real
negative, and worth knowing before it is in an abstract.

**The workload is too short for context to matter.** Trajectories must be long enough for the
capacity regime to be reached. Verify the context growth curve before committing to a task set.

**Arm L is infeasible.** If local-only cannot complete, there is no benchmark envelope to compare
against — but that is itself a finding (the benchmark you would size from cannot run), and it
should be reported rather than engineered away.

**Peak statistics are noisy.** Mitigated by per-task peaks with bootstrap CIs and the P95
companion statistic. Do not let a single outlier task carry the ratio.

## 10. Dependencies

Stage 1 needs: local backend (M4 partial — exists), agent harness with step-level token accounting
(M3 partial), and the logging above. **It does not need** the cloud backend, the confinement
mechanism that failed A0, the second platform, or NPU bring-up.

Stage 2 additionally needs the cloud backend and cost ledger, both of which exist and are
externally verified.

## 11. Outcomes

- **P1 and P2 hold** — local-only benchmarking systematically over-specifies hybrid silicon by a
  measured factor. Open-loop sizing is structurally biased, and the DSE tool is the correction.
- **P1 holds, P2 fails** — the envelope differs but in throughput rather than capacity. Same
  argument, different dimension, and §6 predicted it.
- **P1 fails** — hybrid deployment does not materially change the local hardware requirement. A
  clean negative that saves the field effort, obtained in month two rather than month twelve.
