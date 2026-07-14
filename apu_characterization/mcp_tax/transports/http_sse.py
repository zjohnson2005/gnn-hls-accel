"""Raw HTTP POST + SSE transport with explicit socket and TLS seams."""

from __future__ import annotations

import http.client
import http.server
import socket
import ssl
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from ..transport_instrument import TransportInstrumentation
from .base import (
    DirectionTrace,
    TimingTrace,
    TransportError,
    TransportResult,
    TransportTrace,
    require_logical_message,
)

_HEADER_LIMIT = 64 * 1024


def frame_sse(logical_message: bytes) -> bytes:
    """Encode one logical message as one deterministic SSE data event."""
    message = require_logical_message(logical_message)
    if b"\r" in message or b"\n" in message:
        raise ValueError("logical SSE message must not contain raw newlines")
    return b"data: " + message + b"\n\n"


def unframe_sse(body: bytes) -> bytes:
    """Decode exactly one SSE data event, rejecting partial measurements."""
    events: list[list[bytes]] = []
    current: list[bytes] = []
    for raw_line in body.replace(b"\r\n", b"\n").split(b"\n"):
        if raw_line == b"":
            if current:
                events.append(current)
                current = []
            continue
        if raw_line.startswith(b":"):
            continue
        field, separator, value = raw_line.partition(b":")
        if field == b"data" and separator:
            current.append(value[1:] if value.startswith(b" ") else value)
    if current:
        events.append(current)
    if len(events) != 1 or not events[0]:
        raise TransportError(f"expected one SSE data event, received {len(events)}")
    return b"\n".join(events[0])


def _host_header(host: str, port: int, scheme: str) -> str:
    display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    default = 443 if scheme == "https" else 80
    return display_host if port == default else f"{display_host}:{port}"


def frame_http_post(
    *,
    host: str,
    port: int,
    scheme: str,
    target: str,
    logical_request: bytes,
) -> bytes:
    """Build the exact HTTP/1.1 bytes written to the socket."""
    request = require_logical_message(logical_request)
    headers = (
        f"POST {target} HTTP/1.1\r\n"
        f"Host: {_host_header(host, port, scheme)}\r\n"
        "Content-Type: application/json\r\n"
        "Accept: text/event-stream\r\n"
        f"Content-Length: {len(request)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")
    return headers + request


def _decode_chunked(body: bytes) -> bytes:
    output = bytearray()
    cursor = 0
    while True:
        line_end = body.find(b"\r\n", cursor)
        if line_end < 0:
            raise TransportError("truncated HTTP chunk header")
        size_text = body[cursor:line_end].split(b";", 1)[0]
        try:
            size = int(size_text, 16)
        except ValueError as exc:
            raise TransportError("invalid HTTP chunk size") from exc
        cursor = line_end + 2
        if size == 0:
            return bytes(output)
        end = cursor + size
        if end + 2 > len(body) or body[end : end + 2] != b"\r\n":
            raise TransportError("truncated HTTP chunk body")
        output.extend(body[cursor:end])
        cursor = end + 2


def parse_http_response(wire_response: bytes) -> tuple[int, dict[str, str], bytes]:
    """Separate HTTP framing from the logical SSE response."""
    head_end = wire_response.find(b"\r\n\r\n")
    if head_end < 0 or head_end > _HEADER_LIMIT:
        raise TransportError("missing or oversized HTTP response headers")
    lines = wire_response[:head_end].split(b"\r\n")
    try:
        status = int(lines[0].split(b" ", 2)[1])
    except (IndexError, ValueError) as exc:
        raise TransportError("invalid HTTP status line") from exc
    headers: dict[str, str] = {}
    for line in lines[1:]:
        key, separator, value = line.partition(b":")
        if not separator:
            raise TransportError("malformed HTTP response header")
        headers[key.decode("ascii").lower()] = value.decode("latin-1").strip()
    body = wire_response[head_end + 4 :]
    if headers.get("transfer-encoding", "").lower() == "chunked":
        body = _decode_chunked(body)
    elif "content-length" in headers:
        try:
            expected = int(headers["content-length"])
        except ValueError as exc:
            raise TransportError("invalid HTTP content length") from exc
        if len(body) != expected:
            raise TransportError(
                f"incomplete HTTP body: expected {expected}, received {len(body)}"
            )
    return status, headers, body


class HttpSseTransport:
    """One POST/SSE exchange per connection, plain or CA-verified local TLS.

    Connection semantics (publication-relevant): each ``exchange()`` performs
    ``create_connection``, optional TLS handshake, send/recv, then close, with
    ``Connection: close`` on the request. There is no persistent/reused socket.
    Per-message ``transport_tls_handshake`` CPU is therefore a connection-pattern
    tax, not reused-session record-encryption cost.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        ssl_context: ssl.SSLContext | None = None,
        timeout_s: float = 10.0,
        clock_ns: Callable[[], int] = time.perf_counter_ns,
        max_response_bytes: int = 32 * 1024 * 1024,
    ) -> None:
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("endpoint must be an http:// or https:// URL")
        if parsed.username or parsed.password:
            raise ValueError("credentials are forbidden in MCP transport URLs")
        self.scheme = parsed.scheme
        self.host = parsed.hostname
        self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self.target = parsed.path or "/"
        if parsed.query:
            self.target += "?" + parsed.query
        if self.scheme == "https":
            if ssl_context is None:
                raise ValueError("https transport requires a CA-verifying SSL context")
            if (
                ssl_context.verify_mode != ssl.CERT_REQUIRED
                or not ssl_context.check_hostname
            ):
                raise ValueError("TLS context must require CA and hostname verification")
        elif ssl_context is not None:
            raise ValueError("plain HTTP transport must not receive an SSL context")
        self._ssl_context = ssl_context
        self._timeout_s = timeout_s
        self._clock_ns = clock_ns
        self._max_response_bytes = max_response_bytes
        self._instrumentation: TransportInstrumentation | None = None

    def bind_instrumentation(self, instrumentation: TransportInstrumentation | None) -> None:
        self._instrumentation = instrumentation

    def clear_instrumentation(self) -> None:
        self._instrumentation = None

    def exchange(self, logical_request: bytes) -> TransportResult:
        request = require_logical_message(logical_request)
        instr = self._instrumentation

        def _build_request() -> bytes:
            return frame_http_post(
                host=self.host,
                port=self.port,
                scheme=self.scheme,
                target=self.target,
                logical_request=request,
            )

        if instr is not None:
            wire_request = instr.frame(
                _build_request,
                bytes_out=len(request),
            )
            instr.persist_wire("request", wire_request)
            frame_request_ns = 0
        else:
            frame_start = self._clock_ns()
            wire_request = _build_request()
            frame_request_ns = max(0, self._clock_ns() - frame_start)

        setup_ns = 0
        tls_handshake_ns = 0
        write_ns = 0
        read_ns = 0
        frame_response_ns = 0

        def _connect_and_exchange() -> bytes:
            nonlocal setup_ns, tls_handshake_ns, write_ns, read_ns
            setup_start = self._clock_ns()
            raw_socket = socket.create_connection(
                (self.host, self.port), timeout=self._timeout_s
            )
            setup_ns = max(0, self._clock_ns() - setup_start)
            connection: socket.socket | ssl.SSLSocket = raw_socket
            try:
                if self.scheme == "https":
                    assert self._ssl_context is not None
                    connection = self._ssl_context.wrap_socket(
                        raw_socket,
                        server_hostname=self.host,
                        do_handshake_on_connect=False,
                    )
                    handshake_start = self._clock_ns()
                    connection.do_handshake()
                    tls_handshake_ns = max(0, self._clock_ns() - handshake_start)

                write_start = self._clock_ns()
                connection.sendall(wire_request)
                write_ns = max(0, self._clock_ns() - write_start)

                read_start = self._clock_ns()
                chunks: list[bytes] = []
                received = 0
                while True:
                    chunk = connection.recv(64 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > self._max_response_bytes:
                        raise TransportError("HTTP response exceeds configured maximum")
                    chunks.append(chunk)
                read_ns = max(0, self._clock_ns() - read_start)
            finally:
                connection.close()
            return b"".join(chunks)

        if instr is not None:

            def _connect() -> socket.socket:
                return socket.create_connection(
                    (self.host, self.port), timeout=self._timeout_s
                )

            raw_socket = instr.transport_cpu(_connect, provenance="transport_connect")
            connection: socket.socket | ssl.SSLSocket = raw_socket
            try:
                if self.scheme == "https":
                    assert self._ssl_context is not None

                    def _wrap_and_handshake() -> ssl.SSLSocket:
                        wrapped = self._ssl_context.wrap_socket(
                            raw_socket,
                            server_hostname=self.host,
                            do_handshake_on_connect=False,
                        )
                        wrapped.do_handshake()
                        return wrapped

                    connection = instr.tls_handshake(_wrap_and_handshake)
                instr.transport_cpu(
                    lambda: connection.sendall(wire_request),
                    bytes_out=len(wire_request),
                    provenance="transport_write",
                )

                def _recv_all() -> bytes:
                    chunks: list[bytes] = []
                    received = 0
                    while True:
                        chunk = connection.recv(64 * 1024)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > self._max_response_bytes:
                            raise TransportError(
                                "HTTP response exceeds configured maximum"
                            )
                        chunks.append(chunk)
                    return b"".join(chunks)

                wire_response = instr.transport_cpu(
                    _recv_all,
                    provenance="transport_read",
                )
            finally:
                # Close on the TRANSPORT timer so post-return buffer/teardown is
                # not left as untimed harness-owned code between TRANSPORT and FRAME.
                if instr is not None:
                    instr.transport_cpu(
                        connection.close,
                        provenance="transport_syscall_return",
                    )
                else:
                    connection.close()
        else:
            wire_response = _connect_and_exchange()

        def _parse_response() -> tuple[int, dict[str, str], bytes, bytes]:
            status, headers, sse_body = parse_http_response(wire_response)
            if status < 200 or status >= 300:
                raise TransportError(f"HTTP server returned status {status}")
            content_type = headers.get("content-type", "").split(";", 1)[0].strip()
            if content_type != "text/event-stream":
                raise TransportError(
                    f"expected text/event-stream, received {content_type!r}"
                )
            logical = unframe_sse(sse_body)
            return status, headers, sse_body, logical

        if instr is not None:
            status, headers, sse_body, response = instr.frame(
                _parse_response,
                bytes_in=len(wire_response),
            )
            instr.persist_wire("response", wire_response)
            frame_response_ns = 0
        else:
            parse_start = self._clock_ns()
            status, headers, sse_body, response = _parse_response()
            frame_response_ns = max(0, self._clock_ns() - parse_start)

        content_type = headers.get("content-type", "").split(";", 1)[0].strip()

        return TransportResult(
            response=response,
            trace=TransportTrace(
                transport=(
                    "http_sse_tls_on"
                    if self.scheme == "https"
                    else "http_sse_tls_off"
                ),
                request=DirectionTrace.from_message(
                    request, wire_bytes=len(wire_request)
                ),
                response=DirectionTrace.from_message(
                    response, wire_bytes=len(wire_response)
                ),
                timing=TimingTrace(
                    setup_ns=setup_ns,
                    tls_handshake_ns=tls_handshake_ns,
                    frame_request_ns=frame_request_ns,
                    write_ns=write_ns,
                    read_ns=read_ns,
                    frame_response_ns=frame_response_ns,
                ),
                metadata={
                    "http_status": status,
                    "content_type": content_type,
                    "tls_verified": self.scheme == "https",
                },
            ),
        )

    def send_notification(self, logical_request: bytes) -> None:
        """POST a notification and require an empty successful acknowledgement."""

        request = require_logical_message(logical_request)
        connection: http.client.HTTPConnection
        if self.scheme == "https":
            connection = http.client.HTTPSConnection(
                self.host,
                self.port,
                timeout=self._timeout_s,
                context=self._ssl_context,
            )
        else:
            connection = http.client.HTTPConnection(
                self.host, self.port, timeout=self._timeout_s
            )
        try:
            connection.request(
                "POST",
                self.target,
                body=request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
            )
            response = connection.getresponse()
            body = response.read()
            if response.status not in (200, 202, 204):
                raise TransportError(
                    f"HTTP notification returned status {response.status}"
                )
            if body:
                raise TransportError("JSON-RPC notification returned a response body")
        finally:
            connection.close()

    def close(self) -> None:
        """Connections are per-exchange, so there is no persistent socket."""

    def __enter__(self) -> "HttpSseTransport":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


@dataclass
class LocalSseServer:
    """Small stdlib fixture server used by integration tests and smoke runs."""

    handler: Callable[[bytes], bytes]
    ssl_context: ssl.SSLContext | None = None
    host: str = "127.0.0.1"
    path: str = "/mcp"

    def __post_init__(self) -> None:
        callback = self.handler
        expected_path = self.path

        class RequestHandler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
                if self.path != expected_path:
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    self.send_error(400)
                    return
                request = self.rfile.read(length)
                try:
                    response = callback(request)
                    body = frame_sse(response)
                except Exception:
                    self.send_error(500)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True

            def log_message(self, _format: str, *args: Any) -> None:
                return

        self._server = http.server.ThreadingHTTPServer((self.host, 0), RequestHandler)
        if self.ssl_context is not None:
            self._server.socket = self.ssl_context.wrap_socket(
                self._server.socket, server_side=True
            )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="mcp-tax-sse-server",
            daemon=True,
        )

    @property
    def endpoint(self) -> str:
        scheme = "https" if self.ssl_context is not None else "http"
        port = self._server.server_address[1]
        return f"{scheme}://{self.host}:{port}{self.path}"

    def start(self) -> "LocalSseServer":
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __enter__(self) -> "LocalSseServer":
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.close()

