from __future__ import annotations

import json
import sys

import pytest

from apu_characterization.mcp_tax.client import RawJsonRpcClient
from apu_characterization.mcp_tax.transports import StdioTransport


SERVER = r"""
import json
import sys
for line in sys.stdin.buffer:
    request = json.loads(line)
    response = {
        "jsonrpc": "2.0",
        "id": request["id"],
        "result": {"echo": request["params"]},
    }
    payload = json.dumps(
        response, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    sys.stdout.buffer.write(payload + b"\n")
    sys.stdout.buffer.flush()
"""


def test_stdio_round_trip_preserves_logical_hash_and_counts_newlines() -> None:
    request = b'{"jsonrpc":"2.0","id":7,"method":"echo","params":{"x":1}}'
    with StdioTransport([sys.executable, "-u", "-c", SERVER]) as transport:
        result = transport.exchange(request)

    decoded = json.loads(result.response)
    assert decoded["id"] == 7
    assert decoded["result"]["echo"] == {"x": 1}
    assert result.trace.request.logical_bytes == len(request)
    assert result.trace.request.wire_bytes == len(request) + 1
    assert result.trace.response.wire_bytes == len(result.response) + 1
    assert len(result.trace.request.logical_sha256) == 64
    assert result.trace.timing.write_ns >= 0
    assert result.trace.timing.read_ns >= 0
    assert set(result.trace.metadata["proc_before"]) == {"parent", "server"}


def test_stdio_rejects_raw_newlines_before_writing() -> None:
    with StdioTransport([sys.executable, "-u", "-c", SERVER]) as transport:
        with pytest.raises(ValueError, match="newlines"):
            transport.exchange(b'{"jsonrpc":"2.0"}\n')


def test_raw_client_accepts_traced_transport_results() -> None:
    with StdioTransport([sys.executable, "-u", "-c", SERVER]) as transport:
        result = RawJsonRpcClient(transport).request("echo", {"x": 1})
    assert result == {"echo": {"x": 1}}

