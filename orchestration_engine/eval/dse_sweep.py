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

from fifo_pareto.sweep import LightningSimEvaluator, SweepConfig, StreamingSweep, make_evaluator


def run_dse_synthetic(n_samples: int, batch_size: int) -> dict:
    evaluator = make_evaluator(synthetic="small")
    sweep = StreamingSweep(
        evaluator,
        SweepConfig(n_samples=n_samples, batch_size=batch_size),
    )
    state = sweep.run()
    baseline = evaluator.baseline_max()
    frontier = [
        {"latency": p.latency, "bram": p.bram, "deadlock": p.deadlock}
        for p in state.frontier
    ]
    return {
        "source": "synthetic",
        "solution_dir": "synthetic",
        "note": "Offline stall model; gcn_stream LS trace unavailable on this toolchain",
        "n_samples": n_samples,
        "num_fifos": evaluator.num_fifos,
        "baseline_max_latency": baseline.latency,
        "baseline_max_bram": baseline.bram,
        "evaluations": len(state.all_points),
        "deadlocks": state.deadlocks,
        "pareto_frontier": frontier,
    }


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
        default=None,
        help="Path to Vitis HLS solution dir (sol1/ or solution1/)",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Offline Pareto demo (no Vitis/LightningSim trace)",
    )
    parser.add_argument("--n-samples", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.synthetic:
        if args.output and "phase2" in str(args.output).replace("\\", "/"):
            raise SystemExit(
                "Refusing to write synthetic DSE under characterization/out/phase2/. "
                "Use fifo_pareto.live_demo for offline demos only."
            )
        report = run_dse_synthetic(args.n_samples, args.batch_size)
    elif args.solution_dir is None:
        parser.error("Provide --solution-dir or --synthetic")
    else:
        try:
            report = run_dse(args.solution_dir, args.n_samples, args.batch_size)
        except ImportError as exc:
            raise SystemExit(
                "fifo-advisor not installed. See fifo_pareto/README.md for conda setup."
            ) from exc
        report["source"] = "lightningsim"
        trace = args.solution_dir.resolve() / "trace.pkl"
        if not trace.is_file():
            raise SystemExit("ERROR: {0} missing — cannot emit lightningsim DSE report".format(trace))

    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text)
        print(f"Wrote {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
