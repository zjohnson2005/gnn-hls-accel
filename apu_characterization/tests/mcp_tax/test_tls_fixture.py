from __future__ import annotations

import json
import shutil
import ssl

import pytest

from apu_characterization.mcp_tax.tls_fixture import TlsFixture
from apu_characterization.mcp_tax.transports import HttpSseTransport, LocalSseServer


pytestmark = pytest.mark.skipif(
    shutil.which("openssl") is None, reason="OpenSSL is required for TLS fixture tests"
)


def _response(request: bytes) -> bytes:
    identifier = json.loads(request)["id"]
    return (
        b'{"jsonrpc":"2.0","id":'
        + str(identifier).encode("ascii")
        + b',"result":"tls"}'
    )


def test_tls_fixture_records_public_identity_and_cleans_up() -> None:
    fixture = TlsFixture.create(matrix_id="unit")
    directory = fixture.directory
    try:
        assert len(fixture.ca_sha256) == 64
        assert len(fixture.server_fingerprint_sha256) == 64
        assert "key" not in fixture.public_metadata()
        assert fixture.server_key_path.is_file()
        context = fixture.client_context()
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname
    finally:
        fixture.close()
    assert not directory.exists()


def test_https_sse_verifies_local_ca_and_separates_handshake() -> None:
    request = b'{"jsonrpc":"2.0","id":9,"method":"ping"}'
    with TlsFixture.create(matrix_id="https") as fixture:
        with LocalSseServer(
            _response, ssl_context=fixture.server_context()
        ) as server:
            with HttpSseTransport(
                server.endpoint, ssl_context=fixture.client_context()
            ) as transport:
                result = transport.exchange(request)

    assert json.loads(result.response)["result"] == "tls"
    assert result.trace.transport == "http_sse_tls_on"
    assert result.trace.metadata["tls_verified"] is True
    assert result.trace.timing.tls_handshake_ns > 0
    assert result.trace.timing.session_setup_ns > result.trace.timing.setup_ns
    assert result.trace.timing.steady_state_ns >= result.trace.timing.read_ns


def test_https_rejects_unverified_client_context() -> None:
    context = ssl._create_unverified_context()
    with pytest.raises(ValueError, match="verification"):
        HttpSseTransport("https://localhost:8443/mcp", ssl_context=context)

