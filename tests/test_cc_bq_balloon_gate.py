"""Task BQ balloon-gate option (a): --balloon-floor-credit, CC-BAL cells only, default off.

Hardware-free. Host probes are replaced by the real gate evaluator with fixed values; the
balloon process is a stub psutil process.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psutil  # noqa: E402

import seam.measurement_gates as mg  # noqa: E402
import tools.boot4_session as b4  # noqa: E402
import tools.run_resident_limit as rrl  # noqa: E402

FLOOR = 7000.0
OBSERVED = 4560.0  # bal_g2 range, below the floor alone
PRIVATE = 3 * 2**30  # a 2 GiB balloon process with its host copies and runtime


class _Mem:
    def __init__(self, private: int | None) -> None:
        self.rss = 100 * 2**20
        if private is not None:
            self.private = private


class _Proc:
    def __init__(
        self,
        pid: int,
        cmd: list[str],
        private: int | None = PRIVATE,
        *,
        ppid: int = 1,
        name: str = "python.exe",
    ) -> None:
        self.pid = pid
        self.info: dict[str, Any] = {"pid": pid, "ppid": ppid, "name": name, "cmdline": cmd}
        self._private = private

    def memory_info(self) -> _Mem:
        return _Mem(self._private)


BALLOON = ["python.exe", "-u", r"C:\repo\tools\gpu_balloon.py", "--gpu", "--gib", "2"]


def _host(
    monkeypatch: pytest.MonkeyPatch, procs: list[_Proc], observed: float | None = OBSERVED
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    real = mg.evaluate_measurement_gates

    def fake_eval(root: Path, **kw: Any) -> Any:
        calls.append(dict(kw))
        return real(
            root,
            platform_id="aipc-c1",
            available_mb=kw.get("available_mb", observed),
            uptime_s=100.0,
            skip_host_probes=True,
            skip_uptime=bool(kw.get("skip_uptime")),
            ac_override=mg.GateResult("ac", True, "ac_ok"),
            processor_override=mg.GateResult("processor_ac", True, "ok"),
            process_names=[],
        )

    monkeypatch.setattr(mg, "evaluate_measurement_gates", fake_eval)
    monkeypatch.setattr(mg, "probe_available_mb", lambda: observed)
    monkeypatch.setattr(psutil, "process_iter", lambda _attrs=None: iter(procs))
    return calls


def _cc(monkeypatch: pytest.MonkeyPatch, **over: Any) -> None:
    monkeypatch.setattr(b4, "CC_OVERRIDE", dict(over))


def test_without_the_flag_gates_are_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _host(monkeypatch, [_Proc(7, BALLOON)])
    _cc(monkeypatch, cell="CC-BAL-XPS:gpu2:f16")
    with pytest.raises(SystemExit, match="available_mb_below_floor"):
        b4.require_gates()
    assert calls == [{"skip_uptime": False}]  # no available_mb override: probed as before


def test_non_balloon_cells_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _host(monkeypatch, [], observed=9100.0)
    _cc(monkeypatch, cell="CC-MECH-XPS:u4:unlx")
    out = b4.require_gates()
    assert calls == [{"skip_uptime": False}]
    assert "balloon_floor_credit" not in out
    mem = next(g for g in out["gates"] if g["name"] == "available_mb")
    assert mem["detail"] == {
        "floor_mb": FLOOR,
        "observed_mb": 9100.0,
        "citation": mem["detail"]["citation"],
    }


def test_credit_applies_and_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _host(monkeypatch, [_Proc(1, ["svchost.exe"]), _Proc(7, BALLOON)])
    _cc(monkeypatch, cell="CC-BAL-XPS:gpu2:f16", balloon_floor_credit=True)
    out = b4.require_gates()
    rec = out["balloon_floor_credit"]
    assert rec["observed_available_mb"] == OBSERVED
    assert rec["balloon_pid"] == 7 and rec["balloon_private_bytes"] == PRIVATE
    assert rec["balloon_private_mb"] == 3072.0
    assert rec["credited_available_mb"] == OBSERVED + 3072.0
    assert rec["floor_mb"] == FLOOR and "7477" in str(rec["floor_citation"])
    assert rec["passed"] is True
    assert calls == [{"skip_uptime": False, "available_mb": OBSERVED + 3072.0}]
    mem = next(g for g in out["gates"] if g["name"] == "available_mb")
    assert mem["detail"]["observed_is_credited"] is True and mem["detail"]["floor_mb"] == FLOOR


def test_cmd_wrapper_and_venv_launcher_pick_the_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spawn_detached.ps1 runs cmd.exe /c "python ... gpu_balloon.py > log"; a venv python.exe
    launcher then starts the real interpreter with the same command line."""
    wrapper = _Proc(5, ["cmd.exe", "/c", " ".join(BALLOON)], name="cmd.exe")
    launcher = _Proc(6, BALLOON, private=8 * 2**20, ppid=5)
    interp = _Proc(7, BALLOON, ppid=6)
    shell = _Proc(9, ["powershell", "-Command", "gpu_balloon"], name="powershell.exe")
    _host(monkeypatch, [wrapper, launcher, interp, shell])
    _cc(monkeypatch, cell="CC-BAL-XPS:gpu2:f16", balloon_floor_credit=True)
    rec = b4.require_gates()["balloon_floor_credit"]
    assert rec["balloon_pid"] == 7 and rec["balloon_candidates"] == [6, 7]
    assert rec["balloon_private_bytes"] == PRIVATE


def test_credit_does_not_lower_the_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    _host(monkeypatch, [_Proc(7, BALLOON, private=1 * 2**30)], observed=4500.0)
    _cc(monkeypatch, cell="CC-BAL-XPS:gpu2:f16", balloon_floor_credit=True)
    with pytest.raises(SystemExit, match="available_mb_below_floor"):
        b4.require_gates()  # 4,500 + 1,024 < 7,000


@pytest.mark.parametrize(
    "procs",
    [
        [],
        [_Proc(7, BALLOON), _Proc(8, BALLOON)],
        [_Proc(7, BALLOON, private=None)],
    ],
)
def test_unreadable_or_ambiguous_balloon_refuses(
    monkeypatch: pytest.MonkeyPatch, procs: list[_Proc]
) -> None:
    _host(monkeypatch, procs)
    _cc(monkeypatch, cell="CC-BAL-XPS:gpu1:u4", balloon_floor_credit=True)
    with pytest.raises(SystemExit, match="balloon floor credit"):
        b4.require_gates()


def test_unreadable_available_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    _host(monkeypatch, [_Proc(7, BALLOON)], observed=None)
    _cc(monkeypatch, cell="CC-BAL-XPS:gpu1:u4", balloon_floor_credit=True)
    with pytest.raises(SystemExit, match="Available MB unreadable"):
        b4.require_gates()


def test_credit_refuses_outside_cc_bal_in_the_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    _cc(monkeypatch, cell="CC-MECH-XPS:u4", balloon_floor_credit=True)
    with pytest.raises(SystemExit, match="CC-BAL"):
        b4.require_gates()


def _cli(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(rrl, "run_resident_limit", lambda **_kw: seen.update(b4.CC_OVERRIDE) or 0)
    rrl.main(argv)
    return seen


BASE = ["--arm", "gpu_only_f16", "--model-spec", "configs/models/Qwen3-4B-int4-ov.yaml"]


def test_cli_flag_needs_a_cc_bal_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit, match="CC-BAL"):
        _cli(monkeypatch, [*BASE, "--balloon-floor-credit"])
    with pytest.raises(SystemExit, match="CC-BAL"):
        _cli(monkeypatch, [*BASE, "--cc-cell", "CC-MECH-XPS:f16", "--balloon-floor-credit"])
    seen = _cli(
        monkeypatch,
        [
            *BASE,
            "--cc-cell",
            "CC-BAL-XPS:gpu1:f16",
            "--low",
            "8000",
            "--high",
            "18000",
            "--resolution",
            "250",
            "--balloon-floor-credit",
        ],
    )
    assert seen["balloon_floor_credit"] is True


def test_cli_default_has_no_credit(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _cli(
        monkeypatch,
        [
            *BASE,
            "--cc-cell",
            "CC-BAL-XPS:gpu1:f16",
            "--low",
            "8000",
            "--high",
            "18000",
            "--resolution",
            "250",
        ],
    )
    assert "balloon_floor_credit" not in seen
