#!/usr/bin/env python3
"""Live Pareto frontier animation for FIFO depth DSE (LightningSim V2)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

from fifo_pareto.pareto import DesignPoint, FrontierState, pareto_frontier
from fifo_pareto.sweep import (
    SweepConfig,
    StreamingSweep,
    load_results_json,
    make_evaluator,
    replay_batches,
)


def _latency_tick(value: float, _pos: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{int(value / 1_000)}K"
    return str(int(value))


class LiveParetoPlot:
    def __init__(
        self,
        *,
        design_name: str,
        baseline_max: DesignPoint | None,
        baseline_min: DesignPoint | None,
        fps: int = 30,
        save_path: Path | None = None,
    ):
        self.design_name = design_name
        self.baseline_max = baseline_max
        self.baseline_min = baseline_min
        self.fps = fps
        self.save_path = save_path

        self.state = FrontierState()
        self.pending_batches: list[list[DesignPoint]] = []
        self.elapsed = 0.0
        self.eps = 0.0
        self.done = False

        plt.style.use("dark_background")
        self.fig, self.ax = plt.subplots(figsize=(10, 7))
        self.fig.patch.set_facecolor("#0d1117")
        self.ax.set_facecolor("#161b22")

        (self.scatter_all,) = self.ax.plot(
            [], [], "o", color="#58a6ff", alpha=0.35, markersize=5, linestyle="None"
        )
        (self.scatter_dead,) = self.ax.plot(
            [], [], "x", color="#f85149", alpha=0.5, markersize=6, linestyle="None"
        )
        (self.line_frontier,) = self.ax.plot(
            [], [], "-", color="#3fb950", linewidth=2.5, alpha=0.95
        )
        (self.scatter_frontier,) = self.ax.plot(
            [], [], "o", color="#3fb950", markersize=9, linestyle="None", zorder=5
        )

        self.baseline_max_artist = None
        self.baseline_min_artist = None
        if baseline_max and baseline_max.valid:
            (self.baseline_max_artist,) = self.ax.plot(
                [baseline_max.bram],
                [baseline_max.latency],
                marker="X",
                color="#ffa657",
                markersize=14,
                linestyle="None",
                zorder=10,
            )
        if baseline_min and baseline_min.valid:
            (self.baseline_min_artist,) = self.ax.plot(
                [baseline_min.bram],
                [baseline_min.latency],
                marker="X",
                color="#c9d1d9",
                markersize=14,
                linestyle="None",
                zorder=10,
            )

        self.hud = self.fig.text(
            0.02,
            0.98,
            "",
            transform=self.fig.transFigure,
            va="top",
            ha="left",
            fontsize=11,
            family="monospace",
            color="#c9d1d9",
        )

        self.ax.set_xlabel("Total FIFO BRAM18K", color="#c9d1d9", fontsize=13)
        self.ax.set_ylabel("Latency (cycles)", color="#c9d1d9", fontsize=13)
        self.ax.set_title(
            f"FIFO Depth Pareto Frontier — {design_name}",
            color="#f0f6fc",
            fontsize=15,
            pad=12,
        )
        self.ax.grid(True, linestyle="--", alpha=0.25, color="#30363d")
        self.ax.yaxis.set_major_formatter(FuncFormatter(_latency_tick))

        legend = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="#58a6ff",
                linestyle="None",
                markersize=8,
                label="Evaluated",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="#3fb950",
                linestyle="None",
                markersize=10,
                label="Pareto frontier",
            ),
            Line2D(
                [0],
                [0],
                marker="X",
                color="#ffa657",
                linestyle="None",
                markersize=12,
                label="Baseline-Max",
            ),
            Line2D(
                [0],
                [0],
                marker="X",
                color="#c9d1d9",
                linestyle="None",
                markersize=12,
                label="Baseline-Min",
            ),
            Line2D(
                [0],
                [0],
                marker="x",
                color="#f85149",
                linestyle="None",
                markersize=10,
                label="Deadlock",
            ),
        ]
        self.ax.legend(handles=legend, loc="upper right", framealpha=0.9, fontsize=10)

    def _refresh_artists(self) -> None:
        valid = [p for p in self.state.all_points if p.valid]
        dead = [p for p in self.state.all_points if p.deadlock]

        if valid:
            self.scatter_all.set_data([p.bram for p in valid], [p.latency for p in valid])
        if dead:
            bram_dead = [p.bram if p.bram is not None else 0 for p in dead]
            self.scatter_dead.set_data(bram_dead, [0 for _ in dead])

        frontier = self.state.frontier
        if frontier:
            brams = [p.bram for p in frontier]
            lats = [p.latency for p in frontier]
            self.scatter_frontier.set_data(brams, lats)
            self.line_frontier.set_data(brams, lats)

        xs: list[float] = []
        ys: list[float] = []
        if self.baseline_max and self.baseline_max.valid:
            xs.append(float(self.baseline_max.bram))
            ys.append(float(self.baseline_max.latency))
        if self.baseline_min and self.baseline_min.valid:
            xs.append(float(self.baseline_min.bram))
            ys.append(float(self.baseline_min.latency))
        xs.extend(float(p.bram) for p in valid if p.bram is not None)
        ys.extend(float(p.latency) for p in valid if p.latency is not None)
        if xs and ys:
            pad_x = max(max(xs) * 0.08, 1)
            pad_y = max(max(ys) * 0.05, 1000)
            self.ax.set_xlim(-pad_x * 0.05, max(xs) + pad_x)
            self.ax.set_ylim(min(ys) - pad_y, max(ys) + pad_y)

        self.hud.set_text(
            f"evaluations: {self.state.evaluations:,}\n"
            f"frontier:    {len(self.state.frontier)}\n"
            f"deadlocks:   {self.state.deadlocks}\n"
            f"elapsed:     {self.elapsed:.2f}s\n"
            f"throughput:  {self.eps:,.0f} evals/s"
        )

    def push_batch(self, batch: list[DesignPoint], elapsed: float, eps: float) -> None:
        self.state.all_points.extend(batch)
        self.state.evaluations += len(batch)
        self.state.deadlocks += sum(1 for p in batch if p.deadlock)
        self.state.frontier = pareto_frontier(self.state.all_points)
        self.elapsed = elapsed
        self.eps = eps

    def queue_batches(self, batches: list[list[DesignPoint]]) -> None:
        self.pending_batches = batches

    def _step(self, _frame: int) -> list:
        if self.pending_batches:
            batch = self.pending_batches.pop(0)
            self.elapsed += max(0.04, len(batch) / max(self.eps, 500.0))
            self.eps = max(self.eps, len(batch) / 0.04)
            self.push_batch(batch, self.elapsed, self.eps)
        elif not self.done:
            self.done = True
            if self.save_path:
                self.fig.savefig(self.save_path, dpi=200, bbox_inches="tight")
        self._refresh_artists()
        return [
            self.scatter_all,
            self.scatter_dead,
            self.line_frontier,
            self.scatter_frontier,
            self.hud,
        ]

    def run_live(self, sweep: StreamingSweep) -> FrontierState:
        interval_ms = max(1, int(1000 / self.fps))

        def on_batch(state: FrontierState, elapsed: float, eps: float) -> None:
            self.elapsed = elapsed
            self.eps = eps
            self.state = state
            self._refresh_artists()
            plt.pause(0.001)

        final = sweep.run(on_batch=on_batch)
        self.state = final
        self.done = True
        self._refresh_artists()
        plt.show()
        return final

    def run_replay(self) -> FrontierState:
        interval_ms = max(1, int(1000 / self.fps))
        self.anim = FuncAnimation(
            self.fig,
            self._step,
            interval=interval_ms,
            blit=False,
            cache_frame_data=False,
            repeat=False,
        )
        plt.show()
        return self.state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fifo-pareto-live",
        description=(
            "Live Pareto frontier demo for FIFO depth DSE. "
            "Uses LightningSim V2 parallel evaluation when a Vitis HLS solution "
            "directory is supplied; otherwise runs a synthetic model offline."
        ),
    )
    parser.add_argument(
        "--solution-dir",
        type=Path,
        default=None,
        help="Vitis HLS solution1/ directory (requires fifo-advisor + LightningSim).",
    )
    parser.add_argument(
        "--replay",
        type=Path,
        default=None,
        help="Replay evaluations from fifo-advisor JSON output.",
    )
    parser.add_argument(
        "--synthetic",
        choices=["small", "k15mmtree"],
        default="small",
        help="Synthetic design when --solution-dir is not set (default: small).",
    )
    parser.add_argument(
        "--n-samples",
        type=int,
        default=2000,
        help="Number of FIFO configurations to evaluate (default: 2000).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=128,
        help="Parallel batch size (LightningSim V2 DSE, default: 128).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed for sampling.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=24,
        help="Animation frame rate for replay mode.",
    )
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        help="Save final plot to this PNG path.",
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        help="Write sweep results as fifo-advisor-compatible JSON.",
    )
    return parser


def export_results(path: Path, points: list[DesignPoint]) -> None:
    frontier_mask = {id(p): p in pareto_frontier(points) for p in points}
    payload = {
        "source": "fifo_pareto.live_demo",
        "evaluations": [],
    }
    for point in points:
        payload["evaluations"].append(
            {
                "fifo_sizes": {str(k): v for k, v in point.fifo_sizes.items()},
                "deadlock": point.deadlock,
                "latency": point.latency,
                "bram_usage_total": point.bram,
                "is_pareto_optimal": frontier_mask.get(id(point), False),
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def main() -> None:
    args = build_parser().parse_args()

    if args.replay is not None:
        points, _meta = load_results_json(args.replay)
        design_name = args.replay.stem
        plot = LiveParetoPlot(
            design_name=design_name,
            baseline_max=None,
            baseline_min=None,
            fps=args.fps,
            save_path=args.save,
        )
        batches = list(replay_batches(points, batch_size=args.batch_size))
        plot.queue_batches(batches)
        plot.run_replay()
        return

    evaluator = make_evaluator(
        solution_dir=args.solution_dir,
        synthetic=args.synthetic,
        seed=args.seed,
    )
    design_name = (
        args.solution_dir.name if args.solution_dir else f"{args.synthetic} synthetic"
    )

    print(f"Design: {design_name}  |  FIFOs: {evaluator.num_fifos}")
    print(f"Sampling {args.n_samples} points in batches of {args.batch_size}...")

    baseline_max = evaluator.baseline_max()
    baseline_min = evaluator.baseline_min()

    plot = LiveParetoPlot(
        design_name=design_name,
        baseline_max=baseline_max,
        baseline_min=baseline_min,
        fps=args.fps,
        save_path=args.save,
    )

    sweep = StreamingSweep(
        evaluator,
        SweepConfig(
            n_samples=args.n_samples,
            batch_size=args.batch_size,
            seed=args.seed,
        ),
    )
    final = plot.run_live(sweep)

    print(
        f"Done: {final.evaluations} evaluations, "
        f"{len(final.frontier)} Pareto points, "
        f"{final.deadlocks} deadlocks"
    )

    if args.export:
        export_results(args.export, final.all_points)
        print(f"Wrote {args.export}")


if __name__ == "__main__":
    main()
