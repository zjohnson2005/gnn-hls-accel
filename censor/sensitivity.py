"""One-at-a-time parameter sensitivity + tornado ranking."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, Sequence

import numpy as np

from censor.phase2_constants import CostModelParams, SourcedFloat
from censor.schema import Trajectory
from censor.waterfall import (
    FRICTIONS,
    _mask_from_subset,
    _scaffold_mean_oracle,
    unreachable_fraction,
)


def _set_sourced(obj: Any, field_name: str, value: float) -> Any:
    current = getattr(obj, field_name)
    if isinstance(current, SourcedFloat):
        return replace(
            obj,
            **{
                field_name: SourcedFloat(
                    value, source=current.source + " [sensitivity sweep]"
                )
            },
        )
    return replace(obj, **{field_name: value})


# Plausible ranges: (group, field, low, high, flips_metric)
SWEEP_SPEC: list[tuple[str, str, float, float]] = [
    ("f1", "orch_floor_ms", 3.9, 7.0),
    ("f1", "router_cost_ms.embedding", 1.0, 20.0),
    ("f1", "router_cost_ms.classifier", 20.0, 150.0),
    ("f1", "router_cost_ms.llm", 100.0, 800.0),
    ("f2", "cloud_prefill_ms_per_token", 0.02, 0.15),
    ("f2", "local_prefill_ms_per_token", 0.1, 1.5),
    ("f3", "max_speedup", 1.0, 2.0),
    ("f3", "assumed_concurrency", 2.0, 16.0),
    ("f4", "capacity_factor", 0.5, 1.0),
    ("inference", "local_decode_ms_per_token", 2.0, 30.0),
    ("inference", "local_prefill_ms_per_token", 0.1, 1.5),
]


def _apply_sweep(params: CostModelParams, group: str, field: str, value: float) -> CostModelParams:
    p = deepcopy(params)
    if field.startswith("router_cost_ms."):
        rtype = field.split(".", 1)[1]
        f1 = p.f1
        new_map = dict(f1.router_cost_ms)
        src = new_map[rtype].source
        new_map[rtype] = SourcedFloat(value, src + " [sensitivity sweep]")
        # Also set router_type to match when sweeping that router.
        p = replace(p, f1=replace(f1, router_cost_ms=new_map, router_type=rtype))
        return p
    group_obj = getattr(p, group)
    updated = _set_sourced(group_obj, field, value)
    return replace(p, **{group: updated})


def realizable_ceiling_metrics(
    trajectories: Sequence[Trajectory],
    params: CostModelParams,
    *,
    seed: int = 0,
) -> dict[str, float]:
    """W0, W4, cloud_only, unreachable_fraction, realizable_share_of_naive."""
    rng = np.random.default_rng(seed)
    p0 = params.with_friction_mask(_mask_from_subset([]))
    p4 = params.with_friction_mask(_mask_from_subset(FRICTIONS))
    w0, _, cloud, _, _ = _scaffold_mean_oracle(trajectories, p0, rng=rng, n_boot=0)
    w4, _, _, _, _ = _scaffold_mean_oracle(trajectories, p4, rng=rng, n_boot=0)
    unreach = unreachable_fraction(w0, w4, cloud)
    # Realizable ceiling as fraction of naive ceiling headroom:
    # realizable_share = 1 - unreachable = (cloud - W4) / (cloud - W0)
    headroom = cloud - w0
    realizable = cloud - w4
    share = (realizable / headroom) if abs(headroom) > 1e-15 else 1.0
    return {
        "w0": w0,
        "w4": w4,
        "cloud_only": cloud,
        "unreachable_fraction": unreach,
        "realizable_share_of_naive": share,
    }


def oaat_tornado(
    trajectories: Sequence[Trajectory],
    params: CostModelParams | None = None,
    *,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """One-at-a-time sweep; rank by influence on realizable ceiling share."""
    params = params or CostModelParams()
    if not trajectories:
        return []
    scaffold = trajectories[0].scaffold
    base = realizable_ceiling_metrics(trajectories, params, seed=seed)
    rows: list[dict[str, Any]] = []
    for group, field, lo, hi in SWEEP_SPEC:
        m_lo = realizable_ceiling_metrics(
            trajectories, _apply_sweep(params, group, field, lo), seed=seed
        )
        m_hi = realizable_ceiling_metrics(
            trajectories, _apply_sweep(params, group, field, hi), seed=seed
        )
        influence = abs(
            m_hi["realizable_share_of_naive"] - m_lo["realizable_share_of_naive"]
        )
        # Flag if plausible range flips the 80% gate conclusion.
        gate_base = base["realizable_share_of_naive"] > 0.80
        gate_lo = m_lo["realizable_share_of_naive"] > 0.80
        gate_hi = m_hi["realizable_share_of_naive"] > 0.80
        flips = (gate_lo != gate_base) or (gate_hi != gate_base) or (gate_lo != gate_hi)
        rows.append(
            {
                "scaffold": scaffold,
                "parameter": f"{group}.{field}",
                "low": lo,
                "high": hi,
                "realizable_share_at_low": m_lo["realizable_share_of_naive"],
                "realizable_share_at_high": m_hi["realizable_share_of_naive"],
                "unreachable_at_low": m_lo["unreachable_fraction"],
                "unreachable_at_high": m_hi["unreachable_fraction"],
                "influence": influence,
                "flips_80pct_gate": flips,
                "f4_label": "F4 UNMEASURED" if group == "f4" else "",
                "invariance_bias": "UNMEASURED",
            }
        )
    rows.sort(key=lambda r: -r["influence"])
    return rows
