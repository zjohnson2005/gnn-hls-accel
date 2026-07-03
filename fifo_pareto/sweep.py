from __future__ import annotations

import json
import random
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fifo_pareto.pareto import DesignPoint, FrontierState, pareto_frontier
from fifo_pareto.synthetic import SyntheticDesign, k15mmtree_like, small_demo_design


class Evaluator(Protocol):
    num_fifos: int

    def baseline_max(self) -> DesignPoint: ...
    def baseline_min(self) -> DesignPoint: ...
    def sample_configs(self, n: int, grouped: bool = True) -> list[dict[int, int]]: ...
    def eval_parallel(
        self, configs: list[dict[int, int]], start_id: int = 0
    ) -> list[DesignPoint]: ...


@dataclass
class SweepConfig:
    n_samples: int = 2000
    batch_size: int = 128
    seed: int = 7
    grouped: bool = True


class LightningSimEvaluator:
    """Wraps fifo-advisor LSEnv (LightningSim V2 parallel DSE, FIFOAdvisor §III-A)."""

    def __init__(self, solution_dir: Path):
        from fifo_advisor.opt_env import LSEnv

        self._env = LSEnv(solution_dir)
        self._rng = random.Random(7)
        self._grouped_spaces = self._build_grouped_spaces()
        self._individual_spaces = self._build_individual_spaces()

    @property
    def num_fifos(self) -> int:
        return self._env.num_fifos

    def _build_individual_spaces(self) -> dict[int, list[int]]:
        spaces: dict[int, list[int]] = {}
        for fifo in self._env.fifos:
            spaces[fifo.id] = self._env.trace_base.compiled.get_fifo_design_space(
                [fifo.id], fifo.width
            )
        return spaces

    def _build_grouped_spaces(self) -> dict[str, list[int]]:
        from collections import defaultdict

        groups: dict[str, list] = defaultdict(list)
        for fifo in self._env.fifos:
            groups[fifo.get_display_name()].append(fifo)

        grouped: dict[str, list[int]] = {}
        for name, fifos in groups.items():
            grouped[name] = self._env.trace_base.compiled.get_fifo_design_space(
                [f.id for f in fifos], fifos[0].width
            )
        return grouped

    def _groups(self) -> dict[str, list]:
        from collections import defaultdict

        groups: dict[str, list] = defaultdict(list)
        for fifo in self._env.fifos:
            groups[fifo.get_display_name()].append(fifo)
        return groups

    def sample_configs(self, n: int, grouped: bool = True) -> list[dict[int, int]]:
        configs: list[dict[int, int]] = []
        if grouped:
            groups = self._groups()
            for _ in range(n):
                cfg: dict[int, int] = {}
                for name, fifos in groups.items():
                    depth = self._rng.choice(self._grouped_spaces[name])
                    for fifo in fifos:
                        cfg[fifo.id] = depth
                configs.append(cfg)
        else:
            for _ in range(n):
                cfg = {
                    fifo_id: self._rng.choice(depths)
                    for fifo_id, depths in self._individual_spaces.items()
                }
                configs.append(cfg)
        return configs

    def eval_parallel(
        self, configs: list[dict[int, int]], start_id: int = 0
    ) -> list[DesignPoint]:
        from fifo_advisor.opt_env import EvalResult

        raw: list[EvalResult] = self._env.eval_solution_parallel(configs)
        points: list[DesignPoint] = []
        for idx, result in enumerate(raw):
            points.append(
                DesignPoint(
                    fifo_sizes=result.fifo_sizes,
                    latency=result.latency,
                    bram=result.bram_usage_total,
                    deadlock=result.deadlock,
                    sample_id=start_id + idx,
                )
            )
        return points

    def baseline_max(self) -> DesignPoint:
        result = self._env.eval_solution_default()
        return DesignPoint(
            fifo_sizes=result.fifo_sizes,
            latency=result.latency,
            bram=result.bram_usage_total,
            deadlock=result.deadlock,
            sample_id=-2,
        )

    def baseline_min(self) -> DesignPoint:
        sizes = {fifo.id: 2 for fifo in self._env.fifos}
        result = self._env.eval_solution_single(sizes)
        return DesignPoint(
            fifo_sizes=result.fifo_sizes,
            latency=result.latency,
            bram=result.bram_usage_total,
            deadlock=result.deadlock,
            sample_id=-1,
        )


def make_evaluator(
    *,
    solution_dir: Path | None = None,
    synthetic: str = "small",
    seed: int = 7,
) -> Evaluator:
    if solution_dir is not None:
        return LightningSimEvaluator(solution_dir)
    if synthetic == "k15mmtree":
        return k15mmtree_like(seed=seed)
    return small_demo_design(seed=seed)


class StreamingSweep:
    """Batch-evaluate FIFO configs and emit frontier updates (V2 parallel DSE)."""

    def __init__(self, evaluator: Evaluator, config: SweepConfig | None = None):
        self.evaluator = evaluator
        self.config = config or SweepConfig()
        self.state = FrontierState()

    def run(
        self,
        on_batch: Callable[[FrontierState, float, float], None] | None = None,
    ) -> FrontierState:
        rng = random.Random(self.config.seed)
        _ = rng  # reserved for future stratified sampling

        configs = self.evaluator.sample_configs(
            self.config.n_samples, grouped=self.config.grouped
        )
        t0 = time.perf_counter()
        sample_id = 0

        for start in range(0, len(configs), self.config.batch_size):
            batch = configs[start : start + self.config.batch_size]
            t_batch = time.perf_counter()
            points = self.evaluator.eval_parallel(batch, start_id=sample_id)
            batch_dt = time.perf_counter() - t_batch
            sample_id += len(points)

            self.state.all_points.extend(points)
            self.state.evaluations += len(points)
            self.state.deadlocks += sum(1 for p in points if p.deadlock)
            self.state.frontier = pareto_frontier(self.state.all_points)

            elapsed = time.perf_counter() - t0
            eps = len(points) / batch_dt if batch_dt > 0 else 0.0
            if on_batch is not None:
                on_batch(self.state, elapsed, eps)

        return self.state


def load_results_json(path: Path) -> tuple[list[DesignPoint], dict[str, Any]]:
    payload = json.loads(path.read_text())
    points: list[DesignPoint] = []
    for idx, row in enumerate(payload.get("evaluations", [])):
        sizes = {int(k): int(v) for k, v in row["fifo_sizes"].items()}
        points.append(
            DesignPoint(
                fifo_sizes=sizes,
                latency=row.get("latency"),
                bram=row.get("bram_usage_total"),
                deadlock=bool(row.get("deadlock", False)),
                sample_id=idx,
            )
        )
    return points, payload


def replay_batches(
    points: list[DesignPoint], batch_size: int = 64
) -> Iterator[list[DesignPoint]]:
    for start in range(0, len(points), batch_size):
        yield points[start : start + batch_size]
