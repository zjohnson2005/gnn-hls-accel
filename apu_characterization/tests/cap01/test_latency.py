from __future__ import annotations

import unittest

from apu_characterization.cap01.latency import (
    LOGNORMAL_SIGMA,
    encode_execution_plan,
    make_latency_plan,
)


class LatencyTests(unittest.TestCase):
    def test_draws_are_coordinate_deterministic(self) -> None:
        first = make_latency_plan("task-1", 7, 20, 32)
        second = make_latency_plan("task-1", 7, 20, 32)
        self.assertEqual(LOGNORMAL_SIGMA, 0.6)
        self.assertEqual(first.draws_ns, second.draws_ns)
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())
        self.assertNotEqual(first.draws_ns, make_latency_plan("task-1", 8, 20, 32).draws_ns)

    def test_execution_plan_is_byte_identical_for_every_harness(self) -> None:
        draws = make_latency_plan("floor-anchor", 2, 20, 3).draws_ns
        plans = [
            encode_execution_plan("floor-anchor", 2, ("a", "b", "c"), draws)
            for _harness in ("raw_python", "langgraph", "rust")
        ]
        self.assertEqual(plans[0], plans[1])
        self.assertEqual(plans[1], plans[2])

    def test_zero_latency_is_supported(self) -> None:
        self.assertEqual(make_latency_plan("tiny", 0, 0, 4).draws_ns, (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
