"""Raw MCP stdio transport with deterministic newline framing."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Sequence

from ..transport_instrument import TransportInstrumentation
from .base import (
    DirectionTrace,
    TimingTrace,
    TransportError,
    TransportResult,
    TransportTrace,
    require_logical_message,
)


@dataclass(frozen=True)
class ProcProbe:
    """Best-effort Linux process counters captured at an explicit seam."""

    pid: int
    available: bool
    status: dict[str, str] = field(default_factory=dict)
    io: dict[str, int] = field(default_factory=dict)
    context_switches: dict[str, int] = field(default_factory=dict)
    fdinfo: dict[str, dict[str, str]] = field(default_factory=dict)
    reason: str | None = None


def _read_colon_file(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    return fields


def probe_proc(pid: int, *, fds: Sequence[int] = ()) -> ProcProbe:
    """Read /proc status, I/O, context switches, and selected pipe fdinfo."""
    root = Path("/proc") / str(pid)
    if os.name != "posix" or not root.is_dir():
        return ProcProbe(pid=pid, available=False, reason="/proc is unavailable")
    try:
        status = _read_colon_file(root / "status")
        io_raw = _read_colon_file(root / "io")
        io: dict[str, int] = {}
        for key, value in io_raw.items():
            try:
                io[key] = int(value)
            except ValueError:
                continue
        context_switches = {
            key: int(status[key])
            for key in ("voluntary_ctxt_switches", "nonvoluntary_ctxt_switches")
            if key in status
        }
        fdinfo: dict[str, dict[str, str]] = {}
        for fd in fds:
            path = root / "fdinfo" / str(fd)
            try:
                fdinfo[str(fd)] = _read_colon_file(path)
            except (FileNotFoundError, PermissionError, OSError):
                fdinfo[str(fd)] = {}
        return ProcProbe(
            pid=pid,
            available=True,
            status=status,
            io=io,
            context_switches=context_switches,
            fdinfo=fdinfo,
        )
    except (FileNotFoundError, PermissionError, OSError) as exc:
        return ProcProbe(pid=pid, available=False, reason=str(exc))


def _validate_stdio_message(message: bytes) -> None:
    if b"\n" in message or b"\r" in message:
        raise ValueError("stdio logical messages must not contain raw newlines")
    try:
        decoded = message.decode("utf-8")
        value = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("stdio message must be one UTF-8 JSON value") from exc
    if not isinstance(value, dict):
        raise ValueError("JSON-RPC message must be a JSON object")


class StdioTransport:
    """Persistent raw subprocess transport using MCP newline framing."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: str | os.PathLike[str] | None = None,
        env: Mapping[str, str] | None = None,
        clock_ns: Callable[[], int] = time.perf_counter_ns,
        max_response_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        if not command:
            raise ValueError("stdio command must not be empty")
        self._clock_ns = clock_ns
        self._max_response_bytes = max_response_bytes
        self._lock = threading.Lock()
        self._instrumentation: TransportInstrumentation | None = None
        start = clock_ns()
        self._process = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=dict(env) if env is not None else None,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # MCP permits diagnostic stderr output.  Leaving an unread PIPE
            # here can deadlock a long matrix cell when its buffer fills.
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self._setup_ns = max(0, clock_ns() - start)
        if self._process.stdin is None or self._process.stdout is None:
            self._process.kill()
            raise TransportError("failed to create stdio subprocess pipes")

    @property
    def pid(self) -> int:
        return self._process.pid

    def bind_instrumentation(self, instrumentation: TransportInstrumentation | None) -> None:
        self._instrumentation = instrumentation

    def clear_instrumentation(self) -> None:
        self._instrumentation = None

    def _probes(self) -> dict[str, dict[str, object]]:
        parent_fds = (
            self._process.stdin.fileno(),
            self._process.stdout.fileno(),
        )
        return {
            "parent": asdict(probe_proc(os.getpid(), fds=parent_fds)),
            "server": asdict(probe_proc(self.pid, fds=(0, 1))),
        }

    def exchange(self, logical_request: bytes) -> TransportResult:
        request = require_logical_message(logical_request)
        _validate_stdio_message(request)
        with self._lock:
            if self._process.poll() is not None:
                raise TransportError(
                    f"stdio server exited with code {self._process.returncode}"
                )
            instr = self._instrumentation
            before = self._probes() if instr is None else {"skipped": True}

            def _frame_request() -> bytes:
                wire_request = request + b"\n"
                _validate_stdio_message(request)
                return wire_request

            if instr is not None:
                wire_request = instr.frame(
                    _frame_request,
                    bytes_out=len(request) + 1,
                )
                instr.persist_wire("request", wire_request)
            else:
                frame_start = self._clock_ns()
                wire_request = _frame_request()
                frame_request_ns = max(0, self._clock_ns() - frame_start)

            def _write_request() -> None:
                view = memoryview(wire_request)
                while view:
                    written = self._process.stdin.write(view)
                    if not written:
                        raise TransportError("stdio server closed its input pipe")
                    view = view[written:]
                self._process.stdin.flush()

            if instr is not None:
                instr.transport_cpu(_write_request, bytes_out=len(wire_request))
                write_ns = 0
            else:
                write_start = self._clock_ns()
                _write_request()
                write_ns = max(0, self._clock_ns() - write_start)

            def _read_response() -> bytes:
                wire = self._process.stdout.readline(self._max_response_bytes + 2)
                if not wire:
                    code = self._process.poll()
                    raise TransportError(f"stdio server closed output (exit code {code})")
                return wire

            if instr is not None:
                wire_response = instr.transport_cpu(_read_response)
                read_ns = 0
            else:
                read_start = self._clock_ns()
                wire_response = _read_response()
                read_ns = max(0, self._clock_ns() - read_start)

            def _frame_response() -> bytes:
                if len(wire_response) > self._max_response_bytes + 1:
                    raise TransportError("stdio response exceeds configured maximum")
                if not wire_response.endswith(b"\n"):
                    raise TransportError("stdio response is not newline terminated")
                payload = wire_response[:-1]
                _validate_stdio_message(payload)
                return payload

            if instr is not None:
                # Post-read validation folded into FRAME so TRANSPORT exit → next
                # named region has no untimed harness-owned checks on the happy path.
                response = instr.frame(
                    _frame_response,
                    bytes_in=len(wire_response),
                )
                instr.persist_wire("response", wire_response)
                frame_request_ns = 0
                frame_response_ns = 0
            else:
                parse_start = self._clock_ns()
                response = _frame_response()
                frame_response_ns = max(0, self._clock_ns() - parse_start)
            after = self._probes() if instr is None else {"skipped": True}
            setup_ns, self._setup_ns = self._setup_ns, 0

            return TransportResult(
                response=response,
                trace=TransportTrace(
                    transport="stdio",
                    request=DirectionTrace.from_message(
                        request, wire_bytes=len(wire_request)
                    ),
                    response=DirectionTrace.from_message(
                        response, wire_bytes=len(wire_response)
                    ),
                    timing=TimingTrace(
                        setup_ns=setup_ns,
                        frame_request_ns=frame_request_ns,
                        write_ns=write_ns,
                        read_ns=read_ns,
                        frame_response_ns=frame_response_ns,
                    ),
                    metadata={"proc_before": before, "proc_after": after},
                ),
            )

    def send_notification(self, logical_request: bytes) -> None:
        """Write a JSON-RPC notification without waiting for a forbidden reply."""

        request = require_logical_message(logical_request)
        _validate_stdio_message(request)
        with self._lock:
            if self._process.poll() is not None:
                raise TransportError(
                    f"stdio server exited with code {self._process.returncode}"
                )
            wire_request = request + b"\n"
            view = memoryview(wire_request)
            while view:
                written = self._process.stdin.write(view)
                if not written:
                    raise TransportError("stdio server closed its input pipe")
                view = view[written:]
            self._process.stdin.flush()

    def close(self) -> None:
        with self._lock:
            if self._process.poll() is None:
                if self._process.stdin is not None:
                    self._process.stdin.close()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=2)
            if self._process.stdout is not None:
                self._process.stdout.close()
            if self._process.stderr is not None:
                self._process.stderr.close()

    def __enter__(self) -> "StdioTransport":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

