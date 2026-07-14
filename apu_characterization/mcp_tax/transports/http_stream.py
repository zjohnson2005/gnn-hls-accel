"""Admission probe for the optional Streamable HTTP matrix arm."""

from __future__ import annotations

import importlib
import importlib.metadata
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StreamableHttpSupport:
    supported: bool
    reason: str
    sdk_package: str
    sdk_version: str | None
    client_symbol: str | None = None
    server_symbol: str | None = None


class StreamableHttpUnsupported(RuntimeError):
    pass


def _stable_release(version: str) -> bool:
    # MCP SDK releases use ordinary PEP 440 numeric versions.  Reject dev,
    # alpha, beta, rc, and local builds rather than guessing their stability.
    return bool(re.fullmatch(r"\d+(?:\.\d+)*(?:\.post\d+)?", version))


def _first_symbol(module: object, names: tuple[str, ...]) -> str | None:
    for name in names:
        if callable(getattr(module, name, None)):
            return name
    return None


def _repository_pin(sdk_package: str) -> str | None:
    requirements = Path(__file__).parents[2] / "requirements-mcp.txt"
    try:
        lines = requirements.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    prefix = f"{sdk_package}=="
    matches = [
        line.strip()[len(prefix) :]
        for line in lines
        if line.strip().startswith(prefix)
    ]
    return matches[0] if len(matches) == 1 and matches[0] else None


def probe_streamable_http(
    *,
    sdk_package: str = "mcp",
    pinned_version: str | None = None,
) -> StreamableHttpSupport:
    """Admit the arm only when one stable SDK supplies both complete seams."""
    expected_version = pinned_version or _repository_pin(sdk_package)
    if expected_version is None:
        return StreamableHttpSupport(
            supported=False,
            reason=f"no exact {sdk_package!r} SDK pin is available",
            sdk_package=sdk_package,
            sdk_version=None,
        )
    try:
        version = importlib.metadata.version(sdk_package)
    except importlib.metadata.PackageNotFoundError:
        return StreamableHttpSupport(
            supported=False,
            reason=f"pinned SDK package {sdk_package!r} is not installed",
            sdk_package=sdk_package,
            sdk_version=None,
        )
    if version != expected_version:
        return StreamableHttpSupport(
            supported=False,
            reason=(
                f"installed {sdk_package} version {version} does not match "
                f"pinned version {expected_version}"
            ),
            sdk_package=sdk_package,
            sdk_version=version,
        )
    if not _stable_release(version):
        return StreamableHttpSupport(
            supported=False,
            reason=f"SDK version {version} is not a stable release",
            sdk_package=sdk_package,
            sdk_version=version,
        )

    try:
        client_module = importlib.import_module(f"{sdk_package}.client.streamable_http")
        server_module = importlib.import_module(f"{sdk_package}.server.streamable_http")
    except (ImportError, ModuleNotFoundError) as exc:
        return StreamableHttpSupport(
            supported=False,
            reason=f"stable SDK lacks Streamable HTTP modules: {exc}",
            sdk_package=sdk_package,
            sdk_version=version,
        )

    client_symbol = _first_symbol(
        client_module, ("streamablehttp_client", "streamable_http_client")
    )
    server_symbol = _first_symbol(
        server_module,
        ("StreamableHTTPServerTransport", "streamable_http_server"),
    )
    if client_symbol is None or server_symbol is None:
        missing = []
        if client_symbol is None:
            missing.append("client")
        if server_symbol is None:
            missing.append("server")
        return StreamableHttpSupport(
            supported=False,
            reason=(
                "stable SDK does not expose complete Streamable HTTP "
                + " and ".join(missing)
                + " support"
            ),
            sdk_package=sdk_package,
            sdk_version=version,
            client_symbol=client_symbol,
            server_symbol=server_symbol,
        )
    return StreamableHttpSupport(
        supported=True,
        reason="stable pinned SDK exposes complete client and server support",
        sdk_package=sdk_package,
        sdk_version=version,
        client_symbol=client_symbol,
        server_symbol=server_symbol,
    )


def require_streamable_http(**kwargs: object) -> StreamableHttpSupport:
    """Raise instead of allowing a partial or fabricated transport result."""
    result = probe_streamable_http(**kwargs)
    if not result.supported:
        raise StreamableHttpUnsupported(result.reason)
    return result

