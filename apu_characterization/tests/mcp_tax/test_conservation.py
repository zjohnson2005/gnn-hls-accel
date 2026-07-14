from __future__ import annotations

from apu_characterization.mcp_tax.accum import (
    McpMessageAccumulator,
    ScopeObservation,
)
from apu_characterization.mcp_tax.reconcile import (
    reconcile_endpoint,
    reconcile_endpoints,
    reconcile_message,
)
from apu_characterization.mcp_tax.taxonomy import McpCategory


def _message(
    role: str, message_id: str, *, cpu_ns: int, wall_ns: int
) -> McpMessageAccumulator:
    acc = McpMessageAccumulator(role)  # type: ignore[arg-type]
    acc.set_message_observation(
        message_id, process_cpu_ns=cpu_ns, wall_ns=wall_ns
    )
    return acc


def test_per_message_category_plus_residual_conserves_exactly() -> None:
    acc = _message("client", "m1", cpu_ns=100, wall_ns=1_000)
    acc.book(McpCategory.MSG_SERIAL, 20, message_id="m1")
    acc.book(McpCategory.MSG_DISPATCH, 30, message_id="m1")

    result = reconcile_message(acc, "m1")

    assert result["categories"]["MSG_SERIAL"] == 20
    assert result["categories"]["MSG_DISPATCH"] == 30
    assert result["categories"]["RESIDUAL"] == 50
    assert result["reconstructed_cpu_ns"] == 100
    assert result["conservation_error_ns"] == 0
    assert result["conserved"] is True


def test_over_attribution_is_visible_and_fails_residual_gate() -> None:
    acc = _message("server", "m1", cpu_ns=10, wall_ns=100)
    acc.book(McpCategory.MSG_VALIDATE, 12, message_id="m1")

    result = reconcile_message(acc, "m1")

    assert result["residual_cpu_ns"] == -2
    assert result["conserved"] is True
    assert result["over_attributed"] is True
    assert result["residual_gate_pass"] is False


def test_client_and_server_are_reconciled_independently() -> None:
    client = _message("client", "m1", cpu_ns=100, wall_ns=10_000)
    server = _message("server", "m1", cpu_ns=300, wall_ns=1_000)
    client.book(McpCategory.MSG_FRAME, 90, message_id="m1")
    server.book(McpCategory.MSG_DISPATCH, 280, message_id="m1")

    result = reconcile_endpoints(client, server)

    assert result["client"]["measured_cpu_ns"] == 100
    assert result["server"]["measured_cpu_ns"] == 300
    assert result["client"]["wall_ns"] == 10_000
    assert result["server"]["wall_ns"] == 1_000
    assert "combined_cpu_ns" not in result


def test_endpoint_uses_its_own_process_clock_when_available() -> None:
    acc = _message("client", "m1", cpu_ns=50, wall_ns=100)
    acc.book(McpCategory.MSG_SERIAL, 40, message_id="m1")
    acc.endpoint_observation = ScopeObservation(
        start_wall_ns=1,
        end_wall_ns=1_001,
        process_cpu_ns=80,
        wall_ns=1_000,
    )

    result = reconcile_endpoint(acc)

    assert result["total_source"] == "endpoint_process_clock"
    assert result["measured_cpu_ns"] == 80
    assert result["residual_cpu_ns"] == 40
    assert result["messages"]["m1"]["residual_cpu_ns"] == 10
