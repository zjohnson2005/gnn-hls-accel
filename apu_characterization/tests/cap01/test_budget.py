from __future__ import annotations

import unittest

from apu_characterization.cap01.budget import PoolExhaustionError, execute_task_loop
from apu_characterization.cap01.contracts import CandidateRecord
from apu_characterization.cap01.harnesses import RawPythonHarness


def candidate(index: int) -> CandidateRecord:
    return CandidateRecord(
        candidate_id=f"c{index}",
        task_id="task",
        ordinal=index,
        content=f"answer {index}",
        prompt_tokens=1,
        completion_tokens=1,
    )


class FakeClock:
    def __init__(self) -> None:
        self.now = 0
        self.sleeps: list[int] = []

    def clock(self) -> int:
        return self.now

    def sleep(self, seconds: float) -> None:
        duration = int(round(seconds * 1_000_000_000))
        self.sleeps.append(duration)
        self.now += duration


class SetupAdvancingHarness(RawPythonHarness):
    def __init__(self, fake: FakeClock) -> None:
        super().__init__()
        self.fake = fake

    def setup(self) -> None:
        self.fake.now += 17


class BudgetTests(unittest.TestCase):
    def test_ready_barrier_and_sleep_clipping(self) -> None:
        fake = FakeClock()
        result = execute_task_loop(
            task_id="task",
            candidates=[candidate(0)],
            latency_ns=[10_000_000],
            wall_budget_ms=5,
            adapter=SetupAdvancingHarness(fake),
            verifier=lambda _: True,
            clock_ns=fake.clock,
            sleep=fake.sleep,
        )
        self.assertEqual(result.ready_ns, 17)
        self.assertEqual(fake.sleeps, [5_000_000])
        self.assertEqual((result.started, result.counted, result.abandoned), (1, 0, 1))
        self.assertFalse(result.solved)

    def test_only_verdict_strictly_before_deadline_counts(self) -> None:
        fake = FakeClock()

        def verifier(_: CandidateRecord) -> bool:
            fake.now += 1_000_000
            return True

        result = execute_task_loop(
            task_id="task",
            candidates=[candidate(0)],
            latency_ns=[0],
            wall_budget_ms=1,
            adapter=RawPythonHarness(),
            verifier=verifier,
            clock_ns=fake.clock,
            sleep=fake.sleep,
        )
        self.assertEqual((result.counted, result.abandoned), (0, 1))
        self.assertFalse(result.solved)

    def test_pool_exhaustion_is_hard_failure(self) -> None:
        fake = FakeClock()
        with self.assertRaises(PoolExhaustionError) as raised:
            execute_task_loop(
                task_id="task",
                candidates=[candidate(0)],
                latency_ns=[0],
                wall_budget_ms=1,
                adapter=RawPythonHarness(),
                verifier=lambda _: False,
                clock_ns=fake.clock,
                sleep=fake.sleep,
            )
        result = raised.exception.result
        self.assertTrue(result.pool_exhausted)
        self.assertEqual(result.started, result.counted + result.abandoned)


if __name__ == "__main__":
    unittest.main()
