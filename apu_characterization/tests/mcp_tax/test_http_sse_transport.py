from __future__ import annotations

import json

from apu_characterization.mcp_tax.transports import HttpSseTransport, LocalSseServer
from apu_characterization.mcp_tax.transports.http_sse import frame_sse, unframe_sse


def _respond(request: bytes) -> bytes:
    value = json.loads(request)
    return json.dumps(
        {"jsonrpc": "2.0", "id": value["id"], "result": {"ok": True}},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_plain_http_post_sse_round_trip_has_actual_wire_sizes() -> None:
    request = b'{"jsonrpc":"2.0","id":1,"method":"ping"}'
    with LocalSseServer(_respond) as server:
        with HttpSseTransport(server.endpoint) as transport:
            result = transport.exchange(request)

    assert json.loads(result.response)["result"] == {"ok": True}
    assert result.trace.transport == "http_sse_tls_off"
    assert result.trace.request.logical_bytes == len(request)
    assert result.trace.request.wire_bytes > len(request)
    assert result.trace.response.wire_bytes > len(result.response)
    assert result.trace.metadata["tls_verified"] is False
    assert result.trace.timing.tls_handshake_ns == 0


def test_sse_framing_is_separate_and_deterministic() -> None:
    message = b'{"jsonrpc":"2.0","id":2,"result":null}'
    framed = frame_sse(message)
    assert framed == b"data: " + message + b"\n\n"
    assert unframe_sse(framed) == message

