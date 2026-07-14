"""Compatibility probe and adapter boundary for the official MCP SDK.

This module never substitutes the raw dispatcher for an SDK run.  A
``reference_sdk`` measurement is admissible only when :attr:`compatible` is
true and the selected transport is constructed from the returned SDK symbols.
"""

from __future__ import annotations

import importlib
import importlib.metadata
from dataclasses import asdict, dataclass
from types import ModuleType
from typing import Any

PINNED_MCP_VERSION = "1.28.1"


@dataclass(frozen=True)
class SDKCompatibilityDescriptor:
    package: str
    required_version: str
    installed_version: str | None
    available: bool
    compatible: bool
    client_session: bool
    server: bool
    stdio_transport: bool
    sse_transport: bool
    streamable_http_transport: bool
    reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has(module: ModuleType, name: str) -> bool:
    return getattr(module, name, None) is not None


class ReferenceSdkAdapter:
    """Lazy imports that keep SDK and raw implementation paths unambiguous."""

    def __init__(self) -> None:
        self._modules: dict[str, ModuleType] = {}
        self._descriptor = self._probe()

    @property
    def descriptor(self) -> SDKCompatibilityDescriptor:
        return self._descriptor

    @property
    def compatible(self) -> bool:
        return self._descriptor.compatible

    def _probe(self) -> SDKCompatibilityDescriptor:
        try:
            installed = importlib.metadata.version("mcp")
        except importlib.metadata.PackageNotFoundError as exc:
            return SDKCompatibilityDescriptor(
                package="mcp",
                required_version=PINNED_MCP_VERSION,
                installed_version=None,
                available=False,
                compatible=False,
                client_session=False,
                server=False,
                stdio_transport=False,
                sse_transport=False,
                streamable_http_transport=False,
                reason=str(exc),
            )

        try:
            modules = {
                "mcp": importlib.import_module("mcp"),
                "server": importlib.import_module("mcp.server"),
                "stdio": importlib.import_module("mcp.client.stdio"),
                "sse": importlib.import_module("mcp.client.sse"),
                "stream": importlib.import_module("mcp.client.streamable_http"),
            }
        except ImportError as exc:
            return SDKCompatibilityDescriptor(
                package="mcp",
                required_version=PINNED_MCP_VERSION,
                installed_version=installed,
                available=True,
                compatible=False,
                client_session=False,
                server=False,
                stdio_transport=False,
                sse_transport=False,
                streamable_http_transport=False,
                reason=str(exc),
            )

        checks = {
            "client_session": _has(modules["mcp"], "ClientSession"),
            "server": _has(modules["server"], "Server"),
            "stdio_transport": _has(modules["stdio"], "stdio_client"),
            "sse_transport": _has(modules["sse"], "sse_client"),
            "streamable_http_transport": _has(
                modules["stream"], "streamablehttp_client"
            ),
        }
        exact_version = installed == PINNED_MCP_VERSION
        compatible = exact_version and all(checks.values())
        reason: str | None = None
        if not exact_version:
            reason = (
                f"installed mcp {installed}, required exact "
                f"{PINNED_MCP_VERSION}"
            )
        elif not compatible:
            missing = ", ".join(name for name, ok in checks.items() if not ok)
            reason = f"pinned SDK is missing expected symbols: {missing}"
        self._modules = modules
        return SDKCompatibilityDescriptor(
            package="mcp",
            required_version=PINNED_MCP_VERSION,
            installed_version=installed,
            available=True,
            compatible=compatible,
            reason=reason,
            **checks,
        )

    def require_compatible(self) -> None:
        if not self.compatible:
            raise RuntimeError(
                self.descriptor.reason or "official MCP SDK is not compatible"
            )

    def client_session_class(self) -> type[Any]:
        self.require_compatible()
        return self._modules["mcp"].ClientSession

    def server_class(self) -> type[Any]:
        self.require_compatible()
        return self._modules["server"].Server

    def transport_factory(self, transport: str) -> Any:
        """Return an official client transport factory for an admitted arm."""

        self.require_compatible()
        if transport == "stdio":
            return self._modules["stdio"].stdio_client
        if transport in {"http_sse_tls_on", "http_sse_tls_off"}:
            return self._modules["sse"].sse_client
        if transport == "http_stream":
            return self._modules["stream"].streamablehttp_client
        raise KeyError(f"unknown transport: {transport}")
