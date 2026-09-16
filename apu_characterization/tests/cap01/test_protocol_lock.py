from __future__ import annotations

import json
from pathlib import Path

import pytest

from apu_characterization.cap01.protocol_lock import (
    build_locked_protocol,
    build_pre_generation_locked_protocol,
    write_locked_protocol,
)


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _manifests(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    tasks = []
    domains = (
        "FUNCTION_CALLING",
        "TEXT_TO_SQL",
        "CODE",
        "MATH",
        "STRUCTURED_EXTRACTION",
    )
    for domain in domains:
        for index in range(50):
            task_id = f"{domain}-{index:03d}"
            verifier = {"kind": domain.lower(), "answer": "1"}
            if domain == "FUNCTION_CALLING":
                verifier = {
                    "checker_source_path": "vendor/bfcl/checker.py",
                    "checker_source_sha256": "a" * 64,
                    "checker_module": "bfcl.checker",
                    "checker_callable": "check",
                    "bfcl_version": "v4",
                }
            elif domain == "TEXT_TO_SQL":
                verifier = {
                    "fixture_path": f"fixtures/{task_id}.sqlite",
                    "fixture_sha256": "a" * 64,
                    "reference_query": "SELECT 1",
                }
            elif domain == "CODE":
                verifier = {
                    "tests_path": f"hidden/{task_id}.py",
                    "tests_sha256": "a" * 64,
                }
            elif domain == "STRUCTURED_EXTRACTION":
                verifier = {
                    "schema_path": f"schemas/{task_id}.json",
                    "schema_sha256": "a" * 64,
                    "ground_truth": {"value": 1},
                    "ground_truth_secondary": {"value": 1},
                    "annotation_sources": ["one", "two"],
                    "date_order": "MDY",
                }
            tasks.append(
                {
                    "task_id": task_id,
                    "domain": domain,
                    "prompt": "prompt",
                    "source": "synthetic",
                    "source_version": "1",
                    "provenance": "private fixture",
                    "license": "test",
                    "verifier": verifier,
                    "contamination_note": "test fixture",
                }
            )
    corpus = _write(root / "corpus.json", {"tasks": tasks})
    pools = _write(
        root / "pools.json",
        {
            "tasks": [
                {"task_id": task["task_id"], "candidate_count": 2048}
                for task in tasks
            ]
        },
    )
    classes = _write(
        root / "classification.json",
        {
            "tasks": [
                {"task_id": task["task_id"], "classification": "SCALING"}
                for task in tasks
            ]
        },
    )
    generation = _write(
        root / "generation.json",
        {
            "generation_model": "test-model",
            "temperature": 0.7,
            "prompt_template": "test",
        },
    )
    verifier_pins = _write(
        root / "verifier_pins.json",
        {
            "bfcl": {"version": "v4", "source_sha256": "a" * 64},
            "sqlite": {"version": "test"},
            "cpython": {"version": "test"},
            "jsonschema": {"version": "test"},
        },
    )
    return corpus, pools, classes, generation, verifier_pins


def test_pre_generation_lock_freezes_corpus_and_generation(tmp_path: Path) -> None:
    corpus, pools, classes, generation, verifier_pins = _manifests(tmp_path)
    locked = build_pre_generation_locked_protocol(
        corpus_manifest=corpus,
        generation_config=generation,
        verifier_pin_manifest=verifier_pins,
    )
    assert locked["status"] == "locked"
    assert locked["lock_phase"] == "pre_generation"
    assert locked["lock_fields"]["pool_manifest_sha256"] == locked["lock_fields"][
        "classification_manifest_sha256"
    ]
    assert all(len(value) == 64 for value in locked["lock_fields"].values())


def test_lock_fills_hashes_and_schedule(tmp_path: Path) -> None:
    corpus, pools, classes, generation, verifier_pins = _manifests(tmp_path)
    locked = build_locked_protocol(
        corpus_manifest=corpus,
        pool_manifest=pools,
        classification_manifest=classes,
        generation_config=generation,
        verifier_pin_manifest=verifier_pins,
    )
    assert locked["status"] == "locked"
    assert locked.get("lock_phase") == "post_generation"
    assert all(len(value) == 64 for value in locked["lock_fields"].values())
    assert locked["locked_schedule"]["all_task_cell_runs"] == 45000


def test_lock_refuses_shallow_pool(tmp_path: Path) -> None:
    corpus, pools, classes, generation, verifier_pins = _manifests(tmp_path)
    pool_data = json.loads(pools.read_text(encoding="utf-8"))
    pool_data["tasks"][0]["candidate_count"] = 2047
    pools.write_text(json.dumps(pool_data), encoding="utf-8")
    with pytest.raises(ValueError, match="below depth"):
        build_locked_protocol(
            corpus_manifest=corpus,
            pool_manifest=pools,
            classification_manifest=classes,
            generation_config=generation,
            verifier_pin_manifest=verifier_pins,
        )


def test_locked_protocol_is_append_only(tmp_path: Path) -> None:
    corpus, pools, classes, generation, verifier_pins = _manifests(tmp_path)
    locked = build_locked_protocol(
        corpus_manifest=corpus,
        pool_manifest=pools,
        classification_manifest=classes,
        generation_config=generation,
        verifier_pin_manifest=verifier_pins,
    )
    output = tmp_path / "locked.json"
    digest = write_locked_protocol(output, locked)
    assert write_locked_protocol(output, locked) == digest
    changed = dict(locked)
    changed["claim_under_test"] = "changed"
    with pytest.raises(FileExistsError):
        write_locked_protocol(output, changed)
