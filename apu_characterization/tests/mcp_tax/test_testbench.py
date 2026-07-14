"""Controlled registry, SDK probe, and raw lifecycle tests."""

from __future__ import annotations

import importlib.metadata
import json

import pytest

from apu_characterization.mcp_tax.client import (
    InProcessTransport,
    RawJsonRpcClient,
)
from apu_characterization.mcp_tax.contracts import CellCoordinates
from apu_characterization.mcp_tax.implementations.raw_jsonrpc import (
    LifecycleState,
    RawJsonRpcServer,
)
from apu_characterization.mcp_tax.implementations.reference_sdk import (
    PINNED_MCP_VERSION,
    ReferenceSdkAdapter,
)
from apu_characterization.mcp_tax.plan import build_cell_plan
from apu_characterization.mcp_tax.testbench import (
    ControlledToolRegistry,
    exact_payload,
    semantic_size,
)


def _registry(
    *,
    tool_count: int = 10,
    payload_bytes: int = 256,
    delay_ns: int = 0,
) -> ControlledToolRegistry:
    return ControlledToolRegistry(
        tool_count=tool_count,
        schema_id="flat_5",
        payload_bytes=payload_bytes,
        synthetic_delay_ns=delay_ns,
    )


@pytest.mark.parametrize("tool_count", (1, 10, 100, 1000))
def test_controlled_registry_has_exact_tool_count(tool_count: int) -> None:
    registry = _registry(tool_count=tool_count)
    tools = registry.list_tools()
    assert len(registry) == tool_count
    assert len(tools) == tool_count
    assert len({tool["name"] for tool in tools}) == tool_count
    assert tools[0]["name"] == "tool_0000"
    assert tools[-1]["name"] == f"tool_{tool_count - 1:04d}"
    assert all(tool["inputSchema"] == tools[0]["inputSchema"] for tool in tools)


@pytest.mark.parametrize("payload_bytes", (256, 4096, 65536, 524288))
def test_call_request_and_result_semantic_sizes_are_exact(
    payload_bytes: int,
) -> None:
    registry = _registry(payload_bytes=payload_bytes)
    payload = exact_payload(payload_bytes)
    outcome = registry.call(
        "tool_0003",
        {"schema_id": "flat_5", "payload": payload},
    )
    assert semantic_size(payload) == payload_bytes
    assert outcome.request_payload_bytes == payload_bytes
    assert outcome.result_payload == payload
    assert outcome.result_payload_bytes == payload_bytes
    mcp_result = outcome.as_mcp_result()
    assert semantic_size(mcp_result["content"][0]["text"]) == payload_bytes


def test_registry_rejects_payload_size_drift() -> None:
    registry = _registry(payload_bytes=256)
    with pytest.raises(ValueError, match="expected 256"):
        registry.call(
            "tool_0000",
            {"schema_id": "flat_5", "payload": exact_payload(255)},
        )


def test_optional_smoke_delay_is_reported_outside_protocol_categories() -> None:
    registry = _registry(payload_bytes=256, delay_ns=1_000_000)
    outcome = registry.call(
        "tool_0000",
        {"schema_id": "flat_5", "payload": exact_payload(256)},
    )
    assert outcome.synthetic_delay_ns == 1_000_000
    assert outcome.result_payload_bytes == 256


def test_raw_jsonrpc_lifecycle_and_methods() -> None:
    server = RawJsonRpcServer(_registry(tool_count=3, payload_bytes=256))
    before_init = server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    )
    assert before_init is not None
    assert before_init["error"]["code"] == -32002

    initialized = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        }
    )
    assert initialized is not None
    assert initialized["result"]["protocolVersion"] == "2025-06-18"
    assert server.state is LifecycleState.AWAITING_INITIALIZED
    assert (
        server.handle(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        is None
    )
    assert server.state is LifecycleState.READY

    listed = server.handle(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    )
    assert listed is not None
    assert len(listed["result"]["tools"]) == 3
    called = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "tool_0001",
                "arguments": {
                    "schema_id": "flat_5",
                    "payload": exact_payload(256),
                },
            },
        }
    )
    assert called is not None
    assert called["result"]["content"][0]["text"] == exact_payload(256)


def test_raw_bytes_parse_error_and_client_plan_round_trip() -> None:
    server = RawJsonRpcServer(_registry(tool_count=1, payload_bytes=256))
    parse_error = server.handle_bytes(b"{")
    assert parse_error is not None
    assert json.loads(parse_error)["error"]["code"] == -32700

    client = RawJsonRpcClient(InProcessTransport(server))
    init = client.initialize()
    assert init["serverInfo"]["name"] == "mcp-tax-raw"
    assert len(client.list_tools()) == 1
    coordinates = CellCoordinates(
        transport="stdio",
        payload_bytes=256,
        schema_profile="flat_5",
        tool_count=1,
        implementation="raw_jsonrpc",
        mode="throttle",
    )
    plan = build_cell_plan(
        coordinates,
        seed=0,
        warmup_messages=0,
        measured_messages=1,
    )
    result = client.call_step(plan.steps[0])
    assert result["structuredContent"]["request_payload_bytes"] == 256
    assert result["structuredContent"]["result_payload_bytes"] == 256


def test_reference_sdk_probe_requires_the_exact_official_package() -> None:
    adapter = ReferenceSdkAdapter()
    descriptor = adapter.descriptor
    assert descriptor.package == "mcp"
    assert descriptor.required_version == PINNED_MCP_VERSION
    if not descriptor.available:
        pytest.skip("install requirements-mcp.txt to exercise the SDK probe")
    assert importlib.metadata.version("mcp") == PINNED_MCP_VERSION
    assert descriptor.compatible, descriptor.reason
    assert adapter.client_session_class().__module__.startswith("mcp")
    assert adapter.server_class().__module__.startswith("mcp")
    assert callable(adapter.transport_factory("stdio"))
    assert callable(adapter.transport_factory("http_sse_tls_on"))
    assert callable(adapter.transport_factory("http_stream"))
