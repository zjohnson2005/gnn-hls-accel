"""Context-local profiler for LangGraph / LangChain callbacks."""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestration_engine.characterization.profiler import Profiler

_profiler_var: contextvars.ContextVar[Profiler | None] = contextvars.ContextVar(
    "oe_profiler", default=None
)


def set_profiler(prof: Profiler) -> contextvars.Token:
    return _profiler_var.set(prof)


def reset_profiler(token: contextvars.Token) -> None:
    _profiler_var.reset(token)


def get_profiler() -> Profiler | None:
    return _profiler_var.get()
