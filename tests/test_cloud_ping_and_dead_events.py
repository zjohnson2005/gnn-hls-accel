"""Cloud failures are diagnosable, and launch_h1 pings the cloud first.

T2S V3 b323f0e5 (2026-10-13) aborted aborted_cloud_dead with no error text
on disk: the guard's events lived only in memory. No network in these tests.
"""

from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.bfcl_feasibility_probe as probe  # noqa: E402
import tools.cloud_ping as cp  # noqa: E402
import tools.run_h1_hybrid as rh  # noqa: E402
from tools.h1_cloud_accounting import exception_fields, redact_secrets  # noqa: E402

# A fake key, assembled at runtime so the source holds no key-shaped literal
# (tools/hooks/check_no_secrets.py scans staged text).
SECRET = "-".join(("sk", "ant", "api03", "TESTSECRET0123456789abcdef"))
FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_3entries.json"
LAUNCHER = ROOT / "tools" / "launch_h1.ps1"


class _ApiStatusError(Exception):
    status_code = 401
    request_id = "req_test_1"


@dataclass
class _Usage:
    input_tokens: int = 11
    output_tokens: int = 3


@dataclass
class _Response:
    usage: _Usage = field(default_factory=_Usage)
    stop_reason: str = "end_turn"
    model: str = "claude-sonnet-5"
    _request_id: str = "req_ok_1"


class _Messages:
    def __init__(self, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.fail is not None:
            raise self.fail
        return _Response()


def _backend(fail: Exception | None = None) -> Any:
    client = types.SimpleNamespace(messages=_Messages(fail))
    return types.SimpleNamespace(client=client, cloud_model=probe.CLOUD_DEFAULT_MODEL)


# ---------------------------------------------------------------- redaction


def test_redaction_masks_keys_and_the_live_key(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    text = redact_secrets(f"401 for key {SECRET} Bearer abc.def x-api-key: zz9")
    assert SECRET not in text and "abc.def" not in text and "zz9" not in text
    fields = exception_fields(_ApiStatusError(f"invalid x-api-key {SECRET}"))
    assert fields["error_class"] == "_ApiStatusError"
    assert fields["http_status"] == 401 and fields["request_id"] == "req_test_1"
    assert SECRET not in fields["error_message"]


# ---------------------------------------------------------------- cloud_ping


def test_ping_success(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example.invalid:8080")
    backend = _backend()
    out = tmp_path / "launch" / "cloud_ping.json"
    code = cp.main(["--out", str(out)], backend_factory=lambda _m: backend)
    assert code == 0
    text = out.read_text(encoding="utf-8")
    record = json.loads(text)
    assert record["ok"] is True and record["http_status"] == 200
    assert record["model"] == probe.CLOUD_DEFAULT_MODEL
    assert record["api_key_present"] is True
    assert record["proxy_env_present"]["HTTPS_PROXY"] is True
    assert "proxy.example.invalid" not in text and SECRET not in text
    assert record["usd"] < cp.COST_CEILING_USD and record["usd_under_ceiling"] is True
    assert record["python_version"] and record["platform"]
    sent = backend.client.messages.calls[0]
    assert sent["max_tokens"] == 8 and sent["model"] == probe.CLOUD_DEFAULT_MODEL
    assert "tools" not in sent
    # Same temperature rule as the runner: omitted for the default model id.
    assert "temperature" not in sent


def test_ping_failure_records_class_status_and_redacts(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    backend = _backend(_ApiStatusError(f"authentication_error: invalid x-api-key {SECRET}"))
    out = tmp_path / "cloud_ping.json"
    code = cp.main(["--out", str(out)], backend_factory=lambda _m: backend)
    assert code == 1
    text = out.read_text(encoding="utf-8")
    record = json.loads(text)
    assert record["ok"] is False and record["http_status"] == 401
    assert record["error_class"] == "_ApiStatusError"
    assert record["request_id"] == "req_test_1"
    assert SECRET not in text and "[REDACTED]" in record["error_message"]
    assert record["usd"] == 0.0


def test_ping_setup_refusal_exits_2(tmp_path) -> None:
    def refuse(_model: str | None) -> Any:
        raise SystemExit("REFUSED -- ANTHROPIC_API_KEY unset.")

    out = tmp_path / "cloud_ping.json"
    assert cp.main(["--out", str(out)], backend_factory=refuse) == 2
    assert json.loads(out.read_text(encoding="utf-8"))["error_class"] == "SetupRefused"


def test_ping_uses_the_runner_client_construction(monkeypatch) -> None:
    built: list[dict[str, Any]] = []

    class FakeAnthropic:
        def __init__(self, **kwargs: Any) -> None:
            built.append(kwargs)
            self.messages = _Messages()

    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        types.SimpleNamespace(Anthropic=FakeAnthropic, __version__="0.0-test"),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    record = cp.ping()
    assert record["ok"] is True
    assert record["model"] == probe.CLOUD_DEFAULT_MODEL == "claude-sonnet-5"
    assert record["anthropic_sdk_version"] == "0.0-test"
    assert built == [{}]  # anthropic.Anthropic() exactly as _make_live_cloud builds it
    assert record["client_construction"] == "tools.run_h1_hybrid._make_live_cloud"


# ---------------------------------------------------------------- dead events


def _dead_turn(error: str) -> rh.BackendTurn:
    return rh.BackendTurn(
        n_ctx=0,
        ttft_s=None,
        decode_tok_s=None,
        emitted_parseable_tool_call=False,
        cloud_tokens_in=0,
        cloud_tokens_out=0,
        cloud_usd=0.0,
        cloud_error=error,
        cloud_requests=[
            {
                "turn": 0,
                "step": 0,
                "ok": False,
                "error": error,
                "error_class": "AuthenticationError",
                "http_status": 401,
                "request_id": "req_dead",
                "model": "claude-sonnet-5",
                "prompt_tokens": None,
                "completion_tokens": None,
                "latency_s": 0.4,
                "usd": 0.0,
                "headers": {"x-api-key": SECRET},
                "history_text": "should not be copied",
            }
        ],
    )


def test_guard_writes_events_on_each_dead_turn(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    path = tmp_path / "cloud_dead_events.json"
    guard = rh.CloudDeadPathGuard(n=3, events_path=path)
    guard.observe(
        _dead_turn(f"api_error: AuthenticationError: bad {SECRET}"),
        entry_id="e1",
        turn=0,
        policy="slo_escalate",
    )
    assert path.is_file()
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["status"] == "dead_turn" and doc["consecutive"] == 1
    row = doc["requests"][0]["rows"][0]
    assert set(row) <= set(rh.CLOUD_EVENT_REQUEST_FIELDS)
    assert row["http_status"] == 401 and row["error_class"] == "AuthenticationError"
    assert SECRET not in path.read_text(encoding="utf-8")
    assert "headers" not in row and "history_text" not in row


def test_old_rows_get_error_class_from_the_error_string() -> None:
    row = rh.cloud_event_request_row({"ok": False, "error": "api_error: APIConnectionError: boom"})
    assert row["error_class"] == "APIConnectionError"


class _DeadCloud(rh.StubCloudBackend):
    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> rh.BackendTurn:
        return _dead_turn(f"api_error: AuthenticationError: invalid x-api-key {SECRET}")


def test_abort_writes_events_before_the_seal(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    fix = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out = tmp_path / "run"
    summary = rh.run_session(
        policy="cloud_only",
        entries=fix["entries"],
        out_dir=out,
        max_usd=5.0,
        local=rh.StubLocalBackend(script=fix["local_script"]),
        cloud=_DeadCloud(),
        skip_entry_assert=True,
    )
    assert summary["status"] == "aborted_cloud_dead"
    events = out / "cloud_dead_events.json"
    doc = json.loads(events.read_text(encoding="utf-8"))
    assert doc["status"] == "aborted_cloud_dead"
    assert "CLOUD_DEAD_PATH_STREAK" in doc["abort"]
    assert len(doc["events"]) == rh.CLOUD_DEAD_CONSECUTIVE_N
    assert all(e["dead"] for e in doc["events"])
    assert doc["requests"] and doc["requests"][0]["rows"][0]["http_status"] == 401
    assert SECRET not in events.read_text(encoding="utf-8")
    sealed = out / ".sealed"
    assert sealed.is_file()
    assert events.stat().st_mtime <= sealed.stat().st_mtime


# ---------------------------------------------------------------- launcher


def test_launcher_pings_before_spawn() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "[switch]$NoCloudPing" in text
    smoke = text.index("Lifecycle smoke PASS.")
    ping = text.index("& $PythonExe -u $CloudPingPy --out $CloudPingJson")
    spawn = text.index("& $SpawnPs1 -CommandLine $resolvedCmd")
    assert smoke < ping < spawn
    assert '$CloudPingJson = Join-Path $SessionLaunchDir "cloud_ping.json"' in text
    assert '$_ -ne "local_only"' in text
    assert 'Refuse "-NoCloudPing is only for -DryRun' in text
    assert 'Refuse "cloud ping failed (exit $pingRc' in text
    assert "if (-not $DryRun) { exit $pingRc }" in text
    assert "tools\\cloud_ping.py" in text
