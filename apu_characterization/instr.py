"""Category timers with exclusive (self-time) nested accounting."""

from __future__ import annotations

import gc
import os
import contextvars
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from .taxonomy import Category, INSTRUMENTED

NO_INSTR = os.environ.get("APU_NOINSTR", "0") == "1"


@dataclass
class CategoryTotals:
    cpu_ns: int = 0
    wall_ns: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    count: int = 0

    def add(
        self,
        cpu_ns: int,
        wall_ns: int,
        bytes_in: int = 0,
        bytes_out: int = 0,
        count: int = 1,
    ) -> None:
        self.cpu_ns += cpu_ns
        self.wall_ns += wall_ns
        self.bytes_in += bytes_in
        self.bytes_out += bytes_out
        self.count += count


@dataclass
class _ActiveFrame:
    category: Category
    session_id: str
    profile: str
    t0_cpu: int
    t0_wall: int
    # Self-time accumulated in segments that already ended (a child region
    # pauses this frame; t0 is reset on resume, so completed segments must
    # be banked here and ADDED on exit).
    accum_cpu: int = 0
    accum_wall: int = 0


@dataclass
class RunAccumulator:
    """Per-run accumulator keyed by (category, session_id, profile)."""

    profile: str = "mixed"
    by_key: dict[tuple[str, str, str], CategoryTotals] = field(default_factory=dict)
    session_thread_cpu: dict[str, int] = field(default_factory=dict)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    record_timeline: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def totals_for(self, category: Category, session_id: str) -> CategoryTotals:
        key = (category.value, session_id, self.profile)
        with self._lock:
            if key not in self.by_key:
                self.by_key[key] = CategoryTotals()
            return self.by_key[key]

    def aggregate_by_category(self) -> dict[str, CategoryTotals]:
        out: dict[str, CategoryTotals] = {}
        for (cat, _sid, _prof), totals in self.by_key.items():
            if cat not in out:
                out[cat] = CategoryTotals()
            t = out[cat]
            t.cpu_ns += totals.cpu_ns
            t.wall_ns += totals.wall_ns
            t.bytes_in += totals.bytes_in
            t.bytes_out += totals.bytes_out
            t.count += totals.count
        return out

    def instrumented_cpu_ns(self) -> int:
        return sum(t.cpu_ns for cat, t in self.aggregate_by_category().items())

    def residual_cpu_ns(self, total_thread_cpu_ns: int) -> int:
        return max(0, total_thread_cpu_ns - self.instrumented_cpu_ns())

    def to_run_dict(
        self,
        env: dict[str, Any],
        config: dict[str, Any],
        total_thread_cpu_ns: int,
        total_wall_ns: int,
        os_times: dict[str, float],
        per_session: list[dict[str, Any]],
    ) -> dict[str, Any]:
        per_cat = {
            cat: {
                "cpu_ns": t.cpu_ns,
                "wall_ns": t.wall_ns,
                "bytes_in": t.bytes_in,
                "bytes_out": t.bytes_out,
                "count": t.count,
            }
            for cat, t in self.aggregate_by_category().items()
        }
        per_session_category: dict[str, dict[str, dict[str, int]]] = {}
        for (cat, sid, _prof), t in self.by_key.items():
            per_session_category.setdefault(sid, {})[cat] = {
                "cpu_ns": t.cpu_ns,
                "wall_ns": t.wall_ns,
                "bytes_in": t.bytes_in,
                "bytes_out": t.bytes_out,
                "count": t.count,
            }
        residual = self.residual_cpu_ns(total_thread_cpu_ns)
        return {
            "env": env,
            "config": config,
            "per_category": per_cat,
            "per_session": per_session,
            "per_session_category": per_session_category,
            "residual_cpu_ns": residual,
            "residual_fraction": (
                residual / total_thread_cpu_ns if total_thread_cpu_ns > 0 else 0.0
            ),
            "totals": {
                "thread_cpu_ns": total_thread_cpu_ns,
                "wall_ns": total_wall_ns,
                "instrumented_cpu_ns": self.instrumented_cpu_ns(),
            },
            "os_times_user_sys": os_times,
            "timeline": self.timeline if self.record_timeline else [],
        }


_thread_local = threading.local()
_run_acc: RunAccumulator | None = None
_gc_hook_installed = False
_gc_session: contextvars.ContextVar[str] = contextvars.ContextVar(
    "apu_gc_session", default="global"
)


def set_gc_session(session_id: str) -> None:
    _gc_session.set(session_id)


def reset_gc_session() -> None:
    _gc_session.set("global")


def set_run_accumulator(acc: RunAccumulator | None) -> None:
    global _run_acc
    _run_acc = acc


def get_run_accumulator() -> RunAccumulator | None:
    return _run_acc


def _stack() -> list[_ActiveFrame]:
    if not hasattr(_thread_local, "stack"):
        _thread_local.stack = []
    return _thread_local.stack


def _pause_parent(parent: _ActiveFrame) -> None:
    now_cpu = time.thread_time_ns()
    now_wall = time.perf_counter_ns()
    parent.accum_cpu += now_cpu - parent.t0_cpu
    parent.accum_wall += now_wall - parent.t0_wall


def _resume_parent(parent: _ActiveFrame) -> None:
    parent.t0_cpu = time.thread_time_ns()
    parent.t0_wall = time.perf_counter_ns()


def _record_frame(
    frame: _ActiveFrame,
    cpu_ns: int,
    wall_ns: int,
    bytes_in: int,
    bytes_out: int,
) -> None:
    acc = get_run_accumulator()
    if acc is None:
        return
    totals = acc.totals_for(frame.category, frame.session_id)
    with acc._lock:
        totals.add(cpu_ns, wall_ns, bytes_in, bytes_out)
    if acc.record_timeline:
        acc.timeline.append(
            {
                "category": frame.category.value,
                "session_id": frame.session_id,
                "cpu_ns": cpu_ns,
                "wall_ns": wall_ns,
                "bytes_in": bytes_in,
                "bytes_out": bytes_out,
            }
        )


@contextmanager
def timed(
    category: Category,
    session_id: str = "global",
    *,
    bytes_in: int = 0,
    bytes_out: int = 0,
) -> Iterator[None]:
    if NO_INSTR or category == Category.RESIDUAL:
        yield
        return

    stack = _stack()
    if stack:
        _pause_parent(stack[-1])

    frame = _ActiveFrame(
        category=category,
        session_id=session_id,
        profile=get_run_accumulator().profile if get_run_accumulator() else "mixed",
        t0_cpu=time.thread_time_ns(),
        t0_wall=time.perf_counter_ns(),
    )
    stack.append(frame)
    try:
        yield
    finally:
        stack.pop()
        end_cpu = time.thread_time_ns()
        end_wall = time.perf_counter_ns()
        cpu_ns = (end_cpu - frame.t0_cpu) + frame.accum_cpu
        wall_ns = (end_wall - frame.t0_wall) + frame.accum_wall
        _record_frame(frame, cpu_ns, wall_ns, bytes_in, bytes_out)
        if stack:
            _resume_parent(stack[-1])


def measure_timer_overhead_ns(pairs: int = 1_000_000) -> float:
    """Microbenchmark enter/exit cost; returns ns per pair."""
    acc = RunAccumulator(profile="overhead")
    set_run_accumulator(acc)
    t0 = time.thread_time_ns()
    for _ in range(pairs):
        with timed(Category.LOGGING, "bench"):
            pass
    elapsed = time.thread_time_ns() - t0
    set_run_accumulator(None)
    return elapsed / pairs


def install_gc_hooks() -> None:
    """Attribute collector cycles to GC.

    CPython invokes every callback in gc.callbacks with phase "start" and
    phase "stop", so a single callback dispatching on phase is required.
    Covers collector cycles only; refcount-driven deallocation is not
    observable here (documented as a lower bound in METHODOLOGY.md).
    """
    global _gc_hook_installed
    if _gc_hook_installed or NO_INSTR:
        return

    _gc_state: dict[str, int | None] = {"start_cpu": None}

    def _gc_callback(phase: str, info: dict) -> None:
        if phase == "start":
            _gc_state["start_cpu"] = time.thread_time_ns()
            return
        start = _gc_state.get("start_cpu")
        if start is None:
            return
        cpu_ns = time.thread_time_ns() - int(start)
        acc = get_run_accumulator()
        if acc is not None:
            sid = _gc_session.get()
            totals = acc.totals_for(Category.GC, sid)
            with acc._lock:
                totals.add(cpu_ns, cpu_ns, count=1)
        _gc_state["start_cpu"] = None

    gc.callbacks.append(_gc_callback)
    _gc_hook_installed = True


def reset_thread_state() -> None:
    _thread_local.stack = []


def categories_for_export() -> tuple[str, ...]:
    return tuple(c.value for c in INSTRUMENTED)
