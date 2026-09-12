"""Emit Phase-2 artifacts under ``analysis/censor/phase2/``."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from censor.artifact_audit import (
    corpus_audit_stats,
    render_artifact_audit_md,
    waterfall_with_without_llm_judge,
)
from censor.oracle import STATIC_ASSUMPTION_NOTE
from censor.phase2_constants import CostModelParams
from censor.quality_bounds import BoundInterval, bounds_table, format_bounds_table
from censor.schema import Trajectory, group_by_scaffold
from censor.sensitivity import oaat_tornado, realizable_ceiling_metrics
from censor.waterfall import WaterfallStep, run_all_scaffolds

THREATS_MD = """# Threats to validity (a priori)

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
"""


def write_threats(out_dir: Path) -> Path:
    path = out_dir / "THREATS.md"
    path.write_text(THREATS_MD, encoding="utf-8")
    return path


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def waterfall_to_rows(steps: Sequence[WaterfallStep]) -> list[dict[str, Any]]:
    rows = []
    for s in steps:
        rows.append(
            {
                "scaffold": s.scaffold,
                "stage": s.stage,
                "friction_subset": "+".join(s.friction_subset) if s.friction_subset else "none",
                "mean_seconds": s.mean_seconds,
                "mean_usd": s.mean_usd,
                "cloud_only_seconds": s.cloud_only_seconds,
                "unreachable_fraction": s.unreachable_fraction
                if s.unreachable_fraction is not None
                else "",
                "ci_low": s.ci_low if s.ci_low is not None else "",
                "ci_high": s.ci_high if s.ci_high is not None else "",
                "n_trajectories": s.n_trajectories,
                "f4_label": s.f4_label,
                "invariance_bias": s.invariance_bias,
                "static_assumption_flag": s.static_assumption_flag,
                "static_assumption_note": STATIC_ASSUMPTION_NOTE,
            }
        )
    return rows


def quality_to_rows(
    scaffold: str, intervals: Sequence[BoundInterval]
) -> list[dict[str, Any]]:
    return [
        {
            "scaffold": scaffold,
            "assumption_set": r.assumption_set,
            "lower": r.lower,
            "upper": r.upper,
            "width": r.width,
            "n_trajectories": r.n_trajectories,
            "n_turns": r.n_turns,
            "notes": r.notes,
        }
        for r in intervals
    ]


def plot_waterfall(steps: Sequence[WaterfallStep], path: Path) -> None:
    import matplotlib.pyplot as plt

    by: dict[str, list[WaterfallStep]] = {}
    for s in steps:
        by.setdefault(s.scaffold, []).append(s)
    scaffolds = sorted(by)
    if not scaffolds:
        return
    n = len(scaffolds)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n, 4.0), squeeze=False)
    for ax, scaffold in zip(axes[0], scaffolds):
        rows = by[scaffold]
        labels = [r.stage for r in rows]
        vals = [r.mean_seconds for r in rows]
        ax.bar(labels, vals, color="#3d5a5b")
        ax.set_title(scaffold, fontsize=9)
        ax.set_ylabel("mean oracle seconds")
        ax.tick_params(axis="x", labelrotation=0)
        ax.axhline(0, color="#222", lw=0.5)
    fig.suptitle(
        "Cost waterfall by scaffold (never pooled)\n"
        "F4 UNMEASURED · invariance bias UNMEASURED · static assumption",
        fontsize=10,
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def plot_tornado(rows: Sequence[dict[str, Any]], path: Path) -> None:
    import matplotlib.pyplot as plt

    by: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by.setdefault(r["scaffold"], []).append(r)
    scaffolds = sorted(by)
    if not scaffolds:
        return
    n = len(scaffolds)
    fig, axes = plt.subplots(n, 1, figsize=(8.0, max(2.8, 2.2 * n)), squeeze=False)
    for ax, scaffold in zip(axes[:, 0], scaffolds):
        rr = sorted(by[scaffold], key=lambda x: x["influence"])
        names = [x["parameter"] for x in rr]
        lows = [x["realizable_share_at_low"] for x in rr]
        highs = [x["realizable_share_at_high"] for x in rr]
        y = np.arange(len(names))
        for i, (lo, hi) in enumerate(zip(lows, highs)):
            ax.plot([lo, hi], [i, i], color="#3d5a5b", lw=2)
            ax.plot([lo, hi], [i, i], "o", color="#c45c26")
        ax.set_yticks(y)
        ax.set_yticklabels(names, fontsize=7)
        ax.axvline(0.80, color="#a33", ls="--", lw=0.8, label="80% gate")
        ax.set_xlabel("realizable share of naive ceiling")
        ax.set_title(f"{scaffold} (F4 UNMEASURED)", fontsize=9)
        ax.legend(fontsize=7, loc="lower right")
    fig.suptitle("Parameter sensitivity (tornado)", fontsize=11)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def write_findings(
    out_dir: Path,
    *,
    unreachable: dict[str, float],
    unreachable_ci: dict[str, tuple[float, float]],
    shapley_rows: Sequence[dict[str, Any]],
    quality_rows: Sequence[dict[str, Any]],
    tornado_rows: Sequence[dict[str, Any]],
    gate_weak: bool,
    params: CostModelParams,
) -> Path:
    lines = [
        "# FINDINGS — Phase 2 censor limit study (cost-side frictions)",
        "",
        "## 1. UNREACHABLE FRACTION per scaffold (cost-side only, with CI)",
        "",
        "UNREACHABLE FRACTION = (W0 − W4) / (W0 − cloud_only_baseline)",
        "where cloud_only_baseline is **serial** all-cloud (no concurrency fantasy).",
        "",
        "| scaffold | unreachable_fraction | CI low | CI high |",
        "|---|---:|---:|---:|",
    ]
    for scaffold in sorted(unreachable):
        lo, hi = unreachable_ci.get(scaffold, (float("nan"), float("nan")))
        lines.append(
            f"| {scaffold} | {unreachable[scaffold]:.4f} | {lo:.4f} | {hi:.4f} |"
        )
    lines.extend(
        [
            "",
            "Static trajectory invariance assumed — bound is loose "
            "(upper bound on an upper bound). Invariance bias: **UNMEASURED**.",
            "",
            "## 2. Frictions ranked by Shapley contribution",
            "",
            "| scaffold | friction | mean_marginal_seconds | share_of_abs_total |",
            "|---|---|---:|---:|",
        ]
    )
    for r in shapley_rows:
        lines.append(
            f"| {r['scaffold']} | {r['friction']} | "
            f"{r['mean_marginal_seconds']:.6f} | {r['share_of_abs_total']:.4f} |"
        )
    lines.extend(
        [
            "",
            "Shapley values average marginal contributions over all 24 orderings. "
            "The sequential W0–W4 waterfall is **not** ordering-free.",
            "",
            "## 3. Quality bounds (never a point estimate)",
            "",
            "| scaffold | assumption set | lower | upper | width |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for r in quality_rows:
        lines.append(
            f"| {r['scaffold']} | {r['assumption_set']} | {r['lower']:.4f} | "
            f"{r['upper']:.4f} | {r['width']:.4f} |"
        )
    lines.extend(
        [
            "",
            "Manski (1990) bottom-up procedure. No point estimate of a "
            "realizable quality ceiling is reported at any stage.",
            "",
            "## 4. Explicit flags",
            "",
            "- **F4 UNMEASURED** — local capacity stub (`capacity_factor=1.0`); "
            "Phase 5 hardware curves required.",
            "- **invariance bias UNMEASURED** — static oracle; Phase 4 online slice.",
            "",
            "## 5. Parameters most needing hardware measurement",
            "",
        ]
    )
    # Rank tornado by influence, prefer F4 / local latency / prefill.
    ranked = sorted(tornado_rows, key=lambda r: -r["influence"])
    lines.append("| rank | parameter | influence | flips_80pct_gate |")
    lines.append("|---:|---|---:|---|")
    for i, r in enumerate(ranked[:12], 1):
        lines.append(
            f"| {i} | {r['parameter']} | {r['influence']:.4f} | "
            f"{r['flips_80pct_gate']} |"
        )
    lines.extend(
        [
            "",
            "Priority: any parameter that flips the 80% gate, then F4 capacity,",
            "local prefill/decode, and cloud prefill rates.",
            "",
            "## Gate",
            "",
        ]
    )
    if gate_weak:
        lines.append(
            "**GATE TRIGGERED:** cost-side realizable ceiling exceeds 80% of the "
            "naive ceiling across all scaffolds. Frictions are small under these "
            "sourced priors; the central claim that routing frictions erase most "
            "oracle headroom is **weak** on this corpus. This is a valid result — "
            "parameters were not tuned toward a more interesting outcome."
        )
    else:
        lines.append(
            "Gate not triggered: at least one scaffold has realizable share of "
            "naive ceiling ≤ 80% under default sourced priors."
        )
    lines.extend(
        [
            "",
            "## Method notes",
            "",
            f"- {STATIC_ASSUMPTION_NOTE}",
            f"- Router cost citation: see `params.ROUTER_COST_CITATION` / "
            f"`analysis/censor/phase2/params_audit.json`.",
            "",
        ]
    )
    path = out_dir / "FINDINGS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    # Keep params audit next to findings
    (out_dir / "params_audit.json").write_text(
        json.dumps(params.to_audit_dict(), indent=2) + "\n", encoding="utf-8"
    )
    return path


def bootstrap_unreachable_ci(
    trajectories: Sequence[Trajectory],
    params: CostModelParams,
    *,
    seed: int = 0,
    n_boot: int = 500,
) -> dict[str, tuple[float, float]]:
    out: dict[str, tuple[float, float]] = {}
    for i, (scaffold, trajs) in enumerate(
        sorted(group_by_scaffold(trajectories).items())
    ):
        rng = np.random.default_rng(seed + 17 * i)
        n = len(trajs)
        if n == 0:
            continue
        boots = []
        for _ in range(n_boot):
            idx = rng.integers(0, n, size=n)
            sample = [trajs[j] for j in idx]
            m = realizable_ceiling_metrics(sample, params, seed=0)
            boots.append(m["unreachable_fraction"])
        lo, hi = np.percentile(boots, [2.5, 97.5])
        out[scaffold] = (float(lo), float(hi))
    return out


def run_phase2(
    trajectories: Sequence[Trajectory],
    out_dir: Path,
    *,
    params: CostModelParams | None = None,
    seed: int = 0,
    n_boot: int = 500,
) -> dict[str, Path]:
    params = params or CostModelParams()
    out_dir.mkdir(parents=True, exist_ok=True)

    # THREATS before interpretation
    threats_path = write_threats(out_dir)

    waterfalls, shapley_rows, unreachable = run_all_scaffolds(
        trajectories, params, seed=seed, n_boot=n_boot
    )
    unreach_ci = bootstrap_unreachable_ci(
        trajectories, params, seed=seed, n_boot=n_boot
    )

    wf_rows = waterfall_to_rows(waterfalls)
    _write_csv(
        out_dir / "waterfall_cost.csv",
        wf_rows,
        fieldnames=list(wf_rows[0].keys()) if wf_rows else ["scaffold"],
    )
    _write_csv(
        out_dir / "shapley.csv",
        shapley_rows,
        fieldnames=list(shapley_rows[0].keys()) if shapley_rows else ["scaffold"],
    )

    quality_rows: list[dict[str, Any]] = []
    for scaffold, trajs in sorted(group_by_scaffold(trajectories).items()):
        intervals = bounds_table(trajs, trajectories)
        quality_rows.extend(quality_to_rows(scaffold, intervals))
        # also stash markdown fragment
        (out_dir / f"quality_bounds_{scaffold}.md").write_text(
            format_bounds_table(intervals) + "\n", encoding="utf-8"
        )
    _write_csv(
        out_dir / "quality_bounds.csv",
        quality_rows,
        fieldnames=list(quality_rows[0].keys()) if quality_rows else ["scaffold"],
    )

    tornado_rows: list[dict[str, Any]] = []
    for i, (scaffold, trajs) in enumerate(
        sorted(group_by_scaffold(trajectories).items())
    ):
        tornado_rows.extend(oaat_tornado(trajs, params, seed=seed + i))
    _write_csv(
        out_dir / "tornado.csv",
        tornado_rows,
        fieldnames=list(tornado_rows[0].keys()) if tornado_rows else ["scaffold"],
    )

    plot_waterfall(waterfalls, out_dir / "waterfall.png")
    plot_tornado(tornado_rows, out_dir / "tornado.png")

    stats = corpus_audit_stats(trajectories)
    judge = waterfall_with_without_llm_judge(trajectories, params, seed=seed)
    (out_dir / "artifact_audit.md").write_text(
        render_artifact_audit_md(stats, judge), encoding="utf-8"
    )

    # Gate: realizable share > 0.80 on ALL scaffolds ⇒ weak claim
    shares = []
    for scaffold, trajs in sorted(group_by_scaffold(trajectories).items()):
        m = realizable_ceiling_metrics(trajs, params, seed=seed)
        shares.append(m["realizable_share_of_naive"])
    gate_weak = bool(shares) and all(s > 0.80 for s in shares)

    findings_path = write_findings(
        out_dir,
        unreachable=unreachable,
        unreachable_ci=unreach_ci,
        shapley_rows=shapley_rows,
        quality_rows=quality_rows,
        tornado_rows=tornado_rows,
        gate_weak=gate_weak,
        params=params,
    )

    return {
        "THREATS.md": threats_path,
        "FINDINGS.md": findings_path,
        "waterfall_cost.csv": out_dir / "waterfall_cost.csv",
        "quality_bounds.csv": out_dir / "quality_bounds.csv",
        "shapley.csv": out_dir / "shapley.csv",
        "waterfall.png": out_dir / "waterfall.png",
        "tornado.png": out_dir / "tornado.png",
        "artifact_audit.md": out_dir / "artifact_audit.md",
    }
