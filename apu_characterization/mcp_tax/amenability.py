"""Pre-registered hardware-amenability prior for MCP-01 categories.

This is an analysis assumption, not a measurement. Reports show it beside
measured CPU and never use it to alter booking or audit results.
"""

from __future__ import annotations

from .taxonomy import McpCategory

TIER: dict[str, str] = {
    McpCategory.MSG_SERIAL.value: "direct",
    McpCategory.MSG_VALIDATE.value: "direct",
    McpCategory.MSG_FRAME.value: "direct",
    McpCategory.MSG_TRANSPORT_CPU.value: "overlap",
    McpCategory.MSG_DISPATCH.value: "direct",
    McpCategory.SESSION_SETUP.value: "partial",
    McpCategory.RESIDUAL.value: "none",
}

RATIONALE: dict[str, str] = {
    McpCategory.MSG_SERIAL.value: "JSON encode/decode is table-driven parse/emit work",
    McpCategory.MSG_VALIDATE.value: (
        "JSON Schema validation only maps to DFA/tree walkers; TLS crypto is "
        "booked under MSG_TRANSPORT_CPU"
    ),
    McpCategory.MSG_FRAME.value: "length/header/SSE framing is finite-state parsing",
    McpCategory.MSG_TRANSPORT_CPU.value: (
        "socket syscall and TLS handshake/crypto overlap NIC/DPU/crypto engines"
    ),
    McpCategory.MSG_DISPATCH.value: (
        "true method lookup / result routing is bounded dispatch; client "
        "DISPATCH is currently gap-dominated (inter-region residue). Hardware "
        "amenability for the gap slice is undecided until v9 — diffuseness "
        "(event-loop / FRAMEWORK analog) is the candidate story, not dispatcher "
        "silicon"
    ),
    McpCategory.SESSION_SETUP.value: "catalog registration is partly parse/copy, partly control",
    McpCategory.RESIDUAL.value: "unattributed CPU cannot license a hardware claim",
}
