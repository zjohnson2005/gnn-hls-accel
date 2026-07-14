"""Transport-neutral raw MCP client used by the controlled testbench."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from .contracts import MessageStep, canonical_json_bytes
from .implementations.raw_jsonrpc import RawJsonRpcServer
from .transports.base import (
    DirectionTrace,
    TimingTrace,
    TransportResult,
    TransportTrace,
    response_bytes,
)

DEFAULT_MCP_PROTOCOL_VERSION = "2025-06-18"
JsonObject = dict[str, Any]


class ByteTransport(Protocol):
    """Small boundary implemented by stdio/SSE/HTTP transport arms."""

    def exchange(self, request: bytes) -> TransportResult | bytes | None: ...


@dataclass
class InProcessTransport:
    """Correctness-only transport; never label it as a measured transport."""

    server: RawJsonRpcServer

    def exchange(self, request: bytes) -> bytes | None:
        return self.server.handle_bytes(request)


class JsonRpcResponseError(RuntimeError):
    def __init__(self, error: JsonObject) -> None:
        super().__init__(f"JSON-RPC error {error.get('code')}: {error.get('message')}")
        self.error = error


class RawJsonRpcClient:
    def __init__(self, transport: ByteTransport) -> None:
        self.transport = transport
        self.initialized = False
        self._next_request_id = 1

    def _exchange(self, request: JsonObject) -> JsonObject:
        result = self.transport.exchange(canonical_json_bytes(request))
        if result is None:
            raise RuntimeError("request unexpectedly received no response")
        response = json.loads(response_bytes(result))
        if "error" in response:
            raise JsonRpcResponseError(response["error"])
        return response

    def request(
        self,
        method: str,
        params: JsonObject | None = None,
        *,
        request_id: int | None = None,
    ) -> JsonObject:
        if request_id is None:
            request_id = self._next_request_id
            self._next_request_id += 1
        response = self._exchange(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        if response.get("id") != request_id:
            raise RuntimeError("JSON-RPC response id does not match request")
        return response["result"]

    def notify(self, method: str, params: JsonObject | None = None) -> None:
        request = canonical_json_bytes(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
            }
        )
        sender = getattr(self.transport, "send_notification", None)
        if callable(sender):
            sender(request)
            return
        response = self.transport.exchange(request)
        if response is not None:
            raise RuntimeError("JSON-RPC notification unexpectedly received a response")

    def initialize(
        self,
        *,
        protocol_version: str = DEFAULT_MCP_PROTOCOL_VERSION,
    ) -> JsonObject:
        result = self.request(
            "initialize",
            {
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "mcp-tax-raw-client", "version": "1"},
            },
            request_id=0,
        )
        self.notify("notifications/initialized")
        self.initialized = True
        return result

    def list_tools(self) -> list[JsonObject]:
        self._require_initialized()
        return self.request("tools/list")["tools"]

    def call_tool(
        self,
        name: str,
        arguments: JsonObject,
        *,
        request_id: int | None = None,
    ) -> JsonObject:
        self._require_initialized()
        return self.request(
            "tools/call",
            {"name": name, "arguments": arguments},
            request_id=request_id,
        )

    def call_step(self, step: MessageStep) -> JsonObject:
        """Send the exact canonical request represented by a frozen step."""

        self._require_initialized()
        request_id = step.index + 1
        result = self.transport.exchange(step.canonical_bytes(request_id))
        if result is None:
            raise RuntimeError("tools/call unexpectedly received no response")
        response = json.loads(response_bytes(result))
        if response.get("id") != request_id:
            raise RuntimeError("JSON-RPC response id does not match plan step")
        if "error" in response:
            raise JsonRpcResponseError(response["error"])
        return response["result"]

    def exchange_step(
        self, step: MessageStep, *, request_bytes: bytes | None = None
    ) -> TransportResult:
        """Perform the transport exchange for one frozen plan step."""

        self._require_initialized()
        request_id = step.index + 1
        payload = request_bytes if request_bytes is not None else step.canonical_bytes(request_id)
        result = self.transport.exchange(payload)
        if result is None:
            raise RuntimeError("tools/call unexpectedly received no response")
        return result if isinstance(result, TransportResult) else TransportResult(
            response=response_bytes(result),
            trace=TransportTrace(
                transport="unknown",
                request=DirectionTrace.from_message(
                    step.canonical_bytes(request_id), wire_bytes=0
                ),
                response=DirectionTrace.from_message(
                    response_bytes(result), wire_bytes=0
                ),
                timing=TimingTrace(),
            ),
        )

    def _require_initialized(self) -> None:
        if not self.initialized:
            raise RuntimeError("client has not completed MCP initialization")
