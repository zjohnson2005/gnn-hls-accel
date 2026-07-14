from __future__ import annotations

from pathlib import Path

import pytest

from apu_characterization.mcp_tax.contracts import (
    PROTOCOL_VERSION,
    CellCoordinates,
    CellPlan,
    MessageStep,
    enumerate_matrix,
)
from apu_characterization.mcp_tax.runner import McpTaxRunner, is_complete, run_directory


def _plan() -> CellPlan:
    coordinates = CellCoordinates(
        transport="stdio",
        payload_bytes=256,
        schema_profile="flat_5",
        tool_count=1,
        implementation="raw_jsonrpc",
        mode="throttle",
    )
    return CellPlan(
        protocol_version=PROTOCOL_VERSION,
        seed=0,
        coordinates=coordinates,
        warmup_messages=1,
        measured_messages=1,
        steps=(
            MessageStep(0, "tools/call", "noop", "flat_5", 256),
        ),
    )


def test_runner_layout_completion_and_resume(tmp_path: Path) -> None:
    calls = []

    def execute(plan: CellPlan, run_dir: Path) -> dict:
        calls.append(run_dir)
        endpoint = {
            "process_cpu_ns": 1,
            "wall_ns": 1,
            "categories": {"MSG_SERIAL": {"cpu_ns": 1, "wall_ns": 1}},
            "request_hashes": plan.request_hashes(),
        }
        return {
            "client": endpoint,
            "server": endpoint,
            "manifest": {"protocol_version": PROTOCOL_VERSION},
        }

    root = tmp_path / "runs"
    runner = McpTaxRunner(run_root=root, execute=execute)
    first = runner.run([_plan()])
    expected = run_directory(root, _plan().coordinates, 0)
    assert first[0].run_dir == expected
    assert (expected / "client" / "result.json").is_file()
    assert (expected / "server" / "result.json").is_file()
    assert is_complete(expected)
    second = runner.run([_plan()])
    assert second[0].status == "skipped_complete"
    assert len(calls) == 1
    with pytest.raises(FileExistsError):
        runner.run_one(_plan(), resume=False)


def test_frozen_matrix_has_120_or_160_cells() -> None:
    assert len(enumerate_matrix()) == 120
    assert len(enumerate_matrix(include_http_stream=True)) == 160
