"""Transport-neutral byte and timing records for MCP-01.

Transports accept and return complete logical JSON-RPC messages.  Framing is
owned by each transport, so logical hashes remain comparable while wire byte
counts describe what was actually written to and read from the transport.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


def logical_sha256(message: bytes) -> str:
    """Return the stable digest used to compare logical JSON-RPC messages."""
    return hashlib.sha256(message).hexdigest()


def require_logical_message(message: bytes | bytearray | memoryview) -> bytes:
    """Normalize a logical message without parsing or re-serializing it."""
    if not isinstance(message, (bytes, bytearray, memoryview)):
        raise TypeError("logical JSON-RPC message must be bytes-like")
    value = bytes(message)
    if not value:
        raise ValueError("logical JSON-RPC message must not be empty")
    return value


@dataclass(frozen=True)
class DirectionTrace:
    """Logical identity and observed wire size for one direction."""

    logical_sha256: str
    logical_bytes: int
    wire_bytes: int

    @classmethod
    def from_message(cls, message: bytes, *, wire_bytes: int) -> "DirectionTrace":
        return cls(
            logical_sha256=logical_sha256(message),
            logical_bytes=len(message),
            wire_bytes=wire_bytes,
        )


@dataclass(frozen=True)
class TimingTrace:
    """Transport seams; all values are elapsed wall-clock nanoseconds."""

    setup_ns: int = 0
    tls_handshake_ns: int = 0
    frame_request_ns: int = 0
    write_ns: int = 0
    read_ns: int = 0
    frame_response_ns: int = 0

    @property
    def session_setup_ns(self) -> int:
        """Connection/process setup, including a TLS handshake when present."""
        return self.setup_ns + self.tls_handshake_ns

    @property
    def steady_state_ns(self) -> int:
        """Per-message framing and I/O with session setup explicitly excluded."""
        return (
            self.frame_request_ns
            + self.write_ns
            + self.read_ns
            + self.frame_response_ns
        )


@dataclass(frozen=True)
class TransportTrace:
    transport: str
    request: DirectionTrace
    response: DirectionTrace
    timing: TimingTrace
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransportResult:
    response: bytes
    trace: TransportTrace


def response_bytes(result: TransportResult | bytes | bytearray | memoryview) -> bytes:
    """Normalize traced and compatibility transport results at one boundary."""

    if isinstance(result, TransportResult):
        return result.response
    if isinstance(result, (bytes, bytearray, memoryview)):
        return bytes(result)
    raise TypeError(f"transport returned unsupported result type {type(result).__name__}")


@runtime_checkable
class JsonRpcByteTransport(Protocol):
    """Shared interface implemented by every measured transport."""

    def exchange(self, logical_request: bytes) -> TransportResult:
        """Perform one request/response exchange using logical JSON-RPC bytes."""

    def close(self) -> None:
        """Release transport resources."""


class TransportError(RuntimeError):
    """A transport failed before a complete logical response was available."""

