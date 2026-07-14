from __future__ import annotations

import pytest

from apu_characterization.mcp_tax.accum import (
    McpMessageAccumulator,
    ScopeObservation,
)
from apu_characterization.mcp_tax.instrument import mcp_timed
from apu_characterization.mcp_tax.message_context import message_scope, setup_scope
from apu_characterization.mcp_tax.reconcile import reconcile_endpoint, reconcile_setup
from apu_characterization.mcp_tax.taxonomy import McpCategory


def test_setup_has_no_message_key_and_reconciles_separately() -> None:
    acc = McpMessageAccumulator("client")
    acc.setup_observation = ScopeObservation(0, 100, 40, 100)
    acc.set_message_observation("m1", process_cpu_ns=60, wall_ns=200)
    acc.book(McpCategory.SESSION_SETUP, 30)
    acc.book(McpCategory.MSG_SERIAL, 50, message_id="m1")

    setup = reconcile_setup(acc)
    endpoint = reconcile_endpoint(acc)

    assert setup is not None
    assert setup["message_id"] is None
    assert setup["categories"]["SESSION_SETUP"] == 30
    assert setup["residual_cpu_ns"] == 10
    assert "SESSION_SETUP" not in endpoint["messages"]["m1"]["categories"]
    assert endpoint["categories"]["SESSION_SETUP"] == 30


def test_setup_timer_requires_setup_scope() -> None:
    acc = McpMessageAccumulator("server")
    with pytest.raises(RuntimeError, match="setup_scope"):
        with mcp_timed(McpCategory.SESSION_SETUP, accumulator=acc):
            pass


def test_setup_scope_cannot_overlap_message_scope() -> None:
    acc = McpMessageAccumulator("server")
    with message_scope("m1", accumulator=acc):
        with pytest.raises(RuntimeError, match="inside a message"):
            with setup_scope():
                pass


def test_timed_setup_books_only_setup_ledger() -> None:
    acc = McpMessageAccumulator("server")
    with setup_scope(accumulator=acc):
        with mcp_timed(McpCategory.SESSION_SETUP):
            sum(range(100))

    assert acc.setup_totals().count == 1
    assert not acc.by_key


def test_setup_category_rejects_message_id() -> None:
    acc = McpMessageAccumulator("client")
    with pytest.raises(ValueError, match="must not be attached"):
        acc.book(McpCategory.SESSION_SETUP, 1, message_id="m1")
