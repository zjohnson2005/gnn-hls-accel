#!/usr/bin/env python3
"""Axis 5 follow-up: profile raw stdio transport_read at 512 KiB.

Counts os.read() syscalls on the stdout fd against the theoretical minimum
for a pipe (capacity-bounded reads + one final bytes assembly).
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apu_characterization.mcp_tax.contracts import canonical_json_bytes  # noqa: E402
from apu_characterization.mcp_tax.transports.stdio import StdioTransport  # noqa: E402

PAYLOAD = 524_288
PIPE_BUF_DEFAULT = 65536

SERVER = r"""
import json, sys
for line in sys.stdin.buffer:
    req = json.loads(line)
    payload = req["params"]["arguments"]["payload"]
    resp = {
        "jsonrpc": "2.0",
        "id": req["id"],
        "result": {
            "content": [{"type": "text", "text": payload}],
            "isError": False,
        },
    }
    raw = json.dumps(resp, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(raw + b"\n")
    sys.stdout.buffer.flush()
"""


def theoretical_min_reads(wire_bytes: int, pipe_capacity: int = PIPE_BUF_DEFAULT) -> int:
    if wire_bytes <= 0:
        return 0
    return max(1, (wire_bytes + pipe_capacity - 1) // pipe_capacity)


def build_request() -> bytes:
    return canonical_json_bytes(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "tool_0000",
                "arguments": {
                    "schema_id": "flat_5",
                    "payload": "x" * PAYLOAD,
                },
            },
        }
    )


def main() -> None:
    request = build_request()
    n_iters = 5
    results: list[dict] = []
    orig_os_read = os.read

    with StdioTransport([sys.executable, "-u", "-c", SERVER]) as transport:
        transport.exchange(request)  # warmup
        fd = transport._stdout_fd
        chunk = StdioTransport._READ_CHUNK

        for i in range(n_iters):
            counts: dict = {"calls": 0, "bytes": 0, "sizes": []}

            def tracked_read(read_fd: int, n: int, _fd: int = fd, _c: dict = counts):
                data = orig_os_read(read_fd, n)
                if read_fd == _fd:
                    _c["calls"] += 1
                    got = len(data) if data else 0
                    _c["bytes"] += got
                    _c["sizes"].append(got)
                return data

            os.read = tracked_read  # type: ignore[assignment]
            try:
                t0 = time.perf_counter_ns()
                result = transport.exchange(request)
                t1 = time.perf_counter_ns()
            finally:
                os.read = orig_os_read  # type: ignore[assignment]

            wire_in = result.trace.response.wire_bytes
            tmin = theoretical_min_reads(wire_in)
            sizes = counts["sizes"]
            results.append(
                {
                    "iter": i,
                    "wall_ms": (t1 - t0) / 1e6,
                    "wire_response_bytes": wire_in,
                    "read_syscalls": counts["calls"],
                    "read_bytes_sum": counts["bytes"],
                    "nonzero_chunks": len([s for s in sizes if s > 0]),
                    "read_size_median": statistics.median(sizes) if sizes else 0,
                    "read_size_max": max(sizes) if sizes else 0,
                    "read_chunk_cap": chunk,
                    "theoretical_min_syscalls": tmin,
                    "syscalls_over_min": counts["calls"] - tmin,
                    "at_or_near_minimum": counts["calls"] <= max(2 * tmin, tmin + 4),
                }
            )

    med_calls = statistics.median([r["read_syscalls"] for r in results])
    med_wire = statistics.median([r["wire_response_bytes"] for r in results])
    tmin = theoretical_min_reads(int(med_wire))
    med_chunk = statistics.median([r["read_size_median"] for r in results])
    byte_at_a_time = med_chunk <= 1
    highly_fragmented = med_calls > max(4 * tmin, tmin + 20)
    redundant = byte_at_a_time or highly_fragmented

    out = {
        "payload_bytes": PAYLOAD,
        "n_iters": n_iters,
        "read_impl": "os.read(fd, 65536) chunked _read_framed_line",
        "iters": results,
        "summary": {
            "median_read_syscalls": med_calls,
            "median_wire_response_bytes": med_wire,
            "theoretical_min_syscalls": tmin,
            "median_syscalls_over_min": med_calls - tmin,
            "median_read_size": med_chunk,
            "byte_at_a_time": byte_at_a_time,
            "highly_fragmented": highly_fragmented,
            "redundant_copies_or_syscalls": redundant,
            "verdict": (
                "REDUNDANT — exceeds theoretical minimum; fix read path"
                if redundant
                else "LEAN — at/near theoretical minimum for pipe capacity"
            ),
        },
    }
    out_path = (
        REPO / "apu_characterization" / "out" / "mcp_tax" / "stdio_512kib_read_profile.json"
    )
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
