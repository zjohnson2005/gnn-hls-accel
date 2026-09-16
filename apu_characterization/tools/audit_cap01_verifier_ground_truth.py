#!/usr/bin/env python3
"""CAP-01 Stage A: gold-answer self-verification + garbage rejection audit."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from apu_characterization.cap01.contracts import CandidateRecord, TaskRecord
from apu_characterization.cap01.verifier import verify_candidate


def _concretize_bfcl_value(node: Any) -> Any:
    """Recursively concretize a chosen BFCL possible-answer alternative."""
    if isinstance(node, dict):
        # Dict fields wrap nested possible-answer lists.
        return {
            key: (
                _materialize_bfcl_param(value)
                if isinstance(value, list)
                else _concretize_bfcl_value(value)
            )
            for key, value in node.items()
        }
    if isinstance(node, list):
        # Concrete array-typed alternative (elements are values, not alt lists).
        return [_concretize_bfcl_value(item) for item in node]
    return node


def _materialize_bfcl_param(possible_answers: Any) -> Any:
    """Pick the first BFCL possible-answer alternative for one parameter."""
    if not isinstance(possible_answers, list) or not possible_answers:
        return ""
    return _concretize_bfcl_value(possible_answers[0])


def materialize_fc_gold(reference: Any) -> str:
    """Turn BFCL possible_answer into concrete AST JSON model_output.

    BFCL stores each parameter as a list of acceptable alternatives. Nested
    dict fields again wrap alternative lists. Do not treat a list-of-dicts at
    the param level as a concrete array — that yields type_error:simple when
    the schema expects an object (FC-001/002 ``new_preferences``).

    An empty-string alternative means the parameter is optional/omitted; skip
    it rather than emitting ``\"\"`` (which fails integer/boolean type checks).
    """
    if not isinstance(reference, list):
        raise ValueError("FC reference must be a list")
    concrete: list[dict[str, Any]] = []
    for call in reference:
        if not isinstance(call, dict) or len(call) != 1:
            raise ValueError(f"unexpected FC reference call shape: {call!r}")
        name, params = next(iter(call.items()))
        if not isinstance(params, dict):
            raise ValueError(f"unexpected FC params shape for {name}")
        materialized: dict[str, Any] = {}
        for key, value in params.items():
            chosen = _materialize_bfcl_param(value)
            if chosen == "":
                # Optional param omitted in this alternative set.
                continue
            materialized[key] = chosen
        concrete.append({name: materialized})
    return json.dumps(concrete, ensure_ascii=False)


def gold_content(task: TaskRecord, *, humaneval_by_id: dict[str, dict[str, Any]]) -> str:
    config = dict(task.verifier)
    if task.domain == "MATH":
        return str(config["answer"])
    if task.domain == "TEXT_TO_SQL":
        return str(config["reference_query"])
    if task.domain == "STRUCTURED_EXTRACTION":
        return json.dumps(config["ground_truth"], ensure_ascii=False)
    if task.domain == "FUNCTION_CALLING":
        reference = config.get("reference_call", config.get("reference"))
        return materialize_fc_gold(reference)
    if task.domain == "CODE":
        source_task_id = str(config.get("source_task_id") or "")
        item = humaneval_by_id.get(source_task_id)
        if item is None:
            raise KeyError(f"HumanEval+ source missing for {source_task_id}")
        prompt = str(item.get("prompt") or "")
        canonical = str(item.get("canonical_solution") or "")
        if not canonical:
            raise ValueError(f"{source_task_id}: empty canonical_solution")
        # HumanEval style: prompt already contains def header; append body.
        return prompt + canonical
    raise ValueError(f"unsupported domain {task.domain}")


def garbage_content(task: TaskRecord) -> str:
    if task.domain == "MATH":
        return "NOT_A_NUMBER_ZZZ"
    if task.domain == "TEXT_TO_SQL":
        return "SELECT 1 FROM definitely_missing_table_xyz WHERE 1=0;"
    if task.domain == "STRUCTURED_EXTRACTION":
        return '{"__garbage__": true}'
    if task.domain == "FUNCTION_CALLING":
        return '[{"Totally.Fake": {"nope": 1}}]'
    if task.domain == "CODE":
        return "def definitely_wrong():\n    return 'garbage'\n"
    return ""


def _load_humaneval(path: Path) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return by_id
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        by_id[str(item["task_id"])] = item
    return by_id


def _candidate(task_id: str, content: str, ordinal: int) -> CandidateRecord:
    return CandidateRecord(
        candidate_id=f"gold-audit-{task_id}-{ordinal}",
        task_id=task_id,
        ordinal=ordinal,
        content=content,
        prompt_tokens=0,
        completion_tokens=0,
    )


def audit_task(
    task: TaskRecord,
    *,
    humaneval_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "task_id": task.task_id,
        "domain": task.domain,
        "gold_pass": False,
        "gold_status": "",
        "gold_error": "",
        "garbage_fail": False,
        "garbage_status": "",
        "garbage_error": "",
        "gold_build_error": "",
    }
    try:
        gold = gold_content(task, humaneval_by_id=humaneval_by_id)
    except Exception as exc:  # noqa: BLE001
        row["gold_build_error"] = f"{type(exc).__name__}: {exc}"
        row["gold_status"] = "build_error"
        # Still try garbage.
        gold = None
    if gold is not None:
        try:
            verdict = verify_candidate(task, _candidate(task.task_id, gold, 0))
            row["gold_pass"] = bool(verdict.solved)
            row["gold_status"] = verdict.status
        except Exception as exc:  # noqa: BLE001
            row["gold_status"] = "exception"
            row["gold_error"] = f"{type(exc).__name__}: {exc}"
    try:
        garbage = garbage_content(task)
        verdict = verify_candidate(task, _candidate(task.task_id, garbage, 1))
        row["garbage_fail"] = not bool(verdict.solved)
        row["garbage_status"] = verdict.status
        if hasattr(verdict, "status") and not verdict.solved:
            row["garbage_fail"] = True
    except Exception as exc:  # noqa: BLE001
        # Exception on garbage still counts as rejection (did not accept).
        row["garbage_fail"] = True
        row["garbage_status"] = "exception"
        row["garbage_error"] = f"{type(exc).__name__}: {exc}"
    # Capture domain verifier error for gold if present via re-run DomainVerdict path
    if gold is not None and not row["gold_pass"] and not row["gold_error"]:
        # Pull error from domain path when status invalid/error
        from apu_characterization.cap01.domain_verifiers import (
            verify_function_call,
            verify_structured_extraction,
            verify_text_to_sql,
        )

        try:
            if task.domain == "FUNCTION_CALLING":
                dv = verify_function_call(gold, task.verifier)
                row["gold_error"] = dv.error
            elif task.domain == "TEXT_TO_SQL":
                dv = verify_text_to_sql(gold, task.verifier)
                row["gold_error"] = dv.error
            elif task.domain == "STRUCTURED_EXTRACTION":
                dv = verify_structured_extraction(gold, task.verifier)
                row["gold_error"] = dv.error
        except Exception as exc:  # noqa: BLE001
            row["gold_error"] = f"{type(exc).__name__}: {exc}"
    return row


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_domain.setdefault(row["domain"], []).append(row)
    summary: dict[str, Any] = {}
    for domain, domain_rows in sorted(by_domain.items()):
        n = len(domain_rows)
        gold_pass = sum(1 for row in domain_rows if row["gold_pass"])
        garbage_fail = sum(1 for row in domain_rows if row["garbage_fail"])
        summary[domain] = {
            "n": n,
            "gold_pass": gold_pass,
            "gold_fail": n - gold_pass,
            "garbage_fail": garbage_fail,
            "garbage_accept": n - garbage_fail,
            "healthy": gold_pass == n and garbage_fail == n,
            "sample_gold_failures": [
                {
                    "task_id": row["task_id"],
                    "status": row["gold_status"],
                    "error": row["gold_error"] or row["gold_build_error"],
                }
                for row in domain_rows
                if not row["gold_pass"]
            ][:5],
            "sample_garbage_accepts": [
                {"task_id": row["task_id"], "status": row["garbage_status"]}
                for row in domain_rows
                if not row["garbage_fail"]
            ][:5],
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus.json"),
    )
    parser.add_argument(
        "--humaneval",
        type=Path,
        default=Path(
            "apu_characterization/out/cap01/live_sources/humanevalplus-hf/test.jsonl"
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/out/cap01/verifier_ground_truth_audit.json"),
    )
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    random.seed(args.seed)

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    tasks = [TaskRecord.from_dict(item) for item in corpus["tasks"]]
    humaneval_by_id = _load_humaneval(args.humaneval)
    rows = [
        audit_task(task, humaneval_by_id=humaneval_by_id) for task in tasks
    ]
    report = {
        "tasks": len(rows),
        "summary": summarize(rows),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
