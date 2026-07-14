"""Controlled no-op tool registry for protocol-only measurements.

Tool-body CPU is measured and returned separately.  Instrumented protocol
callers must not wrap :meth:`ControlledToolRegistry.execute` in an MCP
protocol category.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .contracts import load_protocol
from .plan import tool_name
from .schemas import generate_schema, schema_digest


def semantic_size(value: str) -> int:
    return len(value.encode("utf-8"))


def exact_payload(size: int, *, fill: str = "x") -> str:
    """Create an ASCII payload with exactly *size* UTF-8 bytes."""

    if size < 0:
        raise ValueError("payload size cannot be negative")
    if semantic_size(fill) != 1:
        raise ValueError("fill must encode to exactly one UTF-8 byte")
    return fill * size


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    schema_id: str
    schema_sha256: str

    def as_mcp_tool(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass(frozen=True)
class PreparedToolCall:
    definition: ToolDefinition
    request_payload: str


@dataclass(frozen=True)
class ToolCallOutcome:
    tool_name: str
    schema_id: str
    request_payload_bytes: int
    result_payload: str
    result_payload_bytes: int
    tool_cpu_ns: int
    synthetic_delay_ns: int

    def as_mcp_result(self) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": self.result_payload}],
            "structuredContent": {
                "schema_id": self.schema_id,
                "request_payload_bytes": self.request_payload_bytes,
                "result_payload_bytes": self.result_payload_bytes,
                "synthetic_delay_ns": self.synthetic_delay_ns,
            },
            "isError": False,
        }


class ControlledToolRegistry:
    """A deterministic registry of N semantically identical echo tools."""

    def __init__(
        self,
        *,
        tool_count: int,
        schema_id: str,
        payload_bytes: int,
        synthetic_delay_ns: int = 0,
    ) -> None:
        if tool_count < 1:
            raise ValueError("tool_count must be positive")
        if payload_bytes < 0:
            raise ValueError("payload_bytes cannot be negative")
        delay_contract = load_protocol()["tool_delay"]
        allowed_delays = {
            int(delay_contract["primary_ns"]),
            int(delay_contract["smoke_ns"]),
        }
        if synthetic_delay_ns not in allowed_delays:
            raise ValueError("delay must be zero or the frozen 1 ms smoke delay")

        schema = generate_schema(schema_id)
        digest = schema_digest(schema_id)
        self.payload_bytes = payload_bytes
        self.synthetic_delay_ns = synthetic_delay_ns
        self._tools = tuple(
            ToolDefinition(
                name=tool_name(index),
                description="Controlled MCP-01 no-op echo tool.",
                input_schema=schema,
                schema_id=schema_id,
                schema_sha256=digest,
            )
            for index in range(tool_count)
        )
        self._by_name = {tool.name: tool for tool in self._tools}

    def __len__(self) -> int:
        return len(self._tools)

    @property
    def definitions(self) -> tuple[ToolDefinition, ...]:
        return self._tools

    def list_tools(self) -> list[dict[str, Any]]:
        return [definition.as_mcp_tool() for definition in self._tools]

    def prepare(self, name: str, arguments: dict[str, Any]) -> PreparedToolCall:
        try:
            definition = self._by_name[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc
        if not isinstance(arguments, dict):
            raise TypeError("tool arguments must be an object")
        if arguments.get("schema_id") != definition.schema_id:
            raise ValueError("request schema_id does not match the tool schema")
        payload = arguments.get("payload")
        if not isinstance(payload, str):
            raise TypeError("request payload must be a string")
        actual_bytes = semantic_size(payload)
        if actual_bytes != self.payload_bytes:
            raise ValueError(
                f"request payload has {actual_bytes} bytes, "
                f"expected {self.payload_bytes}"
            )
        return PreparedToolCall(definition=definition, request_payload=payload)

    def execute(self, call: PreparedToolCall) -> ToolCallOutcome:
        """Execute outside protocol timers and account tool CPU separately."""

        cpu_start = time.thread_time_ns()
        if self.synthetic_delay_ns:
            time.sleep(self.synthetic_delay_ns / 1_000_000_000)
        # Echoing keeps request/result semantic sizes exactly equal and performs
        # no workload that could be mistaken for agent tool compute.
        result_payload = call.request_payload
        tool_cpu_ns = time.thread_time_ns() - cpu_start
        result_bytes = semantic_size(result_payload)
        if result_bytes != self.payload_bytes:
            raise AssertionError("controlled result payload size drifted")
        return ToolCallOutcome(
            tool_name=call.definition.name,
            schema_id=call.definition.schema_id,
            request_payload_bytes=self.payload_bytes,
            result_payload=result_payload,
            result_payload_bytes=result_bytes,
            tool_cpu_ns=tool_cpu_ns,
            synthetic_delay_ns=self.synthetic_delay_ns,
        )

    def call(self, name: str, arguments: dict[str, Any]) -> ToolCallOutcome:
        """Convenience API; instrumentation should use prepare/execute directly."""

        return self.execute(self.prepare(name, arguments))
