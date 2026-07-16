"""SWE-bench-lite-style coding loop scaffold (Layer 1 shared workload).

This is the structural scaffold — not a full SWE-bench evaluator. It defines the
task record, tool surface, success metric name, and trajectory shape that Layer 1
will reuse. Real instance payloads are loaded from a frozen subset JSON when present.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class SweLiteTask:
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    pass_to_pass: list[str]
    fail_to_pass: list[str]
    image_id: str = "swebench/placeholder:latest"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SUCCESS_METRIC = "swebench_pass"
WORKLOAD_ID = "swebench_lite_layer1"


def load_subset(path: Path) -> list[SweLiteTask]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = []
    for row in raw:
        tasks.append(
            SweLiteTask(
                instance_id=str(row["instance_id"]),
                repo=str(row["repo"]),
                base_commit=str(row["base_commit"]),
                problem_statement=str(row["problem_statement"]),
                pass_to_pass=list(row.get("PASS_TO_PASS") or row.get("pass_to_pass") or []),
                fail_to_pass=list(row.get("FAIL_TO_PASS") or row.get("fail_to_pass") or []),
                image_id=str(row.get("image_id") or "swebench/placeholder:latest"),
            )
        )
    return tasks


def write_fixture_subset(path: Path, n: int = 3) -> Path:
    """Minimal fixture for CI / plumbing — not a real SWE-bench subset."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(n):
        rows.append(
            {
                "instance_id": f"fixture__repo-{i}",
                "repo": f"org/repo-{i}",
                "base_commit": f"{'ab' * 20}{i:02d}",
                "problem_statement": f"Fix bug {i} in module.",
                "PASS_TO_PASS": [f"tests/test_ok_{i}.py"],
                "FAIL_TO_PASS": [f"tests/test_bug_{i}.py"],
                "image_id": "swebench/placeholder:latest",
            }
        )
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return path


def judge_success(*, tests_passed: bool) -> tuple[bool, str]:
    return bool(tests_passed), SUCCESS_METRIC
