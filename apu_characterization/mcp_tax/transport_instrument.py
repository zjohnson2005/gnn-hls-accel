"""Harness-owned transport framing and syscall CPU booking for MCP-01."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, TypeVar

from .instrument import mcp_timed
from .taxonomy import McpCategory

if TYPE_CHECKING:
    from .accum import McpMessageAccumulator

T = TypeVar("T")


@dataclass
class TransportInstrumentation:
    """Optional per-exchange booking context bound for one measured message."""

    accumulator: McpMessageAccumulator
    message_id: str
    wire_dir: Path | None = None
    capture_index: int = 0

    def persist_wire(self, label: str, payload: bytes) -> Path | None:
        if self.wire_dir is None or not payload:
            return None
        self.wire_dir.mkdir(parents=True, exist_ok=True)
        path = self.wire_dir / f"{self.message_id}_{label}_{self.capture_index}.bin"
        path.write_bytes(payload)
        self.capture_index += 1
        relative = path.name
        self.accumulator.record_wire_capture(
            message_id=self.message_id,
            label=label,
            path=f"wire/{relative}",
            byte_count=len(payload),
        )
        return path

    def frame(
        self,
        fn: Callable[[], T],
        *,
        bytes_in: int = 0,
        bytes_out: int = 0,
    ) -> T:
        with mcp_timed(
            McpCategory.MSG_FRAME,
            accumulator=self.accumulator,
            message_id=self.message_id,
            bytes_in=bytes_in,
            bytes_out=bytes_out,
            provenance="transport_frame",
        ):
            return fn()

    def tls_handshake(
        self,
        fn: Callable[[], T],
        *,
        bytes_in: int = 0,
        bytes_out: int = 0,
    ) -> T:
        """Book TLS handshake/cert path into MSG_TRANSPORT_CPU (not MSG_VALIDATE).

        MSG_VALIDATE is JSON Schema validation only (DFA-amenable). Certificate
        and crypto handshake CPU is transport/crypto work.
        """
        return self.transport_cpu(
            fn,
            bytes_in=bytes_in,
            bytes_out=bytes_out,
            provenance="transport_tls_handshake",
        )

    def transport_cpu(
        self,
        fn: Callable[[], T],
        *,
        bytes_in: int = 0,
        bytes_out: int = 0,
        provenance: str = "transport_syscall",
    ) -> T:
        totals = {"bytes_in": bytes_in, "bytes_out": bytes_out}

        def _invoke() -> T:
            result = fn()
            if isinstance(result, (bytes, bytearray)) and not totals["bytes_in"]:
                totals["bytes_in"] = len(result)
            return result

        with mcp_timed(
            McpCategory.MSG_TRANSPORT_CPU,
            accumulator=self.accumulator,
            message_id=self.message_id,
            byte_totals=totals,
            provenance=provenance,
        ):
            return _invoke()
