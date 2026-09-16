"""Run the official SWE-bench evaluator and attach OA-01 success labels."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from apu_characterization.oa01.runner import DEFAULT_OUT

MODEL_LABEL = "oa01-mini-swe-agent-gpt-4.1"
RUN_ID = "oa01"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_records(out_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    rows: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((out_root / "runs").glob("OA01-[PM]-*/trajectory_record.json")):
        value = _load(path)
        rows.append((path, value))
    return rows


def write_predictions(out_root: Path) -> Path:
    records = collect_records(out_root)
    if len(records) != 15:
        raise RuntimeError(f"official OA-01 evaluation requires all 15 rows, found {len(records)}")
    path = out_root / "evaluation" / "predictions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for _, record in records:
            subject_path = record.get("subject_trajectory_path")
            patch = ""
            if subject_path and Path(subject_path).is_file():
                subject = _load(Path(subject_path))
                patch = str(subject.get("info", {}).get("submission") or "")
            fh.write(
                json.dumps(
                    {
                        "instance_id": record["task_id"],
                        "model_name_or_path": MODEL_LABEL,
                        "model_patch": patch,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    return path


def run_evaluator(out_root: Path, *, max_workers: int = 1, timeout_s: int = 1800) -> Path:
    if platform.system() != "Linux":
        raise RuntimeError("official SWE-bench evaluation requires Linux/WSL2 Docker")
    out_root = Path(out_root).resolve()
    predictions = write_predictions(out_root).resolve()
    eval_root = (out_root / "evaluation").resolve()
    command = [
        sys.executable,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        "princeton-nlp/SWE-bench_Lite",
        "--split",
        "test",
        "--predictions_path",
        str(predictions),
        "--max_workers",
        str(max_workers),
        "--run_id",
        RUN_ID,
        "--timeout",
        str(timeout_s),
        "--report_dir",
        str(eval_root),
    ]
    with (eval_root / "evaluator.log").open("wb") as log:
        result = subprocess.run(
            command,
            cwd=str(out_root),
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if result.returncode != 0:
        raise RuntimeError(
            f"SWE-bench evaluator exited {result.returncode}; see {eval_root / 'evaluator.log'}"
        )
    # Newer SWE-bench writes the report relative to cwd (out_root); keep a
    # stable copy under evaluation/ for OA-01 tooling.
    summary_name = f"{MODEL_LABEL}.{RUN_ID}.json"
    candidates = [
        eval_root / summary_name,
        out_root / summary_name,
        Path.cwd() / summary_name,
    ]
    summary = next((path for path in candidates if path.is_file()), None)
    if summary is None:
        raise FileNotFoundError(
            f"missing evaluator summary {summary_name}; checked {[str(p) for p in candidates]}"
        )
    stable = eval_root / summary_name
    if summary.resolve() != stable.resolve():
        stable.write_text(summary.read_text(encoding="utf-8"), encoding="utf-8")
        summary = stable
    return summary


def attach_results(out_root: Path, summary_path: Path) -> dict[str, Any]:
    summary = _load(summary_path)
    resolved = set(summary.get("resolved_ids") or summary.get("resolved_instances") or [])
    error_ids = set(summary.get("error_ids") or summary.get("error_instances") or [])
    empty_ids = set(
        summary.get("empty_patch_ids") or summary.get("empty_patch_instances") or []
    )
    outcomes = []
    for record_path, record in collect_records(out_root):
        task_id = record["task_id"]
        if record.get("censored"):
            success = None
            outcome = "censored"
        elif task_id in resolved:
            success = True
            outcome = "success"
        else:
            success = False
            outcome = "failure"
        flags = list(record.get("flags") or [])
        if task_id in error_ids:
            flags.append("evaluation_error")
        if task_id in empty_ids:
            flags.append("empty_patch")
        record.update({"success": success, "outcome": outcome, "flags": sorted(set(flags))})
        record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        evaluation = {
            "schema_version": "oa01_evaluation_v1",
            "task_id": task_id,
            "success": success,
            "outcome": outcome,
            "official_summary": str(summary_path),
            "evaluation_error": task_id in error_ids,
            "empty_patch": task_id in empty_ids,
        }
        record_path.with_name("evaluation.json").write_text(
            json.dumps(evaluation, indent=2) + "\n", encoding="utf-8"
        )
        outcomes.append(evaluation)
    combined = {
        "schema_version": "oa01_evaluation_attachment_v1",
        "official_summary": summary,
        "outcomes": outcomes,
    }
    (out_root / "evaluation" / "oa01_evaluation.json").write_text(
        json.dumps(combined, indent=2) + "\n", encoding="utf-8"
    )
    return combined


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--attach-only", type=Path, default=None)
    args = parser.parse_args(argv)
    summary = (
        args.attach_only
        if args.attach_only is not None
        else run_evaluator(args.out, max_workers=args.max_workers, timeout_s=args.timeout)
    )
    attached = attach_results(args.out, summary)
    print(json.dumps(attached, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

