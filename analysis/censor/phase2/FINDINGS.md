# FINDINGS — Phase 2 censor limit study (cost-side frictions)

> **SMOKE TEST — corpus gate not met (1 scaffold, 15 trajectories). No generalization claim is supported.**
>
> Prompt-1 gate required ≥3 scaffolds and ≥500 trajectories. This run has
> **1 scaffold** (`mini_swe_agent`) and **15 trajectories** (normalized OA-01;
> not 17). Bootstrap CIs below are **within-sample precision** over these 15
> trajectories, **not** a generalization interval. Scaffold was specified as an
> independent variable and **cannot be varied** with this corpus, so friction
> magnitudes are **untested for scaffold-invariance**.

See also: `THREATS.md` (a priori), `DIAGNOSTIC.md` (absolute-unit dump + F3 audit).

## 0. Critical correction (read before any headline)

The previously reported unreachable fraction **0.689** with F3 at ~98% Shapley
is **not a valid hybrid-routing result**. Part-1 audit:

- F3 divides aggregated **sequential** cloud wall-time by a fantasy concurrency
  factor (8 when off → 1.19 when on).
- Per-trajectory max in-flight cloud requests under the oracle = **1**.
- No cross-trajectory batching is modeled.

F3 was binding because a **concurrency cap was applied to sequential work**,
not because measured concurrency hit a rate-limit ceiling. F3 implementation
was **not** changed in this pass (diagnosis only); see §4 for the F3-off re-run.

## 1. UNREACHABLE FRACTION per scaffold (cost-side only)

### With F3 enabled (current engine — **mis-specified**)

| scaffold | unreachable_fraction | CI low | CI high |
|---|---:|---:|---:|
| mini_swe_agent | 0.6893 | 0.6247 | 0.7203 |

Absolutes: W0=15.88 s, W4=92.52 s, serial cloud_only=127.06 s.

### With F3 entirely disabled (thesis frictions only)

| scaffold | unreachable_fraction (F1+F2+F4) |
|---|---:|
| mini_swe_agent | **0.0021** |

Absolutes: W0=15.88 s, W4(F1+F2+F4)=16.11 s, serial cloud_only=127.06 s.

**Load-bearing:** F1+F2+F4 erase ~0.2% of naive headroom. Decision cost and
switching cost do **not** carry the thesis on this smoke corpus. That is a
valid and useful negative result; parameters were not tuned to hide it.

W0 routes **~0.13%** of turns local (essentially all-cloud), then divides cloud
time by `assumed_concurrency=8`. The naive ceiling is a **modeling artifact**,
not a hybrid routing ceiling.

## 2. Frictions ranked by Shapley contribution

### F3 enabled (absolute seconds)

| scaffold | friction | mean_marginal_seconds | share |
|---|---|---:|---:|
| mini_swe_agent | F3 | 74.989 | 0.978 |
| mini_swe_agent | F2 | 1.420 | 0.019 |
| mini_swe_agent | F1 | 0.229 | 0.003 |
| mini_swe_agent | F4 | 0.000 | 0.000 |

F1 (~0.23 s) and F2 (~1.42 s) are **genuinely small in absolute wall-clock**,
not merely small next to a swamping F3.

### F3 disabled (absolute seconds among F1/F2/F4)

| friction | mean_marginal_seconds | relative_share |
|---|---:|---:|
| F1 | 0.229 | 1.000 |
| F2 | 0.000 | 0.000 |
| F4 | 0.000 | 0.000 |

F2 is zero here because the W0 policy stays on cloud (no switches). F2 only
appears in the F3-on Shapley when some orderings push the oracle toward local
and create switches — still small in absolute seconds.

## 3. Quality bounds — do not treat A1 collapse as informative

| scaffold | assumption set | lower | upper | width |
|---|---|---:|---:|---:|
| mini_swe_agent | Manski (no assumptions) | 0.0000 | 1.0000 | 1.0000 |
| mini_swe_agent | Manski + A1 monotonicity | 0.0000 | 0.0667 | 0.0667 |
| mini_swe_agent | Manski + A1 + A2 | 0.0000 | 0.0667 | 0.0667 |
| mini_swe_agent | Manski + A1 + A2 + A3 | 0.0000 | 0.0667 | 0.0667 |

### Outcome diagnosis (n=15)

| class | count | meaning |
|---|---:|---|
| success (`task_outcome=True`) | **0** | measured resolve |
| fail (`task_outcome=False`) | **14** | **measured failure** (ran; did not resolve) |
| null (`task_outcome=None`) | **1** | unlabeled / not a resolved-or-failed label |
| censored=`True` | **1** | turn_cap; overlaps the null row |

A1 (“if cloud failed, local fails”) applied to **14 measured failures** forces
upper≈0 on those trajectories. The residual upper 0.0667 is **1/15** from the
single **censored/null** trajectory (matplotlib-25433), where A1 does not bind.
That residual is a **missing-data artifact**, not a quality finding. The
near-zero A1 upper bound on the fail majority is also **not** a hybrid-quality
estimate: it only restates “cloud failed ⇒ assume local fails” on a 0-resolve
sample.

**Cross-check:** OA-01 official eval reports `resolved_instances: 0` on this
retained set. Published mini-SWE-agent + GPT-4.1 SWE-bench resolve rates are
nontrivial; **0/15 resolved is unrepresentative** of that literature baseline
(hard/truncated/empty-patch biased smoke set — see `empty_patch`, `turn_cap`,
`nonstreaming_subject_default` flags). Do not generalize quality bounds.

## 4. Explicit flags

- **F4 UNMEASURED**
- **invariance bias UNMEASURED**
- **F3 MISAPPLIED** (concurrency ceiling on sequential trajectories) — diagnosed, not fixed
- **SMOKE / corpus gate FAILED**

## 5. Parameters most needing hardware measurement

Priority after this diagnostic (not for “interesting” results — for correct
identification):

1. **Remove or redesign F3** so it only binds when in-flight cloud concurrency
   actually exceeds 1 (batch throughput study), never as a serial wall-clock dial.
2. Local prefill/decode tok/s (currently priors; W0 barely uses local anyway).
3. F2 switch costs under policies that actually switch tiers.
4. F4 capacity curves (still stub).

Tornado rankings from the F3-on run are dominated by the same mis-specified
concurrency dial and should not set hardware priority until F3 is corrected.

## Gate (80% realizable)

Under the **mis-specified** F3-on run, realizable share of naive ceiling is
well below 80% — but that gate result is **not meaningful** given Part 1.
Under F3-off, nearly all naive headroom remains (unreachable ≈ 0.002): if
anything, the **thesis that decision/switching frictions erase headroom is
weak on this smoke corpus**. Reported plainly; not tuned away.

## Method notes

- Static trajectory invariance assumed; invariance bias UNMEASURED.
- Full absolute dump: `analysis/censor/phase2/DIAGNOSTIC.md`.
- Corpus `corpus/normalized/` left read-only.
