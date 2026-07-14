from __future__ import annotations

from apu_characterization.mcp_tax.report import render_report


def _cell(
    *,
    transport: str,
    implementation: str,
    mode: str,
    dispatch: float,
    serial: float,
    combined: float,
    setup: float = 0.0,
    wait: float = 0.0,
) -> dict:
    return {
        "cell_id": f"{transport}-{implementation}-{mode}",
        "coordinates": {
            "transport": transport,
            "payload_bytes": 256,
            "schema_profile": "flat_5",
            "tool_count": 1,
            "implementation": implementation,
            "mode": mode,
        },
        "combined_cpu_ns_per_message": {"median": combined},
        "steady_combined_cpu_ns_per_message": {
            "median": max(0.0, combined - setup / 20.0)
        },
        "wait_ns_per_message": {"median": wait},
        "session_setup_cpu_ns": {"median": setup},
        "category_cpu_ns_per_message": {
            "MSG_DISPATCH": {"median": dispatch},
            "MSG_FRAME": {"median": 30_000.0},
            "MSG_SERIAL": {"median": serial},
            "MSG_TRANSPORT_CPU": {"median": 200_000.0},
            "MSG_VALIDATE": {"median": 10_000.0},
            "SESSION_SETUP": {"median": setup / 20.0},
        },
    }


def test_report_labels_external_numbers_and_claim_limits() -> None:
    aggregate = {
        "protocol_version": "mcp_tax_v1.5",
        "result_validity": "debug_only",
        "run_count": 1,
        "cell_count": 0,
        "cells": [],
        "audit": {"pass": False, "gates": {}},
        "payload_exponents": [],
        "setup_tool_count_curve": [],
        "sdk_raw_delta": [],
    }
    report = render_report(aggregate)
    assert "DO NOT CITE" in report
    assert "12.4 ms/message" in report
    assert "23.7 ms/message" in report
    assert "8.3 ms/message" in report
    assert "External anchors — not measured by MCP-01" in report
    assert "3.9–7.0" in report
    assert "calls_per_turn * measured_MCP_tax_per_call" in report
    assert "append-only" in report.lower()


def test_category_table_uses_raw_throttle_population_not_sdk() -> None:
    """SDK SERIAL-heavy booking must not pull the steady-state median down/up."""
    cells = [
        _cell(
            transport="stdio",
            implementation="raw_jsonrpc",
            mode="throttle",
            dispatch=1_500_000.0,
            serial=100_000.0,
            combined=2_000_000.0,
        ),
        _cell(
            transport="stdio",
            implementation="reference_sdk",
            mode="throttle",
            dispatch=7_000.0,
            serial=3_000_000.0,
            combined=40_000_000.0,
            setup=700_000_000.0,
        ),
    ]
    report = render_report(
        {
            "protocol_version": "mcp_tax_v1.5",
            "result_validity": "debug_only",
            "run_count": 2,
            "cell_count": 2,
            "cells": cells,
            "audit": {"pass": False, "gates": {}},
            "payload_exponents": [],
            "setup_tool_count_curve": [],
            "sdk_raw_delta": [
                {
                    "transport": "stdio",
                    "mode": "throttle",
                    "sdk_minus_raw_steady_cpu_ns_per_message": 1000.0,
                    "sdk_over_raw_steady_ratio": 1.1,
                    "sdk_minus_raw_setup_cpu_ns": 700_000_000.0,
                }
            ],
            "debug_smoke": {
                "throttle_stripped_tax": [
                    {
                        "transport": "stdio",
                        "implementation": "raw_jsonrpc",
                        "throttle_minus_stripped_ns_per_message": -1000.0,
                    }
                ]
            },
        }
    )
    assert "raw_jsonrpc × throttle × tool_count=1" in report
    assert "MSG_DISPATCH | 1500.000" in report
    assert "MSG_SERIAL | 100.000" in report
    assert "MSG_DISPATCH mechanism note" in report
    assert "Honest headline" in report
    assert "client_call_inter_region_gaps" in report
    assert "Connection: close" in report or "connection-per-message" in report.lower() or "connection pattern" in report.lower()
    assert "DFA pre-registration" in report or "pathological_large" in report
    assert "Bare-metal validation flags" in report
    assert "floor-class" in report.lower() or "diffuse residue" in report.lower()
    assert "SESSION_SETUP excluded" in report
    assert "Steady Δ µs/msg" in report
    assert "Setup Δ µs/cell" in report


def test_provenance_table_renders_dispatch_and_transport() -> None:
    cell = _cell(
        transport="http_sse_tls_on",
        implementation="raw_jsonrpc",
        mode="throttle",
        dispatch=1_600_000.0,
        serial=100_000.0,
        combined=3_000_000.0,
    )
    cell["provenance_cpu_ns_per_message"] = {
        "MSG_DISPATCH": {
            "client_call_inter_region_gaps": {"median": 1_595_000.0},
            "client_result_dispatch": {"median": 3_000.0},
            "measured": {"median": 4_000.0},
        },
        "MSG_TRANSPORT_CPU": {
            "transport_tls_handshake": {"median": 950_000.0},
            "transport_connect": {"median": 50_000.0},
            "transport_write": {"median": 200_000.0},
            "transport_read": {"median": 150_000.0},
            "transport_syscall_return": {"median": 10_000.0},
        },
    }
    report = render_report(
        {
            "protocol_version": "mcp_tax_v1.5",
            "result_validity": "debug_only",
            "run_count": 1,
            "cell_count": 1,
            "cells": [cell],
            "audit": {"pass": False, "gates": {}},
            "payload_exponents": [],
            "setup_tool_count_curve": [],
            "sdk_raw_delta": [],
        }
    )
    assert "Provenance breakdown" in report
    assert "client_call_inter_region_gaps" in report
    assert "transport_tls_handshake" in report
    assert "v10 named subslices" in report
    assert "http_sse_tls_on" in report
    assert "950.000" in report
    assert "1595.000" in report


def test_observer_bracket_excludes_session_setup() -> None:
    cells = [
        _cell(
            transport="stdio",
            implementation="raw_jsonrpc",
            mode="stripped",
            dispatch=0.0,
            serial=0.0,
            combined=2_000_000.0,
            setup=0.0,
        ),
        _cell(
            transport="stdio",
            implementation="raw_jsonrpc",
            mode="throttle",
            dispatch=1_500_000.0,
            serial=100_000.0,
            combined=37_000_000.0,
            setup=700_000_000.0,
        ),
    ]
    report = render_report(
        {
            "protocol_version": "mcp_tax_v1.5",
            "result_validity": "debug_only",
            "run_count": 2,
            "cell_count": 2,
            "cells": cells,
            "audit": {"pass": False, "gates": {}},
            "payload_exponents": [],
            "setup_tool_count_curve": [],
            "sdk_raw_delta": [],
        }
    )
    assert "SESSION_SETUP excluded" in report
    assert "stripped 2000.000 µs/message" in report
    assert "throttle 2000.000 µs/message" in report
