"""Low-overhead process instrumentation for the CAP-01 execution plane."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Iterator, Literal

from ..taxonomy import Category

InstrMode = Literal["throttle", "stripped"]


@dataclass
class CategoryTiming:
    wall_ns: int = 0
    cpu_ns: int = 0
    calls: int = 0


@dataclass(frozen=True)
class ProcessTiming:
    wall_ns: int
    cpu_ns: int


@dataclass(frozen=True)
class TurnTrace:
    """CAP-01 trace compatible with the standing category vocabulary."""

    instr_mode: InstrMode
    process: ProcessTiming
    categories: dict[str, CategoryTiming]
    strict_harness_cpu_ns: int
    strict_harness_wall_ns: int
    process_inclusive_cpu_ns: int
    process_inclusive_wall_ns: int
    external_process_cpu_ns: int
    external_process_wall_ns: int
    residual_cpu_ns: int

    def to_dict(self) -> dict[str, object]:
        return {
            "instr_mode": self.instr_mode,
            "process": asdict(self.process),
            "categories": {
                name: asdict(timing) for name, timing in sorted(self.categories.items())
            },
            "strict_harness_cpu_ns": self.strict_harness_cpu_ns,
            "strict_harness_wall_ns": self.strict_harness_wall_ns,
            "process_inclusive_cpu_ns": self.process_inclusive_cpu_ns,
            "process_inclusive_wall_ns": self.process_inclusive_wall_ns,
            "external_process_cpu_ns": self.external_process_cpu_ns,
            "external_process_wall_ns": self.external_process_wall_ns,
            "residual_cpu_ns": self.residual_cpu_ns,
        }


class TurnInstrumentor:
    """Measure process totals and optional category spans.

    ``throttle`` is the primary mode and records category spans. ``stripped``
    retains only process totals plus the verifier exclusion needed for the
    strict harness metric.
    """

    def __init__(self, mode: InstrMode = "throttle") -> None:
        if mode not in ("throttle", "stripped"):
            raise ValueError(f"unsupported instrumentation mode: {mode}")
        self.mode = mode
        self._categories: dict[str, CategoryTiming] = {}
        self._tool_compute_cpu_ns = 0
        self._tool_compute_wall_ns = 0
        self._wall_start_ns: int | None = None
        self._cpu_start_ns: int | None = None
        self._wall_end_ns: int | None = None
        self._cpu_end_ns: int | None = None
        self._external_cpu_ns = 0
        self._external_wall_ns = 0

    def start(self) -> None:
        if self._wall_start_ns is not None:
            raise RuntimeError("instrumentor already started")
        self._cpu_start_ns = time.process_time_ns()
        self._wall_start_ns = time.monotonic_ns()

    @contextmanager
    def span(self, category: Category | str) -> Iterator[None]:
        if self._wall_start_ns is None:
            raise RuntimeError("instrumentor has not started")
        name = category.value if isinstance(category, Category) else str(category)
        cpu_start = time.process_time_ns()
        wall_start = time.monotonic_ns()
        try:
            yield
        finally:
            wall_ns = max(0, time.monotonic_ns() - wall_start)
            cpu_ns = max(0, time.process_time_ns() - cpu_start)
            if name == Category.TOOL_COMPUTE.value:
                self._tool_compute_cpu_ns += cpu_ns
                self._tool_compute_wall_ns += wall_ns
            if self.mode == "throttle":
                timing = self._categories.setdefault(name, CategoryTiming())
                timing.wall_ns += wall_ns
                timing.cpu_ns += cpu_ns
                timing.calls += 1

    def record_external_process(
        self, category: Category | str, *, cpu_ns: int, wall_ns: int
    ) -> None:
        """Add timers reported by a child harness process.

        Child wall overlaps the parent's blocking dispatch span, so it is
        retained as provenance but is not added to end-to-end wall.
        """
        cpu_ns = max(0, int(cpu_ns))
        wall_ns = max(0, int(wall_ns))
        self._external_cpu_ns += cpu_ns
        self._external_wall_ns += wall_ns
        name = category.value if isinstance(category, Category) else str(category)
        if name == Category.TOOL_COMPUTE.value:
            self._tool_compute_cpu_ns += cpu_ns
            self._tool_compute_wall_ns += wall_ns
        if self.mode == "throttle":
            timing = self._categories.setdefault(name, CategoryTiming())
            timing.cpu_ns += cpu_ns

    def stop(self) -> TurnTrace:
        if self._wall_start_ns is None or self._cpu_start_ns is None:
            raise RuntimeError("instrumentor has not started")
        if self._wall_end_ns is not None:
            raise RuntimeError("instrumentor already stopped")
        self._wall_end_ns = time.monotonic_ns()
        self._cpu_end_ns = time.process_time_ns()
        process_wall = max(0, self._wall_end_ns - self._wall_start_ns)
        parent_cpu = max(0, self._cpu_end_ns - self._cpu_start_ns)
        process_cpu = parent_cpu + self._external_cpu_ns
        categorized_cpu = sum(value.cpu_ns for value in self._categories.values())
        residual_cpu = max(0, process_cpu - categorized_cpu)
        return TurnTrace(
            instr_mode=self.mode,
            process=ProcessTiming(wall_ns=process_wall, cpu_ns=process_cpu),
            categories=dict(self._categories),
            strict_harness_cpu_ns=max(0, process_cpu - self._tool_compute_cpu_ns),
            strict_harness_wall_ns=max(0, process_wall - self._tool_compute_wall_ns),
            process_inclusive_cpu_ns=process_cpu,
            process_inclusive_wall_ns=process_wall,
            external_process_cpu_ns=self._external_cpu_ns,
            external_process_wall_ns=self._external_wall_ns,
            residual_cpu_ns=residual_cpu,
        )
