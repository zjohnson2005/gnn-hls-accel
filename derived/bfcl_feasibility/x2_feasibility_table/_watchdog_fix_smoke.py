"""Smoke: fixed X-2 watchdog spawn produces poll lines (interval 5 s)."""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel")
import sys

sys.path.insert(0, str(ROOT))
from tools.run_x2_feasibility import _start_wsh_watchdog  # noqa: E402

td = ROOT / "derived" / "bfcl_feasibility" / "x2_feasibility_table" / "_watchdog_fix_smoke"
if td.exists():
    for p in td.iterdir():
        try:
            p.unlink()
        except Exception:
            pass
td.mkdir(parents=True, exist_ok=True)
handle = _start_wsh_watchdog(td, interval_s=5)
assert handle is not None, "handle None"
pid = int(handle["pid"])
print("HANDLE", json.dumps(handle, sort_keys=True))
time.sleep(8)
log = td / "watchdog_kills.jsonl"
lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
print("N_LINES", len(lines))
for ln in lines:
    print("LINE", ln)
events = [json.loads(ln)["event"] for ln in lines]
assert "watchdog_start_kill" in events, events
assert "watchdog_poll" in events or "watchdog_kill" in events, events
# stop
import subprocess

subprocess.run(
    [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue",
    ],
    check=False,
)
print("SMOKE_OK")
