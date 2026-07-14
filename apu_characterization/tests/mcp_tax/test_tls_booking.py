from __future__ import annotations

from apu_characterization.mcp_tax.accum import McpMessageAccumulator
from apu_characterization.mcp_tax.taxonomy import McpCategory
from apu_characterization.mcp_tax.transport_instrument import TransportInstrumentation


def test_tls_handshake_books_transport_cpu_not_validate() -> None:
    acc = McpMessageAccumulator("client")
    acc.begin_endpoint()
    instr = TransportInstrumentation(accumulator=acc, message_id="m1")
    instr.tls_handshake(lambda: None)
    assert acc.totals_for(McpCategory.MSG_VALIDATE, "m1").cpu_ns == 0
    transport = acc.totals_for(McpCategory.MSG_TRANSPORT_CPU, "m1")
    assert transport.count >= 1
    assert "transport_tls_handshake" in transport.provenance
