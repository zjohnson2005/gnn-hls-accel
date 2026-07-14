from __future__ import annotations

import itertools

import pytest

from apu_characterization.mcp_tax.accum import McpMessageAccumulator
from apu_characterization.mcp_tax.instrument import mcp_timed
from apu_characterization.mcp_tax.message_context import message_scope
from apu_characterization.mcp_tax.taxonomy import McpCategory


def test_accumulator_is_endpoint_local_and_keyed_by_role() -> None:
    client = McpMessageAccumulator("client")
    server = McpMessageAccumulator("server")
    client.book(McpCategory.MSG_SERIAL, 11, message_id="m1")
    server.book(McpCategory.MSG_SERIAL, 17, message_id="m1")

    assert client.by_key[("MSG_SERIAL", "m1", "client")].cpu_ns == 11
    assert server.by_key[("MSG_SERIAL", "m1", "server")].cpu_ns == 17
    with pytest.raises(ValueError, match="independent accumulator"):
        client.book(
            McpCategory.MSG_SERIAL,
            1,
            message_id="m1",
            process_role="server",
        )


def test_nested_timers_book_exclusive_thread_cpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Entry/exit clocks include a second read when each frame starts and a
    # resume read after the child is booked.
    cpu = itertools.count(1)
    wall = itertools.count(101)
    monkeypatch.setattr(
        "apu_characterization.mcp_tax.instrument.time.thread_time_ns",
        lambda: next(cpu),
    )
    monkeypatch.setattr(
        "apu_characterization.mcp_tax.instrument.time.perf_counter_ns",
        lambda: next(wall),
    )
    acc = McpMessageAccumulator("client")
    with mcp_timed(McpCategory.MSG_SERIAL, accumulator=acc, message_id="m1"):
        with mcp_timed(McpCategory.MSG_VALIDATE, accumulator=acc, message_id="m1"):
            pass

    serial = acc.totals_for(McpCategory.MSG_SERIAL, "m1")
    validate = acc.totals_for(McpCategory.MSG_VALIDATE, "m1")
    assert serial.cpu_ns == 2
    assert validate.cpu_ns == 1
    assert serial.wall_ns == 2
    assert validate.wall_ns == 1


def test_timer_uses_context_and_records_payload_metadata() -> None:
    acc = McpMessageAccumulator("server")
    with message_scope("request-7", accumulator=acc):
        with mcp_timed(
            McpCategory.MSG_FRAME,
            bytes_in=123,
            bytes_out=456,
            provenance="sdk_hook:frame",
        ):
            sum(range(100))

    totals = acc.totals_for(McpCategory.MSG_FRAME, "request-7")
    assert totals.cpu_ns >= 0
    assert totals.wall_ns >= 0
    assert totals.bytes_in == 123
    assert totals.bytes_out == 456
    assert totals.bytes == 579
    assert totals.count == 1
    assert "sdk_hook:frame" in totals.provenance
    assert acc.messages["request-7"].end_wall_ns >= acc.messages["request-7"].start_wall_ns


def test_endpoint_ledger_json_round_trip(tmp_path) -> None:
    acc = McpMessageAccumulator("client", mode="full")
    acc.book(
        McpCategory.MSG_DISPATCH,
        42,
        message_id="m1",
        wall_ns=84,
        bytes_out=9,
        provenance="manual",
    )
    acc.book_wait("transport_blocked", 100, message_id="m1")
    acc.set_message_observation("m1", process_cpu_ns=100, wall_ns=500)

    path = acc.save(tmp_path / "run" / "client_ledger.json")
    restored = McpMessageAccumulator.load(path)

    assert restored.to_dict() == acc.to_dict()
    assert restored.process_role == "client"
    assert restored.mode == "full"


def test_message_category_requires_message_id() -> None:
    acc = McpMessageAccumulator("client")
    with pytest.raises(ValueError, match="message_id"):
        acc.book(McpCategory.MSG_SERIAL, 1)
