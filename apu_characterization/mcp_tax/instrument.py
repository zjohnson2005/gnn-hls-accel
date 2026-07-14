"""Low-overhead exclusive timers for MCP protocol categories."""

from __future__ import annotations

import contextvars
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from .accum import WAIT_KINDS, McpMessageAccumulator
from .contracts import ProcessRole
from .message_context import (
    get_accumulator,
    get_message_context,
    in_setup_scope,
)
from .taxonomy import McpCategory


@dataclass
class _ActiveRegion:
    accumulator: McpMessageAccumulator
    category: McpCategory
    message_id: str | None
    process_role: ProcessRole
    start_cpu_ns: int
    start_wall_ns: int
    accumulated_cpu_ns: int = 0
    accumulated_wall_ns: int = 0


_region_stack: contextvars.ContextVar[tuple[_ActiveRegion, ...]] = (
    contextvars.ContextVar("mcp_region_stack", default=())
)


def _resolve(
    accumulator: McpMessageAccumulator | None,
    process_role: ProcessRole | None,
) -> tuple[McpMessageAccumulator, ProcessRole]:
    acc = accumulator or get_accumulator()
    if acc is None:
        raise RuntimeError("no MCP accumulator is bound")
    role = process_role or acc.process_role
    if role != acc.process_role:
        raise ValueError("timer role does not match endpoint accumulator")
    return acc, role


def _resolve_message_id(
    category: McpCategory, message_id: str | None, role: ProcessRole
) -> str | None:
    if category is McpCategory.SESSION_SETUP:
        if message_id is not None:
            raise ValueError("SESSION_SETUP cannot have a message_id")
        if not in_setup_scope():
            raise RuntimeError("SESSION_SETUP timer requires setup_scope()")
        return None
    if message_id is None:
        context = get_message_context()
        if context is not None and context.process_role == role:
            message_id = context.message_id
    if message_id is None or not str(message_id):
        raise RuntimeError(f"{category.value} timer requires message_scope() or message_id")
    return str(message_id)


@contextmanager
def mcp_timed(
    category: McpCategory | str,
    *,
    accumulator: McpMessageAccumulator | None = None,
    message_id: str | None = None,
    process_role: ProcessRole | None = None,
    bytes: int = 0,
    bytes_in: int = 0,
    bytes_out: int = 0,
    count: int = 1,
    provenance: str = "measured",
    byte_totals: dict[str, int] | None = None,
) -> Iterator[None]:
    """Book exclusive thread CPU and exclusive wall metadata for one region.

    Nested regions pause their parent. ``time.thread_time_ns`` is the only CPU
    clock; ``perf_counter_ns`` is retained solely as elapsed-wall metadata.
    In stripped mode this context manager is intentionally a no-op.
    """

    cat = category if isinstance(category, McpCategory) else McpCategory(category)
    acc, role = _resolve(accumulator, process_role)
    if not acc.category_hooks_enabled:
        yield
        return
    mid = _resolve_message_id(cat, message_id, role)
    stack = _region_stack.get()
    now_cpu_ns = time.thread_time_ns()
    now_wall_ns = time.perf_counter_ns()
    from .gap_measure import get_gap_session

    gap = get_gap_session()
    if gap is not None:
        gap.note_timer_pair()
        gap.on_region_enter()
    if stack:
        parent = stack[-1]
        if parent.accumulator is not acc:
            raise RuntimeError("nested MCP timers cannot switch accumulators")
        parent.accumulated_cpu_ns += max(0, now_cpu_ns - parent.start_cpu_ns)
        parent.accumulated_wall_ns += max(0, now_wall_ns - parent.start_wall_ns)
    frame = _ActiveRegion(
        accumulator=acc,
        category=cat,
        message_id=mid,
        process_role=role,
        start_cpu_ns=time.thread_time_ns(),
        start_wall_ns=time.perf_counter_ns(),
    )
    token = _region_stack.set(stack + (frame,))
    try:
        yield
    finally:
        end_cpu_ns = time.thread_time_ns()
        end_wall_ns = time.perf_counter_ns()
        current = _region_stack.get()
        if not current or current[-1] is not frame:
            _region_stack.reset(token)
            raise RuntimeError("MCP timer stack exited out of order")
        cpu_ns = frame.accumulated_cpu_ns + max(0, end_cpu_ns - frame.start_cpu_ns)
        wall_ns = frame.accumulated_wall_ns + max(0, end_wall_ns - frame.start_wall_ns)
        if cpu_ns > 0:
            wall_ns = min(wall_ns, cpu_ns)
        _region_stack.reset(token)
        acc.book(
            cat,
            cpu_ns,
            message_id=mid,
            process_role=role,
            wall_ns=wall_ns,
            bytes=bytes,
            bytes_in=(byte_totals or {}).get("bytes_in", bytes_in),
            bytes_out=(byte_totals or {}).get("bytes_out", bytes_out),
            count=count,
            provenance=provenance,
        )
        if gap is not None:
            gap.on_region_exit()
        if stack:
            # Exclude child-booking and clock overhead from the parent's
            # exclusive region. That observer cost remains process residual.
            resume_cpu_ns = time.thread_time_ns()
            resume_wall_ns = time.perf_counter_ns()
            stack[-1].start_cpu_ns = resume_cpu_ns
            stack[-1].start_wall_ns = resume_wall_ns


@contextmanager
def mcp_wait(
    kind: str,
    *,
    accumulator: McpMessageAccumulator | None = None,
    message_id: str | None = None,
    process_role: ProcessRole | None = None,
    count: int = 1,
    provenance: str = "measured",
) -> Iterator[None]:
    """Measure elapsed wait on the wall-only axis (CPU is always zero)."""

    if kind not in WAIT_KINDS:
        raise ValueError(f"unknown wait kind {kind!r}")
    acc, role = _resolve(accumulator, process_role)
    if message_id is None:
        context = get_message_context()
        if context is not None and context.process_role == role:
            message_id = context.message_id
    if message_id is None or not str(message_id):
        raise RuntimeError("wait timer requires message_scope() or message_id")
    start_wall_ns = time.perf_counter_ns()
    try:
        yield
    finally:
        acc.book_wait(
            kind,
            max(0, time.perf_counter_ns() - start_wall_ns),
            message_id=str(message_id),
            process_role=role,
            count=count,
            provenance=provenance,
        )
