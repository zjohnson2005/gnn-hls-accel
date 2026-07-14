from __future__ import annotations

from apu_characterization.mcp_tax.analyze import (
    cell_steady_cpu_ns_per_message,
    quantile,
    reduce_records,
    summarize,
)
from apu_characterization.mcp_tax.audit import CATEGORIES


def _record(seed: int) -> dict:
    coordinates = {
        "transport": "stdio",
        "payload_bytes": 4096,
        "schema_profile": "nested_depth_4",
        "tool_count": 10,
        "implementation": "raw_jsonrpc",
        "mode": "throttle",
    }
    setup_total = (seed + 1) * 50
    combined_per_message = (seed + 1) * 10
    steady_per_message = combined_per_message - setup_total / 10.0
    return {
        "run_dir": f"/run/{seed}",
        "cell_id": "curve-cell",
        "seed": seed,
        "transport": "stdio",
        "coordinates": coordinates,
        "manifest": {"seed": seed},
        "result_validity": "protocol_microbenchmark",
        "combined_cpu_ns": (seed + 1) * 100,
        "combined_cpu_ns_per_message": combined_per_message,
        "steady_combined_cpu_ns_per_message": steady_per_message,
        "combined_wall_ns_per_message": (seed + 1) * 20,
        "wait_ns_per_message": (seed + 1) * 5,
        "session_setup_cpu_ns": setup_total,
        "category_cpu_ns_per_message": {
            category: (setup_total / 10.0 if category == "SESSION_SETUP" else 0)
            for category in CATEGORIES
        },
        "category_wall_ns_per_message": {category: 0 for category in CATEGORIES},
        "audit": {
            "pass": True,
            "gates": {
                name: {"pass": True, "errors": []} for name in ("G1", "G2", "G3")
            },
        },
    }


def test_quantiles_and_deterministic_reduction() -> None:
    assert quantile([1, 2, 3, 4, 5], 0.5) == 3
    assert summarize([5, 1, 4, 2, 3]) == {
        "n": 5,
        "median": 3.0,
        "q1": 2.0,
        "q3": 4.0,
        "iqr": 2.0,
    }
    records = [_record(seed) for seed in reversed(range(5))]
    aggregate = reduce_records(records)
    assert aggregate["cells"][0]["seeds"] == [0, 1, 2, 3, 4]
    assert aggregate["cells"][0]["combined_cpu_ns_per_message"]["median"] == 30
    assert aggregate["cells"][0]["steady_combined_cpu_ns_per_message"]["median"] == 15.0
    assert aggregate["audit"]["pass"]
    assert aggregate["result_validity"] == "protocol_microbenchmark"


def test_sdk_raw_delta_splits_setup_and_steady() -> None:
    raw = {
        "cell_id": "raw",
        "coordinates": {
            "transport": "stdio",
            "payload_bytes": 256,
            "schema_profile": "flat_5",
            "tool_count": 1,
            "implementation": "raw_jsonrpc",
            "mode": "throttle",
        },
        "combined_cpu_ns_per_message": {"median": 2_000_000.0},
        "steady_combined_cpu_ns_per_message": {"median": 1_800_000.0},
        "session_setup_cpu_ns": {"median": 4_000_000.0},
        "category_cpu_ns_per_message": {c: {"median": 0.0} for c in CATEGORIES},
        "category_wall_ns_per_message": {c: {"median": 0.0} for c in CATEGORIES},
        "combined_wall_ns_per_message": {"median": 0.0},
        "wait_ns_per_message": {"median": 0.0},
        "n": 1,
        "seeds": [0],
        "all_runs_retained": True,
        "audit_pass_count": 1,
        "retained_runs": [],
    }
    sdk = {
        **raw,
        "cell_id": "sdk",
        "coordinates": {**raw["coordinates"], "implementation": "reference_sdk"},
        "combined_cpu_ns_per_message": {"median": 40_000_000.0},
        "steady_combined_cpu_ns_per_message": {"median": 2_000_000.0},
        "session_setup_cpu_ns": {"median": 760_000_000.0},
    }
    from apu_characterization.mcp_tax.analyze import _sdk_raw_delta

    deltas = _sdk_raw_delta([raw, sdk])
    assert len(deltas) == 1
    assert deltas[0]["sdk_minus_raw_steady_cpu_ns_per_message"] == 200_000.0
    assert deltas[0]["sdk_minus_raw_setup_cpu_ns"] == 756_000_000.0
    assert "sdk_minus_raw_cpu_ns_per_message" not in deltas[0]
    assert cell_steady_cpu_ns_per_message(sdk) == 2_000_000.0
