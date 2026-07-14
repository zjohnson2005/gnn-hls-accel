"""Context propagation and measured scopes for MCP endpoint messages."""

from __future__ import annotations

import contextvars
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator, Mapping

from .contracts import ProcessRole

if TYPE_CHECKING:
    from .accum import McpMessageAccumulator


@dataclass(frozen=True)
class MessageContext:
    message_id: str
    process_role: ProcessRole


_accumulator_ctx: contextvars.ContextVar[McpMessageAccumulator | None] = (
    contextvars.ContextVar("mcp_accumulator", default=None)
)
_message_ctx: contextvars.ContextVar[MessageContext | None] = contextvars.ContextVar(
    "mcp_message", default=None
)
_setup_ctx: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "mcp_setup", default=False
)


def get_accumulator() -> "McpMessageAccumulator | None":
    return _accumulator_ctx.get()


def get_message_context() -> MessageContext | None:
    return _message_ctx.get()


def in_setup_scope() -> bool:
    return _setup_ctx.get()


def _schedstat_totals_ns(
    accumulator: "McpMessageAccumulator",
) -> tuple[int | None, int | None]:
    """Return endpoint-local (on-CPU, runqueue-wait) /proc totals."""

    if accumulator.mode != "full" or os.name == "nt":
        return None, None
    try:
        tids = os.listdir("/proc/self/task")
    except OSError:
        return None, None
    cpu_total = 0
    runqueue_total = 0
    observed = False
    for entry in tids:
        try:
            with open(f"/proc/self/task/{int(entry)}/schedstat", "rb") as stream:
                fields = stream.read().split()
            cpu_total += int(fields[0])
            runqueue_total += int(fields[1])
            observed = True
        except (OSError, ValueError, IndexError):
            continue
    return (
        (cpu_total, runqueue_total) if observed else (None, None)
    )


def _resolve_accumulator(
    accumulator: "McpMessageAccumulator | None",
) -> "McpMessageAccumulator":
    resolved = accumulator or get_accumulator()
    if resolved is None:
        raise RuntimeError("no MCP accumulator is bound")
    return resolved


@contextmanager
def bind_accumulator(accumulator: "McpMessageAccumulator") -> Iterator[None]:
    """Bind one endpoint accumulator for timers and message scopes."""

    token = _accumulator_ctx.set(accumulator)
    try:
        yield
    finally:
        _accumulator_ctx.reset(token)


@contextmanager
def endpoint_scope(
    accumulator: "McpMessageAccumulator",
    *,
    metadata: Mapping[str, Any] | None = None,
) -> Iterator["McpMessageAccumulator"]:
    """Measure total process CPU/wall while binding an endpoint ledger."""

    with bind_accumulator(accumulator):
        accumulator.begin_endpoint(metadata=metadata)
        try:
            yield accumulator
        finally:
            accumulator.end_endpoint()


@contextmanager
def message_scope(
    message_id: str,
    *,
    accumulator: "McpMessageAccumulator | None" = None,
    process_role: ProcessRole | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Iterator[MessageContext]:
    """Record process CPU/wall/timestamps for exactly one protocol message."""

    acc = _resolve_accumulator(accumulator)
    role = process_role or acc.process_role
    if role != acc.process_role:
        raise ValueError("message role does not match endpoint accumulator")
    if get_message_context() is not None:
        raise RuntimeError("nested message scopes are not supported")
    if in_setup_scope():
        raise RuntimeError("a message scope cannot be nested inside setup")
    context = MessageContext(str(message_id), role)
    start_schedstat, start_runqueue = _schedstat_totals_ns(acc)
    acc.begin_message(
        context.message_id,
        schedstat_cpu_ns=start_schedstat,
        metadata=metadata,
    )
    token_acc = _accumulator_ctx.set(acc)
    token_message = _message_ctx.set(context)
    try:
        yield context
    finally:
        end_schedstat, end_runqueue = _schedstat_totals_ns(acc)
        try:
            acc.end_message(context.message_id, schedstat_cpu_ns=end_schedstat)
            if start_runqueue is not None and end_runqueue is not None:
                acc.book_wait(
                    "runqueue",
                    max(0, end_runqueue - start_runqueue),
                    message_id=context.message_id,
                    provenance="schedstat",
                )
        finally:
            _message_ctx.reset(token_message)
            _accumulator_ctx.reset(token_acc)


@contextmanager
def setup_scope(
    *,
    accumulator: "McpMessageAccumulator | None" = None,
    metadata: Mapping[str, Any] | None = None,
) -> Iterator[None]:
    """Measure endpoint setup independently of all protocol messages."""

    acc = _resolve_accumulator(accumulator)
    if get_message_context() is not None:
        raise RuntimeError("setup cannot be nested inside a message")
    if in_setup_scope():
        raise RuntimeError("nested setup scopes are not supported")
    start_schedstat, _start_runqueue = _schedstat_totals_ns(acc)
    acc.begin_setup(schedstat_cpu_ns=start_schedstat, metadata=metadata)
    token_acc = _accumulator_ctx.set(acc)
    token_setup = _setup_ctx.set(True)
    try:
        yield
    finally:
        end_schedstat, _end_runqueue = _schedstat_totals_ns(acc)
        try:
            acc.end_setup(schedstat_cpu_ns=end_schedstat)
        finally:
            _setup_ctx.reset(token_setup)
            _accumulator_ctx.reset(token_acc)
