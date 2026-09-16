#!/usr/bin/env python3
"""Assemble a private synthetic five-domain CAP-01 corpus (50 tasks/domain).

This is NOT a licensed BFCL/BIRD/HumanEval publication corpus. It satisfies
protocol shape so P0→P2 can execute end-to-end under result_validity=debug_only.
Publication capability_scaling requires replacing these manifests with licensed
sources and re-locking.

Scope exclusions (verbatim in domain headers):
  - BFCL Multi-Turn subset excluded (CAP-01 died-ledger #4)
  - BIRD interactive mode excluded (CAP-01 died-ledger #3)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from apu_characterization.cap01.contracts import TaskRecord, sha256_bytes
from apu_characterization.cap01.corpus import build_corpus_manifest, write_corpus_manifest

DOMAINS = (
    "FUNCTION_CALLING",
    "TEXT_TO_SQL",
    "CODE",
    "MATH",
    "STRUCTURED_EXTRACTION",
)

SCOPE_EXCLUSIONS = {
    "FUNCTION_CALLING": (
        "BFCL Multi-Turn subset excluded from CAP-01; single-turn and "
        "parallel-turn only (died-ledger #4)."
    ),
    "TEXT_TO_SQL": (
        "BIRD interactive mode excluded from CAP-01; static verifier only "
        "(died-ledger #3)."
    ),
    "CODE": "HumanEval+/MBPP-style hidden-test tasks only; no live shell.",
    "MATH": "Exact-answer / numeric-tolerance MATH only.",
    "STRUCTURED_EXTRACTION": (
        "Fixed-document extraction with frozen normalization; double-keyed truth."
    ),
}


def _write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(path.read_bytes())


def _build_function_calling(root: Path, index: int) -> TaskRecord:
    task_id = f"FC-{index:03d}"
    checker = root / "assets" / "function_calling" / f"{task_id}_checker.py"
    digest = _write(
        checker,
        "import json\n"
        "def check(candidate, reference):\n"
        "    if isinstance(reference, str):\n"
        "        reference = json.loads(reference)\n"
        "    return candidate == reference\n",
    )
    answer = {"name": "lookup", "arguments": {"q": index}}
    return TaskRecord(
        task_id=task_id,
        domain="FUNCTION_CALLING",
        prompt=f"Emit a JSON function call lookup(q={index}).",
        source="BFCL-synthetic",
        source_version="v4-private-fixture",
        provenance="private synthetic CAP-01 fixture (not BFCL release data)",
        license="private-test",
        verifier={
            "checker_source_path": str(checker.relative_to(root).as_posix()),
            "checker_source_sha256": digest,
            "checker_callable": "check",
            "checker_argument_mode": "candidate_reference",
            "bfcl_version": "v4-private-fixture",
            "reference_call": answer,
        },
        contamination_note=(
            f"{SCOPE_EXCLUSIONS['FUNCTION_CALLING']} Synthetic; not publication corpus."
        ),
    )


def _build_text_to_sql(root: Path, index: int) -> TaskRecord:
    task_id = f"SQL-{index:03d}"
    fixture = root / "assets" / "text_to_sql" / f"{task_id}.sqlite"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    if fixture.exists():
        fixture.unlink()
    with closing(sqlite3.connect(fixture)) as connection:
        connection.execute("CREATE TABLE items(id INTEGER PRIMARY KEY, value INTEGER)")
        connection.execute("INSERT INTO items(value) VALUES (?)", (index,))
        connection.commit()
    digest = sha256_bytes(fixture.read_bytes())
    return TaskRecord(
        task_id=task_id,
        domain="TEXT_TO_SQL",
        prompt=f"Write SQL selecting value from items where id = 1 (expect {index}).",
        source="BIRD-synthetic",
        source_version="static-private-fixture",
        provenance="private synthetic CAP-01 fixture (not BIRD release data)",
        license="private-test",
        verifier={
            "fixture_path": str(fixture.relative_to(root).as_posix()),
            "fixture_sha256": digest,
            "reference_query": "SELECT value FROM items WHERE id = 1",
            "order_sensitive": False,
        },
        contamination_note=(
            f"{SCOPE_EXCLUSIONS['TEXT_TO_SQL']} Synthetic; not publication corpus."
        ),
    )


def _build_code(root: Path, index: int) -> TaskRecord:
    task_id = f"CODE-{index:03d}"
    tests = root / "assets" / "code" / f"{task_id}_tests.py"
    n = index
    digest = _write(
        tests,
        f"assert solution.add({n}, 1) == {n + 1}\n"
        f"assert solution.add(0, {n}) == {n}\n",
    )
    return TaskRecord(
        task_id=task_id,
        domain="CODE",
        prompt=(
            "Implement a Python module with function add(a, b) that returns a+b. "
            "Return only the code."
        ),
        source="HumanEval-synthetic",
        source_version="private-fixture",
        provenance="private synthetic CAP-01 fixture",
        license="private-test",
        verifier={
            "tests_path": str(tests.relative_to(root).as_posix()),
            "tests_sha256": digest,
        },
        contamination_note=(
            f"{SCOPE_EXCLUSIONS['CODE']} Synthetic; not publication corpus."
        ),
    )


def _build_math(root: Path, index: int) -> TaskRecord:
    task_id = f"MATH-{index:03d}"
    answer = str(index * 2)
    return TaskRecord(
        task_id=task_id,
        domain="MATH",
        prompt=f"What is {index} + {index}? Return only the number.",
        source="MATH-synthetic",
        source_version="private-fixture",
        provenance="private synthetic CAP-01 fixture",
        license="private-test",
        verifier={"mode": "numeric", "answer": answer, "abs_tol": "0"},
        contamination_note=(
            f"{SCOPE_EXCLUSIONS['MATH']} Synthetic; not publication corpus."
        ),
    )


def _build_extraction(root: Path, index: int) -> TaskRecord:
    task_id = f"EXT-{index:03d}"
    schema = root / "assets" / "structured_extraction" / f"{task_id}_schema.json"
    truth = {"id": index, "label": f"item-{index}", "date": "01/15/2024"}
    digest = _write(schema, json.dumps({"type": "object"}, sort_keys=True) + "\n")
    return TaskRecord(
        task_id=task_id,
        domain="STRUCTURED_EXTRACTION",
        prompt=(
            f"Extract JSON with id={index}, label=item-{index}, date=01/15/2024 "
            f"from: Record #{index} item-{index} dated January 15, 2024."
        ),
        source="extraction-synthetic",
        source_version="private-fixture",
        provenance="private synthetic CAP-01 fixture",
        license="private-test",
        verifier={
            "schema_path": str(schema.relative_to(root)),
            "schema_sha256": digest,
            "ground_truth": truth,
            "ground_truth_secondary": dict(truth),
            "annotation_sources": ["annotator-a", "annotator-b"],
            "date_order": "MDY",
        },
        contamination_note=(
            f"{SCOPE_EXCLUSIONS['STRUCTURED_EXTRACTION']} Synthetic; not publication corpus."
        ),
    )


BUILDERS = {
    "FUNCTION_CALLING": _build_function_calling,
    "TEXT_TO_SQL": _build_text_to_sql,
    "CODE": _build_code,
    "MATH": _build_math,
    "STRUCTURED_EXTRACTION": _build_extraction,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus_root"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus.json"),
    )
    parser.add_argument("--tasks-per-domain", type=int, default=50)
    args = parser.parse_args()
    root = args.corpus_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    header = {
        "status": "synthetic_private_fixture",
        "result_validity_ceiling": "debug_only",
        "scope_exclusions": SCOPE_EXCLUSIONS,
        "note": (
            "Replace with licensed BFCL/BIRD/HumanEval+/MATH/extraction corpora "
            "before capability_scaling publication."
        ),
    }
    (root / "DOMAIN_HEADERS.json").write_text(
        json.dumps(header, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tasks: list[TaskRecord] = []
    jsonl_paths: dict[str, Path] = {}
    for domain in DOMAINS:
        path = root / f"{domain.lower()}.jsonl"
        lines: list[str] = []
        for index in range(1, args.tasks_per_domain + 1):
            task = BUILDERS[domain](root, index)
            tasks.append(task)
            lines.append(json.dumps(asdict(task), sort_keys=True))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        jsonl_paths[domain] = path
    # Paths in verifiers are relative to corpus root; build from cwd-relative strings
    # by reloading with paths as stored.
    reloaded: list[TaskRecord] = []
    for domain in DOMAINS:
        for line in jsonl_paths[domain].read_text(encoding="utf-8").splitlines():
            if line.strip():
                reloaded.append(TaskRecord.from_dict(json.loads(line)))
    # Rebase relative paths: TaskRecord stored paths relative to root already.
    # build_corpus_manifest resolves against corpus_root.
    # Ensure we run with cwd = repo root and paths relative to corpus_root.
    # Fix: rewrite verifier paths that may be absolute from .relative_to(root)
    fixed: list[TaskRecord] = []
    for task in reloaded:
        verifier = dict(task.verifier)
        for key, value in list(verifier.items()):
            if key.endswith("_path") and isinstance(value, str):
                path = Path(value)
                if path.is_absolute():
                    verifier[key] = path.relative_to(root).as_posix()
                else:
                    verifier[key] = path.as_posix()
        fixed.append(
            TaskRecord(
                task_id=task.task_id,
                domain=task.domain,
                prompt=task.prompt,
                source=task.source,
                source_version=task.source_version,
                provenance=task.provenance,
                license=task.license,
                verifier=verifier,
                contamination_note=task.contamination_note,
            )
        )
        # rewrite jsonl line later
    # Rewrite JSONL with fixed relative paths
    by_domain: dict[str, list[TaskRecord]] = {d: [] for d in DOMAINS}
    for task in fixed:
        by_domain[task.domain].append(task)
    for domain, domain_tasks in by_domain.items():
        path = jsonl_paths[domain]
        path.write_text(
            "\n".join(json.dumps(asdict(t), sort_keys=True) for t in domain_tasks)
            + "\n",
            encoding="utf-8",
        )
    manifest = build_corpus_manifest(fixed, corpus_root=root)
    manifest["scope_exclusions"] = SCOPE_EXCLUSIONS
    manifest["corpus_kind"] = "synthetic_private_fixture"
    digest = write_corpus_manifest(args.output, manifest)
    print(f"corpus_root={root}")
    print(f"corpus_manifest={args.output}")
    print(f"task_count={manifest['task_count']}")
    print(f"sha256={digest}")
    for domain, path in jsonl_paths.items():
        print(f"jsonl_{domain}={path}")


if __name__ == "__main__":
    main()
