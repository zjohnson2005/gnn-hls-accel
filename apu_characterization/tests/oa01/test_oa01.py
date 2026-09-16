from __future__ import annotations

import gzip
import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from apu_characterization.oa01.audit import audit_trajectory
from apu_characterization.oa01.bundle import save_bundle
from apu_characterization.oa01.derive import derive_turn_records
from apu_characterization.oa01.manifest import validate_manifest
from apu_characterization.oa01.proxy import OA01ProxyServer
from apu_characterization.oa01.schema import (
    ApiBoundaryRecord,
    ToolExecSpan,
    UsageRecord,
)


class _Upstream(BaseHTTPRequestHandler):
    request_body = b""

    def log_message(self, format, *args):
        return None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        type(self).request_body = self.rfile.read(length)
        body = json.dumps(
            {
                "id": "x",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "ok",
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "bash",
                                        "arguments": '{"command":"pytest -q"}',
                                    }
                                }
                            ],
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 1200,
                    "completion_tokens": 10,
                    "prompt_tokens_details": {"cached_tokens": 1024},
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_proxy_relays_exact_request_and_captures_cache(tmp_path: Path) -> None:
    upstream = HTTPServer(("127.0.0.1", 0), _Upstream)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    log = tmp_path / "api.jsonl"
    proxy = OA01ProxyServer(
        ("127.0.0.1", 0),
        upstream_base=f"http://127.0.0.1:{upstream.server_address[1]}",
        log_path=log,
        trajectory_id="t1",
    )
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    request_body = json.dumps(
        {
            "model": "gpt-4.1",
            "messages": [{"role": "user", "content": "hello"}],
        },
        separators=(",", ":"),
    ).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{proxy.server_address[1]}/v1/chat/completions",
        data=request_body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer secret"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        assert response.status == 200
        assert json.loads(response.read())["choices"]
    proxy.shutdown()
    proxy.server_close()
    upstream.shutdown()
    upstream.server_close()
    proxy_thread.join(2)
    upstream_thread.join(2)

    assert _Upstream.request_body == request_body
    row = json.loads(log.read_text().strip())
    assert row["usage"]["cached_tokens"] == 1024
    assert row["request_headers"]["Authorization"].startswith("sha256:")
    assert "secret" not in log.read_text()


class _GzipUpstream(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        payload = json.dumps(
            {
                "id": "gz",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 5,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            }
        ).encode()
        body = gzip.compress(payload)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_proxy_parses_usage_from_gzip_wire_body(tmp_path: Path) -> None:
    upstream = HTTPServer(("127.0.0.1", 0), _GzipUpstream)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    log = tmp_path / "api.jsonl"
    proxy = OA01ProxyServer(
        ("127.0.0.1", 0),
        upstream_base=f"http://127.0.0.1:{upstream.server_address[1]}",
        log_path=log,
        trajectory_id="t-gzip",
    )
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    request_body = b'{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hi"}]}'
    request = urllib.request.Request(
        f"http://127.0.0.1:{proxy.server_address[1]}/v1/chat/completions",
        data=request_body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        wire = response.read()
        assert wire[:2] == b"\x1f\x8b"
        assert json.loads(gzip.decompress(wire))["choices"]
    proxy.shutdown()
    proxy.server_close()
    upstream.shutdown()
    upstream.server_close()
    proxy_thread.join(2)
    upstream_thread.join(2)

    row = json.loads(log.read_text().strip())
    assert row["usage"]["input_tokens"] == 50
    assert row["usage"]["output_tokens"] == 5
    assert "usage_missing" not in row["flags"]
    assert row["response_body_b64"]


def _api(
    call_index: int, start_ns: int, *, cached: int, status: int = 200
) -> ApiBoundaryRecord:
    request = {
        "model": "gpt-4.1",
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "task"},
            *(
                [
                    {"role": "assistant", "content": "inspect"},
                    {"role": "tool", "content": "result"},
                ]
                if call_index
                else []
            ),
        ],
    }
    response = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "bash",
                                "arguments": '{"command":"rg bug src"}',
                            }
                        }
                    ]
                }
            }
        ],
        "usage": {
            "prompt_tokens": 100 + call_index * 20,
            "completion_tokens": 10,
            "prompt_tokens_details": {"cached_tokens": cached},
        },
    }
    return ApiBoundaryRecord(
        schema_version="oa01_api_boundary_v1",
        trajectory_id="t1",
        call_id=f"c{call_index}",
        call_index=call_index,
        method="POST",
        path="/v1/chat/completions",
        request_headers={},
        request_body_b64="eA==",
        request_json=request,
        response_status=status,
        response_headers={},
        response_body_b64="eA==",
        response_json=response,
        request_received_unix_ns=start_ns,
        upstream_send_unix_ns=start_ns + 1_000_000,
        response_headers_unix_ns=start_ns + 50_000_000,
        response_first_body_byte_unix_ns=start_ns + 50_000_000,
        response_last_body_byte_unix_ns=start_ns + 60_000_000,
        response_relay_complete_unix_ns=start_ns + 61_000_000,
        stream_requested=False,
        model_id="gpt-4.1",
        usage=UsageRecord.from_provider(response["usage"]),
        cost_usd=0.01,
    )


def test_gap_and_cache_derivation_conserve() -> None:
    calls = [_api(0, 1_000_000_000, cached=0), _api(1, 2_000_000_000, cached=10)]
    exec_span = ToolExecSpan(
        schema_version="oa01_exec_span_v1",
        trajectory_id="t1",
        span_id="e1",
        argv=["exec"],
        docker_operation="exec",
        container_id="cid",
        command="bash",
        start_unix_ns=1_100_000_000,
        end_unix_ns=1_200_000_000,
        returncode=0,
    )
    turns = derive_turn_records(
        api_records=calls,
        exec_spans=[exec_span],
        task_id="task",
        trajectory_start_unix_ns=900_000_000,
        trajectory_end_unix_ns=2_500_000_000,
    )
    assert len(turns) == 2
    assert turns[0].t_tool_ms == 100.0
    for turn in turns:
        accounted = turn.t_model_observed_ms + turn.t_tool_ms + turn.t_orch_gap_ms
        assert abs(turn.t_turn_wall_ms - accounted) < 1e-6
        assert turn.t_prefill_ms is None
        assert "prefill_decode_network_not_isolated" in turn.audit_flags
    assert turns[1].provider_recovered_tokens == 10
    assert turns[1].actually_recomputed_redundant_tokens >= 0
    assert turns[0].step_type_semantic == "inspect"


def test_provider_retry_attempts_remain_in_one_logical_turn() -> None:
    failed = _api(0, 1_000_000_000, cached=0, status=429)
    failed.flags.append("usage_absent_error_response")
    failed.usage = UsageRecord()
    failed.cost_usd = 0.0
    succeeded = _api(1, 1_100_000_000, cached=0)
    turns = derive_turn_records(
        api_records=[failed, succeeded],
        exec_spans=[],
        task_id="task",
        trajectory_start_unix_ns=900_000_000,
        trajectory_end_unix_ns=1_500_000_000,
    )
    assert len(turns) == 1
    assert turns[0].api_attempt_count == 2
    assert turns[0].api_call_ids == ["c0", "c1"]
    assert "provider_retry_attempts" in turns[0].audit_flags


def test_audit_ignores_usage_on_provider_error_retries(tmp_path: Path) -> None:
    failed = _api(0, 1_000_000_000, cached=0, status=429)
    failed.flags.append("usage_missing")  # legacy flag on retained 429 raw rows
    failed.usage = UsageRecord()
    failed.cost_usd = 0.0
    succeeded = _api(1, 1_100_000_000, cached=0)
    turns = derive_turn_records(
        api_records=[failed, succeeded],
        exec_spans=[],
        task_id="task",
        trajectory_start_unix_ns=900_000_000,
        trajectory_end_unix_ns=1_500_000_000,
    )
    bundle_path = save_bundle(
        {
            "trajectory_id": "t1",
            "api_boundary_records": [failed.to_dict(), succeeded.to_dict()],
        },
        tmp_path / "t1.oa01bundle",
    )
    audit = audit_trajectory(
        turns=turns,
        api_records=[failed, succeeded],
        exec_spans=[],
        run_meta={"trajectory_id": "t1", "turns_observed": 1},
        bundle_path=bundle_path,
    )
    assert audit["checks"]["usage_and_cache_fields"]["pass"]
    assert audit["checks"]["usage_and_cache_fields"]["error_records"] == 1


def test_manifest_is_locked_and_hashed() -> None:
    path = (
        Path(__file__).resolve().parents[2] / "oa01" / "task_manifest.json"
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert validate_manifest(manifest) == []
    assert len(manifest["tasks"]) == 15


def test_audit_accepts_complete_synthetic_bundle(tmp_path: Path) -> None:
    calls = [_api(0, 1_000_000_000, cached=0)]
    turns = derive_turn_records(
        api_records=calls,
        exec_spans=[],
        task_id="task",
        trajectory_start_unix_ns=900_000_000,
        trajectory_end_unix_ns=1_500_000_000,
    )
    bundle_path = save_bundle(
        {
            "trajectory_id": "t1",
            "api_boundary_records": [calls[0].to_dict()],
        },
        tmp_path / "t1.oa01bundle",
    )
    audit = audit_trajectory(
        turns=turns,
        api_records=calls,
        exec_spans=[],
        run_meta={"trajectory_id": "t1", "turns_observed": 1},
        bundle_path=bundle_path,
    )
    assert audit["checks"]["call_count_reconciliation"]["pass"]
    assert audit["checks"]["gap_conservation"]["pass"]
    assert audit["checks"]["replay_bundle_integrity"]["pass"]

