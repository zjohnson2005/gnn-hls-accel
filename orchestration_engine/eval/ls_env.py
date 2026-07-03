"""Load ARCHIVE Vitis + conda toolchain env for LightningSim probes."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def ensure_lightningsim_env() -> None:
    """Set XILINX_HLS (and conda CC/LD paths) if not already in the environment."""
    if os.environ.get("XILINX_HLS"):
        return

    repo = Path(__file__).resolve().parents[2]
    env_sh = repo / "orchestration_engine" / "hls_env_lightningsim.sh"
    if not env_sh.is_file():
        raise SystemExit(
            "XILINX_HLS is not set. Source the LS env first:\n"
            f"  source {env_sh}\n"
            "Or run: bash orchestration_engine/run_ls_probe.sh"
        )

    cmd = f"source '{env_sh}' && env -0"
    proc = subprocess.run(
        ["bash", "-lc", cmd],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or b"").decode(errors="replace")
        raise SystemExit(f"Failed to source {env_sh}:\n{err}")

    for entry in proc.stdout.split(b"\0"):
        if not entry or b"=" not in entry:
            continue
        key, val = entry.split(b"=", 1)
        os.environ[key.decode()] = val.decode(errors="replace")

    if not os.environ.get("XILINX_HLS"):
        raise SystemExit(f"Sourced {env_sh} but XILINX_HLS is still unset")
