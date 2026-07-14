from __future__ import annotations

from types import SimpleNamespace

from apu_characterization.mcp_tax.transports import http_stream


def test_probe_returns_false_when_sdk_is_absent(monkeypatch) -> None:
    def missing(_package: str) -> str:
        raise http_stream.importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(http_stream.importlib.metadata, "version", missing)
    result = http_stream.probe_streamable_http(pinned_version="1.0.0")
    assert not result.supported
    assert "not installed" in result.reason
    assert not hasattr(result, "transport_data")


def test_probe_rejects_installed_version_that_is_not_pin(monkeypatch) -> None:
    monkeypatch.setattr(
        http_stream.importlib.metadata, "version", lambda _package: "1.2.0"
    )
    result = http_stream.probe_streamable_http(pinned_version="1.1.0")
    assert not result.supported
    assert "does not match" in result.reason


def test_probe_requires_both_stable_sdk_seams(monkeypatch) -> None:
    monkeypatch.setattr(
        http_stream.importlib.metadata, "version", lambda _package: "1.2.0"
    )

    def import_module(name: str):
        if ".client." in name:
            return SimpleNamespace(streamablehttp_client=lambda: None)
        return SimpleNamespace()

    monkeypatch.setattr(http_stream.importlib, "import_module", import_module)
    result = http_stream.probe_streamable_http(pinned_version="1.2.0")
    assert not result.supported
    assert "server" in result.reason


def test_probe_admits_complete_stable_pinned_sdk(monkeypatch) -> None:
    monkeypatch.setattr(
        http_stream.importlib.metadata, "version", lambda _package: "1.2.0"
    )

    def import_module(name: str):
        if ".client." in name:
            return SimpleNamespace(streamablehttp_client=lambda: None)
        return SimpleNamespace(StreamableHTTPServerTransport=lambda: None)

    monkeypatch.setattr(http_stream.importlib, "import_module", import_module)
    result = http_stream.probe_streamable_http(pinned_version="1.2.0")
    assert result.supported
    assert result.client_symbol == "streamablehttp_client"
    assert result.server_symbol == "StreamableHTTPServerTransport"

