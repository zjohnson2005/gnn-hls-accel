from __future__ import annotations

import unittest

from apu_characterization.cap01.calibration import (
    calibrate_pool,
    classify_probabilities,
)
from apu_characterization.cap01.contracts import CandidateRecord, PoolMetadata


def pool(size: int = 2048) -> PoolMetadata:
    return PoolMetadata(
        task_id="math-1",
        generation_model="gpt-test",
        temperature=1.0,
        prompt_template_sha256="a" * 64,
        candidates=tuple(
            CandidateRecord(
                candidate_id=f"c-{index}",
                task_id="math-1",
                ordinal=index,
                content="x",
                prompt_tokens=1,
                completion_tokens=1,
            )
            for index in range(size)
        ),
    )


class CalibrationTests(unittest.TestCase):
    def test_frozen_thresholds_are_strict(self) -> None:
        self.assertEqual("SATURATED", classify_probabilities(0.91, 1.0))
        self.assertEqual("SCALING", classify_probabilities(0.9, 1.0))
        self.assertEqual("DEAD", classify_probabilities(0.0, 0.04))
        self.assertEqual("SCALING", classify_probabilities(0.0, 0.05))

    def test_calibration_uses_50_deterministic_shuffles(self) -> None:
        metadata = pool()
        truth = [False] * len(metadata.candidates)
        truth[7] = True
        first = calibrate_pool(metadata, truth)
        second = calibrate_pool(metadata, truth)
        self.assertEqual("SCALING", first.task_class)
        self.assertEqual(50, first.shuffles)
        self.assertEqual(1.0, first.solved_probability_n2048)
        self.assertEqual(first.digest, second.digest)

    def test_dead_pool_keeps_legacy_secondary_label(self) -> None:
        result = calibrate_pool(pool(), [False] * 2048)
        self.assertEqual("DEAD", result.task_class)
        self.assertTrue(result.legacy_dead_at_128)
        self.assertEqual(("DEAD@128",), result.secondary_labels)


if __name__ == "__main__":
    unittest.main()
