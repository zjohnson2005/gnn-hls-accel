from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class DesignPoint:
    fifo_sizes: dict[int, int]
    latency: float | None
    bram: int | None
    deadlock: bool
    sample_id: int = 0

    @property
    def valid(self) -> bool:
        return (
            not self.deadlock
            and self.latency is not None
            and self.bram is not None
        )


@dataclass
class FrontierState:
    all_points: list[DesignPoint] = field(default_factory=list)
    frontier: list[DesignPoint] = field(default_factory=list)
    deadlocks: int = 0
    evaluations: int = 0


def bram18k_for_fifo(depth: int, width_bits: int) -> int:
    """BRAM18K count for one FIFO (UltraScale+ model from FIFOAdvisor §III-B)."""
    if depth <= 2:
        return 0
    total_bits = depth * width_bits
    if total_bits < 1024:
        return 0

    configs = [(1024, 18), (2048, 9), (4096, 4), (8192, 2), (16384, 1)]
    remaining = total_bits
    count = 0
    for block_depth, block_width in configs:
        if block_width > width_bits:
            continue
        elems_per_block = block_depth * block_width // width_bits
        if elems_per_block <= 0:
            continue
        blocks = remaining // (elems_per_block * width_bits)
        if blocks <= 0:
            continue
        count += blocks
        remaining -= blocks * elems_per_block * width_bits
        if remaining <= 0:
            break
    return count


def bram_breakpoints(_depth: int, width_bits: int, max_depth: int) -> list[int]:
    """Depth values that change BRAM allocation (search-space pruning from §III-C)."""
    candidates = {2, max_depth}
    for d in range(3, min(max_depth, 512) + 1):
        candidates.add(d)
    probe = 512
    while probe < max_depth:
        probe = min(probe * 2, max_depth)
        candidates.add(probe)

    last_bram = -1
    breakpoints: list[int] = []
    for d in sorted(candidates):
        b = bram18k_for_fifo(d, width_bits)
        if b != last_bram:
            breakpoints.append(d)
            last_bram = b
    if max_depth not in breakpoints:
        breakpoints.append(max_depth)
    return sorted(set(breakpoints))


def pareto_frontier(points: Iterable[DesignPoint]) -> list[DesignPoint]:
    """Non-dominated set minimizing latency and BRAM (FIFOAdvisor §III)."""
    valid = [p for p in points if p.valid]
    if not valid:
        return []

    frontier: list[DesignPoint] = []
    for candidate in valid:
        dominated = False
        to_remove: list[int] = []
        for idx, kept in enumerate(frontier):
            if (
                kept.latency <= candidate.latency  # type: ignore[operator]
                and kept.bram <= candidate.bram  # type: ignore[operator]
                and (
                    kept.latency < candidate.latency  # type: ignore[operator]
                    or kept.bram < candidate.bram  # type: ignore[operator]
                )
            ):
                dominated = True
                break
            if (
                candidate.latency <= kept.latency  # type: ignore[operator]
                and candidate.bram <= kept.bram  # type: ignore[operator]
                and (
                    candidate.latency < kept.latency  # type: ignore[operator]
                    or candidate.bram < kept.bram  # type: ignore[operator]
                )
            ):
                to_remove.append(idx)
        if dominated:
            continue
        for idx in reversed(to_remove):
            frontier.pop(idx)
        frontier.append(candidate)

    return sorted(frontier, key=lambda p: (p.bram, p.latency))  # type: ignore[arg-type, return-value]
