"""Host utilization sampling during a measured batch window.

Samples process-wide and host-wide CPU utilization at a fixed interval on a
daemon thread, and records context-switch and load-average deltas across the
batch window. Used by the concurrency scaling sweep (section 2.4 of the sweep
spec): load average, CPU utilization time series (1 s sampling via psutil),
and context-switch counts per batch.

Degrades gracefully when psutil is missing: the summary records
status="psutil_missing" and all series are empty.
"""

from __future__ import annotations

import threading
import time
from typing import Any


def _loadavg() -> list[float] | None:
    try:
        import os

        return [round(x, 3) for x in os.getloadavg()]
    except (AttributeError, OSError):
        return None


class BatchSampler:
    """1 s CPU utilization sampler over a batch window.

    Usage:
        sampler = BatchSampler()
        sampler.start()
        ... run batch ...
        summary = sampler.stop()
    """

    def __init__(self, interval_s: float = 1.0) -> None:
        self.interval_s = interval_s
        self._samples: list[dict[str, float]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._t0 = 0.0
        self._psutil = None
        self._ctx0: tuple[int, int] | None = None
        self._load0: list[float] | None = None

    def start(self) -> None:
        try:
            import psutil

            self._psutil = psutil
        except ImportError:
            self._psutil = None
            return
        self._t0 = time.perf_counter()
        stats = self._psutil.cpu_stats()
        self._ctx0 = (stats.ctx_switches, stats.interrupts)
        self._load0 = _loadavg()
        # Prime the non-blocking cpu_percent baseline.
        self._psutil.cpu_percent(interval=None)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        assert self._psutil is not None
        while not self._stop.wait(self.interval_s):
            pct = self._psutil.cpu_percent(interval=None)
            self._samples.append(
                {
                    "t_s": round(time.perf_counter() - self._t0, 3),
                    "cpu_pct": pct,
                }
            )

    def stop(self) -> dict[str, Any]:
        if self._psutil is None:
            return {
                "status": "psutil_missing",
                "interval_s": self.interval_s,
                "samples": [],
                "cpu_pct_median": None,
                "cpu_pct_max": None,
                "ctx_switches": None,
                "loadavg_start": None,
                "loadavg_end": None,
            }
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_s * 2)
        stats = self._psutil.cpu_stats()
        ctx_delta = None
        if self._ctx0 is not None:
            ctx_delta = stats.ctx_switches - self._ctx0[0]
        pcts = sorted(s["cpu_pct"] for s in self._samples)
        n = len(pcts)
        median = pcts[n // 2] if n % 2 == 1 else (
            (pcts[n // 2 - 1] + pcts[n // 2]) / 2 if n else None
        )
        return {
            "status": "ok",
            "interval_s": self.interval_s,
            "n_samples": n,
            "samples": self._samples,
            "cpu_pct_median": median,
            "cpu_pct_max": pcts[-1] if pcts else None,
            "ctx_switches": ctx_delta,
            "loadavg_start": self._load0,
            "loadavg_end": _loadavg(),
        }
