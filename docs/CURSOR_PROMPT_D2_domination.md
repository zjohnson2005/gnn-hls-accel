# Cursor dispatch — D2: hunting for dominated hardware configurations

Supersedes `CURSOR_PROMPT_D1_headline.md`. Track: `agent`. Runs after C2. Attrib frozen.

---

## Why D1's two-arm design was too weak

D1 predicted cost rising and accuracy falling with slower hardware. Both directions are
**deducible without measurement** — slower escalates more, so cloud cost rises; faster keeps more
work on the weaker local model, so accuracy falls. A two-arm run measures the magnitude of a
tautology.

Two points give a slope. **Three give curvature, and curvature is where the finding is.**

## The hypothesis

Cost is monotone in local speed. **Accuracy may not be.**

At the fast end, more work stays local on a weaker model — accuracy falls. At the slow end, a
second mechanism appears: `n_out_pred` is a per-step-type **median**, so roughly half of locally
executed steps already overrun their deadline — this is E-FILTER's existing `deadline_overrun`
field, and it is expected behaviour, not a bug. On slower silicon those steps overrun by more. If
overrun produces truncation, timeout, or downstream cascade, accuracy falls at the slow end too.

```
fast      low cost      low accuracy
middle    medium cost   HIGH accuracy
slow      HIGH cost     low accuracy      ← dominated by middle on BOTH objectives
```

> **P-D2a — some hardware configurations are strictly Pareto-dominated.** There exists a
> configuration *h* and another configuration *h′* such that *h′* is better on **both** cloud cost
> and task accuracy. Buying less silicon costs more money and produces worse answers.

**Falsified if** the (cost, accuracy) points are monotone along the hardware axis with no dominated
configuration, CIs excluding domination.

If P-D2a holds, naive reasoning about this decision is not imprecise — it is **wrong in sign**.
That is the strongest possible argument for a search.

## P-D2b — domination survives policy retuning

The obvious objection is *"you tuned the policy badly for the slow config."* Kill it in the design.

Sweep the deadline at every hardware point and compare **best achievable** outcomes per
configuration, not outcomes at one shared deadline.

> **P-D2b — a dominated configuration remains dominated at its own optimal deadline.** If true, the
> hardware is the problem and no routing policy rescues it.

This folds the co-design gain (CS-05) into the same run: the gap between *best-per-hardware* and
*fixed-policy* outcomes is the value of co-designing.

## P-D2c — the mediating mechanism

Domination observed is a result. Domination *explained* is a contribution.

> **P-D2c — deadline-overrun rate mediates the accuracy loss at the slow end.** Overrun rate rises
> with slower hardware, and steps that overran have materially worse task outcomes than steps that
> did not.

Test it directly: regress task success on overrun count, controlling for hardware point. If the
mediation holds, you have named *why* slow silicon costs accuracy — which is the collaborator
meeting's "elongated setup time affecting quality," made precise and measured.

**This matters because a naive claim that quality degrades with slow hardware is physically wrong.**
Deterministic inference computes the same thing regardless of speed. It can only degrade through a
mediating path, and this identifies which one.

## Design

```
hardware points   3, spanning the widest quality-safe throughput range available
deadlines         3 per hardware point, from C2's derived t_pred distribution
tasks             ≥15 per cell, identical set and seeds across all cells
                  = 9 cells
```

**Axis selection — preflight, same as D1.0.** The axis must move `R_prefill` and `R_decode`
**without touching model quality**, or the accuracy half is confounded and the whole run is void.

| Axis | Quality-safe | Status |
|:--|:--|:--|
| Sustained power limit | yes | unverified — may be locked |
| `INFERENCE_NUM_THREADS` 8 / 6 / 4 | yes | available; proxies core count, a real BOM coordinate |
| Core type P vs LP-E | yes | blocked — `mslice-a1a6` UNCLEAR |
| Quantization | **no** | different models, different accuracy. Disqualified. |

Three points need a **wide** range — aim for ≥2× between fastest and slowest, because curvature is
invisible over a narrow span. If no axis provides it, report and stop rather than running a design
that cannot detect the effect.

**Isolation invariant:** between cells, only `R_prefill` and `R_decode` may differ. Identical tasks,
seeds, prompts, step types, `n_out_pred`, model IR, quantization, corpus, tool world. Enforced in
code, with a test that fails on violation.

Interleave cells. Never all of one hardware point then all of another — thermal and position drift
would ride along exactly where the curvature is expected.

## Measurement

Cloud enabled. Per step, everything C2 records, plus:

```
deadline_overrun (bool), overrun_magnitude_s
task_success, step_contributed_to_failure (where attributable)
usd_cost, prompt/completion tokens, cache read/creation
completion_chars, completion_bytes      ← behavioural currency, AM-021
```

Per cell: total cost, success rate, escalation rate, overrun rate, JCT distribution.

**Cost ceiling.** 9 cells × 15 tasks with a handful of escalated steps each is a few dollars against
$50 with $0.15 spent. Set a hard ceiling, abort on breach, and report spend against it.

## Analysis

1. **The frontier.** Plot (cost, accuracy) for all 9 cells. Mark the Pareto set. **Any point outside
   it, with CIs excluding both neighbours, is a dominated configuration.**
2. **Best-per-hardware.** For each hardware point, take its best deadline. Re-plot. Does domination
   survive?
3. **Mediation.** Regress success on overrun count with hardware as a covariate. Report the
   coefficient and whether it explains the slow-end accuracy loss.
4. **Co-design gap.** Best-per-hardware versus best-at-fixed-policy, per configuration.
5. Paired bootstrap over tasks throughout, ≥10,000 resamples.

**Materiality:** a dominated configuration requires CIs on *both* objectives excluding the
dominating point. Anything weaker is reported as suggestive, not as domination.

## Outcomes, all reportable

- **P-D2a holds** → *"Some hardware configurations are strictly dominated — cheaper silicon that
  costs more to run and answers worse."* The headline, and it makes the DSE unavoidable.
- **P-D2a fails, monotone frontier** → D1's original result: hardware moves both objectives in
  opposite directions. Weaker, still material, still forces a search over a trade-off.
- **P-D2b fails** (domination disappears at optimal policy) → **that is itself the co-design
  result**: retuning the routing policy recovers a configuration that looked dominated. Quantify
  the recovery — it is the value of co-design stated in objective units.
- **Everything null** → hardware does not materially affect hybrid outcomes for this workload.
  A genuine negative that revisits the project's premise, obtained cheaply and early.

## Carry forward

Paging gate exclusionary, baseline `e6bae93f`. Lifecycle: run dir first, per-block JSONL with
flush+fsync, seal last. Startup dry-run. Flattened block record. Canary either side. Machine lock
per timed block. Detached launch. Placement readback recorded though not varied. Corrected proxy
per AM-027.

## Report

1. Preflight: axis chosen, the three achieved throughput points, and the fast/slow ratio.
2. Isolation-invariant verification.
3. The 9-cell table: cost, accuracy, escalation rate, overrun rate, with CIs.
4. **The frontier plot and the Pareto set.** Name any dominated configuration explicitly.
5. Best-per-hardware frontier — does domination survive?
6. The mediation regression.
7. Co-design gap in objective units.
8. Cloud spend against ceiling.
9. One line: **dominated, monotone trade-off, co-design-recoverable, or null.**

Every number carries its run_id per AM-027(b). Deadlines in distribution units.

## Standing constraints

No commit, push, or raw mutation. Cloud authorized within the declared ceiling, every call
ledgered. No credential value logged, printed, hashed, or committed — provider, model ID and
pricing table version only.
