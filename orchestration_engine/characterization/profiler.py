"""Lightweight span profiler for agentic workload characterization."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from .taxonomy import Bucket, SpanRecord, WorkloadProfile


class Profiler:
    """Record timed spans into bucket categories."""

    def __init__(self, name: str = "profile", concurrency: int = 1):
        self.name = name
        self.concurrency = concurrency
        self._spans: list[SpanRecord] = []
        self._agent_id = "agent_0"
        self._use_wall = True
        self._sim_clock_us = 0

    def set_agent(self, agent_id: str) -> None:
        self._agent_id = agent_id

    def use_simulated_clock(self, start_us: int = 0) -> None:
        """Switch to deterministic simulated time (for synthetic workloads)."""
        self._use_wall = False
        self._sim_clock_us = start_us

    @property
    def wall_clock(self) -> bool:
        return self._use_wall

    def now_us(self) -> int:
        if self._use_wall:
            return int(time.perf_counter_ns() // 1000)
        return self._sim_clock_us

    def advance_us(self, delta_us: int) -> None:
        if not self._use_wall:
            self._sim_clock_us += delta_us

    def record(self, name: str, bucket: Bucket, duration_us: int, **meta: str) -> None:
        start = self.now_us()
        end = start + duration_us
        if not self._use_wall:
            self._sim_clock_us = end
        self._spans.append(
            SpanRecord(
                name=name,
                bucket=bucket,
                start_us=start,
                end_us=end,
                agent_id=self._agent_id,
                meta=dict(meta),
            )
        )

    @contextmanager
    def span(self, name: str, bucket: Bucket, **meta: str) -> Iterator[None]:
        start = self.now_us()
        try:
            yield
        finally:
            end = self.now_us()
            self._spans.append(
                SpanRecord(
                    name=name,
                    bucket=bucket,
                    start_us=start,
                    end_us=end,
                    agent_id=self._agent_id,
                    meta=dict(meta),
                )
            )

    def span_count(self) -> int:
        return len(self._spans)

    def sum_span_us_since(
        self,
        start_index: int,
        *,
        exclude_buckets: tuple[Bucket, ...] = (),
    ) -> int:
        total = 0
        for span in self._spans[start_index:]:
            if span.bucket in exclude_buckets:
                continue
            total += max(0, span.end_us - span.start_us)
        return total

    def finish(self) -> WorkloadProfile:
        return WorkloadProfile(
            name=self.name,
            spans=list(self._spans),
            concurrency=self.concurrency,
        )


def merge_profiles(profiles: list[WorkloadProfile], name: str) -> WorkloadProfile:
    """Merge per-agent profiles into one concurrent run (wall-clock aligned)."""
    if not profiles:
        return WorkloadProfile(name=name, spans=[], concurrency=0)

    merged: list[SpanRecord] = []
    for prof in profiles:
        merged.extend(prof.spans)

    return WorkloadProfile(
        name=name,
        spans=merged,
        concurrency=len(profiles),
        meta={"merged_from": str(len(profiles))},
    )
