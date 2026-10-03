"""Fixture tests for the T2S APU watchdog launch, cell, and evidence rules."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.seal_c2_ttft import seal_session  # noqa: E402
from tools.t2s_queue_watchdog import (  # noqa: E402
    apply_summary,
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
    assert launch_refusal(text, [], log_path=r"C:\apu\ovn\watchdog.log") is None


def test_launch_refuses_when_last_fixture_line_is_not_empty_flag() -> None:
    text = (FIXTURES / "last_not_empty.jsonl").read_text(encoding="utf-8")
    reason = launch_refusal(text, [], log_path=r"C:\apu\ovn\watchdog.log")
    assert reason is not None
    assert "empty_flag" in reason
    assert "queue_nonempty" in reason


def test_launch_refuses_when_python_or_llama_server_is_running() -> None:
    text = (FIXTURES / "clean.jsonl").read_text(encoding="utf-8")
    assert launch_refusal(text, ["python"], log_path=r"C:\apu\ovn\watchdog.log") is not None
    assert launch_refusal(text, ["llama-server"], log_path=r"C:\apu\ovn\watchdog.log") is not None
    missing = r"C:\apu\ovn\watchdog.log"
    assert (
        launch_refusal(None, [], log_path=missing) == f"REFUSED -- watchdog.log missing: {missing}"
    )


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


def test_custom_log_path_is_the_refusal_and_the_cell_record(tmp_path: Path) -> None:
    custom = tmp_path / "ovn" / "watchdog.log"
    custom.parent.mkdir()
    custom.write_text((FIXTURES / "clean.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    checker = ROOT / "tools" / "t2s_queue_watchdog.py"
    ok = subprocess.run(
        [
            sys.executable,
            str(checker),
            "launch-check",
            "--log",
            str(custom),
            "--running-json",
            "[]",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0, ok.stderr
    missing = tmp_path / "absent" / "watchdog.log"
    refused = subprocess.run(
        [
            sys.executable,
            str(checker),
            "launch-check",
            "--log",
            str(missing),
            "--running-json",
            "[]",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert refused.returncode == 1
    assert f"REFUSED -- watchdog.log missing: {missing}" in refused.stdout
    session = tmp_path / "repo" / "derived" / "c2_ttft" / "run-1"
    session.mkdir(parents=True)
    (session / "plan.json").write_text("{}\n", encoding="utf-8")
    (session / "summary.json").write_text("{}\n", encoding="utf-8")
    applied = apply_summary(
        {
            "log_path": str(custom),
            "started_utc": "2026-09-29T16:00:00Z",
            "ended_utc": "2026-09-29T16:45:00Z",
            "repo_root": str(tmp_path / "repo"),
            "cells": [
                {
                    "name": "T2S 4B-int4 GPU u8",
                    "status": "complete",
                    "run_id": "run-1",
                    "started_utc": "2026-09-29T16:00:00Z",
                    "ended_utc": "2026-09-29T16:30:00Z",
                }
            ],
        }
    )
    assert applied["watchdog_log"] == str(custom)
    assert applied["watchdog_log_missing"] is False
    for name in ("plan.json", "summary.json"):
        doc = json.loads((session / name).read_text(encoding="utf-8"))
        assert doc["watchdog_log"] == str(custom)


def test_dry_run_prints_a_custom_watchdog_log(tmp_path: Path) -> None:
    custom = tmp_path / "ovn" / "watchdog.log"
    custom.parent.mkdir()
    custom.write_text((FIXTURES / "clean.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-File",
            str(LAUNCHER),
            "-DryRun",
            "-WatchdogLog",
            str(custom),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert f"watchdog_log={custom}" in proc.stdout
    assert "DRY_RUN_OK T2S 4B-int4 GPU f16 control" in proc.stdout


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
    assert r"C:\apu\ovn\watchdog.log" in text
    assert r"C:\apu\watchdog.log" not in text
    sequencer = (ROOT / "tools" / "launch_boot1.ps1").read_text(encoding="utf-8")
    assert "-WatchdogLog" in sequencer
    assert r'log_path = "C:\apu\watchdog.log"' not in sequencer


def test_live_log_ending_in_paused_and_digest_is_idle() -> None:
    text = (FIXTURES / "live_paused.jsonl").read_text(encoding="utf-8")
    entry = last_entry(text)
    assert entry is not None
    assert entry["action"] == "paused"
    assert launch_refusal(text, [], log_path=r"C:\apu\ovn\watchdog.log") is None
    assert launch_refusal(text, ["python"], log_path=r"C:\apu\ovn\watchdog.log") is not None


def test_digest_line_is_neither_idle_nor_busy() -> None:
    busy_then_digest = (
        '[2026-10-02T12:23:07Z] {"action": "crashed_requeued", "launched": "job"}\n'
        '[2026-10-02T12:23:09Z] {"digest": {"action": "ran", "rc": 0}}\n'
    )
    reason = launch_refusal(busy_then_digest, [], log_path="w.log")
    assert reason is not None
    assert "crashed_requeued" in reason
    only_digest = '[2026-10-02T12:23:09Z] {"digest": {"action": "ran", "rc": 0}}\n'
    assert launch_refusal(only_digest, [], log_path="w.log") is not None
    lines = evidence_lines(only_digest, "2026-10-02T12:00:00Z", "2026-10-02T13:00:00Z")
    assert len(lines) == 1
    cells = mark_overlapping_cells(
        [
            {
                "name": "cell",
                "status": "complete",
                "started_utc": "2026-10-02T12:00:00Z",
                "ended_utc": "2026-10-02T13:00:00Z",
            }
        ],
        lines,
    )
    assert cells[0]["status"] == "complete"


def test_bracketed_timestamps_parse_into_the_window() -> None:
    text = (FIXTURES / "live_paused.jsonl").read_text(encoding="utf-8")
    lines = evidence_lines(text, "2026-10-02T12:20:00Z", "2026-10-02T12:34:00Z")
    assert len(lines) == 4
    assert all("12:13:" not in line for line in lines)


def test_foreign_launch_inside_the_run_window_is_detected() -> None:
    text = (FIXTURES / "live_foreign_launch.jsonl").read_text(encoding="utf-8")
    lines = evidence_lines(text, "2026-09-29T18:20:00Z", "2026-09-29T18:45:00Z")
    cells = mark_overlapping_cells(
        [
            {
                "name": "T2S 4B-int4 GPU u8",
                "status": "complete",
                "started_utc": "2026-09-29T18:23:01Z",
                "ended_utc": "2026-09-29T18:28:00Z",
            },
            {
                "name": "after",
                "status": "complete",
                "started_utc": "2026-09-29T18:29:00Z",
                "ended_utc": "2026-09-29T18:44:00Z",
            },
        ],
        lines,
    )
    assert cells[0]["status"] == "FOREIGN_ACTIVITY"
    assert cells[0]["exclude_from_sealed_results"] is True
    assert cells[1]["status"] == "complete"


def _cell_dir(root: Path, run_id: str) -> Path:
    session = root / "derived" / "c2_ttft" / run_id
    session.mkdir(parents=True)
    (session / "plan.json").write_text("{}\n", encoding="utf-8")
    (session / "summary.json").write_text("{}\n", encoding="utf-8")
    return session


def test_stamp_patches_only_the_finished_cell(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    first = _cell_dir(repo, "run-1")
    second = _cell_dir(repo, "run-2")
    payload = {
        "log_path": str(tmp_path / "missing.log"),
        "started_utc": "",
        "ended_utc": "",
        "repo_root": str(repo),
        "cells": [
            {"run_id": "run-1", "status": "complete"},
            {"run_id": "run-2", "status": "complete"},
        ],
    }
    apply_summary(payload, patch_run_id="run-1")
    assert "watchdog_log" in json.loads((first / "plan.json").read_text(encoding="utf-8"))
    assert json.loads((second / "plan.json").read_text(encoding="utf-8")) == {}
    before = (first / "summary.json").read_bytes()
    apply_summary(payload, patch_files=False)
    assert (first / "summary.json").read_bytes() == before
    assert json.loads((second / "summary.json").read_text(encoding="utf-8")) == {}
