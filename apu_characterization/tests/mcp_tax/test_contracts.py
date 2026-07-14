"""Contract, schema, and deterministic plan tests for MCP-01."""

from __future__ import annotations

from dataclasses import replace

import pytest
from jsonschema.validators import validator_for

from apu_characterization.experiments.mcp_tax_matrix import (
    build_cell_plan as build_matrix_cell_plan,
)
from apu_characterization.mcp_tax.contracts import (
    CellCoordinates,
    enumerate_matrix,
    load_protocol,
)
from apu_characterization.mcp_tax.plan import (
    build_cell_plan,
    seeded_tool_cycle,
)
from apu_characterization.mcp_tax.schemas import (
    all_schema_digests,
    all_schema_profiles,
    generate_schema,
    scalar_property_count,
    schema_depth,
    schema_digest,
)


def _coordinates(**overrides: object) -> CellCoordinates:
    values: dict[str, object] = {
        "transport": "stdio",
        "payload_bytes": 4096,
        "schema_profile": "nested_depth_4",
        "tool_count": 10,
        "implementation": "raw_jsonrpc",
        "mode": "throttle",
    }
    values.update(overrides)
    return CellCoordinates(**values)  # type: ignore[arg-type]


def test_frozen_matrix_counts() -> None:
    assert len(enumerate_matrix()) == 120
    assert len(enumerate_matrix(include_http_stream=True)) == 160


@pytest.mark.parametrize(
    ("schema_id", "expected_depth", "expected_properties"),
    (
        ("flat_5", 1, 5),
        ("nested_depth_4", 4, 20),
        ("pathological_large", 4, 256),
    ),
)
def test_schema_profiles_match_protocol_definitions(
    schema_id: str,
    expected_depth: int,
    expected_properties: int,
) -> None:
    schema = generate_schema(schema_id)
    assert schema_depth(schema) == expected_depth
    assert scalar_property_count(schema) == expected_properties
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    validator_for(schema).check_schema(schema)

    protocol_definition = load_protocol()["schema_definitions"][schema_id]
    assert expected_depth == protocol_definition["depth"]
    assert expected_properties == protocol_definition["property_count"]


def test_schema_digests_are_canonical_and_complete() -> None:
    expected_ids = tuple(load_protocol()["schema_definitions"])
    profiles = all_schema_profiles()
    digests = all_schema_digests()
    assert tuple(profile.schema_id for profile in profiles) == expected_ids
    assert set(digests) == set(expected_ids)
    assert all(len(digest) == 64 for digest in digests.values())
    assert {
        schema_id: schema_digest(schema_id) for schema_id in expected_ids
    } == digests


def test_default_plan_has_20_warmup_and_200_measured_messages() -> None:
    plan = build_cell_plan(_coordinates(), seed=7)
    assert plan.warmup_messages == 20
    assert plan.measured_messages == 200
    assert len(plan.steps) == 220
    assert all(step.payload_bytes == 4096 for step in plan.steps)
    assert all(step.synthetic_delay_ns == 0 for step in plan.steps)


def test_matrix_cli_uses_the_canonical_plan_builder() -> None:
    plan = build_matrix_cell_plan(_coordinates(), 7)
    assert len(plan.steps) == 220
    assert plan.steps == build_cell_plan(_coordinates(), seed=7).steps
    assert all(step.tool_name.startswith("tool_") for step in plan.steps)


def test_seeded_plan_cycles_a_deterministic_tool_permutation() -> None:
    coordinates = _coordinates(tool_count=10)
    plan = build_cell_plan(coordinates, seed=19)
    cycle = seeded_tool_cycle(10, 19)
    assert tuple(step.tool_name for step in plan.steps[:10]) == cycle
    assert tuple(step.tool_name for step in plan.steps[10:20]) == cycle
    assert seeded_tool_cycle(10, 19) == cycle
    assert seeded_tool_cycle(10, 20) != cycle


def test_request_hashes_are_stable_across_transports_and_implementations() -> None:
    base = _coordinates(transport="stdio", implementation="raw_jsonrpc")
    sdk_http = replace(
        base,
        transport="http_sse_tls_on",
        implementation="reference_sdk",
    )
    first = build_cell_plan(base, seed=4)
    second = build_cell_plan(sdk_http, seed=4)
    repeated = build_cell_plan(base, seed=4)
    assert first.request_hashes() == second.request_hashes()
    assert first.request_hashes() == repeated.request_hashes()
    assert len(set(first.request_hashes())) == len(first.steps)


def test_only_frozen_tool_delays_are_accepted() -> None:
    coordinates = _coordinates()
    smoke = build_cell_plan(coordinates, seed=0, synthetic_delay_ns=1_000_000)
    assert all(step.synthetic_delay_ns == 1_000_000 for step in smoke.steps)
    with pytest.raises(ValueError):
        build_cell_plan(coordinates, seed=0, synthetic_delay_ns=1)
