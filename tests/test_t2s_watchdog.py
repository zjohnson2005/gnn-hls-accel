"""Fixture tests for the T2S APU watchdog launch, cell, and evidence rules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.seal_c2_ttft import seal_session  # noqa: E402
from tools.t2s_queue_watchdog import (  # noqa: E402
    evidence_lines,
    foreign_workers,
    last_entry,
    launch_refusal,
    mark_overlapping_cells,
    seal_exclusion_reason,
)

FIXTURES = ROOT / "tests" / "fixtures" / "t2s_watchdog"
LAUNCHER = ROOT / "tools" / "launch_t2s_boot1.ps1"


def test_launch_accepts_empty_flag_fixture_with_no_workers() -> None:
    text = (FIXTURES / "clean.jsonl").read_text(encoding="utf-8")
    assert last_entry(text) is not None
    assert last_entry(text)["action"] == "empty_flag"
    assert launch_refusal(text, []) is None


def test_launch_refuses_when_last_fixture_line_is_not_empty_flag() -> None:
    text = (FIXTURES / "last_not_empty.jsonl").read_text(encoding="utf-8")
    reason = launch_refusal(text, [])
    assert reason is not None
    assert "empty_flag" in reason
    assert "queue_nonempty" in reason


def test_launch_refuses_when_python_or_llama_server_is_running() -> None:
    text = (FIXTURES / "clean.jsonl").read_text(encoding="utf-8")
    assert launch_refusal(text, ["python"]) is not None
    assert launch_refusal(text, ["llama-server"]) is not None
    assert launch_refusal(None, []) == "REFUSED -- watchdog.log missing"


def test_cell_gate_refuses_foreign_python_and_llama_server() -> None:
    processes = [
        {"pid": 10, "ppid": 1, "name": "powershell.exe"},
        {"pid": 20, "ppid": 10, "name": "python.exe"},
        {"pid": 30, "ppid": 1, "name": "python.exe"},
        {"pid": 40, "ppid": 1, "name": "llama-server.exe"},
    ]
    foreign = foreign_workers(processes, root_pid=10)
    pids = {int(p["pid"]) for p in foreign}
    assert 20 not in pids
    assert pids == {30, 40}


def test_evidence_window_and_overlapping_cell_from_fixture() -> None:
    text = (FIXTURES / "foreign_during_cell.jsonl").read_text(encoding="utf-8")
    lines = evidence_lines(text, "2026-09-29T16:00:00Z", "2026-09-29T16:45:00Z")
    assert len(lines) == 3
    assert "15:50:00" not in "\n".join(lines)
    assert "17:00:00" not in "\n".join(lines)
    cells = mark_overlapping_cells(
        [
            {
                "name": "T2S 4B-int4 GPU u8",
                "status": "complete",
                "run_id": "run-4b",
                "started_utc": "2026-09-29T16:05:00Z",
                "ended_utc": "2026-09-29T16:15:00Z",
            },
            {
                "name": "T2S 8B-int4 GPU u8",
                "status": "complete",
                "run_id": "run-8b",
                "started_utc": "2026-09-29T16:15:00Z",
                "ended_utc": "2026-09-29T16:30:00Z",
            },
        ],
        lines,
    )
    assert cells[0]["status"] == "complete"
    assert "exclude_from_sealed_results" not in cells[0]
    assert cells[1]["status"] == "FOREIGN_ACTIVITY"
    assert cells[1]["exclude_from_sealed_results"] is True


def test_empty_flag_lines_do_not_mark_a_cell() -> None:
    text = (FIXTURES / "clean.jsonl").read_text(encoding="utf-8")
    lines = evidence_lines(text, "2026-09-29T16:00:00Z", "2026-09-29T16:45:00Z")
    cells = mark_overlapping_cells(
        [
            {
                "name": "T2S 4B-int4 GPU u8",
                "status": "complete",
                "started_utc": "2026-09-29T16:00:00Z",
                "ended_utc": "2026-09-29T16:30:00Z",
            }
        ],
        lines,
    )
    assert cells[0]["status"] == "complete"


def test_seal_refuses_foreign_activity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = tmp_path / "abc"
    session.mkdir()
    summary = {"status": "complete", "exclude_from_sealed_results": True}
    plan = {"exclude_from_sealed_results": True}
    (session / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (session / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    assert seal_exclusion_reason(summary, plan) is not None
    monkeypatch.setattr("tools.seal_c2_ttft.SESSION_BASE", tmp_path)
    with pytest.raises(SystemExit, match="FOREIGN_ACTIVITY"):
        seal_session(session_id="abc")


def test_launcher_has_no_logon_registration() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "RunOnce" not in text
    assert "schtasks" not in text
    assert "Register-ScheduledTask" not in text
    assert "RebootIfClear" not in text
    assert "launch-check" in text
    assert "24000" in text
    assert "-Detach" in text
