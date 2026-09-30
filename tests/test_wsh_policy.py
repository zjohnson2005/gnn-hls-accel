"""WorkloadsSessionHost snapshot, kill refusal text, and rehearsal context."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.measurement_gates import GateResult, evaluate_measurement_gates  # noqa: E402
from seam.run_environment import snapshot_workloads_session_host  # noqa: E402
from tools.ttft_slo_canary import TtftSloCanaryGuard  # noqa: E402


class _Proc:
    def __init__(self, pid: int, name: str, wset: int, *, fail_cpu: bool = False) -> None:
        self.info = {"pid": pid, "name": name}
        self._wset = wset
        self._fail_cpu = fail_cpu

    def memory_info(self) -> object:
        return type("Mem", (), {"wset": self._wset})()

    def cpu_times(self) -> object:
        if self._fail_cpu:
            raise psutil.AccessDenied(pid=self.info["pid"])
        return type("Times", (), {"user": 1.25, "system": 0.25})()


def test_snapshot_records_count_pids_ws_and_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    procs = [
        _Proc(9, "WorkloadsSessionHost.exe", 2 * 1024 * 1024),
        _Proc(3, "notepad.exe", 1024),
        _Proc(4, "WorkloadsSessionHost.exe", 4 * 1024 * 1024, fail_cpu=True),
    ]
    monkeypatch.setattr(psutil, "process_iter", lambda *_a, **_k: procs)
    snap = snapshot_workloads_session_host()
    assert snap["instance_count"] == 2
    assert snap["pids"] == [4, 9]
    assert snap["WS_MB"] == [4.0, 2.0]
    assert snap["CPU_s"][0] is None
    assert snap["CPU_s"][1] == 1.5
    assert any("pid 4" in err for err in snap["read_errors"])


def test_skipped_gate_records_the_snapshot_slot() -> None:
    report = evaluate_measurement_gates(
        ROOT,
        platform_id="evo-t2",
        available_mb=30000.0,
        uptime_s=10.0,
        skip_host_probes=True,
        ac_override=GateResult(name="ac", passed=True, reason="ac_ok", detail={}),
        processor_override=GateResult(
            name="processor_ac",
            passed=True,
            reason="processor_ac_100_100",
            detail={"procthrottlemin_ac": 100, "procthrottlemax_ac": 100},
        ),
    )
    host = report.to_dict()["workloads_session_host"]
    assert host["skipped"] is True


def test_canary_plan_keeps_each_snapshot(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"kind": "warm_kv"}) + "\n", encoding="utf-8")
    guard = TtftSloCanaryGuard(
        root=ROOT,
        model_spec=ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml",
        work_dir=tmp_path / "canaries",
        plan_path=plan,
        planned_probe_count=4,
    )
    guard.canaries.append(
        {
            "canary_index": 0,
            "workloads_session_host": {
                "instance_count": 1,
                "pids": [1932],
                "WS_MB": [12.5],
                "CPU_s": [0.4],
            },
        }
    )
    guard._stamp_plan()
    stored = json.loads(plan.read_text(encoding="utf-8"))
    row = stored["canary"]["workloads_session_host_at_canaries"][0]
    assert row["workloads_session_host"]["pids"] == [1932]
    assert row["workloads_session_host"]["WS_MB"] == [12.5]


def test_failed_kill_refusal_keeps_the_exception_text() -> None:
    script = (
        f". '{ROOT / 'tools' / 'wsh_policy.ps1'}'; "
        "$after = [pscustomobject]@{ instance_count = 2; pids = @(1932, 5300) }; "
        "Format-WshKillRefusal -After $after -KillErrors @('Access is denied')"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    text = proc.stdout
    assert "REFUSED -- WorkloadsSessionHost still resident" in text
    assert "instance_count=2" in text
    assert "pids=1932,5300" in text
    assert "exception=Access is denied" in text


def test_rehearsal_refuses_the_cursor_terminal() -> None:
    env = os.environ.copy()
    env.pop("SEAM_BOOT_SMOKE_STUB", None)
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-File",
            str(ROOT / "tools" / "launch_boot4.ps1"),
            "-Rehearsal",
        ],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    combined = proc.stdout + proc.stderr
    assert "REFUSED -- rehearsal must run as the WMI-detached child" in combined
    assert "ssh xps" in combined
    assert "-Detach -Rehearsal" in combined
