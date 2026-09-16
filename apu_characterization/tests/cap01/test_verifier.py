from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from apu_characterization.cap01.contracts import (
    CandidateRecord,
    TaskRecord,
    sha256_bytes,
)
from apu_characterization.cap01.verifier import (
    normalize_numeric,
    reexecute_verification,
    verify_candidate,
)
from apu_characterization.cap01.domain_verifiers import verify_structured_extraction


def candidate(task_id: str, content: str) -> CandidateRecord:
    return CandidateRecord(
        candidate_id="candidate-1",
        task_id=task_id,
        ordinal=0,
        content=content,
        prompt_tokens=1,
        completion_tokens=1,
    )


class VerifierTests(unittest.TestCase):
    def test_math_numeric_normalization_and_tolerance(self) -> None:
        task = TaskRecord(
            task_id="math-1",
            domain="MATH",
            prompt="One half",
            source="synthetic",
            source_version="1",
            provenance="fixture",
            license="CC0",
            verifier={"mode": "numeric", "answer": "0.5", "abs_tol": "0"},
            contamination_note="synthetic fixture",
        )
        verdict = verify_candidate(task, candidate("math-1", r"\boxed{\frac{1}{2}}"))
        self.assertTrue(verdict.solved)
        self.assertEqual("pass", verdict.status)
        self.assertEqual(normalize_numeric("50%"), normalize_numeric("0.5"))
        self.assertGreaterEqual(verdict.wall_ns, 0)

    def test_code_hidden_tests_do_not_leak_and_reexecute(self) -> None:
        secret = "PRIVATE_EXPECTED_BEHAVIOR"
        task = TaskRecord(
            task_id="code-1",
            domain="CODE",
            prompt="Implement add.",
            source="synthetic",
            source_version="1",
            provenance="fixture",
            license="CC0",
            verifier={
                "hidden_tests": (
                    f"assert solution.add(2, 3) == 5, {secret!r}\n"
                    "assert solution.add(-1, 1) == 0"
                )
            },
            contamination_note="synthetic fixture",
        )
        record = candidate("code-1", "def add(a, b):\n    return a + b")
        first = verify_candidate(task, record)
        replay = reexecute_verification(task, record, first)
        self.assertTrue(first.solved)
        self.assertTrue(replay.stable)
        self.assertNotIn(secret, repr(first.to_dict()))
        self.assertEqual(64, len(first.stdout_sha256))
        self.assertEqual(64, len(first.stderr_sha256))

    def test_function_call_uses_pinned_checker_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checker = Path(directory) / "checker.py"
            checker.write_text(
                "def check(candidate, reference):\n"
                "    return candidate == reference\n",
                encoding="utf-8",
            )
            task = TaskRecord(
                task_id="call-1",
                domain="FUNCTION_CALLING",
                prompt="Call lookup.",
                source="BFCL",
                source_version="v4",
                provenance="synthetic fixture",
                license="test",
                verifier={
                    "checker_source_path": str(checker),
                    "checker_source_sha256": sha256_bytes(checker.read_bytes()),
                    "checker_callable": "check",
                    "checker_argument_mode": "candidate_reference",
                    "bfcl_version": "v4",
                    "reference_call": {"name": "lookup", "arguments": {"id": 7}},
                },
                contamination_note="synthetic fixture",
            )
            verdict = verify_candidate(
                task,
                candidate(
                    "call-1",
                    '{"name":"lookup","arguments":{"id":7}}',
                ),
            )
        self.assertTrue(verdict.solved)
        self.assertIn("BFCL-v4", verdict.runtime)

    def test_text_to_sql_canonicalizes_column_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.sqlite"
            with closing(sqlite3.connect(fixture)) as connection:
                connection.execute("CREATE TABLE metrics(name TEXT, value REAL)")
                connection.execute("INSERT INTO metrics VALUES ('x', 1.5)")
                connection.commit()
            task = TaskRecord(
                task_id="sql-1",
                domain="TEXT_TO_SQL",
                prompt="Return metric names and values.",
                source="BIRD",
                source_version="test",
                provenance="synthetic fixture",
                license="test",
                verifier={
                    "fixture_path": str(fixture),
                    "fixture_sha256": sha256_bytes(fixture.read_bytes()),
                    "reference_query": "SELECT name, value FROM metrics",
                },
                contamination_note="synthetic fixture",
            )
            verdict = verify_candidate(
                task, candidate("sql-1", "SELECT value, name FROM metrics")
            )
        self.assertTrue(verdict.solved)
        self.assertTrue(verdict.runtime.startswith("sqlite-"))

    def test_structured_extraction_uses_frozen_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schema = Path(directory) / "schema.json"
            schema.write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["vendor", "date", "amount"],
                        "properties": {
                            "vendor": {"type": "string"},
                            "date": {"type": "string", "format": "date"},
                            "amount": {"type": "string"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            truth = {"vendor": "Acme Inc", "date": "2026-07-14", "amount": "$1,200.00"}
            task = TaskRecord(
                task_id="extract-1",
                domain="STRUCTURED_EXTRACTION",
                prompt="Extract fields from the fixed document.",
                source="synthetic",
                source_version="1",
                provenance="synthetic fixture",
                license="test",
                verifier={
                    "schema_path": str(schema),
                    "schema_sha256": sha256_bytes(schema.read_bytes()),
                    "ground_truth": truth,
                    "ground_truth_secondary": truth,
                    "annotation_sources": ["annotator-a", "annotator-b"],
                    "date_order": "MDY",
                    "currency_paths": ["/amount"],
                },
                contamination_note="synthetic fixture",
            )
            content = '{"vendor":"  ACME   INC ","date":"07/14/2026","amount":"1200"}'
            direct = verify_structured_extraction(content, task.verifier)
            self.assertTrue(direct.solved, direct)
            verdict = verify_candidate(
                task,
                candidate("extract-1", content),
            )
        self.assertTrue(verdict.solved, verdict.to_dict())
        self.assertIn("cap01_d5_norm_v1", verdict.runtime)


if __name__ == "__main__":
    unittest.main()
