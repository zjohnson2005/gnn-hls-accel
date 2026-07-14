"""Minimal MCP lifecycle implemented directly over JSON-RPC 2.0."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from ..contracts import canonical_json_bytes
from ..testbench import ControlledToolRegistry

JsonObject = dict[str, Any]


class LifecycleState(str, Enum):
    NEW = "new"
    AWAITING_INITIALIZED = "awaiting_initialized"
    READY = "ready"


def _error(
    request_id: Any,
    code: int,
    message: str,
    *,
    data: Any | None = None,
) -> JsonObject:
    body: JsonObject = {"code": code, "message": message}
    if data is not None:
        body["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": body}


def _result(request_id: Any, result: JsonObject) -> JsonObject:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


class RawJsonRpcServer:
    """Transport-neutral request dispatcher for the required MCP methods."""

    def __init__(
        self,
        registry: ControlledToolRegistry,
        *,
        server_name: str = "mcp-tax-raw",
        server_version: str = "1",
    ) -> None:
        self.registry = registry
        self.server_name = server_name
        self.server_version = server_version
        self.state = LifecycleState.NEW
        self.negotiated_protocol_version: str | None = None

    def handle(self, message: JsonObject) -> JsonObject | None:
        """Handle one already-decoded JSON-RPC message."""

        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            request_id = message.get("id") if isinstance(message, dict) else None
            return _error(request_id, -32600, "Invalid Request")
        method = message.get("method")
        if not isinstance(method, str):
            return _error(message.get("id"), -32600, "Invalid Request")
        is_notification = "id" not in message
        params = message.get("params", {})
        if not isinstance(params, dict):
            return None if is_notification else _error(
                message.get("id"), -32602, "Invalid params"
            )

        if method == "notifications/initialized":
            if not is_notification:
                return _error(message.get("id"), -32600, "must be a notification")
            if self.state is LifecycleState.AWAITING_INITIALIZED:
                self.state = LifecycleState.READY
            return None
        if is_notification:
            # JSON-RPC notifications never receive a response.
            return None

        request_id = message["id"]
        if method == "initialize":
            return self._initialize(request_id, params)
        if self.state is not LifecycleState.READY:
            return _error(request_id, -32002, "Server not initialized")
        if method == "tools/list":
            return self._list_tools(request_id, params)
        if method == "tools/call":
            return self._call_tool(request_id, params)
        return _error(request_id, -32601, "Method not found")

    def _initialize(self, request_id: Any, params: JsonObject) -> JsonObject:
        if self.state is not LifecycleState.NEW:
            return _error(request_id, -32600, "initialize already completed")
        protocol_version = params.get("protocolVersion")
        if not isinstance(protocol_version, str) or not protocol_version:
            return _error(request_id, -32602, "protocolVersion is required")
        self.negotiated_protocol_version = protocol_version
        self.state = LifecycleState.AWAITING_INITIALIZED
        return _result(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": self.server_name,
                    "version": self.server_version,
                },
            },
        )

    def _list_tools(self, request_id: Any, params: JsonObject) -> JsonObject:
        if params.get("cursor") not in (None, ""):
            return _error(request_id, -32602, "pagination is not supported")
        return _result(request_id, {"tools": self.registry.list_tools()})

    def _call_tool(self, request_id: Any, params: JsonObject) -> JsonObject:
        name = params.get("name")
        arguments = params.get("arguments")
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return _error(request_id, -32602, "name and arguments are required")
        try:
            prepared = self.registry.prepare(name, arguments)
            # Deliberate boundary: execute is tool-body CPU, not protocol CPU.
            outcome = self.registry.execute(prepared)
        except (KeyError, TypeError, ValueError) as exc:
            return _error(request_id, -32602, "Invalid params", data=str(exc))
        return _result(request_id, outcome.as_mcp_result())

    def handle_bytes(self, payload: bytes) -> bytes | None:
        """Decode, dispatch, and canonically encode one raw JSON-RPC message."""

        try:
            message = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return canonical_json_bytes(_error(None, -32700, "Parse error"))
        response = self.handle(message)
        return None if response is None else canonical_json_bytes(response)
