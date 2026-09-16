"""Process-level Docker CLI observer used by OA-01.

Set ``MSWEA_DOCKER_EXECUTABLE`` to an executable shim that invokes this module.
The wrapper preserves argv/stdin/stdout/stderr and exit status while writing
start/end events to ``OA01_EXEC_LOG``.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_LOG_LOCK = threading.Lock()


def _append(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(value, sort_keys=True, separators=(",", ":"))
    with _LOG_LOCK, path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _parse_exec(argv: list[str]) -> tuple[str | None, str | None]:
    if not argv or argv[0] != "exec":
        return None, None
    idx = 1
    options_with_value = {
        "-d",
        "--detach-keys",
        "-e",
        "--env",
        "--env-file",
        "-u",
        "--user",
        "-w",
        "--workdir",
    }
    flags = {"-i", "--interactive", "-t", "--tty", "--detach", "--privileged"}
    while idx < len(argv):
        item = argv[idx]
        if item == "--":
            idx += 1
            break
        if item in flags:
            idx += 1
            continue
        if item in options_with_value:
            idx += 2
            continue
        if item.startswith("-") and "=" in item:
            idx += 1
            continue
        break
    if idx >= len(argv):
        return None, None
    container_id = argv[idx]
    command = "\0".join(argv[idx + 1 :]) if idx + 1 < len(argv) else ""
    return container_id, command


def run(argv: list[str]) -> int:
    real_docker = os.environ.get("OA01_REAL_DOCKER", "docker")
    log_value = os.environ.get("OA01_EXEC_LOG")
    trajectory_id = os.environ.get("OA01_TRAJECTORY_ID", "unknown")
    if Path(real_docker).resolve() == Path(sys.argv[0]).resolve():
        raise RuntimeError("OA01_REAL_DOCKER resolves to observer itself")

    span_id = f"exec-{uuid.uuid4().hex}"
    operation = argv[0] if argv else ""
    container_id, command = _parse_exec(argv)
    start_ns = time.time_ns()
    base = {
        "schema_version": "oa01_exec_event_v1",
        "trajectory_id": trajectory_id,
        "span_id": span_id,
        "argv": argv,
        "docker_operation": operation,
        "container_id": container_id,
        "command": command,
    }
    if log_value:
        _append(Path(log_value), {**base, "event": "start", "unix_ns": start_ns})

    io_dir_value = os.environ.get("OA01_TOOL_IO_DIR")
    io_path = Path(io_dir_value) / f"{span_id}.stdout_stderr.bin" if io_dir_value else None
    if io_path is not None:
        io_path.parent.mkdir(parents=True, exist_ok=True)
    child = subprocess.Popen(
        [real_docker, *argv],
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    received_signal: int | None = None

    def forward(signum: int, _frame: Any) -> None:
        nonlocal received_signal
        received_signal = signum
        if child.poll() is None:
            try:
                child.send_signal(signum)
            except (OSError, ValueError):
                pass

    installed: dict[int, Any] = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            installed[signum] = signal.signal(signum, forward)
        except (OSError, ValueError):
            pass
    try:
        assert child.stdout is not None
        io_file = io_path.open("wb") if io_path is not None else None
        try:
            while True:
                chunk = child.stdout.read1(65_536)
                if not chunk:
                    break
                if io_file is not None:
                    io_file.write(chunk)
                    io_file.flush()
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
        finally:
            if io_file is not None:
                io_file.close()
        returncode = child.wait()
    finally:
        for signum, prior in installed.items():
            try:
                signal.signal(signum, prior)
            except (OSError, ValueError):
                pass

    end_ns = time.time_ns()
    if log_value:
        _append(
            Path(log_value),
            {
                **base,
                "event": "end",
                "unix_ns": end_ns,
                "returncode": returncode,
                "signal": received_signal,
                "stdout_stderr_path": str(io_path) if io_path is not None else None,
            },
        )
    return 128 + abs(returncode) if returncode < 0 else int(returncode)


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

