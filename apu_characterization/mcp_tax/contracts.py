"""Frozen MCP-01 interfaces and deterministic matrix enumeration."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

PROTOCOL_PATH = Path(__file__).with_name("protocol_v1.json")
MANIFEST_SCHEMA_PATH = Path(__file__).with_name("manifest.schema.json")
CELL_PLAN_SCHEMA_PATH = Path(__file__).with_name("cell_plan.schema.json")
PROTOCOL_VERSION = "mcp_tax_v1.5"

Transport = Literal[
    "stdio", "http_sse_tls_on", "http_sse_tls_off", "http_stream"
]
Implementation = Literal["reference_sdk", "raw_jsonrpc"]
InstrMode = Literal["full", "throttle", "stripped"]
ProcessRole = Literal["client", "server"]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_protocol() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if protocol.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("protocol_v1.json version does not match code")
    return protocol


def protocol_sha256() -> str:
    return sha256_bytes(canonical_json_bytes(load_protocol()))


@dataclass(frozen=True)
class CellCoordinates:
    transport: Transport
    payload_bytes: int
    schema_profile: str
    tool_count: int
    implementation: Implementation
    mode: InstrMode

    @property
    def cell_id(self) -> str:
        tls = {
            "http_sse_tls_on": "sse_tls",
            "http_sse_tls_off": "sse_plain",
        }.get(self.transport, self.transport)
        return (
            f"t-{tls}__p-{self.payload_bytes}__s-{self.schema_profile}"
            f"__n-{self.tool_count}__i-{self.implementation}__m-{self.mode}"
        )


@dataclass(frozen=True)
class MessageStep:
    index: int
    method: str
    tool_name: str
    schema_id: str
    payload_bytes: int
    synthetic_delay_ns: int = 0

    def canonical_bytes(self, request_id: int) -> bytes:
        return canonical_json_bytes(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": self.method,
                "params": {
                    "name": self.tool_name,
                    "arguments": {
                        "schema_id": self.schema_id,
                        "payload": "x" * self.payload_bytes,
                    },
                },
            }
        )


@dataclass(frozen=True)
class CellPlan:
    protocol_version: str
    seed: int
    coordinates: CellCoordinates
    warmup_messages: int
    measured_messages: int
    steps: tuple[MessageStep, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def digest(self) -> str:
        return sha256_bytes(canonical_json_bytes(self.as_dict()))

    def request_hashes(self) -> list[str]:
        return [
            sha256_bytes(step.canonical_bytes(request_id=step.index + 1))
            for step in self.steps
        ]


def enumerate_matrix(*, include_http_stream: bool = False) -> list[CellCoordinates]:
    protocol = load_protocol()
    primary = protocol["primary"]
    transports = list(primary["transports"])
    if include_http_stream:
        transports.append(protocol["streamable_http"]["transport"])
    throttle: list[CellCoordinates] = []
    for transport in transports:
        for payload in primary["payload_bytes"]:
            for schema in primary["schema_profiles"]:
                for implementation in primary["implementations"]:
                    throttle.append(
                        CellCoordinates(
                            transport=transport,
                            payload_bytes=payload,
                            schema_profile=schema,
                            tool_count=primary["tool_count"],
                            implementation=implementation,
                            mode=primary["mode"],
                        )
                    )

    observer_n = math.ceil(
        len(throttle) * protocol["observer_subsample"]["fraction"]
    )
    observer_base = sorted(
        throttle, key=lambda cell: sha256_bytes(cell.cell_id.encode("utf-8"))
    )[:observer_n]
    observer = [
        CellCoordinates(
            transport=cell.transport,
            payload_bytes=cell.payload_bytes,
            schema_profile=cell.schema_profile,
            tool_count=cell.tool_count,
            implementation=cell.implementation,
            mode=mode,
        )
        for cell in observer_base
        for mode in protocol["observer_subsample"]["additional_modes"]
    ]

    tool_cfg = protocol["tool_count_sweep"]
    tool_cells = [
        CellCoordinates(
            transport=transport,
            payload_bytes=tool_cfg["payload_bytes"],
            schema_profile=tool_cfg["schema_profile"],
            tool_count=count,
            implementation=implementation,
            mode=tool_cfg["mode"],
        )
        for transport in transports
        for implementation in primary["implementations"]
        for count in tool_cfg["counts"]
    ]
    cells = throttle + observer + tool_cells
    if len({cell.cell_id for cell in cells}) != len(cells):
        raise AssertionError("matrix contains duplicate cell ids")
    expected = 160 if include_http_stream else 120
    if len(cells) != expected:
        raise AssertionError(f"matrix has {len(cells)} cells, expected {expected}")
    return cells


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Return contract violations without adding a runtime schema dependency."""
    required = (
        "protocol_version",
        "experiment",
        "cell_id",
        "seed",
        "coordinates",
        "core_pins",
        "git",
        "software",
        "kernel_version",
        "timestamp_utc",
        "cell_plan_sha256",
    )
    errors = [f"missing manifest field: {key}" for key in required if key not in manifest]
    if manifest.get("protocol_version") not in (None, PROTOCOL_VERSION):
        errors.append("manifest protocol_version mismatch")
    coords = manifest.get("coordinates") or {}
    for key in (
        "transport",
        "payload_bytes",
        "schema_profile",
        "tool_count",
        "implementation",
        "mode",
    ):
        if key not in coords:
            errors.append(f"missing coordinate: {key}")
    return errors


def validate_with_jsonschema(instance: Any, schema_path: Path) -> None:
    """Validate a contract when the pinned MCP dependency set is installed."""
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - explicit bootstrap error
        raise RuntimeError(
            "jsonschema is required; install requirements-mcp.txt"
        ) from exc
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(instance)
