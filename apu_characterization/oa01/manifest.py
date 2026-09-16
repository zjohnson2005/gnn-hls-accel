"""Freeze and verify the pre-registered OA-01 SWE-bench-lite sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DATASET = "princeton-nlp/SWE-bench_Lite"
DEFAULT_SPLIT = "test"
DEFAULT_SEED = 20260716
DEFAULT_N = 15


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def select_rows(
    rows: Iterable[dict[str, Any]], *, seed: int = DEFAULT_SEED, n: int = DEFAULT_N
) -> list[dict[str, Any]]:
    population = sorted((dict(row) for row in rows), key=lambda row: row["instance_id"])
    if len(population) < n:
        raise ValueError(f"dataset has {len(population)} rows; cannot sample {n}")
    return random.Random(seed).sample(population, n)


def build_manifest(
    rows: Iterable[dict[str, Any]],
    *,
    dataset: str = DEFAULT_DATASET,
    split: str = DEFAULT_SPLIT,
    seed: int = DEFAULT_SEED,
    n: int = DEFAULT_N,
    dataset_revision: str | None = None,
    dataset_fingerprint: str | None = None,
) -> dict[str, Any]:
    population = [dict(row) for row in rows]
    selected = select_rows(population, seed=seed, n=n)
    tasks = []
    for order, row in enumerate(selected):
        tasks.append(
            {
                "order": order,
                "instance_id": str(row["instance_id"]),
                "repo": str(row.get("repo", "")),
                "base_commit": str(row.get("base_commit", "")),
                "problem_statement_sha256": hashlib.sha256(
                    str(row.get("problem_statement", "")).encode("utf-8")
                ).hexdigest(),
                "row_sha256": sha256_value(row),
            }
        )
    manifest: dict[str, Any] = {
        "schema_version": "oa01_task_manifest_v1",
        "status": "pre_registered_locked",
        "dataset": dataset,
        "split": split,
        "dataset_revision": dataset_revision,
        "dataset_fingerprint": dataset_fingerprint,
        "population_order": "instance_id_ascending_before_sample",
        "population_size": len(population),
        "sampling_algorithm": "python_random.Random(seed).sample",
        "seed": seed,
        "n": n,
        "tasks": tasks,
    }
    manifest["manifest_sha256"] = sha256_value(manifest)
    return manifest


def validate_manifest(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("status") != "pre_registered_locked":
        errors.append("manifest status is not pre_registered_locked")
    if int(value.get("n", 0)) != DEFAULT_N:
        errors.append(f"manifest n must be {DEFAULT_N}")
    tasks = value.get("tasks") or []
    if len(tasks) != DEFAULT_N:
        errors.append(f"manifest must contain {DEFAULT_N} tasks")
    ids = [task.get("instance_id") for task in tasks]
    if len(set(ids)) != len(ids):
        errors.append("manifest task ids are not unique")
    expected_hash = value.get("manifest_sha256")
    unhashed = dict(value)
    unhashed.pop("manifest_sha256", None)
    if expected_hash != sha256_value(unhashed):
        errors.append("manifest_sha256 mismatch")
    return errors


def freeze_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path = Path(path)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if canonical_bytes(existing) != canonical_bytes(manifest):
            raise FileExistsError(
                f"{path} already contains a different pre-registration; task substitutions forbidden"
            )
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/oa01/task_manifest.json"),
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    from datasets import load_dataset

    dataset = load_dataset(args.dataset, split=args.split)
    info = getattr(dataset, "info", None)
    revision = getattr(info, "version", None)
    manifest = build_manifest(
        dataset,
        dataset=args.dataset,
        split=args.split,
        seed=args.seed,
        dataset_revision=str(revision) if revision is not None else None,
        dataset_fingerprint=getattr(dataset, "_fingerprint", None),
    )
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    freeze_manifest(args.out, manifest)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

