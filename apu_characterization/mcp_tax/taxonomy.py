"""Frozen MCP-01 per-message CPU taxonomy."""

from __future__ import annotations

from enum import Enum


class McpCategory(str, Enum):
    MSG_SERIAL = "MSG_SERIAL"
    MSG_VALIDATE = "MSG_VALIDATE"
    MSG_FRAME = "MSG_FRAME"
    MSG_TRANSPORT_CPU = "MSG_TRANSPORT_CPU"
    MSG_DISPATCH = "MSG_DISPATCH"
    SESSION_SETUP = "SESSION_SETUP"
    RESIDUAL = "RESIDUAL"


MCP_INSTRUMENTED: tuple[McpCategory, ...] = tuple(
    category for category in McpCategory if category is not McpCategory.RESIDUAL
)
