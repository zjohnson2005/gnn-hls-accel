"""Post-mortem helpers when LightningSim instrumented testbench crashes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=120,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out
    except FileNotFoundError:
        return 127, f"(command not found: {cmd[0]})"
    except subprocess.TimeoutExpired:
        return 124, "(timed out)"


def diagnose(
    solution_dir: Path,
    art_dir: Path | None,
    tmp_dir: Path | None,
    tb_bin: Path | None,
) -> None:
    print("\n=== LS crash diagnostics ===")

    if tmp_dir and tmp_dir.is_dir():
        print(f"tempdir: {tmp_dir}")
        fifos = sorted(tmp_dir.glob("fifo_*.ll"))
        if fifos:
            for f in fifos:
                print(f"  fifo IR: {f.name} ({f.stat().st_size} bytes)")
        else:
            print("  WARNING: no fifo_*.ll in tempdir (FIFO template did not generate)")

    csim_dir = solution_dir / "csim" / "build"
    csim_bins = []
    if csim_dir.is_dir():
        csim_bins = [
            p
            for p in csim_dir.rglob("*")
            if p.is_file() and p.stat().st_mode & 0o111 and "csim" in p.name.lower()
        ]
        csim_bins += [p for p in csim_dir.glob("*") if p.is_file() and p.stat().st_mode & 0o111]
    if csim_bins:
        csim_bin = csim_bins[0]
        rc, out = _run([str(csim_bin)], cwd=csim_bin.parent)
        print(f"Vitis csim binary {csim_bin.name}: exit {rc}")
        if out.strip():
            print(out[-1500:])
    else:
        print(f"(no Vitis csim binary under {csim_dir})")

    if not tb_bin or not tb_bin.is_file():
        print("(LS testbench binary not found — skip rerun/gdb)")
        return

    print(f"LS testbench: {tb_bin}")
    rc, out = _run([str(tb_bin)], cwd=art_dir)
    print(f"  rerun without trace fd: exit {rc}")
    if out.strip():
        print(out[-800:])

    rc, out = _run([str(tb_bin)], cwd=art_dir, env=_trace_env())
    print(f"  rerun with HLSLITESIM_TRACE_FD: exit {rc}")

    # gdb inherits fd 9 from env but needs it open — use shell redirect
    import os

    env = _trace_env()
    if art_dir:
        os.chdir(art_dir)
    gdb_cmd = (
        f"HLSLITESIM_TRACE_FD=9 gdb -batch -ex run -ex 'bt 25' {tb_bin} 9>/dev/null 2>&1"
    )
    rc, out = _run(["bash", "-lc", gdb_cmd], cwd=art_dir)
    if rc != 127:
        print("  gdb backtrace:")
        print(out[-2500:] if out else "(empty)")
    else:
        print(f"  {out}")
    import os

    env = os.environ.copy()
    env["HLSLITESIM_TRACE_FD"] = "9"
    return env


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: ls_crash_diag.py <solution_dir> [art_dir] [tmp_dir] [tb_bin]")
        return 2
    solution = Path(sys.argv[1])
    art = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None
    tmp = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
    tb = Path(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else None
    diagnose(solution, art, tmp, tb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
