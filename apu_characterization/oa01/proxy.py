"""Transparent OpenAI-compatible byte-logging proxy for OA-01.

The proxy never edits a request body or response body. It records exact bodies
as base64, relays provider bytes, and normalizes usage only in a derived field.
Authorization values are hashed rather than archived.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import http.client
import json
import os
import ssl
import threading
import time
import urllib.parse
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping

from apu_characterization.oa01.schema import ApiBoundaryRecord, UsageRecord

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "gpt-4.1": {"input": 2.0, "cached_input": 0.5, "output": 8.0},
    "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.6},
}


def _json_or_none(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def _body_for_json(body: bytes, headers: Mapping[str, str]) -> bytes:
    """Decode Content-Encoding for JSON/SSE parsing only.

    Wire bytes remain archived unchanged; this helper never mutates the relayed
    response body.
    """
    encoding = (_header_value(headers, "Content-Encoding") or "").lower().strip()
    if encoding in {"gzip", "x-gzip"} or body[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(body)
        except OSError:
            return body
    if encoding == "deflate":
        try:
            return zlib.decompress(body)
        except zlib.error:
            try:
                return zlib.decompress(body, -zlib.MAX_WBITS)
            except zlib.error:
                return body
    return body


def _sse_final_json(body: bytes) -> Any:
    final: Any = None
    for raw_line in body.decode("utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if value.get("usage") or value.get("type") in {
            "response.completed",
            "response.done",
        }:
            final = value
    return final


def _usage_from_response(value: Any) -> UsageRecord:
    if not isinstance(value, Mapping):
        return UsageRecord()
    usage = value.get("usage")
    if not usage and isinstance(value.get("response"), Mapping):
        usage = value["response"].get("usage")
    return UsageRecord.from_provider(usage if isinstance(usage, Mapping) else None)


def estimate_cost_usd(
    model_id: str,
    usage: UsageRecord,
    pricing: Mapping[str, Mapping[str, float]] = DEFAULT_PRICING,
) -> tuple[float, list[str]]:
    normalized = model_id.split("/", 1)[-1]
    rate = pricing.get(normalized)
    if rate is None:
        return 0.0, ["pricing_model_unknown"]
    cached = min(usage.input_tokens, max(0, usage.cached_tokens))
    uncached = max(0, usage.input_tokens - cached)
    cost = (
        uncached * float(rate["input"])
        + cached * float(rate["cached_input"])
        + usage.output_tokens * float(rate["output"])
    ) / 1_000_000.0
    return cost, []


def _safe_headers(headers: Mapping[str, str]) -> dict[str, str]:
    safe: dict[str, str] = {}
    for name, value in headers.items():
        if name.lower() in {"authorization", "api-key", "x-api-key"}:
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
            safe[name] = f"sha256:{digest}"
        else:
            safe[name] = value
    return safe


class BoundaryLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Always create the archive file so subject failures before the first
        # upstream call still leave a valid empty boundary log.
        self.path.touch(exist_ok=True)
        self._lock = threading.Lock()

    def append(self, record: ApiBoundaryRecord) -> None:
        line = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        with self._lock, self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())


class OA01ProxyServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        upstream_base: str,
        log_path: Path,
        trajectory_id: str,
        pricing: Mapping[str, Mapping[str, float]] = DEFAULT_PRICING,
        on_record: Callable[[ApiBoundaryRecord], None] | None = None,
    ) -> None:
        parsed = urllib.parse.urlsplit(upstream_base)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"invalid upstream base: {upstream_base}")
        self.upstream = parsed
        self.boundary_log = BoundaryLog(log_path)
        self.trajectory_id = trajectory_id
        self.pricing = pricing
        self.on_record = on_record
        self._index_lock = threading.Lock()
        self._call_index = 0
        super().__init__(address, OA01ProxyHandler)

    def next_call_index(self) -> int:
        with self._index_lock:
            value = self._call_index
            self._call_index += 1
            return value


class OA01ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: OA01ProxyServer

    def log_message(self, format: str, *args: Any) -> None:
        return None

    def do_POST(self) -> None:
        self._relay()

    def do_GET(self) -> None:
        self._relay()

    def _relay(self) -> None:
        received_ns = time.time_ns()
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        request_body = self.rfile.read(content_length) if content_length else b""
        request_json = _json_or_none(request_body)
        call_index = self.server.next_call_index()
        call_id = f"{self.server.trajectory_id}-call-{call_index:04d}-{uuid.uuid4().hex[:8]}"
        upstream_headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in HOP_BY_HOP | {"host", "content-length"}
        }
        if request_body:
            upstream_headers["Content-Length"] = str(len(request_body))

        upstream_path = self.path
        if self.server.upstream.path and self.server.upstream.path != "/":
            prefix = self.server.upstream.path.rstrip("/")
            if not upstream_path.startswith(prefix + "/"):
                upstream_path = prefix + "/" + upstream_path.lstrip("/")

        port = self.server.upstream.port
        if self.server.upstream.scheme == "https":
            connection: http.client.HTTPConnection = http.client.HTTPSConnection(
                self.server.upstream.hostname,
                port or 443,
                timeout=3600,
                context=ssl.create_default_context(),
            )
        else:
            connection = http.client.HTTPConnection(
                self.server.upstream.hostname, port or 80, timeout=3600
            )

        send_ns = time.time_ns()
        response_headers_ns = send_ns
        first_body_ns = send_ns
        last_body_ns = send_ns
        response_status = 502
        response_headers: dict[str, str] = {}
        response_body = bytearray()
        flags: list[str] = []
        headers_relayed = False
        try:
            connection.request(
                self.command,
                upstream_path,
                body=request_body if request_body else None,
                headers=upstream_headers,
            )
            upstream_response = connection.getresponse()
            response_headers_ns = time.time_ns()
            response_status = upstream_response.status
            response_headers = dict(upstream_response.getheaders())
            self.send_response(response_status, upstream_response.reason)
            for name, value in upstream_response.getheaders():
                lower = name.lower()
                if lower in HOP_BY_HOP:
                    continue
                if lower == "content-length" and upstream_response.chunked:
                    continue
                self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()
            headers_relayed = True

            first = True
            while True:
                # read1 returns currently available bytes; read(size) may wait for
                # size bytes and would destroy first-byte timing on SSE streams.
                chunk = upstream_response.read1(65_536)
                if not chunk:
                    break
                now_ns = time.time_ns()
                if first:
                    first_body_ns = now_ns
                    first = False
                last_body_ns = now_ns
                response_body.extend(chunk)
                self.wfile.write(chunk)
                self.wfile.flush()
            if first:
                first_body_ns = time.time_ns()
                last_body_ns = first_body_ns
        except Exception as exc:
            flags.append(f"proxy_upstream_error:{type(exc).__name__}")
            error_body = json.dumps(
                {"error": {"type": "oa01_proxy_upstream_error", "message": str(exc)}}
            ).encode("utf-8")
            if not headers_relayed and not self.wfile.closed:
                try:
                    response_status = 502
                    response_headers = {
                        "Content-Type": "application/json",
                        "Content-Length": str(len(error_body)),
                    }
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(error_body)))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(error_body)
                    self.wfile.flush()
                    response_body = bytearray(error_body)
                except OSError:
                    pass
            first_body_ns = last_body_ns = time.time_ns()
        finally:
            connection.close()
            self.close_connection = True

        relay_complete_ns = time.time_ns()
        stream_requested = bool(
            isinstance(request_json, Mapping) and request_json.get("stream", False)
        )
        decoded_body = _body_for_json(bytes(response_body), response_headers)
        response_json = (
            _sse_final_json(decoded_body)
            if stream_requested
            else _json_or_none(decoded_body)
        )
        usage = _usage_from_response(response_json)
        model_id = (
            str(request_json.get("model", "unknown"))
            if isinstance(request_json, Mapping)
            else "unknown"
        )
        if response_status >= 400:
            # Error responses (rate limits, upstream faults) legitimately omit
            # usage; keep them as raw attempts without failing usage audits.
            if not usage.raw:
                flags.append("usage_absent_error_response")
        elif not usage.raw:
            flags.append("usage_missing")
        else:
            details = usage.raw.get("prompt_tokens_details") or usage.raw.get(
                "input_tokens_details"
            )
            if not isinstance(details, Mapping) or "cached_tokens" not in details:
                flags.append("cached_tokens_field_missing")
        cost, cost_flags = estimate_cost_usd(model_id, usage, self.server.pricing)
        flags.extend(cost_flags)
        record = ApiBoundaryRecord(
            schema_version="oa01_api_boundary_v1",
            trajectory_id=self.server.trajectory_id,
            call_id=call_id,
            call_index=call_index,
            method=self.command,
            path=self.path,
            request_headers=_safe_headers(dict(self.headers.items())),
            request_body_b64=base64.b64encode(request_body).decode("ascii"),
            request_json=request_json,
            response_status=response_status,
            response_headers=_safe_headers(response_headers),
            response_body_b64=base64.b64encode(bytes(response_body)).decode("ascii"),
            response_json=response_json,
            request_received_unix_ns=received_ns,
            upstream_send_unix_ns=send_ns,
            response_headers_unix_ns=response_headers_ns,
            response_first_body_byte_unix_ns=first_body_ns,
            response_last_body_byte_unix_ns=last_body_ns,
            response_relay_complete_unix_ns=relay_complete_ns,
            stream_requested=stream_requested,
            model_id=model_id,
            usage=usage,
            cost_usd=cost,
            flags=flags,
        )
        self.server.boundary_log.append(record)
        if self.server.on_record is not None:
            self.server.on_record(record)


def serve(
    *,
    host: str,
    port: int,
    upstream_base: str,
    log_path: Path,
    trajectory_id: str,
) -> None:
    server = OA01ProxyServer(
        (host, port),
        upstream_base=upstream_base,
        log_path=log_path,
        trajectory_id=trajectory_id,
    )
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--upstream", default="https://api.openai.com")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--trajectory-id", required=True)
    args = parser.parse_args(argv)
    serve(
        host=args.host,
        port=args.port,
        upstream_base=args.upstream,
        log_path=args.log,
        trajectory_id=args.trajectory_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

