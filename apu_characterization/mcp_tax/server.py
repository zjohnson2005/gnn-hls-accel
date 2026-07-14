"""Server-side assembly for controlled raw and official-SDK MCP arms."""

from __future__ import annotations

from .contracts import CellCoordinates
from .implementations.raw_jsonrpc import RawJsonRpcServer
from .implementations.reference_sdk import (
    ReferenceSdkAdapter,
    SDKCompatibilityDescriptor,
)
from .testbench import ControlledToolRegistry


def build_registry(
    coordinates: CellCoordinates,
    *,
    synthetic_delay_ns: int = 0,
) -> ControlledToolRegistry:
    return ControlledToolRegistry(
        tool_count=coordinates.tool_count,
        schema_id=coordinates.schema_profile,
        payload_bytes=coordinates.payload_bytes,
        synthetic_delay_ns=synthetic_delay_ns,
    )


def build_raw_server(
    coordinates: CellCoordinates,
    *,
    synthetic_delay_ns: int = 0,
) -> RawJsonRpcServer:
    return RawJsonRpcServer(
        build_registry(
            coordinates,
            synthetic_delay_ns=synthetic_delay_ns,
        )
    )


def probe_reference_sdk() -> SDKCompatibilityDescriptor:
    """Probe the real pinned SDK; incompatible probes must not be measured."""

    return ReferenceSdkAdapter().descriptor


__all__ = [
    "RawJsonRpcServer",
    "ReferenceSdkAdapter",
    "SDKCompatibilityDescriptor",
    "build_raw_server",
    "build_registry",
    "probe_reference_sdk",
]
