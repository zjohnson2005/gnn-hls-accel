"""In-worker cloud preflight (Task R).

The worker runs as a WMI child and can see a different environment than the
ssh session where launch_h1 pings. The worker now makes the same
tools/cloud_ping.py request itself before the first entry. No network.
"""

from __future__ import annotations

import hashlib
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.cloud_ping as cp  # noqa: E402
import tools.run_h1_hybrid as rh  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_3entries.json"
SECRET = "-".join(("sk", "ant", "api03", "WORKERSECRET0123456789abcd"))


class _AuthError(Exception):
    status_code = 401
    request_id = "req_worker_401"


@dataclass
class _Usage:
    input_tokens: int = 11
    output_tokens: int = 3


@dataclass
class _Response:
    usage: _Usage = field(default_factory=_Usage)
    stop_reason: str = "end_turn"
    model: str = "claude-sonnet-5"


class _Messages:
    def __init__(self, fail: Exception | None) -> None:
        self.fail = fail
        self.calls = 0

    def create(self, **kwargs: Any) -> Any:
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        return _Response()


def _preflight(fail: Exception | None = None) -> tuple[Any, _Messages]:
    """The wiring main() uses: cloud_ping.ping over the worker's own backend."""
    messages = _Messages(fail)
    backend = types.SimpleNamespace(
        client=types.SimpleNamespace(messages=messages), cloud_model="claude-sonnet-5"
    )
    return (lambda: cp.ping(backend_factory=lambda _m: backend)), messages


def _fix() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class _CountingCloud(rh.StubCloudBackend):
    def __init__(self) -> None:
        super().__init__(tokens_in=10, tokens_out=5)
        self.n = 0

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> rh.BackendTurn:
        self.n += 1
        return super().run_turn(entry, turn_idx, model=model)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_ping_pass_runs_entries_and_records(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    fix = _fix()
    preflight, messages = _preflight()
    cloud = _CountingCloud()
    out = tmp_path / "run"
    summary = rh.run_session(
        policy="cloud_only",
        entries=fix["entries"],
        out_dir=out,
        max_usd=5.0,
        local=rh.StubLocalBackend(script=fix["local_script"]),
        cloud=cloud,
        skip_entry_assert=True,
        cloud_preflight=preflight,
    )
    assert summary["status"] == "complete"
    assert messages.calls == 1 and cloud.n > 0
    record_path = out / rh.CLOUD_PING_WORKER_FILE
    record = _read(record_path)
    assert record["ok"] is True and record["process"] == "worker"
    assert SECRET not in record_path.read_text(encoding="utf-8")
    block = _read(out / "plan.json")["cloud_ping_worker"]
    assert block["ran"] is True and block["ok"] is True
    assert block["sha256"] == hashlib.sha256(record_path.read_bytes()).hexdigest()
    seal = _read(out / ".sealed")
    assert seal["tree_sha256"] == rh._sha256_tree(out, exclude={".sealed"})


def test_ping_fail_refuses_before_any_entry(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    # Hybrid policies refuse to seal a stub local backend; the seal path is what is tested here.
    monkeypatch.setattr(rh, "assert_seal_allowed", lambda **_kw: None)
    fix = _fix()
    preflight, _messages = _preflight(_AuthError(f"invalid x-api-key {SECRET}"))
    cloud = _CountingCloud()
    out = tmp_path / "run"
    summary = rh.run_session(
        policy="slo_escalate",
        entries=fix["entries"],
        out_dir=out,
        max_usd=5.0,
        local=rh.StubLocalBackend(script=fix["local_script"]),
        cloud=cloud,
        skip_entry_assert=True,
        cloud_preflight=preflight,
    )
    assert summary["status"] == rh.REFUSED_CLOUD_PING
    assert summary["n_entries_completed"] == 0 and summary["running_usd"] == 0.0
    assert cloud.n == 0
    assert "http_status=401" in summary["abort_reason"]
    record_path = out / rh.CLOUD_PING_WORKER_FILE
    record = _read(record_path)
    assert record["ok"] is False and record["http_status"] == 401
    assert SECRET not in record_path.read_text(encoding="utf-8")
    plan = _read(out / "plan.json")
    assert plan["cloud_ping_worker"]["ran"] is True and plan["cloud_ping_worker"]["ok"] is False
    seal = _read(out / ".sealed")
    assert seal["status"] == rh.REFUSED_CLOUD_PING
    assert seal["tree_sha256"] == rh._sha256_tree(out, exclude={".sealed"})


def test_interleaved_ping_fail_refuses_every_policy(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    # Hybrid policies refuse to seal a stub local backend; the seal path is what is tested here.
    monkeypatch.setattr(rh, "assert_seal_allowed", lambda **_kw: None)
    fix = _fix()
    preflight, _messages = _preflight(_AuthError("authentication_error"))
    cloud = _CountingCloud()
    out = tmp_path / "inter"
    summary = rh.run_interleaved_session(
        entries=fix["entries"],
        out_dir=out,
        local=rh.StubLocalBackend(script=fix["local_script"]),
        cloud=cloud,
        policies=("slo_escalate", "local_only"),
        policy_caps_usd={"slo_escalate": 5.0, "local_only": 0.0},
        session_max_usd=5.0,
        run_id="inter-ping-fail",
        skip_entry_assert=True,
        cloud_preflight=preflight,
    )
    assert summary["status"] == rh.REFUSED_CLOUD_PING
    assert cloud.n == 0
    assert all(p["status"] == rh.REFUSED_CLOUD_PING for p in summary["policies"].values())
    assert all(p["n_entries_completed"] == 0 for p in summary["policies"].values())
    assert (out / rh.CLOUD_PING_WORKER_FILE).is_file()
    assert _read(out / ".sealed")["status"] == rh.REFUSED_CLOUD_PING


def test_local_only_skips_the_ping(tmp_path) -> None:
    fix = _fix()
    calls = {"n": 0}

    def preflight() -> dict[str, Any]:
        calls["n"] += 1
        return {"ok": False}

    out = tmp_path / "local"
    summary = rh.run_interleaved_session(
        entries=fix["entries"],
        out_dir=out,
        local=rh.StubLocalBackend(script=fix["local_script"]),
        cloud=rh.StubCloudBackend(tokens_in=10, tokens_out=5),
        policies=("local_only",),
        policy_caps_usd={"local_only": 0.0},
        session_max_usd=1.0,
        run_id="local-only",
        skip_entry_assert=True,
        seal=False,
        cloud_preflight=preflight,
    )
    assert calls["n"] == 0
    assert summary["status"] != rh.REFUSED_CLOUD_PING
    assert not (out / rh.CLOUD_PING_WORKER_FILE).exists()
    assert _read(out / "plan.json")["cloud_ping_worker"]["ran"] is False


def test_no_preflight_leaves_the_plan_unchanged(tmp_path) -> None:
    fix = _fix()
    out = tmp_path / "plain"
    rh.run_session(
        policy="cloud_only",
        entries=fix["entries"],
        out_dir=out,
        max_usd=5.0,
        local=rh.StubLocalBackend(script=fix["local_script"]),
        cloud=rh.StubCloudBackend(tokens_in=10, tokens_out=5),
        skip_entry_assert=True,
        seal=False,
    )
    assert "cloud_ping_worker" not in _read(out / "plan.json")


def test_preflight_exception_is_recorded_not_raised(tmp_path) -> None:
    def boom() -> dict[str, Any]:
        raise RuntimeError("client construction failed")

    block = rh.run_worker_cloud_ping(boom, tmp_path)
    assert block["ok"] is False and block["error_class"] == "RuntimeError"
    assert _read(tmp_path / rh.CLOUD_PING_WORKER_FILE)["process"] == "worker"


def test_live_main_paths_pass_the_preflight() -> None:
    text = (ROOT / "tools" / "run_h1_hybrid.py").read_text(encoding="utf-8")
    assert text.count("cloud_preflight=lambda: cloud_ping(") == 2
    assert text.count("backend_factory=lambda _model: cloud") == 2
    derive = text[text.index("    if args.derive_r1:") : text.index("    if args.interleaved:")]
    assert "cloud_ping" not in derive
