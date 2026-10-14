"""Per-canary host telemetry (NPU amendment 2026-10-14, canary state).

Recorded next to each canary of a guarded NPU-INT8 envelope session. Never
gates, never raises: a field that cannot be read is recorded with its
error. Fields: CPU clock (psutil.cpu_freq), GPU clock (no portable reader;
recorded as not read), active power plan (powercfg /getactivescheme on
Windows), free memory, process count and process names with the change
since the previous canary.
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from typing import Any

POWERCFG_TIMEOUT_S = 5.0
GPU_CLOCK_NOTE = "not read: no portable GPU clock reader on openvino-genai 2026.2.1 hosts"


def _cpu_clock() -> dict[str, Any]:
    try:
        import psutil

        freq = psutil.cpu_freq()
        if freq is None:
            return {"error": "psutil.cpu_freq returned None"}
        return {"current_mhz": freq.current, "min_mhz": freq.min, "max_mhz": freq.max}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _power_plan() -> dict[str, Any]:
    if sys.platform != "win32":
        return {"error": "not windows"}
    try:
        done = subprocess.run(
            ["powercfg", "/getactivescheme"],
            capture_output=True,
            text=True,
            timeout=POWERCFG_TIMEOUT_S,
            check=False,
        )
        return {"returncode": done.returncode, "text": done.stdout.strip()}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _memory() -> dict[str, Any]:
    try:
        import psutil

        vm = psutil.virtual_memory()
        return {"available_mb": vm.available / 1048576.0, "total_mb": vm.total / 1048576.0}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _process_names() -> tuple[Counter[str] | None, str | None]:
    try:
        import psutil

        names: Counter[str] = Counter()
        for proc in psutil.process_iter(["name"]):
            names[str(proc.info.get("name") or "?")] += 1
        return names, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


class CanaryTelemetry:
    """Callable: one snapshot per call, with the process-name change since the last."""

    def __init__(self) -> None:
        self._previous: Counter[str] | None = None

    def __call__(self) -> dict[str, Any]:
        names, error = _process_names()
        processes: dict[str, Any] = {"error": error}
        if names is not None:
            processes = {
                "count": sum(names.values()),
                "names": dict(sorted(names.items())),
                "added_since_previous": None,
                "removed_since_previous": None,
            }
            if self._previous is not None:
                processes["added_since_previous"] = dict(sorted((names - self._previous).items()))
                processes["removed_since_previous"] = dict(sorted((self._previous - names).items()))
            self._previous = names
        return {
            "cpu_clock": _cpu_clock(),
            "gpu_clock": {"error": GPU_CLOCK_NOTE},
            "power_plan": _power_plan(),
            "memory": _memory(),
            "processes": processes,
        }
