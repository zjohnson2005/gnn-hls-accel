"""CPU timer resolution self-test: calibrated busy-loops per category.

Run on the target measurement platform before trusting per-task shares.
Pass criterion: measured CPU within ±10% of calibrated spin target (after
subtracting measured timer overhead).

Run: python -m apu_characterization.tests.test_resolution
"""

from __future__ import annotations

import sys
import time

from ..instr import RunAccumulator, measure_timer_overhead_ns, set_run_accumulator, timed
from ..taxonomy import Category

TARGET_MS = 80.0
TOLERANCE = 0.10
WINDOWS_TICK_MS = 15.625

# Categories exercised in real-agent breakdown
RESOLUTION_CATEGORIES = (
    Category.ORCH_DISPATCH,
    Category.TOOL_COMPUTE,
    Category.TOKENIZATION,
    Category.HTTP_CLIENT,
)


def _spin_ms(ms: float) -> None:
    t0 = time.thread_time_ns()
    target = int(ms * 1e6)
    x = 0
    while time.thread_time_ns() - t0 < target:
        x += 1


def _measure_category(
    cat: Category, target_ms: float, overhead_ms: float
) -> dict[str, float]:
    acc = RunAccumulator(profile="resolution_test")
    set_run_accumulator(acc)

    with timed(cat, "res"):
        _spin_ms(target_ms)

    set_run_accumulator(None)
    measured_ms = acc.totals_for(cat, "res").cpu_ns / 1e6
    adjusted_ms = max(0.0, measured_ms - overhead_ms)
    err = abs(adjusted_ms - target_ms) / target_ms if target_ms else 0.0
    return {
        "category": cat.value,
        "target_ms": target_ms,
        "measured_ms": measured_ms,
        "overhead_ms": overhead_ms,
        "adjusted_ms": adjusted_ms,
        "error_fraction": err,
        "pass": err <= TOLERANCE,
    }


def probe_tick_ms(samples: list[float]) -> float | None:
    """Estimate quantizer step from nonzero CPU samples."""
    nz = sorted(v for v in samples if v > 0.5)
    if len(nz) < 2:
        return None
    diffs = [round(nz[i + 1] - nz[i], 3) for i in range(len(nz) - 1) if nz[i + 1] - nz[i] > 0.5]
    if not diffs:
        return None
    diffs.sort()
    return diffs[len(diffs) // 2]


def main() -> None:
    print(f"platform: {sys.platform}")
    print(f"resolution self-test: target={TARGET_MS} ms, tolerance=+/-{TOLERANCE * 100:.0f}%")
    overhead_ms = measure_timer_overhead_ns(100_000) * 2 / 1e6
    results = [_measure_category(cat, TARGET_MS, overhead_ms) for cat in RESOLUTION_CATEGORIES]
    samples = [r["measured_ms"] for r in results]
    tick = probe_tick_ms(samples)
    if tick:
        print(f"estimated CPU quantizer step: {tick:.3f} ms")
        if sys.platform == "win32" and abs(tick - WINDOWS_TICK_MS) < 2:
            print(
                f"WARNING: ~{WINDOWS_TICK_MS} ms Windows thread-time tick detected. "
                "Per-session CPU below 200 ms is not quotable; use Linux for publishable data."
            )

    all_pass = True
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        if not r["pass"]:
            all_pass = False
        print(
            f"  {r['category']}: measured={r['measured_ms']:.1f} ms "
            f"(adj {r['adjusted_ms']:.1f} ms, err {r['error_fraction'] * 100:.1f}%)  {status}"
        )

    if not all_pass:
        print("resolution self-test FAILED — do not trust per-category shares on this platform")
        sys.exit(1)
    print("resolution self-test passed")


if __name__ == "__main__":
    main()
