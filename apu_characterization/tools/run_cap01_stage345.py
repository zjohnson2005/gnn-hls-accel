#!/usr/bin/env python3
"""CAP-01 Stages 3–5: Axis-2 realism, calibration freeze, P2 smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from apu_characterization.cap01.calibration import calibrate_pool
from apu_characterization.cap01.contracts import (
    CandidateRecord,
    CellCoordinates,
    PoolMetadata,
    TaskRecord,
    sha256_json,
)
from apu_characterization.cap01.pool import load_frozen_pool
from apu_characterization.cap01.runner import RunRequest, run_serial
from apu_characterization.cap01.verification_audit import (
    axis2_candidate_pool_realism,
    write_verification_audit,
)
from apu_characterization.cap01.verifier import verify_candidate
from apu_characterization.validity import DEBUG_ONLY


def _absolutize_task(task: TaskRecord, corpus_root: Path) -> TaskRecord:
    verifier = dict(task.verifier)
    for key, value in list(verifier.items()):
        if key.endswith("_path") and isinstance(value, str):
            path = Path(value)
            if not path.is_file():
                candidate = corpus_root / value
                if candidate.is_file():
                    verifier[key] = str(candidate.resolve())
    return TaskRecord(
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


def _load_corpus(path: Path, corpus_root: Path) -> list[TaskRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        _absolutize_task(TaskRecord.from_dict(item), corpus_root)
        for item in payload["tasks"]
    ]


def _pool_for_task(pools_root: Path, task_id: str) -> PoolMetadata:
    return load_frozen_pool(
        pools_root / "frozen" / f"{task_id}.jsonl",
        pools_root / "frozen" / f"{task_id}.manifest.json",
    )


def _expected_correct(task: TaskRecord) -> str:
    index = int(task.task_id.rsplit("-", 1)[-1])
    if task.domain == "MATH":
        return str(index * 2)
    if task.domain == "CODE":
        return "def add(a, b):\n    return a + b\n"
    if task.domain == "FUNCTION_CALLING":
        return json.dumps(
            {"name": "lookup", "arguments": {"q": index}}, separators=(",", ":")
        )
    if task.domain == "TEXT_TO_SQL":
        return "SELECT value FROM items WHERE id = 1"
    if task.domain == "STRUCTURED_EXTRACTION":
        return json.dumps(
            {"id": index, "label": f"item-{index}", "date": "01/15/2024"},
            separators=(",", ":"),
        )
    raise ValueError(task.domain)


def _oracle_correctness(task: TaskRecord, pool: PoolMetadata) -> dict[str, bool]:
    expected = _expected_correct(task).strip()
    return {
        candidate.candidate_id: candidate.content.strip() == expected
        for candidate in pool.candidates
    }


def _spot_verify_oracle(
    tasks: list[TaskRecord],
    pools_root: Path,
    *,
    per_domain: int = 32,
) -> dict[str, Any]:
    by_domain: dict[str, list[TaskRecord]] = {}
    for task in tasks:
        by_domain.setdefault(task.domain, []).append(task)
    report: dict[str, Any] = {}
    mismatches = 0
    checked = 0
    for domain, domain_tasks in by_domain.items():
        task = domain_tasks[0]
        pool = _pool_for_task(pools_root, task.task_id)
        oracle = _oracle_correctness(task, pool)
        rng = random.Random(int(hashlib.sha256(domain.encode()).hexdigest()[:8], 16))
        sample = rng.sample(list(pool.candidates), min(per_domain, len(pool.candidates)))
        domain_mismatch = 0
        for candidate in sample:
            verdict = verify_candidate(task, candidate)
            checked += 1
            if bool(verdict.solved) != bool(oracle[candidate.candidate_id]):
                domain_mismatch += 1
                mismatches += 1
        report[domain] = {
            "task_id": task.task_id,
            "checked": len(sample),
            "oracle_verifier_mismatches": domain_mismatch,
        }
    report["total_checked"] = checked
    report["total_mismatches"] = mismatches
    report["pass"] = mismatches == 0
    return report


def run_calibration(
    tasks: list[TaskRecord],
    pools_root: Path,
    output: Path,
) -> dict[str, Any]:
    spot = _spot_verify_oracle(tasks, pools_root)
    if not spot["pass"]:
        raise SystemExit(f"oracle/verifier mismatch: {spot}")

    results: list[dict[str, Any]] = []
    for task in tasks:
        pool = _pool_for_task(pools_root, task.task_id)
        correctness = _oracle_correctness(task, pool)
        calibrated = calibrate_pool(pool, correctness)
        payload = calibrated.to_dict()
        payload["classification"] = payload["task_class"]
        results.append(payload)
        print(
            f"calibrated {payload['task_id']} -> {payload['classification']} "
            f"p4={payload['solved_probability_n4']:.3f} "
            f"p2048={payload['solved_probability_n2048']:.3f}"
        )

    results.sort(key=lambda item: item["task_id"])
    manifest = {
        "shuffles": 50,
        "tasks": results,
        "oracle_spot_verify": spot,
        "classification_manifest_sha256": sha256_json(results),
        "note": (
            "Correctness for synthetic_debug pools uses the generator oracle after "
            "a per-domain verifier spot-check (32 candidates). Replace with full "
            "offline verify_candidate sweep when OpenAI pools land."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    task_domain = {task.task_id: task.domain for task in tasks}
    by_domain: dict[str, Counter[str]] = {}
    for row in results:
        by_domain.setdefault(task_domain[row["task_id"]], Counter())[
            row["classification"]
        ] += 1
    scaling_counts = {
        domain: counts.get("SCALING", 0) for domain, counts in by_domain.items()
    }
    return {
        "path": str(output),
        "per_domain": {domain: dict(counts) for domain, counts in by_domain.items()},
        "scaling_counts": scaling_counts,
        "domains_below_20_scaling": [
            domain for domain, count in scaling_counts.items() if count < 20
        ],
        "d5_scaling_count": scaling_counts.get("STRUCTURED_EXTRACTION"),
        "oracle_spot_verify": spot,
    }


def run_axis2(tasks: list[TaskRecord], pools_root: Path) -> dict[str, Any]:
    axis = axis2_candidate_pool_realism()
    by_domain: dict[str, list[TaskRecord]] = {}
    for task in tasks:
        by_domain.setdefault(task.domain, []).append(task)
    spot: dict[str, list[dict[str, Any]]] = {}
    for domain, domain_tasks in by_domain.items():
        task = domain_tasks[0]
        pool = _pool_for_task(pools_root, task.task_id)
        samples = []
        for candidate in pool.candidates[:5]:
            text = candidate.content
            samples.append(
                {
                    "task_id": task.task_id,
                    "candidate_id": candidate.candidate_id,
                    "content_preview": text[:240],
                    "malformed": (not text.strip()) or ("\x00" in text),
                    "truncated_suspect": text.endswith("...") and len(text) < 8,
                }
            )
        spot[domain] = samples
    return {
        "axis2": axis.to_dict(),
        "human_spot_check_for_zach": spot,
        "human_spot_check_note": (
            "Review five previews per domain in one sitting; flag malformed/"
            "truncated outputs. Only human step in this run."
        ),
    }


def run_p2_smoke(
    tasks: list[TaskRecord],
    pools_root: Path,
    output_root: Path,
    classification: dict[str, str],
) -> dict[str, Any]:
    by_domain: dict[str, list[TaskRecord]] = {}
    for task in tasks:
        by_domain.setdefault(task.domain, []).append(task)
    requests: list[RunRequest] = []
    for domain_tasks in by_domain.values():
        for task in domain_tasks[:2]:
            pool = _pool_for_task(pools_root, task.task_id)
            task_class = classification.get(task.task_id, "SCALING")

            def _make_verifier(bound_task: TaskRecord):
                def _verify(candidate: CandidateRecord) -> dict[str, Any]:
                    return verify_candidate(bound_task, candidate).to_dict()

                return _verify

            for harness in ("langgraph", "rust", "raw_python"):
                for scale in (4000, 5):
                    requests.append(
                        RunRequest(
                            task=task,
                            pool=pool,
                            coordinates=CellCoordinates(
                                harness=harness,  # type: ignore[arg-type]
                                latency_scale_ms=scale,
                                wall_budget_ms=2000,
                                seed=0,
                            ),
                            verifier=_make_verifier(task),
                            task_class=task_class,
                        )
                    )
    run_dir = run_serial(
        tuple(requests),
        output_root=output_root,
        run_id="p2_smoke",
        result_validity=DEBUG_ONLY,
    )
    completed = (run_dir / "COMPLETED.json").is_file()
    failed = (run_dir / "FAILED.json").is_file()
    return {
        "run_dir": str(run_dir),
        "request_count": len(requests),
        "completed": completed,
        "failed": failed,
        "result_validity": DEBUG_ONLY,
        "criteria": {
            "tasks_per_domain": 2,
            "harnesses": ["langgraph", "rust", "raw_python"],
            "latency_scales_ms": [4000, 5],
            "wall_budget_ms": 2000,
            "seed": 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=("axis2", "calibrate", "smoke", "allaudit", "all"),
        default="all",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus.json"),
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus_root"),
    )
    parser.add_argument(
        "--pools-root",
        type=Path,
        default=Path("apu_characterization/out/cap01/pools"),
    )
    parser.add_argument(
        "--classification-output",
        type=Path,
        default=Path("apu_characterization/out/cap01/classification.json"),
    )
    parser.add_argument(
        "--smoke-root",
        type=Path,
        default=Path("apu_characterization/out/cap01/runs"),
    )
    args = parser.parse_args()
    tasks = _load_corpus(args.corpus, args.corpus_root.resolve())
    report: dict[str, Any] = {}

    if args.stage in ("axis2", "all", "allaudit"):
        report["axis2"] = run_axis2(tasks, args.pools_root)
        print(json.dumps({"axis2_verdict": report["axis2"]["axis2"]["verdict"]}, indent=2))

    if args.stage in ("calibrate", "all"):
        report["calibration"] = run_calibration(
            tasks, args.pools_root, args.classification_output
        )
        print(json.dumps({
            "scaling_counts": report["calibration"]["scaling_counts"],
            "domains_below_20_scaling": report["calibration"]["domains_below_20_scaling"],
            "d5_scaling_count": report["calibration"]["d5_scaling_count"],
        }, indent=2))

    if args.stage in ("smoke", "all"):
        classification_payload = json.loads(
            args.classification_output.read_text(encoding="utf-8")
        )
        classification = {
            row["task_id"]: row["classification"]
            for row in classification_payload["tasks"]
        }
        report["p2_smoke"] = run_p2_smoke(
            tasks, args.pools_root, args.smoke_root, classification
        )
        print(json.dumps(report["p2_smoke"], indent=2))

    if args.stage in ("allaudit", "all"):
        aggregate = write_verification_audit(
            Path("apu_characterization/cap01/cap01_verification_audit.md"),
            Path("apu_characterization/out/cap01/verification_audit.json"),
            axis1_repeats=200,
        )
        report["full_audit_summary"] = aggregate.get("summary")
        print(json.dumps({"full_audit_summary": aggregate.get("summary")}, indent=2))

    out = Path("apu_characterization/out/cap01/stage345_report.json")
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"stage345_report={out}")


if __name__ == "__main__":
    main()
