"""Git HEAD, dirty flag, and ``git diff HEAD`` sha256 for H1 seals.

Launchers refuse a dirty tree unless allow-dirty is set. That waiver records
``tree_status`` DIRTY and the diff hash in the plan and the seal.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from seam.errors import GitError
from seam.gitinfo import assert_clean_or_allowed, capture_git_state

_TIMEOUT_S = 30


def seal_git_record(*, allow_dirty: bool, root: Path) -> dict[str, Any]:
    """Capture the provenance block written into every new H1 plan and seal.

    Raises:
        DirtyTreeError: The tree is dirty and ``allow_dirty`` is false.
        GitError: ``git`` cannot be run.
    """
    root = root.resolve()
    state = capture_git_state(cwd=root)
    assert_clean_or_allowed(state, allow_dirty=allow_dirty)
    diff = _git_diff_head(root)
    return {
        "git_head": state.sha,
        "dirty": state.dirty,
        "tree_status": "DIRTY" if state.dirty else "CLEAN",
        "git_diff_head_sha256": hashlib.sha256(diff).hexdigest(),
    }


def launch_evidence_record(evidence_dir: Path, *, root: Path) -> dict[str, Any]:
    """Every file the launcher wrote for this run (gate JSON, opening canary).

    The launcher writes them under derived/h1_hybrid/_launches/<run_id>/,
    which is gitignored, before it spawns the worker. Each file is recorded
    by repo-relative path, size and sha256, so the plan and the seal fix
    their bytes. A missing or empty directory refuses: the evidence is lost.
    """
    root = root.resolve()
    base = Path(evidence_dir).resolve()
    if not base.is_dir():
        raise SystemExit(f"REFUSED -- launch evidence dir missing: {base}")
    files = sorted(p for p in base.rglob("*") if p.is_file())
    if not files:
        raise SystemExit(f"REFUSED -- launch evidence dir is empty: {base}")

    def shown(path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()

    return {
        "dir": shown(base),
        "files": [
            {
                "path": shown(path),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in files
        ],
    }


def _git_diff_head(root: Path) -> bytes:
    try:
        proc = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            timeout=_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError("git diff HEAD timed out") from exc
    except FileNotFoundError as exc:
        raise GitError("git executable not found") from exc
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(f"git diff HEAD failed: {err}")
    return proc.stdout
