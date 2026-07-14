from __future__ import annotations

from apu_characterization.mcp_tax.accum import LedgerTotals, McpMessageAccumulator, ScopeObservation
from apu_characterization.mcp_tax.audit import audit_run


def _endpoint_dict(
    *,
    message_id: str = "1",
    categories: dict[str, int],
    boundary_ns: int,
    role: str = "client",
    provenance: str | dict[str, str] = "measured",
) -> dict:
    total = sum(categories.values())
    acc = McpMessageAccumulator(role, mode="throttle")
    for name, cpu_ns in categories.items():
        label = provenance[name] if isinstance(provenance, dict) else provenance
        acc.by_key[(name, message_id, role)] = LedgerTotals()
        acc.by_key[(name, message_id, role)].add(cpu_ns, provenance=label)
    acc.record_message_diagnostic(message_id, "client_call_boundary_ns", boundary_ns)
    acc.record_message_diagnostic(message_id, "client_nested_cpu_ns", total)
    acc.record_canonical_hash("a" * 64)
    acc.messages[message_id] = ScopeObservation(
        start_wall_ns=0,
        end_wall_ns=total,
        process_cpu_ns=total,
        wall_ns=total,
    )
    acc.endpoint_observation = ScopeObservation(
        start_wall_ns=0,
        end_wall_ns=total,
        process_cpu_ns=total,
        wall_ns=total,
    )
    payload = acc.to_dict()
    payload["categories"] = [
        {
            "category": name,
            "message_id": message_id,
            "process_role": role,
            "totals": totals.as_dict(),
        }
        for (name, mid, _), totals in acc.by_key.items()
    ]
    return payload


def _raw_plan() -> dict:
    return {
        "coordinates": {
            "implementation": "raw_jsonrpc",
            "transport": "stdio",
            "mode": "throttle",
        },
        "request_hashes": ["a" * 64],
        "warmup_messages": 0,
    }


def test_g6_passes_raw_client_shape() -> None:
    client = _endpoint_dict(
        categories={
            "MSG_SERIAL": 1000,
            "MSG_FRAME": 2000,
            "MSG_TRANSPORT_CPU": 3000,
        },
        boundary_ns=7000,
        provenance={
            "MSG_SERIAL": "json_encode",
            "MSG_FRAME": "stdio_frame",
            "MSG_TRANSPORT_CPU": "transport_syscall",
        },
    )
    server = _endpoint_dict(
        categories={"MSG_SERIAL": 5000, "MSG_DISPATCH": 1000},
        boundary_ns=6000,
        role="server",
        provenance="server_method_lookup",
    )
    result = audit_run(client, server, plan=_raw_plan())
    assert result["gates"]["G6"]["pass"]


def test_g6_fails_lump_detector() -> None:
    client = _endpoint_dict(
        categories={"MSG_TRANSPORT_CPU": 9900, "MSG_SERIAL": 50, "MSG_FRAME": 50},
        boundary_ns=10000,
        provenance="transport_syscall",
    )
    result = audit_run(client, client, plan=_raw_plan())
    assert not result["gates"]["G6"]["pass"]
    assert any("one category at" in err for err in result["gates"]["G6"]["errors"])


def test_g6_fails_opaque_dominant_provenance() -> None:
    """Dominant category booked only as generic 'measured' → presumptive gap-fill."""
    client = _endpoint_dict(
        categories={
            "MSG_DISPATCH": 7000,
            "MSG_SERIAL": 1500,
            "MSG_FRAME": 1500,
        },
        boundary_ns=10000,
        provenance="measured",
    )
    result = audit_run(client, client, plan=_raw_plan())
    assert not result["gates"]["G6"]["pass"]
    assert any("presumptive gap-fill" in err for err in result["gates"]["G6"]["errors"])


def test_g6_passes_named_gap_provenance() -> None:
    """Named inter-region gaps satisfy coverage even when DISPATCH dominates."""
    client = _endpoint_dict(
        categories={
            "MSG_DISPATCH": 7000,
            "MSG_SERIAL": 1500,
            "MSG_FRAME": 1500,
        },
        boundary_ns=10000,
        provenance={
            "MSG_DISPATCH": "client_call_inter_region_gaps",
            "MSG_SERIAL": "json_encode",
            "MSG_FRAME": "stdio_frame",
        },
    )
    result = audit_run(client, client, plan=_raw_plan())
    assert result["gates"]["G6"]["pass"]
