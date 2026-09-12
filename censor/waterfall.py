"""Waterfall + Shapley-style ordering sensitivity. Never pool scaffolds."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from censor.oracle import STATIC_ASSUMPTION_NOTE, cloud_only_baseline, cost_oracle
from censor.phase2_constants import CostModelParams
from censor.schema import Trajectory, group_by_scaffold

FRICTIONS = ("F1", "F2", "F3", "F4")


@dataclass(frozen=True)
class WaterfallStep:
    scaffold: str
    stage: str
    friction_subset: tuple[str, ...]
    mean_seconds: float
    mean_usd: float
    cloud_only_seconds: float
    unreachable_fraction: float | None
    f4_label: str
    invariance_bias: str
    static_assumption_flag: bool
    n_trajectories: int
    ci_low: float | None = None
    ci_high: float | None = None


def _mask_from_subset(subset: Iterable[str]) -> dict[str, bool]:
    s = set(subset)
    return {f: (f in s) for f in FRICTIONS}


def _scaffold_mean_oracle(
    trajectories: Sequence[Trajectory],
    params: CostModelParams,
    *,
    rng: np.random.Generator,
    n_boot: int = 500,
) -> tuple[float, float, float, float, float]:
    """Return mean_seconds, mean_usd, mean_cloud_s, ci_low, ci_high for oracle."""
    secs = []
    usds = []
    cloud_secs = []
    for tr in trajectories:
        r = cost_oracle(tr, params)
        secs.append(r.seconds)
        usds.append(r.usd)
        base = cloud_only_baseline(tr, params)
        cloud_secs.append(base.seconds)
    secs_a = np.asarray(secs, dtype=float)
    usds_a = np.asarray(usds, dtype=float)
    cloud_a = np.asarray(cloud_secs, dtype=float)
    mean_s = float(secs_a.mean()) if len(secs_a) else 0.0
    mean_u = float(usds_a.mean()) if len(usds_a) else 0.0
    mean_c = float(cloud_a.mean()) if len(cloud_a) else 0.0
    if len(secs_a) < 2 or n_boot <= 0:
        return mean_s, mean_u, mean_c, mean_s, mean_s
    boots = []
    n = len(secs_a)
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boots.append(float(secs_a[idx].mean()))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return mean_s, mean_u, mean_c, float(lo), float(hi)


def unreachable_fraction(w0: float, w4: float, cloud_only: float) -> float:
    """(W0 - W4) / (W0 - cloud_only) — share of naive headroom that is unreachable.

    Algebraically equal to (W4 - W0) / (cloud_only - W0).
    ``cloud_only`` must be the *serial* all-cloud baseline (no concurrency
    fantasy). Values > 1 mean frictions erase all naive headroom and more.
    """
    denom = w0 - cloud_only
    if abs(denom) < 1e-12:
        # No naive headroom: if W4≈W0, unreachable=0; else undefined → nan.
        if abs(w0 - w4) < 1e-12:
            return 0.0
        return float("nan")
    return float((w0 - w4) / denom)


def sequential_waterfall(
    trajectories: Sequence[Trajectory],
    params: CostModelParams | None = None,
    *,
    order: Sequence[str] = FRICTIONS,
    seed: int = 0,
    n_boot: int = 500,
) -> list[WaterfallStep]:
    """W0..W4 sequential waterfall for one scaffold's trajectories."""
    params = params or CostModelParams()
    rng = np.random.default_rng(seed)
    if not trajectories:
        return []
    scaffold = trajectories[0].scaffold
    steps: list[WaterfallStep] = []

    # W0: all frictions off
    subset: list[str] = []
    p0 = params.with_friction_mask(_mask_from_subset(subset))
    m_s, m_u, m_c, lo, hi = _scaffold_mean_oracle(
        trajectories, p0, rng=rng, n_boot=n_boot
    )
    w0 = m_s
    cloud_only = m_c
    steps.append(
        WaterfallStep(
            scaffold=scaffold,
            stage="W0",
            friction_subset=tuple(subset),
            mean_seconds=m_s,
            mean_usd=m_u,
            cloud_only_seconds=cloud_only,
            unreachable_fraction=None,
            f4_label="F4 off",
            invariance_bias="UNMEASURED",
            static_assumption_flag=True,
            n_trajectories=len(trajectories),
            ci_low=lo,
            ci_high=hi,
        )
    )

    stage_names = ["W1", "W2", "W3", "W4"]
    for stage, friction in zip(stage_names, order):
        subset = subset + [friction]
        p = params.with_friction_mask(_mask_from_subset(subset))
        m_s, m_u, _m_c, lo, hi = _scaffold_mean_oracle(
            trajectories, p, rng=rng, n_boot=n_boot
        )
        unreach = None
        if stage == "W4":
            unreach = unreachable_fraction(w0, m_s, cloud_only)
        f4_label = "F4 UNMEASURED" if "F4" in subset else "F4 off"
        steps.append(
            WaterfallStep(
                scaffold=scaffold,
                stage=stage,
                friction_subset=tuple(subset),
                mean_seconds=m_s,
                mean_usd=m_u,
                cloud_only_seconds=cloud_only,
                unreachable_fraction=unreach,
                f4_label=f4_label,
                invariance_bias="UNMEASURED",
                static_assumption_flag=True,
                n_trajectories=len(trajectories),
                ci_low=lo,
                ci_high=hi,
            )
        )
    return steps


def shapley_friction_attribution(
    trajectories: Sequence[Trajectory],
    params: CostModelParams | None = None,
    *,
    seed: int = 0,
) -> list[dict]:
    """Average marginal contribution over all 24 friction orderings.

    Do NOT present the sequential waterfall as if ordering were free.
    """
    params = params or CostModelParams()
    if not trajectories:
        return []
    scaffold = trajectories[0].scaffold
    rng = np.random.default_rng(seed)

    # Value(S) = mean oracle seconds under friction subset S
    cache: dict[frozenset[str], float] = {}

    def value(subset: set[str]) -> float:
        key = frozenset(subset)
        if key not in cache:
            p = params.with_friction_mask(_mask_from_subset(subset))
            m_s, _, _, _, _ = _scaffold_mean_oracle(
                trajectories, p, rng=rng, n_boot=0
            )
            cache[key] = m_s
        return cache[key]

    v0 = value(set())
    contrib = {f: 0.0 for f in FRICTIONS}
    orderings = list(itertools.permutations(FRICTIONS))
    for ordering in orderings:
        current: set[str] = set()
        prev_v = v0
        for f in ordering:
            current = current | {f}
            new_v = value(current)
            contrib[f] += new_v - prev_v
            prev_v = new_v
    n_ord = float(len(orderings))
    rows = []
    total_abs = sum(abs(contrib[f]) for f in FRICTIONS) / n_ord
    for f in FRICTIONS:
        avg = contrib[f] / n_ord
        rows.append(
            {
                "scaffold": scaffold,
                "friction": f,
                "mean_marginal_seconds": avg,
                "share_of_abs_total": (abs(avg) / total_abs) if total_abs else 0.0,
                "n_orderings": len(orderings),
                "f4_label": "F4 UNMEASURED" if f == "F4" else "",
                "static_assumption_note": STATIC_ASSUMPTION_NOTE,
                "invariance_bias": "UNMEASURED",
            }
        )
    rows.sort(key=lambda r: -abs(r["mean_marginal_seconds"]))
    return rows


def run_all_scaffolds(
    trajectories: Sequence[Trajectory],
    params: CostModelParams | None = None,
    *,
    seed: int = 0,
    n_boot: int = 500,
) -> tuple[list[WaterfallStep], list[dict], dict[str, float]]:
    """Per-scaffold waterfall + Shapley. Never pools across scaffolds."""
    params = params or CostModelParams()
    by = group_by_scaffold(trajectories)
    waterfalls: list[WaterfallStep] = []
    shapley_rows: list[dict] = []
    unreachable: dict[str, float] = {}
    for i, scaffold in enumerate(sorted(by)):
        trajs = by[scaffold]
        steps = sequential_waterfall(
            trajs, params, seed=seed + i * 1009, n_boot=n_boot
        )
        waterfalls.extend(steps)
        shapley_rows.extend(
            shapley_friction_attribution(trajs, params, seed=seed + i * 1009)
        )
        w0 = next(s for s in steps if s.stage == "W0")
        w4 = next(s for s in steps if s.stage == "W4")
        # cloud_only from W0 pass
        p0 = params.with_friction_mask(_mask_from_subset([]))
        rng = np.random.default_rng(seed + i * 1009)
        _, _, mean_c, _, _ = _scaffold_mean_oracle(trajs, p0, rng=rng, n_boot=0)
        unreachable[scaffold] = unreachable_fraction(
            w0.mean_seconds, w4.mean_seconds, mean_c
        )
        # attach unreachable on W4 step (already set in sequential)
    return waterfalls, shapley_rows, unreachable
