"""Resolve the CAP-01 P0 manifests into an immutable measurement protocol."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import (
    PROTOCOL_PATH,
    PENDING_MANIFEST_DIGEST,
    canonical_json_bytes,
    load_protocol,
    sha256_bytes,
    sha256_json,
    validate_lock,
)
from .corpus import ASSET_FIELDS


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _task_records(corpus: Any) -> list[Mapping[str, Any]]:
    if isinstance(corpus, list):
        tasks = corpus
    elif isinstance(corpus, dict):
        tasks = corpus.get("tasks")
    else:
        tasks = None
    if not isinstance(tasks, list):
        raise ValueError("corpus manifest must contain a tasks list")
    if not all(isinstance(task, dict) for task in tasks):
        raise ValueError("every corpus task must be an object")
    return tasks


def _classification_records(classification: Any) -> list[Mapping[str, Any]]:
    if isinstance(classification, list):
        records = classification
    elif isinstance(classification, dict):
        records = classification.get("tasks") or classification.get("classifications")
    else:
        records = None
    if not isinstance(records, list):
        raise ValueError("classification manifest must contain a task list")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("every classification record must be an object")
    return records


def _pool_counts(pool_manifest: Any) -> dict[str, int]:
    if not isinstance(pool_manifest, dict):
        raise ValueError("pool manifest must be an object")
    entries = pool_manifest.get("tasks") or pool_manifest.get("pools")
    if isinstance(entries, dict):
        result: dict[str, int] = {}
        for task_id, value in entries.items():
            if isinstance(value, dict):
                count = value.get("candidate_count")
            else:
                count = value
            result[str(task_id)] = int(count)
        return result
    if isinstance(entries, list):
        return {
            str(entry["task_id"]): int(entry["candidate_count"])
            for entry in entries
            if isinstance(entry, dict)
        }
    raise ValueError("pool manifest must contain tasks or pools")


def _validate_verifier_pins(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("verifier pin manifest must be an object")
    for name in ("bfcl", "sqlite", "cpython", "jsonschema"):
        pin = value.get(name)
        if not isinstance(pin, Mapping) or not isinstance(pin.get("version"), str):
            raise ValueError(f"verifier pin manifest requires {name}.version")
    bfcl_hash = (value.get("bfcl") or {}).get("source_sha256")
    if not isinstance(bfcl_hash, str) or len(bfcl_hash) != 64:
        raise ValueError("verifier pin manifest requires bfcl.source_sha256")


def _validate_corpus_tasks(
    tasks: list[Mapping[str, Any]],
    *,
    expected_domains: Mapping[str, int],
    verifier_pins: Mapping[str, Any],
) -> None:
    task_ids = [str(task["task_id"]) for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("corpus contains duplicate task ids")
    actual_domains = {
        domain: sum(task.get("domain") == domain for task in tasks)
        for domain in expected_domains
    }
    if actual_domains != expected_domains:
        raise ValueError(
            f"corpus domain counts {actual_domains} do not match {expected_domains}"
        )
    for task in tasks:
        for field in (
            "task_id",
            "domain",
            "prompt",
            "source",
            "source_version",
            "provenance",
            "license",
            "contamination_note",
        ):
            if not isinstance(task.get(field), str) or not task[field]:
                raise ValueError(f"{task.get('task_id')}: required field {field} missing")
        domain = str(task.get("domain"))
        verifier = task.get("verifier") or {}
        if not isinstance(verifier, Mapping):
            raise ValueError(f"{task.get('task_id')}: verifier must be an object")
        for path_field, hash_field in ASSET_FIELDS.get(domain, ()):
            path_value = verifier.get(path_field)
            hash_value = verifier.get(hash_field)
            if not isinstance(path_value, str) or not isinstance(hash_value, str):
                raise ValueError(
                    f"{task.get('task_id')}: {domain} verifier requires "
                    f"{path_field} and {hash_field}"
                )
            if Path(path_value).is_absolute():
                raise ValueError(
                    f"{domain} verifier asset paths must be repository-relative"
                )
        if (
            domain == "FUNCTION_CALLING"
            and verifier.get("checker_source_sha256")
            != verifier_pins["bfcl"]["source_sha256"]
        ):
            raise ValueError("D1 checker hash differs from the pinned BFCL checker")
        if domain == "FUNCTION_CALLING":
            for field in ("checker_callable", "bfcl_version"):
                if not isinstance(verifier.get(field), str) or not verifier[field]:
                    raise ValueError(
                        f"{task.get('task_id')}: D1 verifier requires {field}"
                    )
            if not verifier.get("checker_source_path") or not verifier.get(
                "checker_source_sha256"
            ):
                raise ValueError(
                    f"{task.get('task_id')}: D1 verifier requires pinned checker source"
                )
        if domain == "STRUCTURED_EXTRACTION":
            if verifier.get("ground_truth") != verifier.get("ground_truth_secondary"):
                raise ValueError(
                    f"{task.get('task_id')}: D5 independent annotations disagree"
                )
            sources = verifier.get("annotation_sources")
            if not isinstance(sources, list) or len(sources) != 2:
                raise ValueError(
                    f"{task.get('task_id')}: D5 requires two annotation sources"
                )


def build_pre_generation_locked_protocol(
    *,
    corpus_manifest: Path,
    generation_config: Path,
    verifier_pin_manifest: Path,
    expectations: Path = Path("apu_characterization/PREDICTIONS_CAP01.md"),
    template_path: Path = PROTOCOL_PATH,
) -> dict[str, Any]:
    """Freeze corpus + generation config before any live pool spend."""
    protocol = copy.deepcopy(load_protocol(template_path))
    corpus = _load_json(corpus_manifest)
    generation = _load_json(generation_config)
    verifier_pins = _load_json(verifier_pin_manifest)
    _validate_verifier_pins(verifier_pins)

    tasks = _task_records(corpus)
    expected_domains = {
        domain: int(protocol["corpus"]["tasks_per_domain"])
        for domain in protocol["corpus"]["domains"]
    }
    _validate_corpus_tasks(
        tasks,
        expected_domains=expected_domains,
        verifier_pins=verifier_pins,
    )
    answer_space = {str(task["task_id"]): task.get("verifier") for task in tasks}
    d5_normalization = protocol["verifiers"]["STRUCTURED_EXTRACTION"]["normalization"]
    protocol["status"] = "locked"
    protocol["lock_phase"] = "pre_generation"
    protocol["lock_fields"] = {
        "corpus_manifest_sha256": sha256_json(corpus),
        "pool_manifest_sha256": PENDING_MANIFEST_DIGEST,
        "classification_manifest_sha256": PENDING_MANIFEST_DIGEST,
        "generation_config_sha256": sha256_json(generation),
        "answer_space_sha256": sha256_json(answer_space),
        "expectations_sha256": sha256_bytes(expectations.read_bytes()),
        "verifier_pin_manifest_sha256": sha256_json(verifier_pins),
        "d5_normalization_sha256": sha256_json(d5_normalization),
    }
    protocol["locked_population"] = {
        "task_count": len(tasks),
        "classification_counts": {"pending": "post_generation_calibration"},
        "minimum_pool_depth": int(
            protocol["candidate_pool"]["minimum_candidates_per_task"]
        ),
    }
    protocol["pre_p2_flags"] = [
        "classification pending until post-generation calibration"
    ]
    protocol["locked_schedule"] = {
        "primary_task_cell_runs": "pending_post_generation_classification",
        "all_task_cell_runs": "pending_post_generation_classification",
        "serial_budget_upper_bound_seconds": "pending_post_generation_classification",
    }
    errors = validate_lock(protocol)
    if errors:
        raise ValueError("; ".join(errors))
    return protocol


def build_locked_protocol(
    *,
    corpus_manifest: Path,
    pool_manifest: Path,
    classification_manifest: Path,
    generation_config: Path,
    verifier_pin_manifest: Path,
    expectations: Path = Path("apu_characterization/PREDICTIONS_CAP01.md"),
    template_path: Path = PROTOCOL_PATH,
) -> dict[str, Any]:
    protocol = copy.deepcopy(load_protocol(template_path))
    corpus = _load_json(corpus_manifest)
    pools = _load_json(pool_manifest)
    classifications = _load_json(classification_manifest)
    generation = _load_json(generation_config)
    verifier_pins = _load_json(verifier_pin_manifest)
    _validate_verifier_pins(verifier_pins)

    tasks = _task_records(corpus)
    class_records = _classification_records(classifications)
    pool_counts = _pool_counts(pools)
    expected_domains = {
        domain: int(protocol["corpus"]["tasks_per_domain"])
        for domain in protocol["corpus"]["domains"]
    }
    _validate_corpus_tasks(
        tasks,
        expected_domains=expected_domains,
        verifier_pins=verifier_pins,
    )
    task_ids = [str(task["task_id"]) for task in tasks]
    classified_ids = [str(record["task_id"]) for record in class_records]
    if set(classified_ids) != set(task_ids) or len(classified_ids) != len(task_ids):
        raise ValueError("classification manifest does not cover corpus exactly once")
    if set(pool_counts) != set(task_ids):
        raise ValueError("pool manifest does not cover corpus exactly once")
    minimum = int(protocol["candidate_pool"]["minimum_candidates_per_task"])
    shallow = {
        task_id: count for task_id, count in pool_counts.items() if count < minimum
    }
    if shallow:
        raise ValueError(f"candidate pools below depth {minimum}: {shallow}")

    valid_classes = {"SCALING", "SATURATED", "DEAD"}
    bad_classes = [
        record
        for record in class_records
        if record.get("classification") not in valid_classes
    ]
    if bad_classes:
        raise ValueError("classification manifest contains invalid classifications")
    counts = {
        name: sum(record.get("classification") == name for record in class_records)
        for name in sorted(valid_classes)
    }
    scaling_count = counts["SCALING"]
    if scaling_count == 0:
        raise ValueError("primary SCALING population is empty")

    answer_space = {
        str(task["task_id"]): task.get("verifier") for task in tasks
    }
    task_domains = {str(task["task_id"]): str(task["domain"]) for task in tasks}
    scaling_by_domain = {
        domain: sum(
            record.get("classification") == "SCALING"
            and task_domains[str(record["task_id"])] == domain
            for record in class_records
        )
        for domain in expected_domains
    }
    minimum_scaling = int(protocol["calibration"]["minimum_scaling_tasks_per_domain"])
    pre_p2_flags = [
        f"{domain} has {count} SCALING tasks; minimum is {minimum_scaling}"
        for domain, count in scaling_by_domain.items()
        if count < minimum_scaling
    ]
    d5_normalization = protocol["verifiers"]["STRUCTURED_EXTRACTION"]["normalization"]
    protocol["status"] = "locked"
    protocol["lock_phase"] = "post_generation"
    protocol["lock_fields"] = {
        "corpus_manifest_sha256": sha256_json(corpus),
        "pool_manifest_sha256": sha256_json(pools),
        "classification_manifest_sha256": sha256_json(classifications),
        "generation_config_sha256": sha256_json(generation),
        "answer_space_sha256": sha256_json(answer_space),
        "expectations_sha256": sha256_bytes(expectations.read_bytes()),
        "verifier_pin_manifest_sha256": sha256_json(verifier_pins),
        "d5_normalization_sha256": sha256_json(d5_normalization),
    }
    protocol["locked_population"] = {
        "task_count": len(tasks),
        "classification_counts": counts,
        "classification_counts_by_domain": {
            domain: {
                name: sum(
                    record.get("classification") == name
                    and task_domains[str(record["task_id"])] == domain
                    for record in class_records
                )
                for name in sorted(valid_classes)
            }
            for domain in expected_domains
        },
        "minimum_pool_depth": min(pool_counts.values()),
    }
    protocol["pre_p2_flags"] = pre_p2_flags
    axes = protocol["matrix"]
    scales = protocol["latency_backend"]["median_scales_ms"]
    protocol["locked_schedule"] = {
        "primary_task_cell_runs": (
            len(axes["harnesses"])
            * len(scales)
            * len(axes["wall_budgets_ms"])
            * len(axes["seeds"])
            * scaling_count
        ),
        "all_task_cell_runs": (
            len(axes["harnesses"])
            * len(scales)
            * len(axes["wall_budgets_ms"])
            * len(axes["seeds"])
            * len(tasks)
        ),
        "serial_budget_upper_bound_seconds": (
            len(axes["harnesses"])
            * len(scales)
            * len(axes["seeds"])
            * len(tasks)
            * sum(int(value) for value in axes["wall_budgets_ms"])
            / 1000.0
        ),
    }
    errors = validate_lock(protocol)
    if errors:
        raise ValueError("; ".join(errors))
    return protocol


def write_locked_protocol(path: Path, protocol: Mapping[str, Any]) -> str:
    if path.exists():
        existing = path.read_bytes()
        proposed = canonical_json_bytes(protocol) + b"\n"
        if existing != proposed:
            raise FileExistsError(
                f"refusing to replace existing locked protocol: {path}"
            )
        return sha256_bytes(existing)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(protocol) + b"\n"
    path.write_bytes(payload)
    return sha256_bytes(payload)
