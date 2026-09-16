from __future__ import annotations

from pathlib import Path

import pytest

from apu_characterization.cap01.contracts import TaskRecord, sha256_bytes
from apu_characterization.cap01.corpus import build_corpus_manifest


def test_corpus_verifies_hidden_test_hash(tmp_path: Path) -> None:
    tests = tmp_path / "hidden.py"
    tests.write_text("assert candidate(1) == 2\n", encoding="utf-8")
    tasks = [
        TaskRecord(
            task_id="CODE-001",
            domain="CODE",
            prompt="increment",
            source="synthetic",
            source_version="1",
            provenance="private",
            license="test",
            verifier={
                "kind": "code",
                "tests_path": "hidden.py",
                "tests_sha256": sha256_bytes(tests.read_bytes()),
            },
            contamination_note="private task",
        )
    ]
    manifest = build_corpus_manifest(
        tasks,
        corpus_root=tmp_path,
        expected_domains={
            "FUNCTION_CALLING": 0,
            "TEXT_TO_SQL": 0,
            "CODE": 1,
            "MATH": 0,
            "STRUCTURED_EXTRACTION": 0,
        },
    )
    assert manifest["domain_counts"]["CODE"] == 1


def test_corpus_rejects_changed_hidden_tests(tmp_path: Path) -> None:
    tests = tmp_path / "hidden.py"
    tests.write_text("assert False\n", encoding="utf-8")
    task = TaskRecord(
        task_id="CODE-001",
        domain="CODE",
        prompt="increment",
        source="synthetic",
        source_version="1",
        provenance="private",
        license="test",
        verifier={
            "kind": "code",
            "tests_path": "hidden.py",
            "tests_sha256": "0" * 64,
        },
        contamination_note="private task",
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        build_corpus_manifest(
            [task],
            corpus_root=tmp_path,
            expected_domains={
                "FUNCTION_CALLING": 0,
                "TEXT_TO_SQL": 0,
                "CODE": 1,
                "MATH": 0,
                "STRUCTURED_EXTRACTION": 0,
            },
        )
