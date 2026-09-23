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
