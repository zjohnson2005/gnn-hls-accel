"""v10 authenticity follow-ups: stdio harness skip + TRANSPORT subslices."""

from __future__ import annotations

import json
import sys

from apu_characterization.mcp_tax.accum import McpMessageAccumulator
from apu_characterization.mcp_tax.transport_instrument import TransportInstrumentation
from apu_characterization.mcp_tax.transports.stdio import (
    StdioTransport,
    _check_stdio_newlines,
    _validate_stdio_message,
)


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


def test_check_stdio_newlines_only() -> None:
    _check_stdio_newlines(b'{"ok":true}')
    try:
        _check_stdio_newlines(b'{"a":1}\n')
    except ValueError as exc:
        assert "newlines" in str(exc)
    else:
        raise AssertionError("expected newline rejection")


def test_validate_stdio_rejects_non_object() -> None:
    try:
        _validate_stdio_message(b"[1,2]")
    except ValueError as exc:
        assert "object" in str(exc)
    else:
        raise AssertionError("expected object rejection")


def test_instrumented_stdio_books_write_and_read_provenance() -> None:
    request = b'{"jsonrpc":"2.0","id":1,"method":"echo","params":{"x":1}}'
    acc = McpMessageAccumulator("client", mode="throttle")
    acc.begin_message("1")
    instr = TransportInstrumentation(accumulator=acc, message_id="1")
    with StdioTransport([sys.executable, "-u", "-c", SERVER]) as transport:
        transport.bind_instrumentation(instr)
        result = transport.exchange(request)
        transport.clear_instrumentation()
    acc.end_message("1")
    assert json.loads(result.response)["id"] == 1
    transport_totals = None
    for key, totals in acc.by_key.items():
        if key[0] == "MSG_TRANSPORT_CPU":
            transport_totals = totals
            break
    assert transport_totals is not None
    assert "transport_write" in transport_totals.provenance
    assert "transport_read" in transport_totals.provenance
    assert transport_totals.provenance["transport_write"] >= 0
    assert transport_totals.provenance["transport_read"] >= 0
