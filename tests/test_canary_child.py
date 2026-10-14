"""NPU amendment 2026-10-14b: canary cell in a child process (tests first)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import seam.run_environment as env  # noqa: E402
import tools.smoke_delta_prefill as sdp  # noqa: E402
import tools.ttft_slo_canary as tsc  # noqa: E402
from tools import canary_child  # noqa: E402

RAW = {
    "classification": "OK",
    "execute_ok": True,
    "execute_error": None,
    "turn1": {"prefill_s": 1.1},
    "turn2": {"prefill_s": 0.5},
    "environment_start": {"available_mb": 40000.0},
}


def _writer(raw: dict[str, Any]) -> Any:
    """Child command that writes ``raw`` as the result file (a real subprocess)."""

    def cmd(out: Path, model_spec: Path) -> list[str]:
        payload = json.dumps({"cell": raw})
        code = f"import pathlib,sys; pathlib.Path(sys.argv[1]).write_text({payload!r})"
        return [sys.executable, "-c", code, str(out)]

    return cmd


def _guard(tmp_path: Path, monkeypatch, **kw: Any) -> tsc.TtftSloCanaryGuard:
    monkeypatch.setattr(tsc, "capture_canary_power_snapshot", lambda: {"on_ac": True})
    monkeypatch.setattr(tsc, "assert_no_ac_transition", lambda **_kw: {"ok": True})
    monkeypatch.setattr(env, "snapshot_workloads_session_host", lambda: {})
    return tsc.TtftSloCanaryGuard(
        root=ROOT,
        model_spec=tmp_path / "spec.yaml",
        work_dir=tmp_path / "w",
        enforce_probe_budget=False,
        arm_before_probes=True,
        **kw,
    )


def _strip(rec: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in rec.items() if k not in ("utc", "child", "inprocess_transition")}


def test_child_result_matches_in_process(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sdp, "run_cell", lambda *_a, **_k: json.loads(json.dumps(RAW)))
    inproc = _guard(tmp_path / "a", monkeypatch)
    child = _guard(tmp_path / "b", monkeypatch, child_process=True, child_command=_writer(RAW))
    a = inproc.run_canary(after_probe_count=-1)
    b = child.run_canary(after_probe_count=-1)
    assert _strip(a) == _strip(b)
    rec = b["child"]
    assert rec["exit_code"] == 0 and rec["timed_out"] is False
    assert set(rec) >= {"pid", "exit_code", "wall_s", "timeout_s", "timed_out", "stderr_tail"}
    assert "child" not in a
    doc = json.loads((tmp_path / "b" / "w" / "canary.0.json").read_text(encoding="utf-8"))
    assert doc["record"]["child"]["exit_code"] == 0


def test_child_crash_is_other_with_exit_code(tmp_path, monkeypatch) -> None:
    guard = _guard(
        tmp_path,
        monkeypatch,
        child_process=True,
        child_command=lambda _out, _spec: [sys.executable, "-c", "import sys; sys.exit(5)"],
    )
    rec = guard.run_canary(after_probe_count=-1)
    assert rec["classification"] == "OTHER"
    assert rec["child"]["exit_code"] == 5
    assert "exit code 5" in rec["execute_error"]


def test_child_timeout_is_other(tmp_path, monkeypatch) -> None:
    guard = _guard(
        tmp_path,
        monkeypatch,
        child_process=True,
        child_timeout_s=1.0,
        child_command=lambda _out, _spec: [sys.executable, "-c", "import time; time.sleep(30)"],
    )
    rec = guard.run_canary(after_probe_count=-1)
    assert rec["classification"] == "OTHER"
    assert rec["child"]["timed_out"] is True
    assert "timeout" in rec["execute_error"]


def test_other_after_arming_still_refuses(tmp_path, monkeypatch) -> None:
    good = _writer(RAW)
    state = {"n": 0}

    def cmd(out: Path, spec: Path) -> list[str]:
        state["n"] += 1
        if state["n"] <= 3:
            return good(out, spec)
        return [sys.executable, "-c", "import sys; sys.exit(7)"]

    guard = _guard(tmp_path, monkeypatch, child_process=True, child_command=cmd)
    guard.opening()
    assert guard.gate["armed"] is True
    with pytest.raises(tsc.CanaryDriftAbort, match="OTHER"):
        guard.run_canary(after_probe_count=5)


def test_transition_record_at_record_only_and_first_post_arm(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sdp, "run_cell", lambda *_a, **_k: json.loads(json.dumps(RAW)))
    guard = _guard(
        tmp_path,
        monkeypatch,
        child_process=True,
        child_command=_writer(RAW),
        inprocess_transition=True,
        telemetry=lambda: {"processes": {"count": 1}},
    )
    rec0 = guard.run_canary(after_probe_count=-1, warmup=True)
    guard.opening()
    first = guard.run_canary(after_probe_count=4)
    later = guard.run_canary(after_probe_count=9)
    assert rec0["inprocess_transition"]["point"] == "record_only"
    assert rec0["inprocess_transition"]["turn1_prefill_s"] == 1.1
    assert first["inprocess_transition"]["point"] == "first_post_arm"
    assert "inprocess_transition" not in later
    calib = [c for c in guard.canaries if not c.get("warmup") and c["after_probe_count"] == -1]
    assert all("inprocess_transition" not in c for c in calib)
    assert first["telemetry"] == {"processes": {"count": 1}}


def test_defaults_stay_in_process(tmp_path, monkeypatch) -> None:
    calls = {"n": 0}

    def fake(*a: Any, **k: Any) -> dict[str, Any]:
        calls["n"] += 1
        return json.loads(json.dumps(RAW))

    monkeypatch.setattr(sdp, "run_cell", fake)
    rec = _guard(tmp_path, monkeypatch).run_canary(after_probe_count=-1)
    assert calls["n"] == 1 and "child" not in rec and "inprocess_transition" not in rec


def test_child_entrypoint_writes_result(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(sdp, "run_cell", lambda *_a, **_k: json.loads(json.dumps(RAW)))
    out = tmp_path / "r.json"
    assert canary_child.main(["--out", str(out), "--model-spec", str(tmp_path / "s.yaml")]) == 0
    assert "CANARY_CHILD classification=OK t1=1.1 t2=0.5" in capsys.readouterr().out
    assert json.loads(out.read_text(encoding="utf-8"))["cell"]["classification"] == "OK"
    cmd = canary_child.child_command(out, tmp_path / "s.yaml")
    assert cmd[:3] == [sys.executable, "-m", "tools.canary_child"]


def test_config_file() -> None:
    import yaml

    cfg = yaml.safe_load((ROOT / "configs" / "npu_canary_child.yaml").read_text(encoding="utf-8"))
    assert cfg["inprocess_transition_record"] is True
    assert cfg["child_timeout_s"] == 180


def test_guarded_envelope_session_uses_child_canary(monkeypatch, tmp_path) -> None:
    from tests.test_npu_canary_state import _run_guarded

    code, plan, summary, _npu, guard = _run_guarded(monkeypatch, tmp_path)
    assert code == 0, summary
    assert guard.kwargs["child_process"] is True
    assert guard.kwargs["child_timeout_s"] == 180.0
    assert guard.kwargs["inprocess_transition"] is True
    assert plan["canary_child"]["amendment"].startswith("NPU amendment 2026-10-14b")
    assert "2026-10-14b" in plan["guard_schedule"]


def test_arm_canary_default_has_no_child(monkeypatch, tmp_path) -> None:
    import tools.run_npu_profile as rnp
    from tests.test_npu_canary_state import _Guard
    from tests.test_npu_int8_envelope import _Pipe

    npu = _Pipe(10)
    _Guard.instances = []
    monkeypatch.setattr(tsc, "TtftSloCanaryGuard", lambda **kw: _Guard(npu, **kw))
    rnp._arm_canary(tmp_path, tmp_path / "spec.yaml", 12, before_probes=True)
    assert "child_process" not in _Guard.instances[-1].kwargs
