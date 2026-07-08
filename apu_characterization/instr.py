"""Category timers with exclusive (self-time) nested accounting."""

from __future__ import annotations

import ctypes
import gc
import os
import contextvars
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from .taxonomy import Category, INSTRUMENTED
from .provenance import MEASURED, STEP_INFERRED, Provenance, RESIDUAL

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
    instr_version: int = 1
    by_key: dict[tuple[str, str, str], CategoryTotals] = field(default_factory=dict)
    by_provenance: dict[tuple[str, str, str, str], CategoryTotals] = field(
        default_factory=dict
    )
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

    def book_cpu(
        self,
        category: Category,
        session_id: str,
        cpu_ns: int,
        wall_ns: int,
        *,
        provenance: Provenance = MEASURED,
        bytes_in: int = 0,
        bytes_out: int = 0,
        count: int = 1,
    ) -> None:
        """Book CPU to category totals and provenance ledger."""
        if category in (Category.RESIDUAL, Category.RESIDUAL_UNATTRIBUTED):
            provenance = RESIDUAL
        totals = self.totals_for(category, session_id)
        pkey = (category.value, session_id, self.profile, provenance)
        with self._lock:
            totals.add(cpu_ns, wall_ns, bytes_in, bytes_out, count=count)
            if pkey not in self.by_provenance:
                self.by_provenance[pkey] = CategoryTotals()
            self.by_provenance[pkey].add(cpu_ns, wall_ns, bytes_in, bytes_out, count=count)

    def provenance_cpu_ns(self, provenance: Provenance, session_id: str | None = None) -> int:
        total = 0
        with self._lock:
            for (_cat, sid, _prof, prov), t in self.by_provenance.items():
                if prov != provenance:
                    continue
                if session_id is not None and sid != session_id:
                    continue
                total += t.cpu_ns
        return total

    def provenance_summary(self, session_id: str | None = None) -> dict[str, int]:
        return {
            MEASURED: self.provenance_cpu_ns(MEASURED, session_id),
            STEP_INFERRED: self.provenance_cpu_ns(STEP_INFERRED, session_id),
            RESIDUAL: self.provenance_cpu_ns(RESIDUAL, session_id),
        }

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

# ------------------------------------------------------------------
# Per-thread tagged-CPU ledger (v3 dedup).
#
# Thread-identity sampling (psutil) sees ALL CPU a thread burned, including
# CPU already booked by @timed regions on that thread. To avoid double
# counting, every timer booking records its CPU against the current kernel
# TID here; ThreadRegistry.sample_and_book subtracts the tagged delta from
# the psutil delta and books only the untagged remainder.
_tagged_tid_cpu: dict[int, int] = {}
_tagged_tid_lock = threading.Lock()


def _read_native_tid() -> int:
    """Kernel thread id (matches psutil.Process().threads()[].id on Linux)."""
    if sys.platform == "win32":
        return int(threading.get_ident())
    try:
        with open("/proc/thread-self/id", encoding="ascii") as f:
            return int(f.read().strip())
    except OSError:
        pass
    if hasattr(os, "gettid"):
        tid = int(os.gettid())
        if tid < 1_000_000:
            return tid
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        return int(libc.syscall(186))  # SYS_gettid on x86_64 Linux
    except OSError:
        return int(threading.get_ident())


def current_native_tid() -> int:
    """Cached kernel TID for the current thread."""
    tid = getattr(_thread_local, "native_tid", None)
    if tid is None:
        tid = _read_native_tid()
        _thread_local.native_tid = tid
    return tid


def add_tagged_thread_cpu(cpu_ns: int) -> None:
    """Record CPU already booked by a timer on the current thread."""
    if cpu_ns <= 0:
        return
    tid = current_native_tid()
    with _tagged_tid_lock:
        _tagged_tid_cpu[tid] = _tagged_tid_cpu.get(tid, 0) + cpu_ns


def tagged_thread_cpu(tid: int) -> int:
    with _tagged_tid_lock:
        return _tagged_tid_cpu.get(tid, 0)


def tagged_thread_cpu_snapshot() -> dict[int, int]:
    with _tagged_tid_lock:
        return dict(_tagged_tid_cpu)


def drop_tagged_thread(tid: int) -> None:
    """Forget a dead thread's ledger entry (kernel TIDs can be reused)."""
    with _tagged_tid_lock:
        _tagged_tid_cpu.pop(tid, None)


def reset_session_tagged_ledger() -> None:
    """Clear per-thread tagged CPU at a sequential session boundary.

    Tagged totals are cumulative within a session only; carrying them across
    sessions makes psutil net deltas under-book worker threads in later sessions.
    """
    with _tagged_tid_lock:
        _tagged_tid_cpu.clear()
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
    *,
    provenance: Provenance = MEASURED,
) -> None:
    acc = get_run_accumulator()
    if acc is None:
        return
    acc.book_cpu(
        frame.category,
        frame.session_id,
        cpu_ns,
        wall_ns,
        provenance=provenance,
        bytes_in=bytes_in,
        bytes_out=bytes_out,
    )
    add_tagged_thread_cpu(cpu_ns)
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
    if NO_INSTR or category in (Category.RESIDUAL, Category.RESIDUAL_UNATTRIBUTED):
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
            acc.book_cpu(Category.GC, sid, cpu_ns, cpu_ns)
            add_tagged_thread_cpu(cpu_ns)
        _gc_state["start_cpu"] = None

    gc.callbacks.append(_gc_callback)
    _gc_hook_installed = True


def reset_thread_state() -> None:
    _thread_local.stack = []


def categories_for_export() -> tuple[str, ...]:
    return tuple(c.value for c in INSTRUMENTED)
