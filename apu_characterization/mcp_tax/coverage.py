"""Per-arm category coverage classification for MCP-01 ledgers."""

from __future__ import annotations

from typing import Any, Mapping

from .taxonomy import McpCategory

CoverageClass = str  # harness_owned | harness_boundary | uncovered

RAW_COVERAGE: dict[str, CoverageClass] = {
    McpCategory.MSG_SERIAL.value: "harness_owned",
    McpCategory.MSG_VALIDATE.value: "harness_owned",
    McpCategory.MSG_FRAME.value: "harness_owned",
    McpCategory.MSG_TRANSPORT_CPU.value: "harness_owned",
    McpCategory.MSG_DISPATCH.value: "harness_owned",
    McpCategory.SESSION_SETUP.value: "harness_owned",
}

SDK_COVERAGE: dict[str, CoverageClass] = {
    McpCategory.MSG_SERIAL.value: "harness_boundary",
    McpCategory.MSG_VALIDATE.value: "uncovered",
    McpCategory.MSG_FRAME.value: "harness_boundary",
    McpCategory.MSG_TRANSPORT_CPU.value: "harness_boundary",
    McpCategory.MSG_DISPATCH.value: "harness_boundary",
    McpCategory.SESSION_SETUP.value: "harness_owned",
}


def coverage_record(
    *,
    implementation: str,
    sdk_version: str | None = None,
) -> dict[str, Any]:
    mapping = RAW_COVERAGE if implementation == "raw_jsonrpc" else SDK_COVERAGE
    return {
        "implementation": implementation,
        "observed_version": sdk_version,
        "coverage_class": dict(mapping),
        "register_mcp_tax_hook": "retired",
    }


def category_comparable(
    left: Mapping[str, CoverageClass],
    right: Mapping[str, CoverageClass],
    category: str,
) -> bool:
    return left.get(category) == "harness_owned" and right.get(category) == "harness_owned"
