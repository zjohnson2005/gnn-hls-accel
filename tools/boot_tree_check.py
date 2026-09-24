"""Clean-tree rule for boot sequencers.

Block on modified tracked files and on untracked files under tools/, tests/,
configs/, and seam/. Untracked run output under derived/ is recorded, not blocked.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BLOCK_UNTRACKED_PREFIXES = ("tools/", "tests/", "configs/", "seam/")


def classify_porcelain(lines: list[str]) -> dict[str, list[str]]:
    blocked: list[str] = []
    untracked_derived: list[str] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        status = line[:2]
        path = line[3:].replace("\\", "/")
        if status == "??":
            if path.startswith("derived/"):
                untracked_derived.append(path)
            elif path.startswith(_BLOCK_UNTRACKED_PREFIXES):
                blocked.append(line)
            continue
        blocked.append(line)
    return {"blocked": blocked, "untracked_derived": untracked_derived}


def porcelain(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"REFUSED -- git status failed: {proc.stderr.strip()}")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    del argv
    verdict = classify_porcelain(porcelain(ROOT))
    json.dump(verdict, sys.stdout)
    sys.stdout.write("\n")
    if verdict["blocked"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
