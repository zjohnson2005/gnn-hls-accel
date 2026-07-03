from __future__ import annotations

import random
from dataclasses import dataclass

from fifo_pareto.pareto import DesignPoint, bram18k_for_fifo, bram_breakpoints


@dataclass(frozen=True)
class SyntheticFifo:
    fifo_id: int
    width_bits: int
    critical_depth: int
    baseline_depth: int


@dataclass
class SyntheticDesign:
    """Analytical stall model for offline Pareto demos (no Vitis/LightningSim)."""

    name: str
    fifos: list[SyntheticFifo]
    base_latency: float
    seed: int = 7

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self._design_spaces: dict[int, list[int]] = {}
        for fifo in self.fifos:
            self._design_spaces[fifo.fifo_id] = bram_breakpoints(
                2, fifo.width_bits, fifo.baseline_depth
            )

    @property
    def num_fifos(self) -> int:
        return len(self.fifos)

    def baseline_max(self) -> DesignPoint:
        sizes = {f.fifo_id: f.baseline_depth for f in self.fifos}
        return self.eval_single(sizes, sample_id=-2)

    def baseline_min(self) -> DesignPoint:
        sizes = {f.fifo_id: 2 for f in self.fifos}
        return self.eval_single(sizes, sample_id=-1)

    def sample_configs(self, n: int, grouped: bool = True) -> list[dict[int, int]]:
        _ = grouped  # synthetic model has no array grouping metadata
        configs: list[dict[int, int]] = []
        for _ in range(n):
            cfg = {
                fifo.fifo_id: self._rng.choice(self._design_spaces[fifo.fifo_id])
                for fifo in self.fifos
            }
            configs.append(cfg)
        return configs

    def eval_single(self, sizes: dict[int, int], sample_id: int = 0) -> DesignPoint:
        bram = sum(
            bram18k_for_fifo(sizes[f.fifo_id], f.width_bits) for f in self.fifos
        )
        if any(sizes.get(f.fifo_id, 2) < 2 for f in self.fifos):
            return DesignPoint(sizes, None, None, True, sample_id)

        latency = self.base_latency
        for fifo in self.fifos:
            depth = sizes[fifo.fifo_id]
            if depth < fifo.critical_depth:
                ratio = depth / fifo.critical_depth
                stall = (1.0 - ratio) * fifo.critical_depth * 12.0
                latency += stall

        # A few grouped FIFOs deadlock together at minimum depth (paper Fig. 3).
        shallow = [f for f in self.fifos if sizes[f.fifo_id] <= 2]
        if len(shallow) > len(self.fifos) * 0.55:
            return DesignPoint(sizes, None, bram, True, sample_id)

        return DesignPoint(sizes, latency, bram, False, sample_id)

    def eval_parallel(
        self, configs: list[dict[int, int]], start_id: int = 0
    ) -> list[DesignPoint]:
        return [
            self.eval_single(cfg, sample_id=start_id + idx)
            for idx, cfg in enumerate(configs)
        ]


def k15mmtree_like(seed: int = 7) -> SyntheticDesign:
    """~180 FIFO Stream-HLS benchmark shape (FIFOAdvisor Table II)."""
    rng = random.Random(seed)
    fifos: list[SyntheticFifo] = []
    for fifo_id in range(178):
        width = rng.choice([32, 64, 128, 256])
        baseline = rng.choice([512, 1024, 2048, 4096, 8192])
        critical = max(2, baseline // rng.choice([2, 4, 8, 16]))
        fifos.append(
            SyntheticFifo(
                fifo_id=fifo_id,
                width_bits=width,
                critical_depth=critical,
                baseline_depth=baseline,
            )
        )
    return SyntheticDesign(
        name="k15mmtree (synthetic)",
        fifos=fifos,
        base_latency=1_850_000.0,
        seed=seed,
    )


def small_demo_design(seed: int = 7) -> SyntheticDesign:
    """Compact design for quick laptop demos (~24 FIFOs)."""
    rng = random.Random(seed)
    fifos = []
    for fifo_id in range(24):
        width = rng.choice([32, 64, 128])
        baseline = rng.choice([256, 512, 1024, 2048])
        critical = max(2, baseline // rng.choice([2, 4, 8]))
        fifos.append(
            SyntheticFifo(
                fifo_id=fifo_id,
                width_bits=width,
                critical_depth=critical,
                baseline_depth=baseline,
            )
        )
    return SyntheticDesign(
        name="demo-gnn-layer (synthetic)",
        fifos=fifos,
        base_latency=420_000.0,
        seed=seed,
    )
