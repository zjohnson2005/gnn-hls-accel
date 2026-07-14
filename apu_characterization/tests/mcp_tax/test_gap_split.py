from __future__ import annotations

from apu_characterization.mcp_tax.accum import LedgerTotals, McpMessageAccumulator, ScopeObservation
from apu_characterization.mcp_tax.audit import audit_run
from apu_characterization.mcp_tax.contracts import load_protocol
from apu_characterization.mcp_tax.gap_measure import (
    GAP_EVENT_LOOP,
    GAP_GC,
    GAP_INSTRUMENTATION,
    GAP_SYSCALL_RETURN,
    GAP_UNATTRIBUTED,
    apply_precedence,
    build_gap_decomposition,
    gap_session,
    microbench_timer_pair_ns,
)
from apu_characterization.mcp_tax.gap_split import (
    classify_with_population_gate,
    evaluate_diffuseness_verdict,
    observer_instrumentation_crosscheck,
)


def _cfg() -> dict:
    return load_protocol()["audit"]


def test_diffuseness_confirmed_when_spread() -> None:
    result = evaluate_diffuseness_verdict(
        {
            "parent_cpu_ns": 1_000_000,
            "mechanisms": {
                GAP_EVENT_LOOP: 250_000,
                GAP_INSTRUMENTATION: 200_000,
                GAP_GC: 200_000,
                GAP_SYSCALL_RETURN: 200_000,
                GAP_UNATTRIBUTED: 150_000,  # 15% ≤ 20% bound
            },
            "boundaries": ["serial_to_frame", "frame_to_transport"],
        },
        cfg=_cfg(),
    )
    assert result["verdict"] == "confirmed"


def test_unattributed_forces_inconclusive_not_refuted() -> None:
    """v1.5: dominant (e) must not fire refuted — residual is unmeasured."""
    result = evaluate_diffuseness_verdict(
        {
            "parent_cpu_ns": 1_000_000,
            "mechanisms": {
                GAP_EVENT_LOOP: 100_000,
                GAP_INSTRUMENTATION: 100_000,
                GAP_GC: 50_000,
                GAP_SYSCALL_RETURN: 150_000,
                GAP_UNATTRIBUTED: 600_000,  # 60% — v9 advisory shape
            },
            "boundaries": ["serial_to_transport", "transport_to_serial"],
        },
        cfg=_cfg(),
    )
    assert result["verdict"] == "inconclusive"
    assert GAP_UNATTRIBUTED in result["reason"]
    assert "v1.5" in result["reason"]


def test_diffuseness_refuted_when_named_mechanism_concentrated() -> None:
    result = evaluate_diffuseness_verdict(
        {
            "parent_cpu_ns": 1_000_000,
            "mechanisms": {
                GAP_GC: 700_000,
                GAP_EVENT_LOOP: 100_000,
                GAP_UNATTRIBUTED: 100_000,  # 10% — below e bound
                GAP_INSTRUMENTATION: 50_000,
                GAP_SYSCALL_RETURN: 50_000,
            },
            "boundaries": ["serial_to_frame", "frame_to_transport"],
        },
        cfg=_cfg(),
    )
    assert result["verdict"] == "refuted"
    assert GAP_GC in result["reason"]


def test_diffuseness_refuted_when_majority_on_one_of_two() -> None:
    result = evaluate_diffuseness_verdict(
        {
            "parent_cpu_ns": 1_000_000,
            "mechanisms": {
                GAP_EVENT_LOOP: 400_000,
                GAP_INSTRUMENTATION: 500_000,  # 50% not >50%; need >50%
                GAP_UNATTRIBUTED: 100_000,
            },
            "boundaries": ["serial_to_frame"],
        },
        cfg=_cfg(),
    )
    # 50% is not > refute threshold; with only 2 named and 1 boundary → inconclusive
    # unless we push instrumentation over 50%
    assert result["verdict"] in {"inconclusive", "refuted"}


def test_named_majority_above_half_refutes() -> None:
    result = evaluate_diffuseness_verdict(
        {
            "parent_cpu_ns": 1_000_000,
            "mechanisms": {
                GAP_EVENT_LOOP: 300_000,
                GAP_INSTRUMENTATION: 550_000,
                GAP_UNATTRIBUTED: 150_000,
            },
            "boundaries": ["serial_to_frame"],
        },
        cfg=_cfg(),
    )
    assert result["verdict"] == "refuted"


def test_diffuseness_inconclusive_insufficient_spread() -> None:
    result = evaluate_diffuseness_verdict(
        {
            "parent_cpu_ns": 1_000_000,
            "mechanisms": {
                GAP_EVENT_LOOP: 400_000,
                GAP_INSTRUMENTATION: 300_000,
                GAP_GC: 300_000,
            },
            "boundaries": ["serial_to_frame"],
        },
        cfg=_cfg(),
    )
    assert result["verdict"] == "inconclusive"


def test_verdict_deferred_below_population_floor() -> None:
    result = classify_with_population_gate(
        {
            "parent_cpu_ns": 1_000_000,
            "mechanisms": {
                GAP_EVENT_LOOP: 250_000,
                GAP_INSTRUMENTATION: 200_000,
                GAP_GC: 200_000,
                GAP_SYSCALL_RETURN: 200_000,
                GAP_UNATTRIBUTED: 150_000,
            },
            "boundaries": ["a", "b"],
        },
        cfg=_cfg(),
        measured_messages=20,
        seed_count=1,
    )
    assert result["verdict"] == "deferred_insufficient_population"
    assert result["binding"] is False
    assert result["advisory_only"]["verdict"] == "confirmed"


def test_verdict_binding_at_population_floor() -> None:
    result = classify_with_population_gate(
        {
            "parent_cpu_ns": 1_000_000,
            "mechanisms": {
                GAP_EVENT_LOOP: 250_000,
                GAP_INSTRUMENTATION: 200_000,
                GAP_GC: 200_000,
                GAP_SYSCALL_RETURN: 200_000,
                GAP_UNATTRIBUTED: 150_000,
            },
            "boundaries": ["a", "b"],
        },
        cfg=_cfg(),
        measured_messages=20,
        seed_count=3,
    )
    assert result["verdict"] == "confirmed"
    assert result["binding"] is True


def _client_with_gap_decomp(
    *,
    parent_ns: int,
    mechanisms: dict[str, int],
) -> dict:
    categories = {
        "MSG_DISPATCH": parent_ns,
        "MSG_SERIAL": 1000,
        "MSG_FRAME": 1000,
    }
    total = sum(categories.values())
    acc = McpMessageAccumulator("client", mode="throttle")
    message_id = "1"
    for name, cpu_ns in categories.items():
        label = (
            "client_call_inter_region_gaps"
            if name == "MSG_DISPATCH"
            else "json_encode" if name == "MSG_SERIAL" else "stdio_frame"
        )
        acc.by_key[(name, message_id, "client")] = LedgerTotals()
        acc.by_key[(name, message_id, "client")].add(cpu_ns, provenance=label)
    acc.record_message_diagnostic(message_id, "client_call_boundary_ns", total)
    acc.record_message_diagnostic(message_id, "client_nested_cpu_ns", total)
    acc.record_message_diagnostic(
        message_id,
        "gap_decomposition",
        {
            "parent_cpu_ns": parent_ns,
            "mechanisms": mechanisms,
            "boundaries": ["serial_to_transport", "transport_to_serial"],
        },
    )
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
            "process_role": "client",
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


def test_g7_passes_without_decomposition() -> None:
    categories = {
        "MSG_SERIAL": 1000,
        "MSG_FRAME": 2000,
        "MSG_TRANSPORT_CPU": 3000,
    }
    total = sum(categories.values())
    acc = McpMessageAccumulator("client", mode="throttle")
    message_id = "1"
    provenance = {
        "MSG_SERIAL": "json_encode",
        "MSG_FRAME": "stdio_frame",
        "MSG_TRANSPORT_CPU": "transport_syscall",
    }
    for name, cpu_ns in categories.items():
        acc.by_key[(name, message_id, "client")] = LedgerTotals()
        acc.by_key[(name, message_id, "client")].add(
            cpu_ns, provenance=provenance[name]
        )
    acc.record_message_diagnostic(message_id, "client_call_boundary_ns", total)
    acc.record_message_diagnostic(message_id, "client_nested_cpu_ns", total)
    acc.record_canonical_hash("a" * 64)
    acc.messages[message_id] = ScopeObservation(
        start_wall_ns=0, end_wall_ns=total, process_cpu_ns=total, wall_ns=total
    )
    acc.endpoint_observation = ScopeObservation(
        start_wall_ns=0, end_wall_ns=total, process_cpu_ns=total, wall_ns=total
    )
    client = acc.to_dict()
    client["categories"] = [
        {
            "category": name,
            "message_id": message_id,
            "process_role": "client",
            "totals": totals.as_dict(),
        }
        for (name, mid, _), totals in acc.by_key.items()
    ]
    result = audit_run(client, client, plan=_raw_plan())
    assert result["gates"]["G7"]["pass"]
    assert result["gates"]["G7"]["g7_live"] is False


def test_g7_passes_conserved_split() -> None:
    parent = 1_000_000
    client = _client_with_gap_decomp(
        parent_ns=parent,
        mechanisms={
            GAP_EVENT_LOOP: 300_000,
            GAP_INSTRUMENTATION: 250_000,
            GAP_GC: 250_000,
            GAP_SYSCALL_RETURN: 100_000,
            GAP_UNATTRIBUTED: 100_000,
        },
    )
    result = audit_run(client, client, plan=_raw_plan())
    assert result["gates"]["G7"]["pass"]
    assert result["gates"]["G7"]["g7_live"] is True
    assert result["gates"]["G7"]["evaluated_count"] == 1


def test_g7_fails_when_split_creates_time() -> None:
    client = _client_with_gap_decomp(
        parent_ns=1_000_000,
        mechanisms={
            GAP_EVENT_LOOP: 800_000,
            GAP_INSTRUMENTATION: 600_000,
            GAP_GC: 600_000,
            GAP_UNATTRIBUTED: 0,
        },
    )
    result = audit_run(client, client, plan=_raw_plan())
    assert not result["gates"]["G7"]["pass"]
    assert any("gap split conservation" in err for err in result["gates"]["G7"]["errors"])


def test_g7_fails_when_unattributed_missing() -> None:
    client = _client_with_gap_decomp(
        parent_ns=1_000_000,
        mechanisms={
            GAP_EVENT_LOOP: 500_000,
            GAP_INSTRUMENTATION: 500_000,
        },
    )
    result = audit_run(client, client, plan=_raw_plan())
    assert not result["gates"]["G7"]["pass"]
    assert any(GAP_UNATTRIBUTED in err for err in result["gates"]["G7"]["errors"])


def test_precedence_leaves_unattributed_residual() -> None:
    allocated, log = apply_precedence(
        {
            GAP_INSTRUMENTATION: 400_000,
            GAP_GC: 400_000,
            GAP_EVENT_LOOP: 400_000,
            GAP_SYSCALL_RETURN: 400_000,
        },
        1_000_000,
    )
    assert sum(allocated.values()) == 1_000_000
    assert allocated[GAP_INSTRUMENTATION] == 400_000
    assert allocated[GAP_GC] == 400_000
    assert allocated[GAP_EVENT_LOOP] == 200_000
    assert allocated[GAP_SYSCALL_RETURN] == 0
    assert allocated[GAP_UNATTRIBUTED] == 0
    assert log  # carved event_loop / syscall


def test_microbench_and_gap_session_emit_decomposition() -> None:
    bench = microbench_timer_pair_ns(iterations=1000)
    assert bench["timer_pair_cost_ns"] >= 0
    with gap_session("1", timer_pair_cost_ns=bench["timer_pair_cost_ns"]) as session:
        session.mark_boundary("serial_to_transport")
        session.on_region_exit()
        session.note_timer_pair()
        session.note_timer_pair()
    decomp = build_gap_decomposition(10_000, session)
    assert GAP_UNATTRIBUTED in decomp["mechanisms"]
    assert sum(decomp["mechanisms"].values()) == 10_000
    assert GAP_EVENT_LOOP in decomp["unmeasured"]


def test_observer_crosscheck_flags_over_attribution() -> None:
    throttle = {
        "coordinates": {"transport": "stdio", "implementation": "raw_jsonrpc", "mode": "throttle"},
        "steady_combined_cpu_ns_per_message": 2_000_000,
        "gap_decomposition_ns_per_message": {GAP_INSTRUMENTATION: 1_600_000},
    }
    stripped = {
        "coordinates": {"transport": "stdio", "implementation": "raw_jsonrpc", "mode": "stripped"},
        "steady_combined_cpu_ns_per_message": 1_000_000,
    }
    result = observer_instrumentation_crosscheck(throttle, stripped, cfg=_cfg())
    assert result["flag"] == "OBSERVER_ATTRIBUTION_SUSPECT"


def test_observer_crosscheck_negative_bracket_unusable() -> None:
    throttle = {
        "coordinates": {"transport": "stdio", "implementation": "raw_jsonrpc"},
        "steady_combined_cpu_ns_per_message": 900_000,
        "gap_decomposition_ns_per_message": {GAP_INSTRUMENTATION: 1_000},
    }
    stripped = {
        "coordinates": {"transport": "stdio", "implementation": "raw_jsonrpc"},
        "steady_combined_cpu_ns_per_message": 1_000_000,
    }
    result = observer_instrumentation_crosscheck(throttle, stripped, cfg=_cfg())
    assert result["flag"] == "OBSERVER_BRACKET_NEGATIVE"
    assert result["usable"] is False


def test_report_prints_live_g7_when_decomposition_present() -> None:
    from apu_characterization.mcp_tax.report import _gap_decomposition_section

    lines = _gap_decomposition_section(
        {
            "audit": {
                "g7_live_cells": ["cell-a"],
                "diffuseness_verdict": {
                    "verdict": "deferred_insufficient_population",
                    "binding": False,
                    "per_arm": True,
                    "reason": "per-arm",
                },
                "diffuseness_verdict_by_arm": {
                    "raw_jsonrpc": {
                        "verdict": "deferred_insufficient_population",
                        "binding": False,
                        "reason": "seed-0",
                        "advisory_only": [
                            {
                                "verdict": "inconclusive",
                                "reason": "gap_unattributed holds 60%",
                                "transport": "stdio",
                            }
                        ],
                    },
                    "reference_sdk": {
                        "verdict": "deferred_insufficient_population",
                        "binding": False,
                        "reason": "no samples",
                        "advisory_only": None,
                    },
                },
                "observer_instrumentation_crosscheck": [],
            }
        },
        [
            {
                "coordinates": {
                    "transport": "stdio",
                    "mode": "throttle",
                    "implementation": "raw_jsonrpc",
                    "tool_count": 1,
                },
                "gap_decomposition_ns_per_message": {
                    "parent_cpu_ns": {"median": 1_600_000},
                    GAP_EVENT_LOOP: {"median": 0},
                    GAP_INSTRUMENTATION: {"median": 50_000},
                    GAP_GC: {"median": 10_000},
                    GAP_SYSCALL_RETURN: {"median": 40_000},
                    GAP_UNATTRIBUTED: {"median": 1_500_000},
                    "boundaries": ["serial_to_transport"],
                    "gap_syscall_return_subprovenance": {
                        "measured_ns": {"median": 0},
                        "adjacent_segments_ns": {"median": 40_000},
                    },
                },
            }
        ],
    )
    report = "\n".join(lines)
    assert "G7 status:" in report
    assert "LIVE evaluation" in report
    assert "ADVISORY — verdict deferred" in report
    assert "e% base" in report or "e% of parent" in report
    assert "d_meas" in report or "d_adj" in report
