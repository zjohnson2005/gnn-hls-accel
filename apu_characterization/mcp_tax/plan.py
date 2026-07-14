"""Seeded, transport-independent message plans for MCP-01 cells."""

from __future__ import annotations

import random

from .contracts import (
    PROTOCOL_VERSION,
    CellCoordinates,
    CellPlan,
    MessageStep,
    load_protocol,
)
from .schemas import generate_schema

TOOL_NAME_WIDTH = 4


def tool_name(index: int) -> str:
    if index < 0:
        raise ValueError("tool index cannot be negative")
    return f"tool_{index:0{TOOL_NAME_WIDTH}d}"


def seeded_tool_cycle(tool_count: int, seed: int) -> tuple[str, ...]:
    """Return one seeded permutation that is repeated by a cell plan."""

    if tool_count < 1:
        raise ValueError("tool_count must be positive")
    names = [tool_name(index) for index in range(tool_count)]
    random.Random(seed).shuffle(names)
    return tuple(names)


def build_cell_plan(
    coordinates: CellCoordinates,
    *,
    seed: int,
    warmup_messages: int | None = None,
    measured_messages: int | None = None,
    synthetic_delay_ns: int | None = None,
) -> CellPlan:
    """Build a deterministic plan whose requests do not encode transport/SDK.

    This separation is important: cells that differ only in transport or
    implementation receive byte-identical semantic JSON-RPC requests.
    """

    protocol = load_protocol()
    primary = protocol["primary"]
    warmup = (
        int(primary["warmup_messages"])
        if warmup_messages is None
        else warmup_messages
    )
    measured = (
        int(primary["measured_messages"])
        if measured_messages is None
        else measured_messages
    )
    delay_ns = (
        int(protocol["tool_delay"]["primary_ns"])
        if synthetic_delay_ns is None
        else synthetic_delay_ns
    )
    if warmup < 0 or measured < 1:
        raise ValueError("warmup must be non-negative and measured must be positive")
    if delay_ns not in (
        int(protocol["tool_delay"]["primary_ns"]),
        int(protocol["tool_delay"]["smoke_ns"]),
    ):
        raise ValueError("synthetic delay must be the frozen primary or smoke value")

    # Fail early if a coordinate names a schema outside the frozen protocol.
    generate_schema(coordinates.schema_profile)
    cycle = seeded_tool_cycle(coordinates.tool_count, seed)
    total = warmup + measured
    steps = tuple(
        MessageStep(
            index=index,
            method="tools/call",
            tool_name=cycle[index % len(cycle)],
            schema_id=coordinates.schema_profile,
            payload_bytes=coordinates.payload_bytes,
            synthetic_delay_ns=delay_ns,
        )
        for index in range(total)
    )
    return CellPlan(
        protocol_version=PROTOCOL_VERSION,
        seed=seed,
        coordinates=coordinates,
        warmup_messages=warmup,
        measured_messages=measured,
        steps=steps,
    )


def split_warmup_measured(
    plan: CellPlan,
) -> tuple[tuple[MessageStep, ...], tuple[MessageStep, ...]]:
    boundary = plan.warmup_messages
    return plan.steps[:boundary], plan.steps[boundary:]
