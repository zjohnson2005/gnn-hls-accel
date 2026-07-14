"""v9 gap-split measurement: mechanisms (a)–(e), not interpretation.

Populates ``message_diagnostics[mid].gap_decomposition`` with measured
mechanism CPU. Only ``gap_unattributed`` is a residual; (a)–(d) are measured
(or explicitly marked unmeasured). Overlaps use frozen precedence from
``protocol_v1.json``: instrumentation < gc < event_loop < syscall_return.
"""

from __future__ import annotations

import gc
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Sequence

# Canonical mechanism keys (Task 1).
GAP_EVENT_LOOP = "gap_event_loop"
GAP_INSTRUMENTATION = "gap_instrumentation"
GAP_GC = "gap_gc"
GAP_SYSCALL_RETURN = "gap_syscall_return"
GAP_UNATTRIBUTED = "gap_unattributed"

# Sub-provenance keys for (d) — measured named sites vs adjacent gap segments.
GAP_SYSCALL_MEASURED = "gap_syscall_return_measured"
GAP_SYSCALL_ADJACENT = "gap_syscall_return_adjacent"

NAMED_MECHANISMS = (
    GAP_EVENT_LOOP,
    GAP_INSTRUMENTATION,
    GAP_GC,
    GAP_SYSCALL_RETURN,
)

ALL_MECHANISM_KEYS = (
    GAP_EVENT_LOOP,
    GAP_INSTRUMENTATION,
    GAP_GC,
    GAP_SYSCALL_RETURN,
    GAP_UNATTRIBUTED,
)

# Precedence carve order: lowest index carved first from the shared pool.
DEFAULT_PRECEDENCE = (
    GAP_INSTRUMENTATION,
    GAP_GC,
    GAP_EVENT_LOOP,
    GAP_SYSCALL_RETURN,
)

BOUNDARY_LABELS = (
    "pre_serial",
    "serial_to_transport",
    "transport_to_serial",
    "serial_to_dispatch",
    "post_dispatch",
    "inter_region",
)

_active_session: ContextVar["GapSession | None"] = ContextVar(
    "mcp_gap_session", default=None
)


def get_gap_session() -> "GapSession | None":
    return _active_session.get()


def microbench_timer_pair_ns(*, iterations: int = 100_000) -> dict[str, Any]:
    """Measure empty enter/exit cost on the same clocks used by mcp_timed."""
    # Warmup
    for _ in range(1000):
        t0 = time.thread_time_ns()
        t1 = time.perf_counter_ns()
        _ = time.thread_time_ns() - t0
        _ = time.perf_counter_ns() - t1
    samples: list[int] = []
    for _ in range(iterations):
        c0 = time.thread_time_ns()
        w0 = time.perf_counter_ns()
        c1 = time.thread_time_ns()
        w1 = time.perf_counter_ns()
        samples.append(max(0, c1 - c0) + max(0, (w1 - w0) // 4))
    samples.sort()
    mid = samples[len(samples) // 2]
    return {
        "iterations": iterations,
        "timer_pair_cost_ns": int(mid),
        "timer_pair_p90_ns": int(samples[int(len(samples) * 0.9)]),
        "clock": "thread_time_ns+perf_counter_ns/4",
    }


@dataclass
class _GcInterval:
    start_cpu_ns: int
    start_wall_ns: int
    end_cpu_ns: int = 0
    end_wall_ns: int = 0
    generation: int = 0


@dataclass
class _GapSegment:
    boundary: str
    start_cpu_ns: int
    start_wall_ns: int
    end_cpu_ns: int = 0
    end_wall_ns: int = 0

    @property
    def cpu_ns(self) -> int:
        if self.end_cpu_ns <= 0:
            return 0
        return max(0, self.end_cpu_ns - self.start_cpu_ns)


@dataclass
class GapSession:
    """Per-message collector for gap mechanism raw measurements."""

    message_id: str
    timer_pair_cost_ns: int
    run_dir: Any | None = None
    timer_pairs: int = 0
    event_loop_cpu_ns: int = 0
    event_loop_measured: bool = False
    # Named post-return work still booked inside the gap (usually 0 after
    # TRANSPORT boundary tighten moves close/wrap into MSG_TRANSPORT_CPU).
    syscall_measured_ns: int = 0
    gc_intervals: list[_GcInterval] = field(default_factory=list)
    gap_segments: list[_GapSegment] = field(default_factory=list)
    open_segment: _GapSegment | None = None
    in_named_region: bool = False
    boundary_cpu_start: int = 0
    boundary_wall_start: int = 0
    gc_stats_before: tuple[dict[str, Any], ...] = ()
    overlap_log: list[dict[str, Any]] = field(default_factory=list)
    _token: Any = None
    _gc_callback: Any = None
    _pending_boundary: str = "inter_region"

    def note_timer_pair(self) -> None:
        self.timer_pairs += 1

    def mark_boundary(self, label: str) -> None:
        self._pending_boundary = label

    def on_region_enter(self) -> None:
        now_cpu = time.thread_time_ns()
        now_wall = time.perf_counter_ns()
        if self.open_segment is not None and not self.in_named_region:
            self.open_segment.end_cpu_ns = now_cpu
            self.open_segment.end_wall_ns = now_wall
            self.gap_segments.append(self.open_segment)
            self.open_segment = None
        self.in_named_region = True

    def on_region_exit(self) -> None:
        now_cpu = time.thread_time_ns()
        now_wall = time.perf_counter_ns()
        self.in_named_region = False
        self.open_segment = _GapSegment(
            boundary=self._pending_boundary,
            start_cpu_ns=now_cpu,
            start_wall_ns=now_wall,
        )
        self._pending_boundary = "inter_region"

    def add_event_loop_cpu(self, cpu_ns: int) -> None:
        self.event_loop_measured = True
        self.event_loop_cpu_ns += max(0, int(cpu_ns))

    def _on_gc(self, phase: str, info: Mapping[str, Any]) -> None:
        if phase == "start":
            self.gc_intervals.append(
                _GcInterval(
                    start_cpu_ns=time.thread_time_ns(),
                    start_wall_ns=time.perf_counter_ns(),
                    generation=int(info.get("generation", 0)),
                )
            )
        elif phase == "stop" and self.gc_intervals and self.gc_intervals[-1].end_cpu_ns == 0:
            self.gc_intervals[-1].end_cpu_ns = time.thread_time_ns()
            self.gc_intervals[-1].end_wall_ns = time.perf_counter_ns()

    def start(self, *, boundary_cpu_start: int, boundary_wall_start: int) -> None:
        self.boundary_cpu_start = boundary_cpu_start
        self.boundary_wall_start = boundary_wall_start
        try:
            self.gc_stats_before = tuple(gc.get_stats())
        except Exception:
            self.gc_stats_before = ()
        self._gc_callback = self._on_gc
        gc.callbacks.append(self._gc_callback)
        self._token = _active_session.set(self)

    def stop(self) -> None:
        now_cpu = time.thread_time_ns()
        now_wall = time.perf_counter_ns()
        if self.open_segment is not None and not self.in_named_region:
            self.open_segment.end_cpu_ns = now_cpu
            self.open_segment.end_wall_ns = now_wall
            self.gap_segments.append(self.open_segment)
            self.open_segment = None
        if self._gc_callback is not None:
            try:
                gc.callbacks.remove(self._gc_callback)
            except ValueError:
                pass
            self._gc_callback = None
        if self._token is not None:
            _active_session.reset(self._token)
            self._token = None

    def raw_measurements(self) -> dict[str, Any]:
        instrumentation_ns = int(self.timer_pairs) * int(self.timer_pair_cost_ns)
        gc_ns = 0
        for interval in self.gc_intervals:
            if interval.end_cpu_ns > 0:
                gc_ns += max(0, interval.end_cpu_ns - interval.start_cpu_ns)
        # Syscall-return: adjacent gap segments vs named measured sites.
        syscall_adjacent_ns = 0
        boundaries_seen: list[str] = []
        for segment in self.gap_segments:
            boundaries_seen.append(segment.boundary)
            if segment.boundary in {
                "serial_to_transport",
                "transport_to_serial",
                "pre_serial",
            }:
                syscall_adjacent_ns += segment.cpu_ns
        syscall_measured_ns = max(0, int(self.syscall_measured_ns))
        syscall_ns = syscall_adjacent_ns + syscall_measured_ns
        event_loop_ns = int(self.event_loop_cpu_ns) if self.event_loop_measured else 0
        gc_stats_after: tuple[dict[str, Any], ...] = ()
        try:
            gc_stats_after = tuple(gc.get_stats())
        except Exception:
            pass
        return {
            GAP_INSTRUMENTATION: instrumentation_ns,
            GAP_GC: gc_ns,
            GAP_EVENT_LOOP: event_loop_ns,
            GAP_SYSCALL_RETURN: syscall_ns,
            GAP_SYSCALL_MEASURED: syscall_measured_ns,
            GAP_SYSCALL_ADJACENT: syscall_adjacent_ns,
            "event_loop_measured": self.event_loop_measured,
            "timer_pairs": self.timer_pairs,
            "timer_pair_cost_ns": self.timer_pair_cost_ns,
            "boundaries_seen": sorted(set(boundaries_seen)),
            "gc_interval_count": len(self.gc_intervals),
            "gc_stats_before": list(self.gc_stats_before),
            "gc_stats_after": list(gc_stats_after),
            "gap_segment_count": len(self.gap_segments),
        }


def apply_precedence(
    raw: Mapping[str, int],
    parent_cpu_ns: int,
    *,
    precedence: Sequence[str] = DEFAULT_PRECEDENCE,
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Carve overlapping raw claims so Σ(a..d)+e == parent. Only e is residual."""
    remaining = max(0, int(parent_cpu_ns))
    allocated: dict[str, int] = {key: 0 for key in ALL_MECHANISM_KEYS}
    overlap_log: list[dict[str, Any]] = []
    for key in precedence:
        claim = max(0, int(raw.get(key, 0)))
        take = min(claim, remaining)
        if claim > take:
            overlap_log.append(
                {
                    "mechanism": key,
                    "raw_ns": claim,
                    "allocated_ns": take,
                    "carved_ns": claim - take,
                    "reason": "precedence_budget",
                }
            )
        allocated[key] = take
        remaining -= take
    allocated[GAP_UNATTRIBUTED] = remaining
    return allocated, overlap_log


def build_gap_decomposition(
    parent_cpu_ns: int,
    session: GapSession,
    *,
    precedence: Sequence[str] | None = None,
) -> dict[str, Any]:
    raw = session.raw_measurements()
    order = tuple(precedence or DEFAULT_PRECEDENCE)
    allocated, overlap_log = apply_precedence(
        {
            GAP_INSTRUMENTATION: int(raw[GAP_INSTRUMENTATION]),
            GAP_GC: int(raw[GAP_GC]),
            GAP_EVENT_LOOP: int(raw[GAP_EVENT_LOOP]),
            GAP_SYSCALL_RETURN: int(raw[GAP_SYSCALL_RETURN]),
        },
        parent_cpu_ns,
        precedence=order,
    )
    session.overlap_log.extend(overlap_log)
    mechanisms = {key: int(allocated[key]) for key in ALL_MECHANISM_KEYS}
    # Scale (d) sub-provenance to the post-precedence allocation.
    d_alloc = int(allocated[GAP_SYSCALL_RETURN])
    d_meas_raw = int(raw[GAP_SYSCALL_MEASURED])
    d_adj_raw = int(raw[GAP_SYSCALL_ADJACENT])
    d_raw_sum = d_meas_raw + d_adj_raw
    if d_raw_sum > 0 and d_alloc > 0:
        d_meas = int(round(d_alloc * (d_meas_raw / d_raw_sum)))
        d_adj = d_alloc - d_meas
    else:
        d_meas, d_adj = 0, d_alloc
    unmeasured = []
    if not raw["event_loop_measured"]:
        unmeasured.append(GAP_EVENT_LOOP)
    return {
        "parent_cpu_ns": int(parent_cpu_ns),
        "mechanisms": mechanisms,
        "boundaries": list(raw["boundaries_seen"]) or ["inter_region"],
        "raw_before_precedence": {
            GAP_INSTRUMENTATION: int(raw[GAP_INSTRUMENTATION]),
            GAP_GC: int(raw[GAP_GC]),
            GAP_EVENT_LOOP: int(raw[GAP_EVENT_LOOP]),
            GAP_SYSCALL_RETURN: int(raw[GAP_SYSCALL_RETURN]),
            GAP_SYSCALL_MEASURED: d_meas_raw,
            GAP_SYSCALL_ADJACENT: d_adj_raw,
        },
        "gap_syscall_return_subprovenance": {
            "measured_ns": d_meas,
            "adjacent_segments_ns": d_adj,
            "note": (
                "measured = named post-return sites still inside the gap; "
                "adjacent_segments = transport-adjacent inter-region intervals. "
                "TRANSPORT-timer tighten (close/wrap) leaves the gap into "
                "MSG_TRANSPORT_CPU/transport_syscall_return and is not double-counted here."
            ),
        },
        "precedence": list(order),
        "overlap_resolutions": list(session.overlap_log),
        "unmeasured": unmeasured,
        "provenance_sites": {
            GAP_INSTRUMENTATION: "timer_pair_microbench×pairs",
            GAP_GC: "gc.callbacks_overlap",
            GAP_EVENT_LOOP: (
                "gap_event_loop/run_once_ready"
                if raw["event_loop_measured"]
                else "unmeasured_sync_path"
            ),
            GAP_SYSCALL_RETURN: "measured_sites+adjacent_segments",
            GAP_SYSCALL_MEASURED: "named_post_return_inside_gap",
            GAP_SYSCALL_ADJACENT: "inter_region_transport_adjacent_segments",
            GAP_UNATTRIBUTED: "residual_after_precedence",
        },
        "diagnostics": {
            "timer_pairs": raw["timer_pairs"],
            "timer_pair_cost_ns": raw["timer_pair_cost_ns"],
            "gc_interval_count": raw["gc_interval_count"],
            "gap_segment_count": raw["gap_segment_count"],
            "gc_stats_before": raw["gc_stats_before"],
            "gc_stats_after": raw["gc_stats_after"],
        },
    }


@contextmanager
def instrumented_asyncio_loop() -> Iterator[None]:
    """Harness-owned event loop that books ready-queue drain into the gap session.

    Times the selector loop's ``_run_once`` ready-callback dispatch window
    (result-ready → awaiting coroutine resumes). Provenance site:
    ``gap_event_loop/run_once_ready``.
    """
    import asyncio

    class GapSelectorLoop(asyncio.SelectorEventLoop):
        def _run_once(self) -> None:  # type: ignore[override]
            session = get_gap_session()
            start = time.thread_time_ns()
            super()._run_once()
            if session is not None:
                session.add_event_loop_cpu(max(0, time.thread_time_ns() - start))
                if not getattr(session, "_event_loop_site", None):
                    session._event_loop_site = "gap_event_loop/run_once_ready"  # type: ignore[attr-defined]

    class GapPolicy(asyncio.DefaultEventLoopPolicy):
        def new_event_loop(self) -> asyncio.AbstractEventLoop:
            return GapSelectorLoop()

    previous = asyncio.get_event_loop_policy()
    asyncio.set_event_loop_policy(GapPolicy())
    try:
        yield
    finally:
        asyncio.set_event_loop_policy(previous)


@contextmanager
def gap_session(
    message_id: str,
    *,
    timer_pair_cost_ns: int,
    run_dir: Any | None = None,
    boundary_cpu_start: int | None = None,
    boundary_wall_start: int | None = None,
) -> Iterator[GapSession]:
    session = GapSession(
        message_id=str(message_id),
        timer_pair_cost_ns=int(timer_pair_cost_ns),
        run_dir=run_dir,
    )
    session.start(
        boundary_cpu_start=boundary_cpu_start or time.thread_time_ns(),
        boundary_wall_start=boundary_wall_start or time.perf_counter_ns(),
    )
    try:
        yield session
    finally:
        session.stop()
