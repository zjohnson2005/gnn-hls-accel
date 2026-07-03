"""LightningSim DSE wrapper for orchestration engine HLS kernel.

After `vitis_hls -f orchestration_engine/run_hls.tcl`, point --solution-dir at
the directory containing solution1/ (typically oe_proj/sol1).

Requires fifo-advisor / LightningSim on the remote box (same setup as fifo_pareto/).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Repo root must be on PYTHONPATH when invoked as `python -m orchestration_engine.eval.dse_sweep`
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from fifo_pareto.sweep import LightningSimEvaluator, SweepConfig, StreamingSweep


def run_dse(solution_dir: Path, n_samples: int, batch_size: int) -> dict:
    solution_dir = solution_dir.resolve()
    evaluator = LightningSimEvaluator(solution_dir)
    sweep = StreamingSweep(
        evaluator,
        SweepConfig(n_samples=n_samples, batch_size=batch_size),
    )
    state = sweep.run()
    baseline = evaluator.baseline_max()

    points = [
        {
            "latency": p.latency,
            "bram": p.bram,
            "deadlock": p.deadlock,
            "fifo_sizes": p.fifo_sizes,
        }
        for p in state.all_points
        if p.latency is not None
    ]
    frontier = [
        {
            "latency": p.latency,
            "bram": p.bram,
            "deadlock": p.deadlock,
        }
        for p in state.frontier
    ]

    return {
        "solution_dir": str(solution_dir),
        "n_samples": n_samples,
        "num_fifos": evaluator.num_fifos,
        "baseline_max_latency": baseline.latency,
        "baseline_max_bram": baseline.bram,
        "evaluations": len(state.all_points),
        "deadlocks": state.deadlocks,
        "pareto_frontier": frontier,
        "all_points": points,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Orchestration engine LightningSim DSE")
    parser.add_argument(
        "--solution-dir",
        type=Path,
        required=True,
        help="Path to Vitis HLS solution dir (contains solution1/)",
    )
    parser.add_argument("--n-samples", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    try:
        report = run_dse(args.solution_dir, args.n_samples, args.batch_size)
    except ImportError as exc:
        raise SystemExit(
            "fifo-advisor not installed. See fifo_pareto/README.md for conda setup."
        ) from exc

    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text)
        print(f"Wrote {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
