from __future__ import annotations

import time

import pytest

from apu_characterization.mcp_tax.accum import McpMessageAccumulator
from apu_characterization.mcp_tax.instrument import mcp_wait
from apu_characterization.mcp_tax.message_context import message_scope
from apu_characterization.mcp_tax.reconcile import reconcile_message
from apu_characterization.mcp_tax.taxonomy import McpCategory


def test_wait_ledger_has_zero_cpu_and_is_not_a_cpu_category() -> None:
    acc = McpMessageAccumulator("client")
    acc.set_message_observation("m1", process_cpu_ns=100, wall_ns=1_000)
    acc.book(McpCategory.MSG_TRANSPORT_CPU, 80, message_id="m1")
    acc.book_wait("transport_blocked", 700, message_id="m1")
    acc.book_wait("runqueue", 50, message_id="m1")
    acc.book_wait("synthetic_tool_delay", 100, message_id="m1")
    acc.book_wait("unattributed_wait", 20, message_id="m1")

    result = reconcile_message(acc, "m1")

    assert result["residual_cpu_ns"] == 20
    assert result["wait"]["cpu_ns"] == 0
    assert result["wait"]["wall_ns"] == 870
    assert set(result["wait"]["by_kind"]) == {
        "transport_blocked",
        "runqueue",
        "synthetic_tool_delay",
        "unattributed_wait",
    }
    assert all(cell.cpu_ns == 0 for cell in acc.waits_by_key.values())


def test_wait_context_measures_wall_only() -> None:
    acc = McpMessageAccumulator("server")
    with message_scope("m1", accumulator=acc):
        with mcp_wait("transport_blocked"):
            time.sleep(0.002)

    totals = acc.wait_totals("transport_blocked", "m1")
    assert totals.cpu_ns == 0
    assert totals.wall_ns >= 1_000_000


def test_unknown_wait_kind_is_rejected() -> None:
    acc = McpMessageAccumulator("client")
    with pytest.raises(ValueError, match="unknown wait kind"):
        acc.book_wait("socket_magic", 1, message_id="m1")
