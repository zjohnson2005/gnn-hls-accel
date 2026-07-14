"""Harness package — lazy exports to avoid circular import with tools.impl."""

from __future__ import annotations

from typing import Any

from .. import env_pin as _env_pin  # noqa: F401 — pin BLAS before numpy (tools.impl)

__all__ = ["run_batch", "run_agent_session"]


def __getattr__(name: str) -> Any:
    if name == "run_batch":
        from .runner import run_batch

        return run_batch
    if name == "run_agent_session":
        from .react_loop import run_agent_session

        return run_agent_session
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
