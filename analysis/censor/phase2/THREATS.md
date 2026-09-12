# Threats to validity (a priori)

This document is written **before** interpreting Phase-2 results. It fixes the
identification and measurement threats that the engine is designed around.

## 1. Support violation — why we bound rather than estimate

Logged trajectories were generated under a **single tier**. The corpus contains
no logged `route_local` action. Estimating costs or outcomes under a hybrid
routing policy is off-policy evaluation with **zero support** for the
counterfactual action. Importance-sampling estimators are undefined, not merely
high-variance. This is an identification problem.

We therefore split the problem:

- **Cost side (F1–F4):** deterministic functions of trajectory structure
  (turn counts, context lengths, tier transitions). Computable exactly without
  knowing whether local would have answered correctly.
- **Quality side:** Manski-style worst-case bounds (Manski 1990), with
  assumptions added one at a time. **Never a point estimate.**

## 2. Trajectory dependence and static-oracle looseness

Single-turn routing oracles take a max over a reward matrix because queries are
independent. Multi-turn agents are not: routing turn t changes turns
t+1+. The matrix-max oracle does not transfer.

Phase 2's cost oracle assumes **static trajectory invariance** (logged
structure held fixed under counterfactual tier assignments). That assumption
makes the bound **loose** — an upper bound on an upper bound. Every oracle
output carries `static_assumption_flag=true` and the prose note in the engine.
**Invariance bias: UNMEASURED** until Phase 4's online slice. We do not
implement naive counterfactual branch sampling (Tang & Wiens: naively
augmenting logged data with counterfactual annotations is biased).

## 3. Artifact inheritance from public outcome labels

Task outcomes may come from SWE-bench exact evaluation, synthetic harness
labels, or (in other corpora) LLM-judge scores. Published work shows judge
scoring can diverge from exact-match by 10–24pp on knowledge tasks, and
truncation has affected up to 65% of responses in some settings — both can
inflate apparent headroom. Phase 2 reports truncation and parse-failure rates
and recomputes the waterfall with LLM-judge rows excluded when present.

## 4. Quality-model assumptions and dependent results

Quality results depend on the assumption set:

| Assumption | Content | What it affects |
|---|---|---|
| Manski only | Unobserved local outcome ∈ {0,1} | Widest bounds |
| A1 monotonicity | Cloud fail ⇒ local fail | Tightens upper bound |
| A2 task-class transfer | Local rate = measured rate on class | Requires local observations; skipped if none |
| A3 smoothness | Lipschitz in difficulty proxy | Optional; only if A1/A2 leave bounds uselessly wide |

Cost-side headline numbers (unreachable fraction, Shapley) **do not** depend on
A1–A3. Quality tables never collapse to a point.

## 5. Single-corpus / single-scaffold generalization limits

Results are reported **per scaffold, never pooled**. Generalization beyond the
normalized corpus (benchmark family, model, harness) is not identified.
OA-01 is one scaffold/model/benchmark configuration; TurnTrace scaffolds are
characterization workloads, not the same task distribution.

## 6. F4 local capacity

F4 is a Phase-2 stub (`capacity_factor=1.0`). Every F4-dependent output is
labeled **UNMEASURED** until hardware discharge/recharge calibration (Phase 5).

## 7. Gate (pre-registered)

If the cost-side realizable ceiling exceeds 80% of the naive ceiling across
**all** scaffolds, frictions are small and the central claim is weak. Report
that plainly. Do **not** tune parameters toward a more interesting result.
