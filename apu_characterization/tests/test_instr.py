"""Correctness tests for exclusive-time category timers.

Run: python -m apu_characterization.tests.test_instr
"""

from __future__ import annotations

import time

from ..instr import RunAccumulator, measure_timer_overhead_ns, set_run_accumulator, timed
from ..taxonomy import Category


def _spin_ms(ms: float) -> None:
    """Burn thread CPU for approximately ms milliseconds."""
    t0 = time.thread_time_ns()
    target = int(ms * 1e6)
    x = 0
    while time.thread_time_ns() - t0 < target:
        x += 1


def test_nested_exclusive() -> None:
    """Inner region CPU must not be double-counted in the outer region.

    Spin targets are large relative to the Windows thread-time tick
    (15.625 ms), so quantization overshoot stays within the bounds.
    """
    acc = RunAccumulator(profile="test")
    set_run_accumulator(acc)

    with timed(Category.PROMPT_ASSEMBLY, "s0"):
        _spin_ms(50)
        with timed(Category.SERIALIZATION, "s0"):
            _spin_ms(75)
        _spin_ms(50)

    set_run_accumulator(None)
    agg = acc.aggregate_by_category()
    outer = agg["PROMPT_ASSEMBLY"].cpu_ns / 1e6
    inner = agg["SERIALIZATION"].cpu_ns / 1e6

    assert 95 <= outer <= 160, f"outer self-time {outer:.1f} ms, expected ~100"
    assert 70 <= inner <= 120, f"inner self-time {inner:.1f} ms, expected ~75"
    print(f"  nested exclusive: outer={outer:.1f} ms (~100), inner={inner:.1f} ms (~75)  OK")


def test_sum_matches_thread_cpu() -> None:
    """Sum of category CPU + residual must equal total thread CPU."""
    acc = RunAccumulator(profile="test")
    set_run_accumulator(acc)
    t0 = time.thread_time_ns()

    with timed(Category.TOOL_COMPUTE, "s0"):
        _spin_ms(60)
    _spin_ms(40)  # uninstrumented -> residual
    with timed(Category.TOKENIZATION, "s0"):
        _spin_ms(50)

    total = time.thread_time_ns() - t0
    set_run_accumulator(None)

    instrumented = acc.instrumented_cpu_ns()
    residual = acc.residual_cpu_ns(total)
    recon = instrumented + residual
    err = abs(recon - total) / total
    assert err < 0.01, f"invariant broken: {recon} vs {total}"
    assert residual / total > 0.10, "residual should capture the uninstrumented 40 ms"
    print(
        f"  invariant: instrumented={instrumented/1e6:.1f} ms + residual={residual/1e6:.1f} ms"
        f" = total={total/1e6:.1f} ms  OK"
    )


def test_sleep_costs_zero_cpu() -> None:
    """time.sleep inside a region must contribute wall time but ~zero CPU."""
    acc = RunAccumulator(profile="test")
    set_run_accumulator(acc)

    with timed(Category.HTTP_CLIENT, "s0"):
        time.sleep(0.15)

    set_run_accumulator(None)
    agg = acc.aggregate_by_category()
    cpu_ms = agg["HTTP_CLIENT"].cpu_ns / 1e6
    wall_ms = agg["HTTP_CLIENT"].wall_ns / 1e6
    # Allow one Windows thread-time tick (15.625 ms) of measurement noise.
    assert cpu_ms < 16.5, f"sleep burned {cpu_ms:.1f} ms CPU, expected ~0"
    assert wall_ms > 100, f"wall {wall_ms:.1f} ms, expected ~150"
    print(f"  sleep: cpu={cpu_ms:.2f} ms (~0), wall={wall_ms:.0f} ms (~150)  OK")


def test_overhead() -> None:
    ns = measure_timer_overhead_ns(100_000)
    print(f"  timer overhead: {ns:.0f} ns/pair")
    assert ns < 50_000, f"timer overhead {ns:.0f} ns/pair is implausibly high"


def main() -> None:
    print("test_nested_exclusive")
    test_nested_exclusive()
    print("test_sum_matches_thread_cpu")
    test_sum_matches_thread_cpu()
    print("test_sleep_costs_zero_cpu")
    test_sleep_costs_zero_cpu()
    print("test_overhead")
    test_overhead()
    print("all instr tests passed")


if __name__ == "__main__":
    main()
