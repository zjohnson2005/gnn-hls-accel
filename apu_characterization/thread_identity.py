"""Thread-identity CPU accounting (Linux / psutil).

Classify threads by role + propagated session_id; charge per-thread CPU deltas
to categories. Survives concurrent sessions in one process (concurrency sweep).

instr_version >= 3 enables this path and disables step-inferred booking.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum

from .instr import (
    RunAccumulator,
    current_native_tid,
    drop_tagged_thread,
    get_run_accumulator,
    reset_session_tagged_ledger,
    tagged_thread_cpu,
    tagged_thread_cpu_snapshot,
)
from .provenance import MEASURED, RESIDUAL
from .taxonomy import Category

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]

# Back-compat alias (tests and tools import _native_tid from this module).
_native_tid = current_native_tid

# psutil thread times come from /proc/<pid>/task/<tid>/stat utime+stime, which
# tick at SC_CLK_TCK (10 ms on WSL2). Short-lived fan-out threads burning <10 ms
# read as 0 and dead threads vanish entirely — measured CPU lands in the
# session-end residual gap. /proc/.../schedstat field 0 is the scheduler's
# ns-accurate on-CPU time, so prefer it when the kernel exposes it.
_schedstat_supported: bool | None = None


def _probe_schedstat() -> bool:
    global _schedstat_supported
    if _schedstat_supported is None:
        try:
            with open("/proc/thread-self/schedstat", "rb") as f:
                _schedstat_supported = len(f.read().split()) >= 1
        except OSError:
            _schedstat_supported = False
    return _schedstat_supported


def _schedstat_cpu_ns(tid: int) -> int | None:
    try:
        with open(f"/proc/self/task/{tid}/schedstat", "rb") as f:
            return int(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _schedstat_all_cpu_ns() -> dict[int, int]:
    out: dict[int, int] = {}
    try:
        entries = os.listdir("/proc/self/task")
    except OSError:
        return out
    for entry in entries:
        try:
            tid = int(entry)
        except ValueError:
            continue
        cpu = _schedstat_cpu_ns(tid)
        if cpu is not None:
            out[tid] = cpu
    return out


class ThreadRole(str, Enum):
    MAIN = "main"
    HTTP_TRANSPORT = "http_transport"
    EXECUTOR = "executor"
    EVENT_LOOP = "event_loop"
    UNKNOWN = "unknown"


ROLE_TO_CATEGORY: dict[ThreadRole, Category] = {
    ThreadRole.HTTP_TRANSPORT: Category.CLIENT_HTTP,
    ThreadRole.EXECUTOR: Category.THREADPOOL,
    ThreadRole.EVENT_LOOP: Category.EVENT_LOOP,
    ThreadRole.MAIN: Category.FRAMEWORK,
    ThreadRole.UNKNOWN: Category.RESIDUAL_UNATTRIBUTED,
}


@dataclass
class ThreadRegistry:
    """Maps OS thread ids to (role, session_id) and samples CPU via psutil."""

    _role: dict[int, ThreadRole] = field(default_factory=dict)
    _session: dict[int, str] = field(default_factory=dict)
    _last_cpu_ns: dict[int, int] = field(default_factory=dict)
    # Tagged-CPU baseline / carryover per tid: psutil ticks at ~10 ms while
    # timers tick at ns, so a timer booking can momentarily exceed the psutil
    # delta; the surplus carries into the next interval instead of being lost.
    _last_tagged_ns: dict[int, int] = field(default_factory=dict)
    _tag_carry_ns: dict[int, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def register(
        self,
        tid: int,
        role: ThreadRole,
        session_id: str,
        *,
        overwrite: bool = False,
        fresh: bool = False,
    ) -> None:
        """Register *tid*. ``fresh=True`` means the thread was just created:
        baseline 0 so interpreter/thread startup CPU is attributed instead of
        leaking into the session-end residual gap."""
        with self._lock:
            if tid not in self._role or overwrite:
                self._role[tid] = role
                self._session[tid] = session_id
                if sys.platform != "win32":
                    if fresh:
                        self._last_cpu_ns.setdefault(tid, 0)
                    elif tid not in self._last_cpu_ns:
                        cpu = self._one_thread_cpu_ns(tid)
                        if cpu is not None:
                            self._last_cpu_ns[tid] = cpu
                if tid not in self._last_tagged_ns:
                    self._last_tagged_ns[tid] = tagged_thread_cpu(tid)

    def register_current(self, role: ThreadRole, session_id: str) -> None:
        self.register(_native_tid(), role, session_id, overwrite=True)

    def _one_thread_cpu_ns(self, tid: int) -> int | None:
        """Cheap single-thread CPU read (avoids scanning every /proc task)."""
        if sys.platform != "win32" and _probe_schedstat():
            cpu = _schedstat_cpu_ns(tid)
            if cpu is not None:
                return cpu
        return self._thread_cpu_ns().get(tid)

    def _thread_cpu_ns(self) -> dict[int, int]:
        # schedstat is ns-accurate; psutil /proc stat ticks at ~10 ms and reads
        # 0 for short-lived fan-out threads (they die within one tick).
        if sys.platform != "win32" and _probe_schedstat():
            out = _schedstat_all_cpu_ns()
            if out:
                return out
        if psutil is None:
            return {}
        out = {}
        proc = psutil.Process()
        for th in proc.threads():
            out[th.id] = int((th.user_time + th.system_time) * 1e9)
        return out

    def _prune_dead_threads(self, live_tids: set[int]) -> None:
        """Drop registry state for threads that exited between sessions."""
        with self._lock:
            dead = [tid for tid in self._role if tid not in live_tids]
            for tid in dead:
                self._role.pop(tid, None)
                self._session.pop(tid, None)
                self._last_cpu_ns.pop(tid, None)
                self._last_tagged_ns.pop(tid, None)
                self._tag_carry_ns.pop(tid, None)
                drop_tagged_thread(tid)

    def begin_session(self, session_id: str) -> None:
        """Sequential session start: reset baselines; attribute all threads to *session_id*."""
        set_active_session(session_id)
        reset_session_tagged_ledger()
        self.register_current(ThreadRole.MAIN, session_id)
        if sys.platform == "win32" or psutil is None:
            return
        now = self._thread_cpu_ns()
        live = set(now)
        self._prune_dead_threads(live)
        with self._lock:
            for tid, cpu_ns in now.items():
                self._last_cpu_ns[tid] = cpu_ns
                self._last_tagged_ns[tid] = 0
                self._tag_carry_ns[tid] = 0
                if tid not in self._role:
                    self._role[tid] = ThreadRole.UNKNOWN
                self._session[tid] = session_id

    def _net_delta_locked(self, tid: int, cpu_ns: int, tagged_ns: int) -> int:
        """Untagged CPU delta for *tid* since last sample (lock held)."""
        prev = self._last_cpu_ns[tid]
        delta = max(0, cpu_ns - prev)
        self._last_cpu_ns[tid] = cpu_ns
        tag_delta = max(0, tagged_ns - self._last_tagged_ns.get(tid, 0))
        self._last_tagged_ns[tid] = tagged_ns
        net = delta - tag_delta - self._tag_carry_ns.get(tid, 0)
        if net < 0:
            self._tag_carry_ns[tid] = -net
            return 0
        self._tag_carry_ns[tid] = 0
        return net

    def sample_and_book(self, acc: RunAccumulator | None = None) -> dict[str, int]:
        """Sample all process threads; book untagged CPU deltas (measured)."""
        acc = acc or get_run_accumulator()
        if acc is None or sys.platform == "win32" or psutil is None:
            return {}
        now = self._thread_cpu_ns()
        tagged = tagged_thread_cpu_snapshot()
        booked: dict[str, int] = {}
        with self._lock:
            for tid, cpu_ns in now.items():
                if tid not in self._last_cpu_ns:
                    self._last_cpu_ns[tid] = cpu_ns
                    self._last_tagged_ns[tid] = tagged.get(tid, 0)
                    continue
                net = self._net_delta_locked(tid, cpu_ns, tagged.get(tid, 0))
                if net <= 0:
                    continue
                role = self._role.get(tid, ThreadRole.UNKNOWN)
                sid = self._session.get(tid) or get_active_session()
                if sid == "global":
                    sid = get_active_session()
                if role == ThreadRole.UNKNOWN and sid != "global":
                    role = ThreadRole.EXECUTOR
                    self._role[tid] = role
                    self._session[tid] = sid
                cat = ROLE_TO_CATEGORY.get(role, Category.RESIDUAL_UNATTRIBUTED)
                prov = MEASURED if role != ThreadRole.UNKNOWN else RESIDUAL
                acc.book_cpu(cat, sid, net, net, provenance=prov)
                key = f"{sid}:{role.value}"
                booked[key] = booked.get(key, 0) + net
        return booked

    def finalize_current_thread(self, acc: RunAccumulator | None = None) -> None:
        """Book the dying thread's remaining CPU before its TID disappears.

        Short-lived threads (e.g. LangGraph fan-out pools) can exit between
        stream-step samples; psutil no longer lists them, so without this
        their CPU lands in the session-end residual gap.
        """
        acc = acc or get_run_accumulator()
        tid = current_native_tid()
        if acc is None or sys.platform == "win32" or psutil is None:
            drop_tagged_thread(tid)
            return
        cpu_ns = self._one_thread_cpu_ns(tid)
        with self._lock:
            role = self._role.pop(tid, ThreadRole.UNKNOWN)
            sid = self._session.pop(tid, None) or get_active_session()
            if sid == "global":
                sid = get_active_session()
            if cpu_ns is None or tid not in self._last_cpu_ns:
                self._last_cpu_ns.pop(tid, None)
                self._last_tagged_ns.pop(tid, None)
                self._tag_carry_ns.pop(tid, None)
                drop_tagged_thread(tid)
                return
            net = self._net_delta_locked(tid, cpu_ns, tagged_thread_cpu(tid))
            self._last_cpu_ns.pop(tid, None)
            self._last_tagged_ns.pop(tid, None)
            self._tag_carry_ns.pop(tid, None)
        drop_tagged_thread(tid)
        if net <= 0:
            return
        if role == ThreadRole.UNKNOWN and sid != "global":
            role = ThreadRole.EXECUTOR
        cat = ROLE_TO_CATEGORY.get(role, Category.RESIDUAL_UNATTRIBUTED)
        prov = MEASURED if role != ThreadRole.UNKNOWN else RESIDUAL
        acc.book_cpu(cat, sid, net, net, provenance=prov)

    def snapshot(self) -> None:
        """Initialize baselines without booking."""
        if sys.platform == "win32" or psutil is None:
            return
        now = self._thread_cpu_ns()
        tagged = tagged_thread_cpu_snapshot()
        with self._lock:
            for tid, cpu_ns in now.items():
                self._last_cpu_ns[tid] = cpu_ns
                self._last_tagged_ns[tid] = tagged.get(tid, 0)


_registry: ThreadRegistry | None = None
_active_session: str = "global"


def set_active_session(session_id: str) -> None:
    global _active_session
    _active_session = session_id


def get_active_session() -> str:
    return _active_session


def get_thread_registry() -> ThreadRegistry:
    global _registry
    if _registry is None:
        _registry = ThreadRegistry()
    return _registry


def install_thread_identity_hooks() -> None:
    """Thread hooks + thread.start classifier for v3."""
    from .harness.thread_hooks import install_thread_hooks

    install_thread_hooks()
    reg = get_thread_registry()
    reg.register_current(ThreadRole.MAIN, "global")

    _orig_thread_start = threading.Thread.start

    def _start(self: threading.Thread) -> None:
        name = (self.name or "").lower()
        if any(x in name for x in ("httpx", "http", "openai")):
            role = ThreadRole.HTTP_TRANSPORT
        elif "asyncio" in name or "event" in name:
            role = ThreadRole.EVENT_LOOP
        else:
            role = ThreadRole.EXECUTOR
        _orig_run = self.run

        def run_wrapper() -> None:
            from .session_context import session_id_ctx

            sid = session_id_ctx.get("global")
            # fresh=True: baseline 0 so thread startup CPU is attributed too.
            reg.register(_native_tid(), role, sid, overwrite=True, fresh=True)
            try:
                return _orig_run()
            finally:
                # Book remaining CPU before the TID vanishes from psutil.
                reg.finalize_current_thread()

        self.run = run_wrapper  # type: ignore[method-assign]
        _orig_thread_start(self)

    threading.Thread.start = _start  # type: ignore[method-assign]


def sample_session_threads(
    acc: RunAccumulator | None = None, *, burst: bool = False
) -> dict[str, int]:
    """Sample all process threads; optional extra passes after tool/LLM bursts."""
    acc = acc or get_run_accumulator()
    if acc is None or acc.instr_version < 3 or sys.platform == "win32":
        return {}
    reg = get_thread_registry()
    booked = reg.sample_and_book(acc)
    if burst and not _probe_schedstat():
        # psutil /proc stat ticks at ~10 ms; short fan-out pool threads can
        # finish between single back-to-back samples. With schedstat (ns) the
        # dying-thread finalize hook already captures them — skip the sleeps.
        for _ in range(3):
            time.sleep(0.015)
            extra = reg.sample_and_book(acc)
            for key, ns in extra.items():
                booked[key] = booked.get(key, 0) + ns
    return booked


def finalize_session_threads(acc: RunAccumulator, session_id: str) -> None:
    """Final thread sample at session end (v3)."""
    if acc.instr_version < 3 or sys.platform == "win32":
        return
    reg = get_thread_registry()
    reg.register_current(ThreadRole.MAIN, session_id)
    sample_session_threads(acc, burst=True)


def end_session(session_id: str) -> None:
    """Mark session complete (sequential attribution boundary)."""
    if get_active_session() == session_id:
        set_active_session("global")
