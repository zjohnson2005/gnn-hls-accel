from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Callable

from apu_characterization.mcp_tax.accum import McpMessageAccumulator
from apu_characterization.mcp_tax.instrument import mcp_timed
from apu_characterization.mcp_tax.message_context import message_scope
from apu_characterization.mcp_tax.reconcile import reconcile_message
from apu_characterization.mcp_tax.sdk_hooks import register_sdk_hooks
from apu_characterization.mcp_tax.taxonomy import McpCategory


class _FakeSdk:
    sdk_name = "fake-mcp-sdk"
    sdk_version = "1.2.3"

    def __init__(self) -> None:
        self.hooks: dict[str, Callable[..., AbstractContextManager[None]]] = {}

    def register_mcp_tax_hook(
        self, name: str, factory: Callable[..., AbstractContextManager[None]]
    ) -> None:
        self.hooks[name] = factory


def test_throttle_is_default_and_categories_are_enabled() -> None:
    acc = McpMessageAccumulator("client")
    assert acc.mode == "throttle"
    assert acc.category_hooks_enabled is True
    with mcp_timed(McpCategory.MSG_SERIAL, accumulator=acc, message_id="m1"):
        sum(range(10))
    assert acc.totals_for(McpCategory.MSG_SERIAL, "m1").count == 1


def test_stripped_keeps_process_and_timestamps_but_disables_categories() -> None:
    acc = McpMessageAccumulator("client", mode="stripped")
    with message_scope("m1", accumulator=acc):
        with mcp_timed(McpCategory.MSG_SERIAL):
            sum(range(100))

    assert acc.category_hooks_enabled is False
    assert not acc.by_key
    observation = acc.messages["m1"]
    assert observation.process_cpu_ns >= 0
    assert observation.wall_ns >= 0
    assert observation.end_wall_ns >= observation.start_wall_ns
    result = reconcile_message(acc, "m1")
    assert result["instrumented_cpu_ns"] == 0
    assert result["residual_cpu_ns"] == observation.process_cpu_ns


def test_full_records_local_schedstat_metadata_when_platform_supports_it() -> None:
    acc = McpMessageAccumulator("server", mode="full")
    with message_scope("m1", accumulator=acc):
        sum(range(100))
    # Linux/WSL normally records a value; unsupported kernels and Windows
    # explicitly serialize None without changing the process-clock contract.
    assert "m1" in acc.messages
    assert acc.messages["m1"].thread_schedstat_cpu_ns is None or (
        acc.messages["m1"].thread_schedstat_cpu_ns >= 0
    )


def test_exact_version_sdk_hooks_attribute_only_registered_regions() -> None:
    sdk = _FakeSdk()
    acc = McpMessageAccumulator("server")
    registration = register_sdk_hooks(
        sdk, accumulator=acc, expected_version="1.2.3"
    )

    assert registration.complete is True
    assert registration.coverage_fraction == 1.0
    with message_scope("m1", accumulator=acc):
        with sdk.hooks["message_dispatch"]():
            sum(range(100))
    assert acc.totals_for(McpCategory.MSG_DISPATCH, "m1").count == 1
    assert acc.sdk_coverage[-1]["complete"] is True


def test_version_mismatch_registers_nothing_and_surfaces_zero_coverage() -> None:
    sdk = _FakeSdk()
    acc = McpMessageAccumulator("client")
    registration = register_sdk_hooks(
        sdk, accumulator=acc, expected_version="9.9.9"
    )

    assert not sdk.hooks
    assert registration.complete is False
    assert registration.coverage_fraction == 0.0
    assert registration.as_dict()["version_match"] is False
    assert len(registration.unavailable_hooks) == registration.requested_hooks


def test_opaque_sdk_is_not_monkey_patched() -> None:
    class OpaqueSdk:
        sdk_version = "1.0"

    sdk = OpaqueSdk()
    before = dict(vars(sdk))
    acc = McpMessageAccumulator("client")
    registration = register_sdk_hooks(
        sdk, accumulator=acc, expected_version="1.0"
    )

    assert dict(vars(sdk)) == before
    assert registration.registered_hooks == []
    assert registration.coverage_fraction == 0.0
    assert "registration_api" in registration.errors
