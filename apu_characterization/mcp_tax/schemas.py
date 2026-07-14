"""Deterministic JSON Schema profiles frozen by ``protocol_v1.json``.

The property count is the number of scalar leaves.  Object-valued links used
to form a nested profile are deliberately not counted as semantic properties.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import canonical_json_bytes, load_protocol, sha256_bytes

JSONSchema = dict[str, Any]


@dataclass(frozen=True)
class SchemaProfile:
    """One generated schema plus its frozen, independently checked metadata."""

    schema_id: str
    schema: JSONSchema
    depth: int
    property_count: int
    digest: str


def _string_properties(count: int) -> dict[str, JSONSchema]:
    width = max(2, len(str(count - 1)))
    return {
        f"value_{index:0{width}d}": {"type": "string"}
        for index in range(count)
    }


def _object_schema(*, leaves: int, child: JSONSchema | None = None) -> JSONSchema:
    properties = _string_properties(leaves)
    if child is not None:
        properties["nested"] = child
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _nested_schema(*, depth: int, leaves_per_level: int) -> JSONSchema:
    if depth < 1:
        raise ValueError("schema depth must be positive")
    schema: JSONSchema | None = None
    for _ in range(depth):
        schema = _object_schema(leaves=leaves_per_level, child=schema)
    assert schema is not None
    return schema


def schema_depth(schema: JSONSchema) -> int:
    """Return the greatest number of object levels in *schema*."""

    if schema.get("type") != "object":
        return 0
    children = [
        value
        for value in schema.get("properties", {}).values()
        if isinstance(value, dict) and value.get("type") == "object"
    ]
    return 1 + max((schema_depth(child) for child in children), default=0)


def scalar_property_count(schema: JSONSchema) -> int:
    """Count non-object property leaves recursively."""

    count = 0
    for value in schema.get("properties", {}).values():
        if isinstance(value, dict) and value.get("type") == "object":
            count += scalar_property_count(value)
        else:
            count += 1
    return count


def generate_schema(schema_id: str) -> JSONSchema:
    """Generate exactly one profile described by the frozen protocol."""

    definitions = load_protocol()["schema_definitions"]
    if schema_id not in definitions:
        raise KeyError(f"unknown schema profile: {schema_id}")
    definition = definitions[schema_id]
    depth = int(definition["depth"])
    property_count = int(definition["property_count"])
    if property_count % depth:
        raise ValueError(
            f"{schema_id} property count {property_count} is not divisible "
            f"by depth {depth}"
        )
    schema = _nested_schema(
        depth=depth,
        leaves_per_level=property_count // depth,
    )
    actual_depth = schema_depth(schema)
    actual_properties = scalar_property_count(schema)
    if (actual_depth, actual_properties) != (depth, property_count):
        raise AssertionError(
            f"{schema_id} generated ({actual_depth}, {actual_properties}), "
            f"expected ({depth}, {property_count})"
        )
    return schema


def schema_digest(schema_id: str) -> str:
    """Return the canonical SHA-256 digest of a generated schema."""

    return sha256_bytes(canonical_json_bytes(generate_schema(schema_id)))


def get_schema_profile(schema_id: str) -> SchemaProfile:
    schema = generate_schema(schema_id)
    return SchemaProfile(
        schema_id=schema_id,
        schema=schema,
        depth=schema_depth(schema),
        property_count=scalar_property_count(schema),
        digest=sha256_bytes(canonical_json_bytes(schema)),
    )


def all_schema_profiles() -> tuple[SchemaProfile, ...]:
    return tuple(
        get_schema_profile(schema_id)
        for schema_id in load_protocol()["schema_definitions"]
    )


def all_schema_digests() -> dict[str, str]:
    return {
        profile.schema_id: profile.digest for profile in all_schema_profiles()
    }
