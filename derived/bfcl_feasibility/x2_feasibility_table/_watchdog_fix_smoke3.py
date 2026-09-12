"""Smoke: fixed X-2 watchdog (Popen, no DETACHED_PROCESS) produces poll lines."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel")
sys.path.insert(0, str(ROOT))
from tools.run_x2_feasibility import _start_wsh_watchdog  # noqa: E402


def _alive(pid: int) -> bool:
    r = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue) -ne $null",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return (r.stdout or "").strip().lower() in ("true", "true\r")


td = ROOT / "derived" / "bfcl_feasibility" / "x2_feasibility_table" / "_watchdog_fix_smoke3"
td.mkdir(parents=True, exist_ok=True)
for p in td.iterdir():
    try:
        p.unlink()
    except Exception:
        pass

handle = _start_wsh_watchdog(td, interval_s=60)
assert handle is not None
pid = int(handle["pid"])
print("HANDLE", json.dumps(handle, sort_keys=True))
print("alive_after_start", _alive(pid))
assert _alive(pid), "watchdog dead immediately after start"
# Script clamps IntervalS < 30 up to 30; wait past first poll.
time.sleep(35)
log = td / "watchdog_kills.jsonl"
lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
events = [json.loads(ln)["event"] for ln in lines]
print("events", events)
print("alive_35s", _alive(pid))
subprocess.run(
    [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue",
    ],
    check=False,
)
assert "watchdog_start_kill" in events
assert "watchdog_poll" in events or "watchdog_kill" in events, events
print("SMOKE_OK")
