"""Validated corpus assembly for CAP-01.

This module does not download benchmarks. Corpus licensing, provenance, hidden
tests, and contamination notes must be supplied explicitly by the operator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import TaskRecord, canonical_json_bytes, sha256_bytes, sha256_json

DOMAINS = (
    "FUNCTION_CALLING",
    "TEXT_TO_SQL",
    "CODE",
    "MATH",
    "STRUCTURED_EXTRACTION",
)
DEFAULT_DOMAIN_COUNTS = {domain: 50 for domain in DOMAINS}
ASSET_FIELDS = {
    "FUNCTION_CALLING": (("checker_source_path", "checker_source_sha256"),),
    "TEXT_TO_SQL": (("fixture_path", "fixture_sha256"),),
    "CODE": (("tests_path", "tests_sha256"),),
    "STRUCTURED_EXTRACTION": (("schema_path", "schema_sha256"),),
}


def load_task_jsonl(path: Path) -> list[TaskRecord]:
    tasks: list[TaskRecord] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            tasks.append(TaskRecord.from_dict(value))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
    return tasks


def _resolve_corpus_asset(root: Path, relative_path: str) -> Path:
    """Resolve verifier asset paths stored either root-relative or repo-relative."""
    direct = Path(relative_path)
    if direct.is_file():
        return direct.resolve()
    nested = (root / relative_path).resolve()
    if nested.is_file():
        return nested
    raise ValueError(f"verifier asset does not exist: {relative_path}")


def _validate_verifier_assets(task: TaskRecord, root: Path) -> None:
    verifier = task.verifier
    for path_field, hash_field in ASSET_FIELDS.get(task.domain, ()):
        relative_path = verifier.get(path_field)
        expected_hash = verifier.get(hash_field)
        if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
            raise ValueError(
                f"{task.task_id}: {task.domain} verifier requires "
                f"{path_field} and {hash_field}"
            )
        path = _resolve_corpus_asset(root, relative_path)
        try:
            path.relative_to(root.resolve())
        except ValueError:
            # Repo-relative paths that still resolve under root after normalize.
            try:
                path.relative_to(Path.cwd().resolve())
            except ValueError as exc:
                raise ValueError(
                    f"{task.task_id}: {path_field} escapes corpus root"
                ) from exc
        if sha256_bytes(path.read_bytes()) != expected_hash:
            raise ValueError(
                f"{task.task_id}: verifier asset hash mismatch ({hash_field})"
            )

    if task.domain == "FUNCTION_CALLING":
        for field in ("checker_callable", "bfcl_version"):
            if not isinstance(verifier.get(field), str) or not verifier[field]:
                raise ValueError(f"{task.task_id}: D1 verifier requires {field}")
        module = verifier.get("checker_module")
        if module is not None and (
            not isinstance(module, str)
            or (module == "" and not verifier.get("checker_source_path"))
        ):
            raise ValueError(
                f"{task.task_id}: D1 checker_module must be a module path or "
                "omitted/empty when checker_source_path is pinned"
            )
    if task.domain == "STRUCTURED_EXTRACTION":
        primary = verifier.get("ground_truth")
        secondary = verifier.get("ground_truth_secondary")
        sources = verifier.get("annotation_sources")
        if not isinstance(primary, Mapping) or not isinstance(secondary, Mapping):
            raise ValueError(f"{task.task_id}: D5 ground truth must be double-keyed")
        if canonical_json_bytes(primary) != canonical_json_bytes(secondary):
            raise ValueError(f"{task.task_id}: D5 independent annotations disagree")
        if (
            not isinstance(sources, list)
            or len(sources) != 2
            or not all(isinstance(item, str) and item for item in sources)
        ):
            raise ValueError(
                f"{task.task_id}: D5 requires two annotation_sources"
            )
        if verifier.get("date_order") not in {"MDY", "DMY"}:
            raise ValueError(f"{task.task_id}: D5 date_order must be MDY or DMY")


def _manifest_verifier(task: TaskRecord, root: Path) -> dict[str, Any]:
    verifier = dict(task.verifier)
    for path_field, _ in ASSET_FIELDS.get(task.domain, ()):
        source = _resolve_corpus_asset(root, str(verifier[path_field]))
        try:
            relative = source.relative_to(Path.cwd().resolve())
            verifier[path_field] = relative.as_posix()
        except ValueError:
            # Temporary fixture corpora may be external. Publication preflight
            # rejects absolute answer-space paths because they are not bundleable.
            verifier[path_field] = source.as_posix()
    return verifier


def build_corpus_manifest(
    tasks: Iterable[TaskRecord],
    *,
    corpus_root: Path,
    expected_domains: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    records = sorted(tasks, key=lambda task: task.task_id)
    ids = [task.task_id for task in records]
    if len(ids) != len(set(ids)):
        raise ValueError("corpus contains duplicate task ids")
    for task in records:
        _validate_verifier_assets(task, corpus_root)
    domain_counts = {
        domain: sum(task.domain == domain for task in records) for domain in DOMAINS
    }
    expected = dict(expected_domains or DEFAULT_DOMAIN_COUNTS)
    if domain_counts != expected:
        raise ValueError(
            f"corpus domain counts {domain_counts} do not match {expected}"
        )
    verifiers = {
        task.task_id: _manifest_verifier(task, corpus_root) for task in records
    }
    answer_space = dict(verifiers)
    task_values = [
        {
            "task_id": task.task_id,
            "domain": task.domain,
            "prompt": task.prompt,
            "source": task.source,
            "source_version": task.source_version,
            "provenance": task.provenance,
            "license": task.license,
            "verifier": verifiers[task.task_id],
            "contamination_note": task.contamination_note,
            "task_sha256": task.digest(),
        }
        for task in records
    ]
    return {
        "experiment": "CAP-01",
        "task_count": len(records),
        "domain_counts": domain_counts,
        "answer_space_sha256": sha256_json(answer_space),
        "tasks": task_values,
        "corpus_sha256": sha256_json(task_values),
    }


def write_corpus_manifest(path: Path, manifest: Mapping[str, Any]) -> str:
    payload = canonical_json_bytes(manifest) + b"\n"
    if path.exists() and path.read_bytes() != payload:
        raise FileExistsError(f"refusing to replace corpus manifest: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return sha256_bytes(payload)
