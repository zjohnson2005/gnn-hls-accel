"""Per-turn wall-clock watchdog (Task AW, harness only; default off)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.turn_watchdog import HANG_EVENTS_NAME, HANG_EXIT_CODE, TurnWatchdog  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    StubCloudBackend,
    StubLocalBackend,
    build_argparser,
    build_turn_watchdog,
    main,
    run_interleaved_session,
)

PWSH = shutil.which("pwsh")


class _ExitError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def _raise_exit(code: int) -> None:
    raise _ExitError(code)


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _turn() -> dict[str, Any]:
    return {
        "n_ctx": 100,
        "ttft_s": 0.5,
        "decode_tok_s": 20.0,
        "emitted_parseable_tool_call": True,
        "turn_wall_s": 0.01,
        "t_generate": 0.004,
        "t_tokenize": 0.002,
        "t_template_build": 0.002,
        "t_tool_exec": 0.002,
    }


def test_no_fire_within_limit_or_when_disarmed(tmp_path: Path) -> None:
    clock = _Clock()
    wd = TurnWatchdog(limit_s=10, out_dir=tmp_path, exit_fn=_raise_exit, clock=clock)
    assert wd.check() is None
    wd.arm(entry_id="e0", policy="local_only", turn=0)
    clock.t = 10.0
    assert wd.check() is None
    wd.disarm()
    clock.t = 1000.0
    assert wd.check() is None
    assert not (tmp_path / HANG_EVENTS_NAME).exists()


def test_fire_records_hang_dumps_stacks_and_exits(tmp_path: Path) -> None:
    clock = _Clock()
    seen: list[dict[str, Any]] = []
    wd = TurnWatchdog(
        limit_s=10,
        out_dir=tmp_path,
        run_id="r1",
        on_fire=seen.append,
        exit_fn=_raise_exit,
        clock=clock,
    )
    wd.arm(entry_id="multi_turn_long_context_123", policy="local_only", turn=0)
    clock.t = 10.5
    with pytest.raises(_ExitError) as exc:
        wd.check()
    assert exc.value.code == HANG_EXIT_CODE == 86
    doc = json.loads((tmp_path / HANG_EVENTS_NAME).read_text(encoding="utf-8"))
    (rec,) = doc["events"]
    assert rec["outcome"] == "hang"
    assert rec["entry_id"] == "multi_turn_long_context_123"
    assert rec["turn"] == 0 and rec["policy"] == "local_only" and rec["run_id"] == "r1"
    assert rec["elapsed_s"] == 10.5 and rec["limit_s"] == 10.0
    assert rec["pid"] == os.getpid()
    assert rec["errors"] == []
    stacks = (tmp_path / rec["stacks"]).read_text(encoding="utf-8")
    assert "test_fire_records_hang_dumps_stacks_and_exits" in stacks
    assert seen and seen[0]["entry_id"] == rec["entry_id"]


def test_fires_once(tmp_path: Path) -> None:
    clock = _Clock()
    exits: list[int] = []
    wd = TurnWatchdog(limit_s=1, out_dir=tmp_path, exit_fn=exits.append, clock=clock)
    wd.arm(entry_id="e0", policy="p", turn=2)
    clock.t = 5.0
    assert wd.check() is not None
    assert wd.check() is None
    assert exits == [HANG_EXIT_CODE]


def test_dump_cmd_gets_pid_and_failures_are_recorded(tmp_path: Path) -> None:
    clock = _Clock()
    cmd = [sys.executable, "-c", "import sys; print('PID=' + sys.argv[1])", "{pid}"]
    wd = TurnWatchdog(
        limit_s=1, out_dir=tmp_path, dump_cmd=cmd, exit_fn=lambda _c: None, clock=clock
    )
    wd.arm(entry_id="e/0", policy="p", turn=1)
    clock.t = 2.0
    rec = wd.check()
    assert rec is not None and rec["dump"]["returncode"] == 0
    assert (tmp_path / rec["dump"]["path"]).read_text().strip() == f"PID={os.getpid()}"
    assert rec["dump"]["path"] == "hang_dump_e_0_t1.txt"

    bad = TurnWatchdog(
        limit_s=1,
        out_dir=tmp_path / "b",
        dump_cmd=[str(tmp_path / "no_such_py_spy.exe")],
        on_fire=lambda _r: (_ for _ in ()).throw(RuntimeError("boom")),
        exit_fn=lambda _c: None,
        clock=clock,
    )
    bad.arm(entry_id="e1", policy="p", turn=0)
    clock.t = 10.0
    rec2 = bad.check()
    assert rec2 is not None
    assert any(e.startswith("dump:") for e in rec2["errors"])
    assert any(e.startswith("on_fire: RuntimeError") for e in rec2["errors"])
    saved = json.loads((tmp_path / "b" / HANG_EVENTS_NAME).read_text())["events"]
    assert len(saved) == 1 and saved[0]["errors"] == rec2["errors"]


def test_thread_fires_on_real_clock(tmp_path: Path) -> None:
    exits: list[int] = []
    wd = TurnWatchdog(limit_s=0.05, out_dir=tmp_path, exit_fn=exits.append, poll_s=0.01)
    wd.start()
    try:
        wd.arm(entry_id="e0", policy="p", turn=0)
        for _ in range(300):
            if exits:
                break
            import time

            time.sleep(0.01)
    finally:
        wd.stop()
    assert exits == [HANG_EXIT_CODE]


def test_limit_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        TurnWatchdog(limit_s=0, out_dir=tmp_path)


class _HangOn(StubLocalBackend):
    """Stub local backend whose turn for one entry runs past the watchdog limit."""

    def __init__(self, *, hang_entry: str, clock: _Clock, **kw: Any) -> None:
        super().__init__(**kw)
        self.hang_entry = hang_entry
        self.clock = clock

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> Any:
        if str(entry["id"]) == self.hang_entry:
            self.clock.t += 1e6
            self.turn_watchdog.check()  # type: ignore[attr-defined]
        return super().run_turn(entry, turn_idx, model=model)


def test_session_persists_hang_outcome(tmp_path: Path) -> None:
    clock = _Clock()
    script = {f"e{i}": [_turn()] for i in range(3)}
    entries = [{"id": f"e{i}", "question": [[]], "n_user_turns": 1} for i in range(3)]
    wd = TurnWatchdog(limit_s=900, out_dir=tmp_path, exit_fn=_raise_exit, clock=clock)
    out = tmp_path / "run"
    with pytest.raises(_ExitError):
        run_interleaved_session(
            entries=entries,
            out_dir=out,
            local=_HangOn(hang_entry="e1", clock=clock, script=script),
            cloud=StubCloudBackend(tokens_in=1000, tokens_out=200),
            policies=("slo_escalate",),
            policy_caps_usd={"slo_escalate": 1.0},
            session_max_usd=1.0,
            run_id="hang-1",
            skip_entry_assert=True,
            seal=False,
            turn_watchdog=wd,
        )
    plan = json.loads((out / "plan.json").read_text())
    assert plan["turn_watchdog"]["limit_s"] == 900.0
    assert plan["turn_watchdog"]["exit_code"] == 86
    pol = out / "policies" / "slo_escalate"
    ckpt = json.loads((pol / "checkpoint.json").read_text())
    assert ckpt["completed_entry_ids"] == ["e0"]
    assert ckpt["status"] == "aborted_hang"
    quality = json.loads((pol / "entry_quality.json").read_text())["entries"]
    assert quality[-1]["entry_id"] == "e1" and quality[-1]["outcome"] == "hang"
    summary = json.loads((out / "summary.json").read_text())
    assert summary["status"] == "aborted_hang"
    assert summary["hang"]["entry_id"] == "e1" and summary["hang"]["turn"] == 0
    session_ckpt = json.loads((out / "checkpoint.json").read_text())
    assert session_ckpt["cell_log"][-1]["status"] == "hang"
    events = json.loads((out / HANG_EVENTS_NAME).read_text())["events"]
    assert events[0]["run_id"] == "hang-1"


def test_default_off_plan_unchanged(tmp_path: Path) -> None:
    script = {"e0": [_turn()]}
    local = StubLocalBackend(script=script)
    run_interleaved_session(
        entries=[{"id": "e0", "question": [[]], "n_user_turns": 1}],
        out_dir=tmp_path / "run",
        local=local,
        cloud=StubCloudBackend(tokens_in=1000, tokens_out=200),
        policies=("slo_escalate",),
        policy_caps_usd={"slo_escalate": 1.0},
        session_max_usd=1.0,
        run_id="off-1",
        skip_entry_assert=True,
        seal=False,
    )
    plan = json.loads((tmp_path / "run" / "plan.json").read_text())
    assert "turn_watchdog" not in plan
    assert not hasattr(local, "turn_watchdog")
    assert not (tmp_path / "run" / HANG_EVENTS_NAME).exists()


def test_cli_defaults_and_refusals(tmp_path: Path) -> None:
    args = build_argparser().parse_args(["--out", str(tmp_path)])
    assert args.turn_watchdog_s is None and args.hang_dump_py_spy is None
    assert build_turn_watchdog(args) is None
    args = build_argparser().parse_args(["--out", str(tmp_path), "--hang-dump-py-spy", "x"])
    with pytest.raises(SystemExit, match="needs --turn-watchdog-s"):
        build_turn_watchdog(args)
    args = build_argparser().parse_args(["--out", str(tmp_path), "--turn-watchdog-s", "-1"])
    with pytest.raises(SystemExit, match="must be positive"):
        build_turn_watchdog(args)
    args = build_argparser().parse_args(
        [
            "--out",
            str(tmp_path),
            "--turn-watchdog-s",
            "900",
            "--hang-dump-py-spy",
            "C:/x/py-spy.exe",
        ]
    )
    wd = build_turn_watchdog(args)
    assert wd.limit_s == 900.0
    assert wd.dump_cmd == ["C:/x/py-spy.exe", "dump", "--native", "--pid", "{pid}"]
    with pytest.raises(SystemExit, match="interleaved only"):
        main(
            [
                "--out",
                str(tmp_path),
                "--allow-dirty",
                "--policy",
                "slo_escalate",
                "--turn-watchdog-s",
                "900",
            ]
        )


@pytest.mark.skipif(PWSH is None, reason="pwsh not installed")
def test_launcher_passes_watchdog_flags() -> None:
    done = subprocess.run(
        [
            str(PWSH),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(ROOT / "tools" / "launch_h1.ps1"),
            "-DryRun",
            "-AllowDirty",
            "-NoCloudPing",
            "-Interleaved",
            "-InterleavedPolicies",
            "local_only",
            "-PolicyCapUsd",
            "local_only=0",
            "-SessionMaxUsd",
            "1",
            "-Placement",
            "gpu_only",
            "-Kv",
            "default",
            "-Residency",
            "RESIDENT",
            "-Entries",
            "derived/h1_hybrid/demo1/DEMO1_LONGCTX_30.json",
            "-EntryOffset",
            "14",
            "-EntryCount",
            "16",
            "-TurnWatchdogS",
            "1800",
            "-HangDumpPySpy",
            "C:\\tools\\py-spy.exe",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "POWERSHELL_TELEMETRY_OPTOUT": "1"},
    )
    out = done.stdout + done.stderr
    # Parameters bind (no type or case-collision error); off the host the dry run
    # then stops at the host gates, before the worker command is printed.
    assert "Mode           : INTERLEAVED" in out
    assert "TurnWatchdogS" not in out and "HangDumpPySpy" not in out


def test_launcher_passthrough_lines() -> None:
    text = (ROOT / "tools" / "launch_h1.ps1").read_text(encoding="utf-8")
    assert "[Nullable[double]]$TurnWatchdogS = $null" in text
    assert "$resolvedCmd + ' --turn-watchdog-s ' + $TurnWatchdogS" in text
    assert "$resolvedCmd + ' --hang-dump-py-spy \"' + $HangDumpPySpy + '\"'" in text
