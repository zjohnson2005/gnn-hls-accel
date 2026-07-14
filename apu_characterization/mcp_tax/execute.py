"""Real raw/official-SDK execution callback for MCP-01 cells."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from .accum import McpMessageAccumulator, ScopeObservation
from .client import RawJsonRpcClient
from .contracts import CellPlan
from .coverage import coverage_record
from .implementations.reference_sdk import PINNED_MCP_VERSION, ReferenceSdkAdapter
from .instrument import mcp_timed
from .isolation import (
    CorePartitions,
    discover_topology,
    parse_cpu_list,
    publication_preflight,
    set_current_affinity,
    taskset_command,
)
from .manifest import build_manifest, capture_git_state
from .plan import split_warmup_measured
from .run_context import get_run_tls_fixture
from .taxonomy import McpCategory
from .tls_fixture import TlsFixture
from .transport_instrument import TransportInstrumentation
from .transports.http_sse import HttpSseTransport
from .transports.stdio import StdioTransport

REPO_ROOT = Path(__file__).resolve().parents[2]
SDK_LOCK = REPO_ROOT / "apu_characterization" / "requirements-mcp.txt"
_ORIGINAL_AFFINITY = (
    frozenset(os.sched_getaffinity(0))
    if hasattr(os, "sched_getaffinity")
    else frozenset(range(os.cpu_count() or 1))
)


class AdmissionError(RuntimeError):
    """The requested arm is not admissible as a real measurement."""


def _dependency_versions() -> dict[str, str]:
    packages = ("mcp", "jsonschema", "httpx", "httpx-sse", "cryptography")
    return {package: importlib.metadata.version(package) for package in packages}


def _locked_versions() -> dict[str, str]:
    locked: dict[str, str] = {}
    for raw_line in SDK_LOCK.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, version = line.partition("==")
        if separator != "==" or not name or not version:
            raise AdmissionError(f"dependency lock is not exact: {raw_line!r}")
        locked[name] = version
    return locked


def _require_sdk_lock() -> dict[str, str]:
    installed = _dependency_versions()
    locked = _locked_versions()
    mismatches = {
        package: {"locked": version, "installed": installed.get(package)}
        for package, version in locked.items()
        if installed.get(package) != version
    }
    if mismatches:
        raise AdmissionError(f"installed MCP dependency lock mismatch: {mismatches}")
    adapter = ReferenceSdkAdapter()
    adapter.require_compatible()
    return installed


def _partitions(publication: bool) -> CorePartitions:
    if publication:
        return CorePartitions(
            os_cpus=parse_cpu_list(os.environ["MCP_OS_ANALYSIS_CORES"]),
            client_cpus=parse_cpu_list(os.environ["MCP_CLIENT_CORES"]),
            server_cpus=parse_cpu_list(os.environ["MCP_SERVER_CORES"]),
        )
    available = sorted(_ORIGINAL_AFFINITY)
    if len(available) < 3:
        raise AdmissionError("debug smoke requires at least three available logical CPUs")
    return CorePartitions(
        os_cpus=frozenset(available[2:]),
        client_cpus=frozenset({available[0]}),
        server_cpus=frozenset({available[1]}),
    )


def _preflight(publication: bool, partitions: CorePartitions) -> dict[str, Any]:
    installed = _require_sdk_lock()
    topology = discover_topology()
    result = publication_preflight(
        topology,
        partitions,
        mode="publication" if publication else "smoke",
        require_complete=True,
    )
    if not result.passed:
        raise AdmissionError("; ".join(result.errors))
    git = capture_git_state(REPO_ROOT)
    if publication and git.get("dirty") != "no":
        raise AdmissionError("publication requires a clean tracked Git tree")
    return {
        "installed": installed,
        "git": git,
        "preflight": {
            "mode": result.mode,
            "caveats": list(result.caveats),
            "environment": {
                "system": result.environment.system,
                "release": result.environment.release,
                "is_wsl": result.environment.is_wsl,
                "is_virtualized": result.environment.is_virtualized,
                "virtualization": result.environment.virtualization,
            },
            "governors": {str(key): value for key, value in result.governors.items()},
        },
    }


def _server_command(config_path: Path, server_cpus: frozenset[int]) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "apu_characterization.mcp_tax.server_process",
        "--config",
        os.fspath(config_path),
    ]
    return taskset_command(command, server_cpus)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_port(process: subprocess.Popen[Any], port: int) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"MCP server exited early with code {process.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"MCP server did not listen on port {port}")


def _server_config(
    plan: CellPlan,
    run_dir: Path,
    partitions: CorePartitions,
    *,
    tls: TlsFixture | None,
    port: int | None,
) -> Path:
    config = {
        "plan": plan.as_dict(),
        "server_output": os.fspath(run_dir / "server" / "result.json"),
        "server_cores": sorted(partitions.server_cpus),
        "port": port,
        "tls": tls is not None,
        "server_cert": os.fspath(tls.server_cert_path) if tls else None,
        "server_key": os.fspath(tls.server_key_path) if tls else None,
    }
    path = run_dir / "server_config.json"
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _finish_client(accumulator: McpMessageAccumulator, last_message: str) -> None:
    observation = accumulator.end_endpoint(
        metadata={"canonical_hashes": list(accumulator.canonical_hashes)}
    )
    setup_cpu = accumulator.setup_totals().cpu_ns
    setup_wall = accumulator.setup_totals().wall_ns
    message_boundary_cpu = sum(
        int(values.get("client_call_boundary_ns", 0))
        for values in accumulator.message_diagnostics.values()
    )
    message_boundary_wall = sum(
        int(values.get("client_call_boundary_wall_ns", 0))
        for values in accumulator.message_diagnostics.values()
    )
    effective_process_cpu = setup_cpu + message_boundary_cpu
    effective_wall_ns = setup_wall + message_boundary_wall
    if effective_process_cpu > 0 or effective_wall_ns > 0:
        observation = ScopeObservation(
            start_wall_ns=observation.start_wall_ns,
            end_wall_ns=observation.end_wall_ns,
            process_cpu_ns=effective_process_cpu,
            wall_ns=effective_wall_ns,
            thread_schedstat_cpu_ns=observation.thread_schedstat_cpu_ns,
            metadata=observation.metadata,
        )
        accumulator.endpoint_observation = observation
    accounted_cpu = (
        setup_cpu
        + sum(totals.cpu_ns for totals in accumulator.by_key.values())
    )
    accounted_wall = (
        setup_wall
        + sum(totals.wall_ns for totals in accumulator.by_key.values())
    )
    wait_wall = sum(totals.wall_ns for totals in accumulator.waits_by_key.values())
    endpoint_residual = max(0, observation.process_cpu_ns - accounted_cpu)
    if endpoint_residual:
        accumulator.book(
            McpCategory.RESIDUAL,
            endpoint_residual,
            message_id=last_message,
            wall_ns=max(0, observation.wall_ns - accounted_wall - wait_wall),
            provenance="endpoint_reconciliation",
        )


def _bind_transport_instrumentation(
    transport: Any,
    accumulator: McpMessageAccumulator,
    *,
    message_id: str,
    wire_dir: Path | None,
) -> None:
    bind = getattr(transport, "bind_instrumentation", None)
    if not callable(bind):
        return
    bind(
        TransportInstrumentation(
            accumulator=accumulator,
            message_id=message_id,
            wire_dir=wire_dir,
        )
    )


def _clear_transport_instrumentation(transport: Any) -> None:
    clear = getattr(transport, "clear_instrumentation", None)
    if callable(clear):
        clear()


def _record_client_call(
    accumulator: McpMessageAccumulator,
    step: Any,
    client: RawJsonRpcClient,
    *,
    wire_dir: Path | None,
    timer_pair_cost_ns: int = 0,
    run_dir: Path | None = None,
) -> Any:
    from .client import JsonRpcResponseError
    from .gap_measure import build_gap_decomposition, gap_session
    from .gap_split import GAP_DECOMPOSITION_KEY

    message_id = str(step.index)
    request_id = step.index + 1
    accumulator.begin_message(message_id)
    try:
        if accumulator.mode == "full":
            cpu_start = time.thread_time_ns()
            wall_start = time.perf_counter_ns()
            json.loads(step.canonical_bytes(request_id))
            cpu_ns = time.thread_time_ns() - cpu_start
            accumulator.book(
                McpCategory.MSG_VALIDATE,
                cpu_ns,
                message_id=message_id,
                wall_ns=min(time.perf_counter_ns() - wall_start, cpu_ns),
                provenance="full_observer_prevalidation",
            )

        boundary_cpu_start = time.thread_time_ns()
        boundary_wall_start = time.perf_counter_ns()

        with gap_session(
            message_id,
            timer_pair_cost_ns=timer_pair_cost_ns,
            run_dir=run_dir,
            boundary_cpu_start=boundary_cpu_start,
            boundary_wall_start=boundary_wall_start,
        ) as session:
            session.mark_boundary("pre_serial")
            req_bytes: dict[str, int] = {"bytes_out": 0}
            with mcp_timed(
                McpCategory.MSG_SERIAL,
                accumulator=accumulator,
                message_id=message_id,
                byte_totals=req_bytes,
                provenance="client_request_materialize",
            ):
                request_bytes = step.canonical_bytes(request_id)
                req_bytes["bytes_out"] = len(request_bytes)

            session.mark_boundary("serial_to_transport")
            _bind_transport_instrumentation(
                client.transport,
                accumulator,
                message_id=message_id,
                wire_dir=wire_dir,
            )
            try:
                transport_result = client.exchange_step(
                    step, request_bytes=request_bytes
                )
            finally:
                _clear_transport_instrumentation(client.transport)

            session.mark_boundary("transport_to_serial")
            response_bytes = transport_result.response
            with mcp_timed(
                McpCategory.MSG_SERIAL,
                accumulator=accumulator,
                message_id=message_id,
                bytes_in=len(response_bytes),
                provenance="client_response_parse",
            ):
                response = json.loads(response_bytes)
            session.mark_boundary("serial_to_dispatch")
            if response.get("id") != request_id:
                raise RuntimeError("JSON-RPC response id does not match plan step")
            if "error" in response:
                raise JsonRpcResponseError(response["error"])
            with mcp_timed(
                McpCategory.MSG_DISPATCH,
                accumulator=accumulator,
                message_id=message_id,
                provenance="client_result_dispatch",
            ):
                result = response["result"]
            session.mark_boundary("post_dispatch")

            boundary_cpu_ns = max(0, time.thread_time_ns() - boundary_cpu_start)
            boundary_wall_ns = max(0, time.perf_counter_ns() - boundary_wall_start)
            nested_cpu_ns = accumulator.message_booked_cpu_ns(message_id)
            gap_cpu = max(0, boundary_cpu_ns - nested_cpu_ns)
            if gap_cpu:
                accumulator.book(
                    McpCategory.MSG_DISPATCH,
                    gap_cpu,
                    message_id=message_id,
                    wall_ns=gap_cpu,
                    provenance="client_call_inter_region_gaps",
                )
            # Always emit decomposition when hooks are on (including zero parent).
            if accumulator.category_hooks_enabled:
                from .contracts import load_protocol

                precedence = (
                    load_protocol()
                    .get("audit", {})
                    .get("gap_split_precedence")
                    or None
                )
                decomp = build_gap_decomposition(
                    gap_cpu if gap_cpu else 0,
                    session,
                    precedence=precedence,
                )
                if run_dir is not None and decomp.get("overlap_resolutions"):
                    overlap_dir = Path(run_dir) / "gap_overlaps"
                    overlap_dir.mkdir(parents=True, exist_ok=True)
                    (overlap_dir / f"{message_id}.json").write_text(
                        json.dumps(decomp["overlap_resolutions"], indent=2) + "\n",
                        encoding="utf-8",
                    )
                accumulator.record_message_diagnostic(
                    message_id, GAP_DECOMPOSITION_KEY, decomp
                )

        nested_cpu_ns = accumulator.message_booked_cpu_ns(message_id)
        accumulator.record_message_diagnostic(
            message_id, "client_call_boundary_ns", boundary_cpu_ns
        )
        accumulator.record_message_diagnostic(
            message_id, "client_call_boundary_wall_ns", boundary_wall_ns
        )
        accumulator.record_message_diagnostic(
            message_id, "client_nested_cpu_ns", nested_cpu_ns
        )
        accumulator.book_wait(
            "transport_blocked",
            max(0, boundary_wall_ns - boundary_cpu_ns),
            message_id=message_id,
            provenance="client_call_wall_minus_thread_cpu",
        )
        return result
    finally:
        accumulator.end_message(message_id)
        accumulator.record_canonical_hash(plan_hash(step))


def plan_hash(step: Any) -> str:
    from .contracts import sha256_bytes

    return sha256_bytes(step.canonical_bytes(step.index + 1))


def _end_setup(accumulator: McpMessageAccumulator) -> None:
    observation = accumulator.end_setup()
    accumulator.book(
        McpCategory.SESSION_SETUP,
        observation.process_cpu_ns,
        wall_ns=observation.wall_ns,
        provenance="client_setup_process_clock",
    )


def _run_raw(
    plan: CellPlan,
    run_dir: Path,
    partitions: CorePartitions,
    *,
    tls: TlsFixture | None,
    timer_pair_cost_ns: int,
) -> McpMessageAccumulator:
    warmup, measured = split_warmup_measured(plan)
    accumulator = McpMessageAccumulator("client", mode=plan.coordinates.mode)
    accumulator.record_sdk_coverage(coverage_record(implementation="raw_jsonrpc"))
    accumulator.begin_setup(metadata={"implementation": "raw_jsonrpc"})
    wire_dir = run_dir / "wire"
    call_kwargs = {
        "wire_dir": wire_dir,
        "timer_pair_cost_ns": timer_pair_cost_ns,
        "run_dir": run_dir,
    }
    if plan.coordinates.transport == "stdio":
        config_path = _server_config(plan, run_dir, partitions, tls=None, port=None)
        with StdioTransport(_server_command(config_path, partitions.server_cpus)) as transport:
            client = RawJsonRpcClient(transport)
            client.initialize()
            client.list_tools()
            _end_setup(accumulator)
            for step in warmup:
                client.call_step(step)
            accumulator.begin_endpoint(
                metadata={
                    "pid": os.getpid(),
                    "timer_pair_cost_ns": timer_pair_cost_ns,
                }
            )
            for step in measured:
                _record_client_call(accumulator, step, client, **call_kwargs)
            _finish_client(accumulator, str(measured[-1].index))
        return accumulator

    port = _free_port()
    config_path = _server_config(plan, run_dir, partitions, tls=tls, port=port)
    stdout_path = run_dir / "server" / "stdout.log"
    stderr_path = run_dir / "server" / "stderr.log"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            _server_command(config_path, partitions.server_cpus),
            cwd=REPO_ROOT,
            stdout=stdout,
            stderr=stderr,
        )
        try:
            _wait_for_port(process, port)
            scheme = "https" if tls else "http"
            transport = HttpSseTransport(
                f"{scheme}://127.0.0.1:{port}/mcp",
                ssl_context=tls.client_context() if tls else None,
            )
            client = RawJsonRpcClient(transport)
            client.initialize()
            client.list_tools()
            _end_setup(accumulator)
            for step in warmup:
                client.call_step(step)
            accumulator.begin_endpoint(
                metadata={
                    "pid": os.getpid(),
                    "timer_pair_cost_ns": timer_pair_cost_ns,
                }
            )
            for step in measured:
                _record_client_call(accumulator, step, client, **call_kwargs)
            _finish_client(accumulator, str(measured[-1].index))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    return accumulator


async def _run_sdk_async(
    plan: CellPlan,
    run_dir: Path,
    partitions: CorePartitions,
    *,
    tls: TlsFixture | None,
    timer_pair_cost_ns: int = 0,
) -> McpMessageAccumulator:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    from mcp.client.stdio import StdioServerParameters, stdio_client

    warmup, measured = split_warmup_measured(plan)
    accumulator = McpMessageAccumulator("client", mode=plan.coordinates.mode)
    accumulator.record_sdk_coverage(
        coverage_record(
            implementation="reference_sdk",
            sdk_version=importlib.metadata.version("mcp"),
        )
    )
    accumulator.begin_setup(metadata={"implementation": "reference_sdk"})
    wire_dir = run_dir / "wire"

    async def exercise(session: Any) -> None:
        await session.initialize()
        await session.list_tools()
        _end_setup(accumulator)
        for step in warmup:
            await session.call_tool(
                step.tool_name,
                {"schema_id": step.schema_id, "payload": "x" * step.payload_bytes},
            )
        accumulator.begin_endpoint(metadata={"pid": os.getpid()})
        for step in measured:
            await _record_sdk_call(
                accumulator,
                session,
                step,
                wire_dir=wire_dir,
                timer_pair_cost_ns=timer_pair_cost_ns,
                run_dir=run_dir,
            )
        _finish_client(accumulator, str(measured[-1].index))

    if plan.coordinates.transport == "stdio":
        config_path = _server_config(plan, run_dir, partitions, tls=None, port=None)
        command = _server_command(config_path, partitions.server_cpus)
        parameters = StdioServerParameters(command=command[0], args=command[1:])
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams) as session:
                await exercise(session)
        return accumulator

    port = _free_port()
    config_path = _server_config(plan, run_dir, partitions, tls=tls, port=port)
    stdout_path = run_dir / "server" / "stdout.log"
    stderr_path = run_dir / "server" / "stderr.log"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            _server_command(config_path, partitions.server_cpus),
            cwd=REPO_ROOT,
            stdout=stdout,
            stderr=stderr,
        )
        try:
            _wait_for_port(process, port)
            scheme = "https" if tls else "http"
            url = f"{scheme}://127.0.0.1:{port}/sse"
            kwargs: dict[str, Any] = {}
            if tls:
                import httpx

                def factory(
                    headers: dict[str, str] | None = None,
                    timeout: httpx.Timeout | None = None,
                    auth: httpx.Auth | None = None,
                ) -> httpx.AsyncClient:
                    return httpx.AsyncClient(
                        headers=headers,
                        timeout=timeout,
                        auth=auth,
                        verify=os.fspath(tls.ca_cert_path),
                    )

                kwargs["httpx_client_factory"] = factory
            async with sse_client(url, **kwargs) as streams:
                async with ClientSession(*streams) as session:
                    await exercise(session)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    return accumulator


async def _record_sdk_call(
    accumulator: McpMessageAccumulator,
    session: Any,
    step: Any,
    *,
    wire_dir: Path | None,
    timer_pair_cost_ns: int = 0,
    run_dir: Path | None = None,
) -> Any:
    """Measure one SDK tool call with gap decomposition (authenticity Axis 4a).

    Unlike the pre-v10 path, ``session.call_tool`` is *not* wrapped in a single
    MSG_SERIAL timer that would absorb the entire interior. Harness-owned
    SERIAL/DISPATCH boundaries stay thin; uncovered SDK interior becomes the
    gap parent and is decomposed via ``build_gap_decomposition``.
    """

    from .gap_measure import build_gap_decomposition, gap_session
    from .gap_split import GAP_DECOMPOSITION_KEY

    message_id = str(step.index)
    accumulator.begin_message(message_id)
    try:
        if accumulator.mode == "full":
            cpu_start = time.thread_time_ns()
            json.loads(step.canonical_bytes(step.index + 1))
            cpu_ns = time.thread_time_ns() - cpu_start
            accumulator.book(
                McpCategory.MSG_VALIDATE,
                cpu_ns,
                message_id=message_id,
                wall_ns=cpu_ns,
                provenance="full_observer_prevalidation",
            )
        boundary_cpu_start = time.thread_time_ns()
        boundary_wall_start = time.perf_counter_ns()
        arguments = {
            "schema_id": step.schema_id,
            "payload": "x" * step.payload_bytes,
        }
        with gap_session(
            message_id,
            timer_pair_cost_ns=timer_pair_cost_ns,
            run_dir=run_dir,
            boundary_cpu_start=boundary_cpu_start,
            boundary_wall_start=boundary_wall_start,
        ) as gap:
            gap.mark_boundary("pre_serial")
            with mcp_timed(
                McpCategory.MSG_SERIAL,
                accumulator=accumulator,
                message_id=message_id,
                bytes_out=step.payload_bytes,
                provenance="harness_sdk_boundary",
            ):
                # Thin harness boundary: copy args for the SDK call without
                # wrapping the await (which would absorb the uncovered interior).
                call_args = dict(arguments)
            gap.mark_boundary("serial_to_transport")
            # Uncovered SDK interior (event loop + transport + SDK parse).
            result = await session.call_tool(step.tool_name, call_args)
            gap.mark_boundary("transport_to_serial")
            gap.mark_boundary("serial_to_dispatch")
            with mcp_timed(
                McpCategory.MSG_DISPATCH,
                accumulator=accumulator,
                message_id=message_id,
                provenance="harness_sdk_boundary",
            ):
                payload = result
            gap.mark_boundary("post_dispatch")

            boundary_cpu_ns = max(0, time.thread_time_ns() - boundary_cpu_start)
            boundary_wall_ns = max(0, time.perf_counter_ns() - boundary_wall_start)
            nested_cpu_ns = accumulator.message_booked_cpu_ns(message_id)
            gap_cpu = max(0, boundary_cpu_ns - nested_cpu_ns)
            if gap_cpu:
                accumulator.book(
                    McpCategory.MSG_DISPATCH,
                    gap_cpu,
                    message_id=message_id,
                    wall_ns=gap_cpu,
                    provenance="harness_sdk_uncovered_interior",
                )
            if accumulator.category_hooks_enabled:
                from .contracts import load_protocol

                precedence = (
                    load_protocol()
                    .get("audit", {})
                    .get("gap_split_precedence")
                    or None
                )
                decomp = build_gap_decomposition(
                    gap_cpu if gap_cpu else 0,
                    gap,
                    precedence=precedence,
                )
                if run_dir is not None and decomp.get("overlap_resolutions"):
                    overlap_dir = Path(run_dir) / "gap_overlaps"
                    overlap_dir.mkdir(parents=True, exist_ok=True)
                    (overlap_dir / f"{message_id}.json").write_text(
                        json.dumps(decomp["overlap_resolutions"], indent=2) + "\n",
                        encoding="utf-8",
                    )
                accumulator.record_message_diagnostic(
                    message_id, GAP_DECOMPOSITION_KEY, decomp
                )

        nested_cpu_ns = accumulator.message_booked_cpu_ns(message_id)
        accumulator.record_message_diagnostic(
            message_id, "client_call_boundary_ns", boundary_cpu_ns
        )
        accumulator.record_message_diagnostic(
            message_id, "client_call_boundary_wall_ns", boundary_wall_ns
        )
        accumulator.record_message_diagnostic(
            message_id, "client_nested_cpu_ns", nested_cpu_ns
        )
        accumulator.book_wait(
            "transport_blocked",
            max(0, boundary_wall_ns - boundary_cpu_ns),
            message_id=message_id,
            provenance="client_call_wall_minus_thread_cpu",
        )
        return payload
    finally:
        accumulator.end_message(message_id)
        accumulator.record_canonical_hash(plan_hash(step))


@contextmanager
def _tls_for(plan: CellPlan) -> Iterator[TlsFixture | None]:
    if plan.coordinates.transport == "http_sse_tls_on":
        fixture = get_run_tls_fixture()
        if fixture is None:
            raise AdmissionError(
                "TLS fixture must be scoped to the run root for http_sse_tls_on cells"
            )
        yield fixture
    else:
        yield None


def _wait_for_server_result(path: Path) -> dict[str, Any]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        time.sleep(0.02)
    raise TimeoutError(f"server did not write endpoint ledger: {path}")


def execute_cell(plan: CellPlan, run_dir: Path) -> Mapping[str, Any]:
    """Execute one cell without substituting implementations or endpoints."""

    if plan.coordinates.transport == "http_stream":
        raise AdmissionError(
            "Streamable HTTP is conditional and has not passed this harness smoke"
        )
    publication = os.environ.get("MCP_TAX_PUBLICATION") == "1"
    partitions = _partitions(publication)
    preflight = _preflight(publication, partitions)
    from .gap_measure import microbench_timer_pair_ns

    timer_bench = microbench_timer_pair_ns()
    timer_pair_cost_ns = int(timer_bench["timer_pair_cost_ns"])
    set_current_affinity(partitions.client_cpus)
    with _tls_for(plan) as tls:
        if plan.coordinates.implementation == "raw_jsonrpc":
            client_accumulator = _run_raw(
                plan,
                run_dir,
                partitions,
                tls=tls,
                timer_pair_cost_ns=timer_pair_cost_ns,
            )
        elif plan.coordinates.implementation == "reference_sdk":
            from .gap_measure import instrumented_asyncio_loop

            # GapSelectorLoop books ready-queue drain into mechanism (a).
            with instrumented_asyncio_loop():
                client_accumulator = asyncio.run(
                    _run_sdk_async(
                        plan,
                        run_dir,
                        partitions,
                        tls=tls,
                        timer_pair_cost_ns=timer_pair_cost_ns,
                    )
                )
        else:
            raise AdmissionError(
                f"unsupported implementation {plan.coordinates.implementation!r}"
            )
        server_result = _wait_for_server_result(run_dir / "server" / "result.json")
        core_pins = {
            "os_analysis": sorted(partitions.os_cpus),
            "client": sorted(partitions.client_cpus),
            "server": sorted(partitions.server_cpus),
        }
        manifest = build_manifest(
            plan,
            repo_root=REPO_ROOT,
            core_pins=core_pins,
            sdk_lock_path=SDK_LOCK,
            cert_path=tls.server_cert_path if tls else None,
            software={
                "python": sys.version.split()[0],
                "dependencies": preflight["installed"],
                "preflight": preflight["preflight"],
                "tls": tls.public_metadata() if tls else None,
                "instrumentation": {
                    "timer_pair_cost_ns": timer_pair_cost_ns,
                    "timer_pair_microbench": timer_bench,
                },
            },
            git=preflight["git"],
            result_validity=(
                "protocol_microbenchmark" if publication else "debug_only"
            ),
        )
        return {
            "client": client_accumulator.to_dict(),
            "server": server_result,
            "manifest": manifest,
        }
