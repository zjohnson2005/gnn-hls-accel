"""Measure epoll wakeup latency for full-path delivery constants.

Linux: eventfd + epoll_wait round-trip (completion -> dispatcher wakeup).
Other platforms: writes literature mid-range used in crossover.py / dispatch_stress.

Run:
  py -3 -m orchestration_engine.characterization.epoll_wakeup_bench
  python3 -m orchestration_engine.characterization.epoll_wakeup_bench --iterations 50000
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from pathlib import Path

OUT_PATH = Path("orchestration_engine/characterization/out/gate/epoll_wakeup.json")

# Mid-range used when not measured locally (see crossover.py DELIVERY_CITATIONS).
LITERATURE_MID_US = 3.5
LITERATURE_RANGE_US = (2.0, 5.0)


def _bench_linux(iterations: int) -> dict:
    import os
    import select

    rfd, wfd = os.pipe()
    flags = os.fcntl.fcntl(rfd, os.fcntl.F_GETFL)
    os.fcntl.fcntl(rfd, os.fcntl.F_SETFL, flags | os.O_NONBLOCK)

    ep = select.epoll()
    ep.register(rfd, select.EPOLLIN)

    # Warmup
    for _ in range(min(1000, iterations // 10)):
        os.write(wfd, b"x")
        ep.poll(0.001)
        os.read(rfd, 1)

    samples_us = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        os.write(wfd, b"x")
        events = ep.poll(0.1)
        if not events:
            raise RuntimeError("epoll_wait timed out")
        os.read(rfd, 1)
        samples_us.append((time.perf_counter() - t0) * 1e6)

    ep.close()
    os.close(rfd)
    os.close(wfd)

    samples_us.sort()
    p50 = statistics.median(samples_us)
    p99 = samples_us[int(len(samples_us) * 0.99) - 1]
    return {
        "platform": platform.platform(),
        "method": "pipe_write_epoll_wait_read",
        "iterations": iterations,
        "median_us": round(p50, 3),
        "p99_us": round(p99, 3),
        "min_us": round(min(samples_us), 3),
        "max_us": round(max(samples_us), 3),
        "source": "measured",
        "citation": (
            "Local pipe->epoll wakeup; use idle Linux host before citing in paper."
        ),
    }


def _literature_stub() -> dict:
    return {
        "platform": platform.platform(),
        "method": "literature_mid_range",
        "iterations": 0,
        "median_us": LITERATURE_MID_US,
        "p99_us": LITERATURE_RANGE_US[1],
        "min_us": LITERATURE_RANGE_US[0],
        "max_us": LITERATURE_RANGE_US[1],
        "source": "literature",
        "citation": (
            "NIC->kernel->epoll path mid-range 2-5 us (Linux networking stack); "
            "run this script on Linux for a measured constant."
        ),
    }


def run_bench(iterations: int = 20000) -> dict:
    if sys.platform.startswith("linux"):
        try:
            return _bench_linux(iterations)
        except OSError as exc:
            return {
                **_literature_stub(),
                "error": str(exc),
                "note": "Linux bench failed; fell back to literature mid-range.",
            }
    return _literature_stub()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Epoll wakeup micro-bench")
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    result = run_bench(args.iterations)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print("\nWrote {0}".format(args.out.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
