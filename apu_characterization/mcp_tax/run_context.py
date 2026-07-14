"""Run-scoped context shared across serial MCP-01 cells."""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tls_fixture import TlsFixture

_run_tls: contextvars.ContextVar[TlsFixture | None] = contextvars.ContextVar(
    "mcp_run_tls_fixture", default=None
)


def set_run_tls_fixture(fixture: TlsFixture | None) -> contextvars.Token:
    return _run_tls.set(fixture)


def get_run_tls_fixture() -> TlsFixture | None:
    return _run_tls.get()


def reset_run_tls_fixture(token: contextvars.Token) -> None:
    _run_tls.reset(token)
