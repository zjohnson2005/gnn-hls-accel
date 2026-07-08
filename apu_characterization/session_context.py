"""Per-session context for tools and thread hooks."""

from __future__ import annotations

import contextvars
from typing import Any

session_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "apu_session_id", default="global"
)
rng_ctx: contextvars.ContextVar[Any] = contextvars.ContextVar("apu_rng", default=None)
spec_ctx: contextvars.ContextVar[Any] = contextvars.ContextVar("apu_spec", default=None)


def get_session_id() -> str:
    return session_id_ctx.get()
