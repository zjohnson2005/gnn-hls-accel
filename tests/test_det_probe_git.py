"""DET-PROBE records git HEAD, dirty flag, and the sha256 of git diff HEAD."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_det_probe import capture_run_git  # noqa: E402

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "seal-test",
    "GIT_AUTHOR_EMAIL": "seal-test@example.com",
    "GIT_COMMITTER_NAME": "seal-test",
    "GIT_COMMITTER_EMAIL": "seal-test@example.com",
}


def _git(args: list[str], cwd: Path) -> bytes:
    env = {**os.environ, **_GIT_ENV}
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env=env,
    )
    return proc.stdout


def _init_repo(tmp_path: Path) -> None:
    _git(["init", "-b", "main"], tmp_path)
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(["add", "a.txt"], tmp_path)
    _git(["commit", "-m", "init"], tmp_path)


def test_clean_tree_records_head_dirty_and_diff_sha(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    rec = capture_run_git(allow_dirty=False, root=tmp_path)
    diff = _git(["diff", "HEAD"], tmp_path)
    assert rec["dirty"] is False
    assert rec["tree_status"] == "CLEAN"
    assert rec["git_head"]
    assert rec["git_diff_head_sha256"] == hashlib.sha256(diff).hexdigest()


def test_dirty_tree_is_refused(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("b\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="REFUSED"):
        capture_run_git(allow_dirty=False, root=tmp_path)
