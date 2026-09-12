"""Pre-commit hook: sealed run directories are write-once once tracked.

Fails if a staged change modifies or deletes a file that already exists under
a sealed evidence directory in HEAD. New sealed run directories may be added.

Sealed roots:
  - raw/<run_id>/
  - derived/**/sealed_<run_id>/

Exit 0 = clean, 1 = blocked.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

RAW_FILE = re.compile(r"^raw/[^/]+/.+")
SEALED_DERIVED = re.compile(r"^derived/.*/sealed_[^/]+/.+")


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _in_head(rel: str) -> bool:
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{rel}"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def _is_sealed_path(rel: str) -> bool:
    if RAW_FILE.match(rel):
        # raw/_blinding/ is excluded from commits; still treat as protected if present.
        return True
    return bool(SEALED_DERIVED.match(rel))


def scan(paths: list[str]) -> int:
    # No HEAD yet (orphan / empty) — nothing previously sealed in git.
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if head.returncode != 0:
        return 0

    violations: list[str] = []
    for raw in paths:
        rel = _norm(raw)
        if not _is_sealed_path(rel):
            continue
        if not _in_head(rel):
            # New evidence file — allowed.
            continue
        # Exists in HEAD: any staged change is a sealed-tree mutation.
        violations.append(rel)

    if violations:
        sys.stderr.write("\nBLOCKED — sealed evidence must not be modified after seal:\n")
        for v in violations:
            sys.stderr.write(f"  {v}\n")
        sys.stderr.write(
            "\nraw/<run_id>/ and derived/**/sealed_*/ are write-once once tracked.\n"
            "Add a new run_id / sealed_* tree instead of editing an existing one.\n\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(scan(sys.argv[1:]))
