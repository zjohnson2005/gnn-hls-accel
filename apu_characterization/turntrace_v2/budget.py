"""Open question #3 — trajectory-count vs API budget math (fill before C1 launch)."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CellBudget:
    cell_id: str
    model_id: str
    harnesses: int
    cache_modes: int
    n_trajectories: int
    mean_tokens_in: float
    mean_tokens_out: float
    usd_per_1m_in: float
    usd_per_1m_out: float
    # Extra fixed cost per trajectory (tools, retries, network probes amortized)
    usd_fixed_per_traj: float = 0.0

    @property
    def n_calls_approx(self) -> float:
        # Toy / SWE-lite scaffold default horizon; override via mean_* if needed.
        return float(self.n_trajectories * self.harnesses * self.cache_modes)

    def estimate_usd(self, *, turns_per_traj: float = 8.0) -> dict[str, float]:
        calls = self.n_trajectories * self.harnesses * self.cache_modes * turns_per_traj
        tokens_in = calls * self.mean_tokens_in
        tokens_out = calls * self.mean_tokens_out
        usd_in = tokens_in / 1_000_000.0 * self.usd_per_1m_in
        usd_out = tokens_out / 1_000_000.0 * self.usd_per_1m_out
        usd_fixed = self.n_trajectories * self.harnesses * self.cache_modes * self.usd_fixed_per_traj
        total = usd_in + usd_out + usd_fixed
        return {
            "calls": calls,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "usd_in": usd_in,
            "usd_out": usd_out,
            "usd_fixed": usd_fixed,
            "usd_total": total,
        }


# Spec floor: ≥10 trajectories per (workload × harness × deployment × cache-mode).
DEFAULT_CELLS = (
    CellBudget(
        cell_id="C1",
        model_id="FILL_FRONTIER_MODEL",
        harnesses=2,
        cache_modes=1,
        n_trajectories=10,
        mean_tokens_in=4000.0,
        mean_tokens_out=400.0,
        usd_per_1m_in=0.0,  # fill from provider quote
        usd_per_1m_out=0.0,
    ),
    CellBudget(
        cell_id="C2",
        model_id="FILL_CHEAP_MODEL",
        harnesses=2,
        cache_modes=1,
        n_trajectories=10,
        mean_tokens_in=4000.0,
        mean_tokens_out=400.0,
        usd_per_1m_in=0.0,
        usd_per_1m_out=0.0,
    ),
)


def render_budget_table(
    cells: tuple[CellBudget, ...] = DEFAULT_CELLS,
    *,
    turns_per_traj: float = 8.0,
) -> dict:
    rows = []
    for cell in cells:
        est = cell.estimate_usd(turns_per_traj=turns_per_traj)
        rows.append({**asdict(cell), **est, "status": "blocked_on_price_quote" if cell.usd_per_1m_in <= 0 else "priced"})
    return {
        "turns_per_traj": turns_per_traj,
        "floor_n_trajectories": 10,
        "formula": (
            "cost ≈ n_traj × n_harness × n_cache_modes × turns × "
            "(mean_in×$/1M_in + mean_out×$/1M_out) + fixed"
        ),
        "cells": rows,
        "note": "Do not launch C1/C2 collection until usd_per_1m_* are filled and Est. USD approved.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--turns-per-traj", type=float, default=8.0)
    p.add_argument("--usd-in-c1", type=float, default=0.0)
    p.add_argument("--usd-out-c1", type=float, default=0.0)
    p.add_argument("--usd-in-c2", type=float, default=0.0)
    p.add_argument("--usd-out-c2", type=float, default=0.0)
    p.add_argument("--model-c1", type=str, default="FILL_FRONTIER_MODEL")
    p.add_argument("--model-c2", type=str, default="FILL_CHEAP_MODEL")
    args = p.parse_args(argv)
    cells = (
        CellBudget(
            cell_id="C1",
            model_id=args.model_c1,
            harnesses=2,
            cache_modes=1,
            n_trajectories=10,
            mean_tokens_in=4000.0,
            mean_tokens_out=400.0,
            usd_per_1m_in=args.usd_in_c1,
            usd_per_1m_out=args.usd_out_c1,
        ),
        CellBudget(
            cell_id="C2",
            model_id=args.model_c2,
            harnesses=2,
            cache_modes=1,
            n_trajectories=10,
            mean_tokens_in=4000.0,
            mean_tokens_out=400.0,
            usd_per_1m_in=args.usd_in_c2,
            usd_per_1m_out=args.usd_out_c2,
        ),
    )
    report = render_budget_table(cells, turns_per_traj=args.turns_per_traj)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
