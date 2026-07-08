"""Per-session context for tools and thread hooks."""

from __future__ import annotations

import contextvars
import time
from typing import Any

session_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "apu_session_id", default="global"
)
rng_ctx: contextvars.ContextVar[Any] = contextvars.ContextVar("apu_rng", default=None)
spec_ctx: contextvars.ContextVar[Any] = contextvars.ContextVar("apu_spec", default=None)

# Turn-transition holder: mutable dict shared between the session thread, the
# LLM callback, and tool executor threads (contextvars propagate the reference).
# t_llm_ns is stamped when an LLM response is received; the next tool body entry
# records (now - t_llm_ns) as one turn-transition latency sample.
turn_transition_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "apu_turn_transition", default=None
)


def get_session_id() -> str:
    return session_id_ctx.get()


def stamp_llm_response_ns() -> None:
    """Record 'LLM response received' timestamp for turn-transition latency."""
    holder = turn_transition_ctx.get()
    if holder is not None:
        holder["t_llm_ns"] = time.perf_counter_ns()


def record_turn_transition() -> None:
    """Record one LLM-response-to-tool-start latency sample, if pending."""
    holder = turn_transition_ctx.get()
    if holder is None:
        return
    t0 = holder.get("t_llm_ns")
    if t0 is None:
        return
    holder["t_llm_ns"] = None
    holder["latencies_ms"].append((time.perf_counter_ns() - t0) / 1e6)
