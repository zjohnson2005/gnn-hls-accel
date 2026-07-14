"""Standalone publication/debug validation policy for MCP-01 aggregates."""

from __future__ import annotations

import platform
from typing import Any, Mapping

from .contracts import PROTOCOL_VERSION, protocol_sha256
from .manifest import validate_manifest


def validate_mcp_tax(
    data: Mapping[str, Any],
    *,
    debug_smoke: bool = False,
    platform_string: str | None = None,
) -> list[str]:
    errors: list[str] = []
    validity = data.get("result_validity")
    if debug_smoke:
        if validity != "debug_only":
            errors.append("debug smoke must remain result_validity='debug_only'")
    elif validity != "protocol_microbenchmark":
        errors.append(
            f"result_validity is {validity!r}, not protocol_microbenchmark"
        )
    if data.get("protocol_version") != PROTOCOL_VERSION:
        errors.append(f"protocol version is not frozen {PROTOCOL_VERSION}")
    captured_hash = data.get("protocol_sha256")
    if captured_hash != protocol_sha256():
        errors.append("aggregate protocol_sha256 mismatch")

    audit = data.get("audit") or {}
    gates = audit.get("gates") or {}
    gates_to_require = ("G1", "G2", "G3", "G6", "G7") if debug_smoke else (
        "G1",
        "G2",
        "G3",
        "G4",
        "G5",
        "G6",
        "G7",
    )
    for gate_name in gates_to_require:
        gate = gates.get(gate_name)
        if not gate or not gate.get("pass"):
            errors.append(f"{gate_name} is missing or failed")
    if not debug_smoke:
        if not audit.get("pass"):
            errors.append("audit.pass is false")
        for violation in audit.get("violations") or []:
            errors.append(f"audit violation: {violation}")

    cells = data.get("cells") or []
    if not cells:
        errors.append("aggregate has no cells")
    for cell in cells:
        n = int(cell.get("n") or 0)
        seeds = cell.get("seeds") or []
        if not debug_smoke and (n < 5 or len(set(seeds)) < 5):
            errors.append(f"cell {cell.get('cell_id')} has n={n}; n>=5 required")
        if not cell.get("all_runs_retained", True):
            errors.append(f"cell {cell.get('cell_id')} did not retain every run")

    manifests = data.get("manifests") or []
    for index, manifest in enumerate(manifests):
        for error in validate_manifest(manifest, require_clean=not debug_smoke):
            errors.append(f"manifest[{index}]: {error}")

    if not debug_smoke:
        system = _platform_string(data, platform_string)
        lower = system.lower()
        if "linux" not in lower:
            errors.append(f"native bare-metal Linux required; platform={system!r}")
        if "microsoft" in lower or "wsl" in lower:
            errors.append(f"WSL is debug-only; platform={system!r}")
        git = data.get("git") or data.get("measurement_git") or {}
        if git.get("dirty") != "no":
            errors.append("git capture is not clean")
        if not git.get("commit"):
            errors.append("git commit pin is missing")
        if not manifests:
            for field in ("core_pins", "software", "kernel_version"):
                if not data.get(field):
                    errors.append(f"aggregate missing reproducibility pin: {field}")
            sdk = data.get("sdk_lock") or (data.get("software") or {}).get("sdk_lock")
            if not isinstance(sdk, Mapping) or not _valid_sha256(sdk.get("sha256")):
                errors.append("aggregate missing SDK lock hash")
            pins = data.get("core_pins") or {}
            client = set(_cores(pins.get("client")))
            server = set(_cores(pins.get("server")))
            os_cores = set(_cores(pins.get("os_analysis")))
            if not client or not server or not os_cores:
                errors.append("aggregate requires client/server/OS core pins")
            if client & server or client & os_cores or server & os_cores:
                errors.append("aggregate core pins are not disjoint")
            transports = {
                (cell.get("coordinates") or {}).get("transport") for cell in cells
            }
            if "http_sse_tls_on" in transports:
                certificate = data.get("certificate")
                if not isinstance(certificate, Mapping) or not _valid_sha256(
                    certificate.get("sha256")
                ):
                    errors.append("aggregate missing TLS certificate hash")
    return errors


def _platform_string(data: Mapping[str, Any], override: str | None) -> str:
    if override is not None:
        return override
    env = data.get("env") or data.get("environment") or {}
    return str(
        data.get("platform")
        or env.get("platform")
        or data.get("kernel_version")
        or platform.platform()
    )


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def _cores(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, str):
        result: list[int] = []
        for part in value.split(","):
            if "-" in part:
                start, stop = (int(item) for item in part.split("-", 1))
                result.extend(range(start, stop + 1))
            elif part.strip():
                result.append(int(part))
        return result
    return [int(item) for item in value]
