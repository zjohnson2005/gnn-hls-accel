"""Concrete CAP-01 harness adapters sharing one JSON message contract."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping, TypedDict

from ..taxonomy import Category
from .contracts import canonical_json_bytes

RUST_HARNESS_ROOT = Path(__file__).with_name("rust_harness")
RUST_SOURCE = RUST_HARNESS_ROOT / "src" / "main.rs"


class HarnessUnavailableError(RuntimeError):
    pass


class _LangGraphState(TypedDict, total=False):
    request: dict[str, Any]
    response: dict[str, Any]


def _candidate_response(
    request: Mapping[str, Any], handler: Callable[[Mapping[str, Any]], None]
) -> dict[str, Any]:
    if request.get("op") != "candidate":
        raise ValueError("unsupported harness operation")
    cpu_start = time.process_time_ns()
    wall_start = time.monotonic_ns()
    handler(request)
    wall_ns = max(0, time.monotonic_ns() - wall_start)
    cpu_ns = max(0, time.process_time_ns() - cpu_start)
    return {
        "ok": True,
        "candidate_id": str(request["candidate_id"]),
        "candidate_sha256": str(request["candidate_sha256"]),
        "sequence_index": int(request["sequence_index"]),
        "harness_wall_ns": wall_ns,
        "harness_cpu_ns": cpu_ns,
        "timer_scope": "current_process",
    }


class RawPythonHarness:
    """A direct Python function call with no framework emulation."""

    category = Category.ORCH_DISPATCH

    def __init__(
        self, handler: Callable[[Mapping[str, Any]], None] | None = None
    ) -> None:
        self._handler = handler or (lambda request: None)

    def setup(self) -> None:
        return None

    def dispatch(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        # Round-trip the canonical payload to exercise the same JSON boundary
        # shape used by the Rust process.
        decoded = json.loads(canonical_json_bytes(dict(request)))
        return _candidate_response(decoded, self._handler)

    def close(self) -> None:
        return None


class LangGraphHarness:
    """A real one-node LangGraph. Absence is an explicit refusal."""

    category = Category.FRAMEWORK

    def __init__(
        self, handler: Callable[[Mapping[str, Any]], None] | None = None
    ) -> None:
        self._handler = handler or (lambda request: None)
        self._graph: Any = None

    def setup(self) -> None:
        try:
            from langgraph.graph import END, StateGraph
        except ImportError as exc:
            raise HarnessUnavailableError(
                "LangGraph harness requested but langgraph is not installed"
            ) from exc

        handler = self._handler

        def candidate_node(state: dict[str, Any]) -> dict[str, Any]:
            request = dict(state["request"])
            return {"response": _candidate_response(request, handler)}

        try:
            builder = StateGraph(_LangGraphState)
            builder.add_node("candidate", candidate_node)
            builder.set_entry_point("candidate")
            builder.add_edge("candidate", END)
            self._graph = builder.compile()
        except Exception as exc:
            raise HarnessUnavailableError(
                "installed LangGraph cannot construct the CAP-01 graph"
            ) from exc

    def dispatch(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        if self._graph is None:
            raise RuntimeError("LangGraph harness is not set up")
        decoded = json.loads(canonical_json_bytes(dict(request)))
        state = self._graph.invoke({"request": decoded})
        return dict(state["response"])

    def close(self) -> None:
        self._graph = None


def rust_executable_path() -> Path:
    suffix = ".exe" if __import__("os").name == "nt" else ""
    return RUST_HARNESS_ROOT / "target" / f"cap01_rust_harness{suffix}"


def build_rust_harness(
    *,
    executable: Path | None = None,
    rustc: str = "rustc",
    force: bool = False,
) -> Path:
    output = executable or rust_executable_path()
    if not RUST_SOURCE.is_file():
        raise HarnessUnavailableError(f"Rust harness source is missing: {RUST_SOURCE}")
    if (
        not force
        and output.is_file()
        and output.stat().st_mtime_ns >= RUST_SOURCE.stat().st_mtime_ns
    ):
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            [rustc, "--edition=2021", "-O", str(RUST_SOURCE), "-o", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise HarnessUnavailableError("rustc is required for the Rust harness") from exc
    if completed.returncode != 0:
        raise HarnessUnavailableError(
            "Rust harness compilation failed: " + completed.stderr.strip()
        )
    return output


class RustHarness:
    """Persistent native process speaking newline-delimited JSON."""

    category = Category.ORCH_DISPATCH

    def __init__(self, executable: Path | None = None, *, build: bool = True) -> None:
        self.executable = executable
        self.build = build
        self._process: subprocess.Popen[str] | None = None

    def setup(self) -> None:
        executable = self.executable
        if executable is None:
            if not self.build:
                raise HarnessUnavailableError("Rust executable was not provided")
            executable = build_rust_harness()
        if not executable.is_file():
            raise HarnessUnavailableError(f"Rust executable does not exist: {executable}")
        self._process = subprocess.Popen(
            [str(executable)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        response = self._exchange({"op": "ping"})
        if not response.get("ok"):
            self.close()
            raise HarnessUnavailableError("Rust harness did not pass setup handshake")

    def _exchange(self, request: Mapping[str, Any]) -> dict[str, Any]:
        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise RuntimeError("Rust harness is not set up")
        process.stdin.write(canonical_json_bytes(dict(request)).decode("ascii") + "\n")
        process.stdin.flush()
        line = process.stdout.readline()
        if not line:
            stderr = process.stderr.read() if process.stderr is not None else ""
            raise RuntimeError(f"Rust harness terminated without a response: {stderr}")
        response = json.loads(line)
        if not isinstance(response, dict):
            raise RuntimeError("Rust harness returned a non-object response")
        return response

    def dispatch(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._exchange(request)

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.poll() is None and process.stdin is not None:
            try:
                process.stdin.write('{"op":"shutdown"}\n')
                process.stdin.flush()
                process.wait(timeout=2)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                process.kill()
                process.wait()


def make_harness(name: str, *, rust_executable: Path | None = None) -> Any:
    if name == "raw_python":
        return RawPythonHarness()
    if name == "langgraph":
        return LangGraphHarness()
    if name == "rust":
        return RustHarness(rust_executable)
    raise ValueError(f"unsupported CAP-01 harness: {name}")
