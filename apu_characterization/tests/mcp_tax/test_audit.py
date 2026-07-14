from __future__ import annotations

from apu_characterization.mcp_tax.accum import McpMessageAccumulator, ScopeObservation
from apu_characterization.mcp_tax.audit import audit_aggregate, audit_run
from apu_characterization.mcp_tax.taxonomy import McpCategory


def _endpoint(residual: int = 0) -> dict:
    total = 100_000_000
    return {
        "process_cpu_ns": total,
        "wall_ns": total,
        "categories": {
            "MSG_SERIAL": {"cpu_ns": total - residual, "wall_ns": total},
            "RESIDUAL": {"cpu_ns": residual, "wall_ns": 0},
        },
        "request_hashes": ["a", "b"],
    }


def test_g1_g2_g3_pass_and_hash_failure() -> None:
    result = audit_run(
        _endpoint(),
        _endpoint(),
        plan={"request_hashes": ["a", "b"]},
    )
    assert result["pass"]
    bad = _endpoint()
    bad["request_hashes"] = ["b", "a"]
    result = audit_run(_endpoint(), bad, plan={"request_hashes": ["a", "b"]})
    assert not result["gates"]["G2"]["pass"]


def test_g1_uses_per_endpoint_and_combined_15_percent_plus_slack() -> None:
    # At 100 ms CPU the threshold is 15 ms + max(15.625 ms, 5 ms).
    assert audit_run(_endpoint(30_000_000), _endpoint())["gates"]["G1"]["pass"]
    assert not audit_run(_endpoint(31_000_000), _endpoint())["gates"]["G1"]["pass"]


def test_audit_normalizes_endpoint_observation_and_wait_ledger() -> None:
    accumulator = McpMessageAccumulator("client")
    accumulator.endpoint_observation = ScopeObservation(0, 1_000, 100, 1_000)
    accumulator.book(
        McpCategory.MSG_SERIAL, 80, message_id="m1", wall_ns=80
    )
    accumulator.book_wait("transport_blocked", 800, message_id="m1")
    accumulator.book(
        McpCategory.RESIDUAL, 20, message_id="m1", wall_ns=120
    )
    accumulator.record_canonical_hash("a" * 64)
    endpoint = accumulator.to_dict()
    result = audit_run(
        endpoint,
        {**endpoint, "process_role": "server"},
        plan={"request_hashes": ["a" * 64]},
    )
    assert result["pass"]
    assert result["endpoints"]["client"]["wait_ns"] == 800


def test_g5_retains_exactly_five_and_flags_pathological_spread() -> None:
    runs = []
    for seed, cpu in enumerate((1, 1, 1, 1, 10)):
        runs.append(
            {
                "cell_id": "cell",
                "seed": seed,
                "coordinates": {
                    "transport": "stdio",
                    "payload_bytes": 256,
                    "schema_profile": "flat_5",
                    "tool_count": 10,
                    "implementation": "raw_jsonrpc",
                    "mode": "throttle",
                },
                "aggregate": {"combined_cpu_ns": cpu},
            }
        )
    audit = audit_aggregate(runs)
    assert audit["gates"]["G5"]["pass"]
    assert audit["spread_flags"][0]["pathological"]
    assert not audit_aggregate(runs[:-1])["gates"]["G5"]["pass"]
