from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apu_characterization.cap01.contracts import (
    CandidateRecord,
    CellCoordinates,
    PoolMetadata,
    TaskRecord,
)
from apu_characterization.cap01.runner import (
    RunRequest,
    prepare_task_plan,
    run_serial,
)


def fixture(task_id: str) -> tuple[TaskRecord, PoolMetadata]:
    task = TaskRecord(
        task_id=task_id,
        domain="MATH",
        prompt="Return one.",
        source="synthetic",
        source_version="1",
        provenance="unit test",
        license="CC0",
        verifier={"kind": "fake"},
        contamination_note="synthetic test fixture",
    )
    candidates = tuple(
        CandidateRecord(
            candidate_id=f"{task_id}-c{index}",
            task_id=task_id,
            ordinal=index,
            content=str(index),
            prompt_tokens=1,
            completion_tokens=1,
        )
        for index in range(3)
    )
    pool = PoolMetadata(
        task_id=task_id,
        generation_model="fixture",
        temperature=0.0,
        prompt_template_sha256="b" * 64,
        candidates=candidates,
    )
    return task, pool


def coordinates(harness: str = "raw_python") -> CellCoordinates:
    return CellCoordinates(
        harness=harness,  # type: ignore[arg-type]
        latency_scale_ms=0,
        wall_budget_ms=100,
        seed=4,
    )


class RunnerTests(unittest.TestCase):
    def test_seed_fixes_order_and_cross_harness_plan(self) -> None:
        task, pool = fixture("parity")
        plans = [
            prepare_task_plan(task, pool, coordinates(harness))
            for harness in ("raw_python", "langgraph", "rust")
        ]
        self.assertEqual(plans[0].canonical_bytes, plans[1].canonical_bytes)
        self.assertEqual(plans[1].canonical_bytes, plans[2].canonical_bytes)
        self.assertEqual(
            [item.candidate_id for item in plans[0].candidates],
            [item.candidate_id for item in pool.ordered_candidates(4)],
        )

    def test_completed_run_is_immutable(self) -> None:
        task, pool = fixture("immutable")
        request = RunRequest(task, pool, coordinates(), lambda _: True)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = run_serial([request], output_root=root, run_id="run-1")
            self.assertTrue((run_dir / "COMPLETED.json").is_file())
            self.assertFalse((run_dir / "RUNNING.json").exists())
            with self.assertRaises(FileExistsError):
                run_serial([request], output_root=root, run_id="run-1", resume=True)

    def test_failed_run_resumes_without_rewriting_results(self) -> None:
        task_a, pool_a = fixture("resume-a")
        task_b, pool_b = fixture("resume-b")
        good = RunRequest(task_a, pool_a, coordinates(), lambda _: True)

        def fail(_: CandidateRecord) -> bool:
            raise RuntimeError("planned interruption")

        bad = RunRequest(task_b, pool_b, coordinates(), fail)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, "planned interruption"):
                run_serial([good, bad], output_root=root, run_id="resume")
            first_result = next((root / "resume" / "results").rglob("resume-a.json"))
            original = first_result.read_bytes()
            repaired = RunRequest(task_b, pool_b, coordinates(), lambda _: True)
            run_dir = run_serial(
                [good, repaired], output_root=root, run_id="resume", resume=True
            )
            self.assertEqual(first_result.read_bytes(), original)
            self.assertTrue((run_dir / "COMPLETED.json").is_file())


if __name__ == "__main__":
    unittest.main()
