"""Compare WSH watchdog spawn methods (X-2 vs matrix Start-Process)."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

ROOT = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel")
TD = ROOT / "derived" / "bfcl_feasibility" / "x2_feasibility_table" / "_watchdog_spawn_test"
TD.mkdir(parents=True, exist_ok=True)
SCRIPT = TD / "_wsh_watchdog.ps1"
LOG = TD / "watchdog_kills.jsonl"

BODY = r"""param([string]$LogPath, [int]$IntervalS)
$ErrorActionPreference = "Continue"
if ($IntervalS -lt 5) { $IntervalS = 5 }
while ($true) {
    Start-Sleep -Seconds $IntervalS
    $utc = (Get-Date).ToUniversalTime().ToString("o")
    $procs = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
    if ($procs.Count -eq 0) {
        $rec = [ordered]@{ utc = $utc; event = "watchdog_poll"; n_found = 0; n_killed = 0 }
        Add-Content -LiteralPath $LogPath -Value (ConvertTo-Json -InputObject $rec -Compress)
        continue
    }
    $pids = @($procs | ForEach-Object { [int]$_.Id })
    $procs | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    $left = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
    $rec = [ordered]@{
        utc            = $utc
        event          = "watchdog_kill"
        n_found        = $pids.Count
        pids_found     = $pids
        n_killed       = $pids.Count - $left.Count
        pids_remaining = @($left | ForEach-Object { [int]$_.Id })
    }
    Add-Content -LiteralPath $LogPath -Value (ConvertTo-Json -InputObject $rec -Compress -Depth 4)
}
"""
SCRIPT.write_text(BODY, encoding="utf-8")


def _clear_log() -> None:
    if LOG.exists():
        LOG.unlink()


def _read_lines() -> list[str]:
    if not LOG.exists():
        return []
    return [ln for ln in LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]


def spawn_popen(label: str, flags: int) -> dict:
    _clear_log()
    proc = subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-NoLogo",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-LogPath",
            str(LOG),
            "-IntervalS",
            "5",
        ],
        cwd=str(ROOT),
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)
    alive1 = proc.poll() is None
    time.sleep(7.0)
    alive8 = proc.poll() is None
    lines = _read_lines()
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception as exc:  # noqa: BLE001
        print("terminate_err", label, exc)
    return {
        "label": label,
        "flags": flags,
        "pid": proc.pid,
        "alive_after_1s": alive1,
        "alive_after_8s": alive8,
        "n_log_lines": len(lines),
        "sample": lines[:2],
    }


def spawn_start_process() -> dict:
    _clear_log()
    helper = TD / "_start_process_spawn.ps1"
    helper.write_text(
        f"""
$ErrorActionPreference = "Stop"
$p = Start-Process -FilePath "powershell.exe" -PassThru -WindowStyle Hidden -ArgumentList @(
    "-NoProfile", "-NoLogo", "-ExecutionPolicy", "Bypass",
    "-File", "{SCRIPT}",
    "-LogPath", "{LOG}",
    "-IntervalS", "5"
)
Start-Sleep -Seconds 8
$alive = $null -ne (Get-Process -Id $p.Id -ErrorAction SilentlyContinue)
$n = @(Get-Content -LiteralPath "{LOG}" -ErrorAction SilentlyContinue).Count
[pscustomobject]@{{
    label = "start_process_matrix_pattern"
    pid = $p.Id
    alive_after_8s = $alive
    n_log_lines = $n
}} | ConvertTo-Json -Compress
if ($alive) {{ Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }}
""",
        encoding="utf-8",
    )
    r = subprocess.run(
        ["powershell.exe", "-NoProfile", "-File", str(helper)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    out = (r.stdout or "").strip()
    try:
        payload = json.loads(out.splitlines()[-1])
    except Exception:
        payload = {"raw_stdout": out, "stderr": r.stderr, "code": r.returncode}
    return payload


def main() -> None:
    results = [
        spawn_popen("x2_DETACHED|NEW_GROUP", 0x00000008 | 0x00000200),
        spawn_popen("NEW_GROUP_only", 0x00000200),
        spawn_popen("no_flags", 0),
        spawn_start_process(),
    ]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
