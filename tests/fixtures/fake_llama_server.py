#!/usr/bin/env python3
"""Task BS test fixture: a stand-in for llama-server (b11559 CLI subset) for the runbook dry-run.

Accepts the runbook argv (-c, -ub, -ctk, -fa, --port, ...). Writes llama.cpp-style buffer lines to
stderr. If -c exceeds FAKE_LOAD_MAX it logs an allocation error and exits 1 (fail_load). Otherwise
it serves /health, /tokenize and /completion on 127.0.0.1; /completion returns HTTP 500 when the
prompt is longer than FAKE_PREFILL_MAX tokens (fail_prefill). Standard library only.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

K_BYTES = {"f16": 147456, "q8_0": 78336, "q4_0": 41472}


def arg(argv: list[str], flag: str, default: str) -> str:
    return argv[argv.index(flag) + 1] if flag in argv else default


def main() -> int:
    argv = sys.argv[1:]
    if "--version" in argv or "--list-devices" in argv:
        print("version: 0 (fake)")
        return 0
    n_ctx = int(arg(argv, "-c", "4096"))
    kv = arg(argv, "-ctk", "f16")
    port = int(arg(argv, "--port", "8091"))
    load_max = int(os.environ.get("FAKE_LOAD_MAX", "1000000000"))
    prefill_max = int(os.environ.get("FAKE_PREFILL_MAX", "1000000000"))
    err = sys.stderr
    print(
        "llama_model_load_from_file_impl: using device CUDA0 (Fake GPU) (0000:01:00.0) - 7800 MiB free",
        file=err,
    )
    print("load_tensors:        CUDA0 model buffer size =  2124.81 MiB", file=err)
    print("load_tensors:   CPU_Mapped model buffer size =   304.28 MiB", file=err)
    if n_ctx > load_max:
        print(
            "ggml_backend_cuda_buffer_type_alloc_buffer: allocating failed: cudaMalloc failed: out of memory",
            file=err,
        )
        print("llama_init_from_model: failed to initialize the context", file=err)
        err.flush()
        return 1
    kv_mib = n_ctx * K_BYTES[kv] / 2**20
    print(f"llama_kv_cache:      CUDA0 KV buffer size = {kv_mib:8.2f} MiB", file=err)
    print("llama_context:      CUDA0 compute buffer size =   300.75 MiB", file=err)
    print("main: model loaded", file=err)
    print(f"main: server is listening on http://127.0.0.1:{port}", file=err)
    err.flush()

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *a: Any) -> None:
            return

        def _send(self, code: int, obj: Any) -> None:
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 (http.server API name)
            self._send(200, {"status": "ok"})

        def do_POST(self) -> None:  # noqa: N802 (http.server API name)
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/tokenize":
                self._send(200, {"tokens": [791, 10931, 2083, 14858, 279, 15140]})
                return
            n = len(body["prompt"])
            if n > prefill_max:
                self._send(
                    500, {"error": {"code": 500, "message": "failed to allocate compute buffer"}}
                )
                return
            self._send(
                200,
                {
                    "content": "x",
                    "tokens_evaluated": n,
                    "timings": {"prompt_n": n, "prompt_ms": 1.5},
                },
            )

    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
