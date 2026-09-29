"""Read-only evidence from Rithwik's APU queue watchdog log.

Does not create, edit, or reschedule the watchdog task. Callers pass a log
path. The live path is C:\\apu\\watchdog.log.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_TS_KEYS = ("utc", "timestamp", "ts", "time")
_WORKER_PREFIXES = ("python", "llama-server")


def parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_log_line(line: str) -> dict[str, Any] | None:
    text = line.strip()
    if not text:
        return None
    if not text.startswith("{"):
        parts = text.split(None, 1)
        if len(parts) == 2 and parts[1].startswith("{"):
            try:
                obj = json.loads(parts[1])
            except json.JSONDecodeError:
                return None
            if isinstance(obj, dict):
                obj.setdefault("utc", parts[0])
                return obj
            return None
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def entry_utc(entry: dict[str, Any]) -> datetime | None:
    for key in _TS_KEYS:
        raw = entry.get(key)
        if isinstance(raw, str) and raw.strip():
            try:
                return parse_utc(raw)
            except ValueError:
                continue
    return None


def last_entry(text: str) -> dict[str, Any] | None:
    last: dict[str, Any] | None = None
    for line in text.splitlines():
        parsed = parse_log_line(line)
        if parsed is not None:
            last = parsed
    return last


def is_worker_name(name: str) -> bool:
    lowered = name.lower()
    if lowered.endswith(".exe"):
        lowered = lowered[: -len(".exe")]
    return lowered.startswith(_WORKER_PREFIXES)


def launch_refusal(log_text: str | None, running_names: list[str]) -> str | None:
    """(a) last log entry must be empty_flag, and no python or llama-server."""
    if log_text is None:
        return "REFUSED -- watchdog.log missing"
    if last_entry(log_text) is None:
        return "REFUSED -- watchdog.log has no JSON entry"
    entry = last_entry(log_text)
    assert entry is not None
    if entry.get("action") != "empty_flag":
        return (
            "REFUSED -- last watchdog action is "
            f"{entry.get('action')!r}, want empty_flag"
        )
    busy = [name for name in running_names if is_worker_name(name)]
    if busy:
        return "REFUSED -- python or llama-server is running"
    return None


def _ancestor_owned(pid: int, by_pid: dict[int, dict[str, Any]], root_pid: int) -> bool:
    seen: set[int] = set()
    current = pid
    while current and current not in seen:
        if current == root_pid:
            return True
        seen.add(current)
        parent = by_pid.get(current)
        if parent is None:
            return False
        current = int(parent.get("ppid") or 0)
    return False


def foreign_workers(processes: list[dict[str, Any]], root_pid: int) -> list[dict[str, Any]]:
    """(b) python / llama-server whose parent chain does not include root_pid."""
    by_pid = {int(p["pid"]): p for p in processes}
    foreign: list[dict[str, Any]] = []
    for proc in processes:
        name = str(proc.get("name") or "")
        if not is_worker_name(name):
            continue
        pid = int(proc["pid"])
        if _ancestor_owned(pid, by_pid, root_pid):
            continue
        foreign.append(proc)
    return foreign


def evidence_lines(log_text: str, started_utc: str, ended_utc: str) -> list[str]:
    """Log lines whose UTC timestamp falls inside the run window, inclusive."""
    start = parse_utc(started_utc)
    end = parse_utc(ended_utc)
    kept: list[str] = []
    for line in log_text.splitlines():
        parsed = parse_log_line(line)
        if parsed is None:
            continue
        stamp = entry_utc(parsed)
        if stamp is None:
            continue
        if start <= stamp <= end:
            kept.append(line.strip())
    return kept


def mark_overlapping_cells(
    cells: list[dict[str, Any]], evidence: list[str]
) -> list[dict[str, Any]]:
    """Mark a cell FOREIGN_ACTIVITY when a non-empty_flag line overlaps it."""
    parsed_window: list[tuple[datetime, dict[str, Any]]] = []
    for line in evidence:
        parsed = parse_log_line(line)
        if parsed is None:
            continue
        stamp = entry_utc(parsed)
        if stamp is None:
            continue
        parsed_window.append((stamp, parsed))
    updated: list[dict[str, Any]] = []
    for cell in cells:
        row = dict(cell)
        started = row.get("started_utc")
        ended = row.get("ended_utc")
        if isinstance(started, str) and isinstance(ended, str) and started and ended:
            c0 = parse_utc(started)
            c1 = parse_utc(ended)
            bad = any(
                c0 <= stamp <= c1 and entry.get("action") != "empty_flag"
                for stamp, entry in parsed_window
            )
            if bad:
                row["status"] = "FOREIGN_ACTIVITY"
                row["exclude_from_sealed_results"] = True
        updated.append(row)
    return updated


def seal_exclusion_reason(summary: dict[str, Any], plan: dict[str, Any]) -> str | None:
    flagged = (
        summary.get("exclude_from_sealed_results")
        or plan.get("exclude_from_sealed_results")
        or summary.get("status") == "FOREIGN_ACTIVITY"
        or plan.get("status") == "FOREIGN_ACTIVITY"
    )
    if flagged:
        return "REFUSED -- FOREIGN_ACTIVITY; excluded from sealed results"
    return None


def _patch_cell_files(repo_root: Path, cell: dict[str, Any], evidence: list[str]) -> None:
    run_id = str(cell.get("run_id") or "").strip()
    if not run_id:
        return
    session = repo_root / "derived" / "c2_ttft" / run_id
    sealed = repo_root / "derived" / "c2_ttft" / f"sealed_{run_id}"
    if sealed.exists() or not session.is_dir():
        return
    exclude = bool(cell.get("exclude_from_sealed_results"))
    for name in ("plan.json", "summary.json"):
        path = session / name
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(doc, dict):
            continue
        doc["foreign_queue_evidence"] = list(evidence)
        if exclude:
            doc["exclude_from_sealed_results"] = True
            doc["status"] = "FOREIGN_ACTIVITY"
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def apply_summary(payload: dict[str, Any]) -> dict[str, Any]:
    log_path = Path(str(payload.get("log_path") or ""))
    started = str(payload.get("started_utc") or "")
    ended = str(payload.get("ended_utc") or "")
    cells = [dict(c) for c in (payload.get("cells") or [])]
    if not log_path.is_file() or not started or not ended:
        return {
            "cells": cells,
            "foreign_queue_evidence": [],
            "watchdog_log_missing": not log_path.is_file(),
        }
    text = log_path.read_text(encoding="utf-8")
    lines = evidence_lines(text, started, ended)
    marked = mark_overlapping_cells(cells, lines)
    repo = payload.get("repo_root")
    if repo:
        root = Path(str(repo))
        for cell in marked:
            _patch_cell_files(root, cell, lines)
    return {
        "cells": marked,
        "foreign_queue_evidence": lines,
        "watchdog_log_missing": False,
    }


def _running_names_from_args(raw: str) -> list[str]:
    if not raw.strip():
        return []
    data = json.loads(raw)
    if data is None:
        return []
    if isinstance(data, str):
        return [data]
    return [str(item) for item in data]


def _list_processes() -> list[dict[str, Any]]:
    script = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "process snapshot failed")
    data = json.loads(completed.stdout or "[]")
    if isinstance(data, dict):
        data = [data]
    rows: list[dict[str, Any]] = []
    for item in data or []:
        rows.append(
            {
                "pid": int(item["ProcessId"]),
                "ppid": int(item["ParentProcessId"]),
                "name": str(item["Name"]),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    launch = sub.add_parser("launch-check")
    launch.add_argument("--log", type=Path, required=True)
    launch.add_argument("--running-json", default="[]")

    cell = sub.add_parser("cell-check")
    cell.add_argument("--root-pid", type=int, required=True)

    apply = sub.add_parser("apply-summary")
    apply.add_argument("--payload", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.cmd == "launch-check":
        text = args.log.read_text(encoding="utf-8") if args.log.is_file() else None
        reason = launch_refusal(text, _running_names_from_args(args.running_json))
        if reason:
            print(reason)
            return 1
        print("watchdog_launch_ok")
        return 0

    if args.cmd == "cell-check":
        foreign = foreign_workers(_list_processes(), args.root_pid)
        if foreign:
            names = ", ".join(f"{p['name']}:{p['pid']}" for p in foreign)
            print(f"REFUSED -- foreign python or llama-server: {names}")
            return 1
        print("cell_workers_owned")
        return 0

    payload = json.loads(args.payload.read_text(encoding="utf-8-sig"))
    json.dump(apply_summary(payload), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
