"""Executable, separately accounted MCP server process for MCP-01."""

from __future__ import annotations

import argparse
import asyncio
import http.server
import json
import os
import ssl
import time
from pathlib import Path
from typing import Any, Mapping

from .accum import McpMessageAccumulator, ScopeObservation
from .contracts import CellCoordinates, canonical_json_bytes, sha256_bytes
from .implementations.raw_jsonrpc import RawJsonRpcServer
from .instrument import mcp_timed
from .taxonomy import McpCategory
from .testbench import ControlledToolRegistry
from .transports.http_sse import frame_sse


class MeasuredServerEndpoint:
    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = config
        plan = config["plan"]
        coordinates = CellCoordinates(**plan["coordinates"])
        self.steps = list(plan["steps"])
        self.warmup_messages = int(plan["warmup_messages"])
        self.measured_messages = int(plan["measured_messages"])
        self.registry = ControlledToolRegistry(
            tool_count=coordinates.tool_count,
            schema_id=coordinates.schema_profile,
            payload_bytes=coordinates.payload_bytes,
            synthetic_delay_ns=int(self.steps[0]["synthetic_delay_ns"]),
        )
        self.raw = RawJsonRpcServer(self.registry)
        self.accumulator = McpMessageAccumulator(
            process_role="server", mode=coordinates.mode
        )
        self.accumulator.begin_setup(metadata={"implementation": coordinates.implementation})
        self.call_index = 0
        self._setup_finished = False
        self._endpoint_active = False
        self._saved = False
        self.output = Path(config["server_output"])

    def _finish_setup(self) -> None:
        if self._setup_finished:
            return
        observation = self.accumulator.end_setup()
        self.accumulator.book(
            McpCategory.SESSION_SETUP,
            observation.process_cpu_ns,
            wall_ns=observation.wall_ns,
            provenance="server_setup_process_clock",
        )
        self._setup_finished = True

    def _begin_measured(self) -> None:
        if not self._endpoint_active:
            self.accumulator.begin_endpoint(
                metadata={
                    "measurement_scope": "measured_messages_only",
                    "pid": os.getpid(),
                }
            )
            self._endpoint_active = True

    def _verify_call(self, name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if self.call_index >= len(self.steps):
            raise RuntimeError("server received more tool calls than the cell plan")
        step = self.steps[self.call_index]
        if (
            name != step["tool_name"]
            or arguments.get("schema_id") != step["schema_id"]
            or arguments.get("payload") != "x" * int(step["payload_bytes"])
        ):
            raise RuntimeError(
                f"tool call {self.call_index} does not match the frozen cell plan"
            )
        return step

    def raw_handle(self, payload: bytes) -> bytes | None:
        preview = json.loads(payload)
        if preview.get("method") != "tools/call":
            return self.raw.handle_bytes(payload)
        self._finish_setup()
        params = preview.get("params") or {}
        step = self._verify_call(str(params.get("name")), params.get("arguments") or {})
        measured = self.call_index >= self.warmup_messages
        self.call_index += 1
        if not measured:
            return self.raw.handle_bytes(payload)

        self._begin_measured()
        message_id = str(step["index"])
        self.accumulator.begin_message(message_id)
        with mcp_timed(
            McpCategory.MSG_SERIAL,
            accumulator=self.accumulator,
            message_id=message_id,
        ):
            request = json.loads(payload)
        with mcp_timed(
            McpCategory.MSG_VALIDATE,
            accumulator=self.accumulator,
            message_id=message_id,
        ):
            params = request["params"]
            prepared = self.registry.prepare(params["name"], params["arguments"])
        tool_wall_start = time.perf_counter_ns()
        outcome = self.registry.execute(prepared)
        tool_wall_ns = time.perf_counter_ns() - tool_wall_start
        if outcome.synthetic_delay_ns:
            self.accumulator.book_wait(
                "synthetic_tool_delay",
                min(tool_wall_ns, outcome.synthetic_delay_ns),
                message_id=message_id,
                provenance="controlled_tool_delay",
            )
        with mcp_timed(
            McpCategory.MSG_DISPATCH,
            accumulator=self.accumulator,
            message_id=message_id,
        ):
            response = {
                "jsonrpc": "2.0",
                "id": request["id"],
                "result": outcome.as_mcp_result(),
            }
        with mcp_timed(
            McpCategory.MSG_SERIAL,
            accumulator=self.accumulator,
            message_id=message_id,
        ):
            encoded = canonical_json_bytes(response)
        self.accumulator.end_message(message_id)
        self._record_and_maybe_save(step)
        return encoded

    def sdk_call(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        self._finish_setup()
        step = self._verify_call(name, arguments)
        measured = self.call_index >= self.warmup_messages
        self.call_index += 1
        if not measured:
            return self.registry.call(name, dict(arguments)).as_mcp_result()

        self._begin_measured()
        message_id = str(step["index"])
        self.accumulator.begin_message(message_id)
        with mcp_timed(
            McpCategory.MSG_VALIDATE,
            accumulator=self.accumulator,
            message_id=message_id,
        ):
            prepared = self.registry.prepare(name, dict(arguments))
        tool_wall_start = time.perf_counter_ns()
        outcome = self.registry.execute(prepared)
        tool_wall_ns = time.perf_counter_ns() - tool_wall_start
        if outcome.synthetic_delay_ns:
            self.accumulator.book_wait(
                "synthetic_tool_delay",
                min(tool_wall_ns, outcome.synthetic_delay_ns),
                message_id=message_id,
                provenance="controlled_tool_delay",
            )
        with mcp_timed(
            McpCategory.MSG_DISPATCH,
            accumulator=self.accumulator,
            message_id=message_id,
            provenance="official_sdk_tool_callback",
        ):
            result = outcome.as_mcp_result()
        self.accumulator.end_message(message_id)
        self._record_and_maybe_save(step)
        return result

    def _record_and_maybe_save(self, step: Mapping[str, Any]) -> None:
        digest = sha256_bytes(
            canonical_json_bytes(
                {
                    "jsonrpc": "2.0",
                    "id": int(step["index"]) + 1,
                    "method": step["method"],
                    "params": {
                        "name": step["tool_name"],
                        "arguments": {
                            "schema_id": step["schema_id"],
                            "payload": "x" * int(step["payload_bytes"]),
                        },
                    },
                }
            )
        )
        self.accumulator.record_canonical_hash(digest)
        if len(self.accumulator.canonical_hashes) == self.measured_messages:
            self._finish_endpoint()

    def _finish_endpoint(self) -> None:
        if self._saved:
            return
        observation = self.accumulator.end_endpoint(
            metadata={"canonical_hashes": list(self.accumulator.canonical_hashes)}
        )
        setup_cpu = self.accumulator.setup_totals().cpu_ns
        setup_wall = self.accumulator.setup_totals().wall_ns
        message_cpu = sum(
            obs.process_cpu_ns for obs in self.accumulator.messages.values()
        )
        message_wall = sum(
            obs.wall_ns for obs in self.accumulator.messages.values()
        )
        effective_process_cpu = setup_cpu + message_cpu
        effective_wall_ns = setup_wall + message_wall
        if effective_process_cpu > 0 or effective_wall_ns > 0:
            observation = ScopeObservation(
                start_wall_ns=observation.start_wall_ns,
                end_wall_ns=observation.end_wall_ns,
                process_cpu_ns=effective_process_cpu,
                wall_ns=effective_wall_ns,
                thread_schedstat_cpu_ns=observation.thread_schedstat_cpu_ns,
                metadata=observation.metadata,
            )
            self.accumulator.endpoint_observation = observation
        accounted_cpu = (
            self.accumulator.setup_totals().cpu_ns
            + sum(totals.cpu_ns for totals in self.accumulator.by_key.values())
        )
        accounted_wall = (
            setup_wall
            + sum(totals.wall_ns for totals in self.accumulator.by_key.values())
        )
        wait_wall = sum(totals.wall_ns for totals in self.accumulator.waits_by_key.values())
        last_message = str(self.steps[-1]["index"])
        endpoint_residual = max(0, observation.process_cpu_ns - accounted_cpu)
        if endpoint_residual:
            self.accumulator.book(
                McpCategory.RESIDUAL,
                endpoint_residual,
                message_id=last_message,
                wall_ns=max(0, observation.wall_ns - accounted_wall - wait_wall),
                provenance="endpoint_reconciliation",
            )
        self.accumulator.save(self.output)
        self._saved = True


def _make_sdk_server(endpoint: MeasuredServerEndpoint) -> Any:
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(
        "mcp-tax-reference-sdk",
        host="127.0.0.1",
        port=int(endpoint.config.get("port") or 8000),
        log_level="ERROR",
    )
    for definition in endpoint.registry.definitions:
        name = definition.name

        def factory(tool_name: str) -> Any:
            async def controlled_tool(schema_id: str, payload: str) -> dict[str, Any]:
                return endpoint.sdk_call(
                    tool_name, {"schema_id": schema_id, "payload": payload}
                )

            controlled_tool.__name__ = tool_name
            return controlled_tool

        server.tool(name=name, description=definition.description)(factory(name))
    return server


def _serve_raw_stdio(endpoint: MeasuredServerEndpoint) -> None:
    import sys

    for line in sys.stdin.buffer:
        request = line.rstrip(b"\r\n")
        response = endpoint.raw_handle(request)
        if response is not None:
            sys.stdout.buffer.write(response + b"\n")
            sys.stdout.buffer.flush()


def _serve_raw_http(endpoint: MeasuredServerEndpoint) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length)
            response = endpoint.raw_handle(payload)
            if response is None:
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = frame_sse(response)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *args: Any) -> None:
            return

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", int(endpoint.config["port"])), Handler
    )
    if endpoint.config.get("tls"):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(
            endpoint.config["server_cert"], endpoint.config["server_key"]
        )
        server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


def _serve_sdk_http(endpoint: MeasuredServerEndpoint) -> None:
    import uvicorn

    server = _make_sdk_server(endpoint)
    config: dict[str, Any] = {
        "app": server.sse_app(),
        "host": "127.0.0.1",
        "port": int(endpoint.config["port"]),
        "log_level": "error",
    }
    if endpoint.config.get("tls"):
        config.update(
            ssl_certfile=endpoint.config["server_cert"],
            ssl_keyfile=endpoint.config["server_key"],
        )
    uvicorn.run(**config)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    server_cores = config.get("server_cores") or []
    if server_cores and hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, set(int(cpu) for cpu in server_cores))
    endpoint = MeasuredServerEndpoint(config)
    implementation = config["plan"]["coordinates"]["implementation"]
    transport = config["plan"]["coordinates"]["transport"]
    if implementation == "raw_jsonrpc":
        if transport == "stdio":
            _serve_raw_stdio(endpoint)
        else:
            _serve_raw_http(endpoint)
    else:
        if transport == "stdio":
            asyncio.run(_make_sdk_server(endpoint).run_stdio_async())
        else:
            _serve_sdk_http(endpoint)


if __name__ == "__main__":
    main()
