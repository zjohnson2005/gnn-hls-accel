"""H1 seal provenance: HEAD, dirty flag, sha256 of git diff HEAD."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.errors import DirtyTreeError  # noqa: E402
from tools.h1_seal_git import seal_git_record  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    StubCloudBackend,
    StubLocalBackend,
    run_interleaved_session,
    run_session,
)

FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_3entries.json"

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


def test_clean_tree_records_head_and_empty_diff(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    rec = seal_git_record(allow_dirty=False, root=tmp_path)
    assert rec["dirty"] is False
    assert rec["tree_status"] == "CLEAN"
    assert rec["git_head"]
    diff = _git(["diff", "HEAD"], tmp_path)
    assert rec["git_diff_head_sha256"] == hashlib.sha256(diff).hexdigest()


def test_dirty_tree_is_refused_without_allow(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("b\n", encoding="utf-8")
    with pytest.raises(DirtyTreeError, match="uncommitted"):
        seal_git_record(allow_dirty=False, root=tmp_path)


def test_allow_dirty_records_dirty_and_diff_sha(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("b\n", encoding="utf-8")
    rec = seal_git_record(allow_dirty=True, root=tmp_path)
    diff = _git(["diff", "HEAD"], tmp_path)
    assert rec["dirty"] is True
    assert rec["tree_status"] == "DIRTY"
    assert rec["git_diff_head_sha256"] == hashlib.sha256(diff).hexdigest()
    assert diff != b""


def _git_block() -> dict[str, object]:
    return {
        "git_head": "abc123",
        "dirty": True,
        "tree_status": "DIRTY",
        "git_diff_head_sha256": "deadbeef",
    }


def test_session_seal_and_plan_include_git(tmp_path: Path) -> None:
    fix = json.loads(FIXTURE.read_text(encoding="utf-8"))
    git = _git_block()
    out = tmp_path / "cap"
    run_session(
        policy="cloud_only",
        entries=fix["entries"],
        out_dir=out,
        max_usd=1000.0,
        local=StubLocalBackend(script=fix["local_script"]),
        cloud=StubCloudBackend(
            tokens_in=fix["cloud_tokens_in"],
            tokens_out=fix["cloud_tokens_out"],
        ),
        skip_entry_assert=True,
        seal=True,
        seal_git=git,
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    seal = json.loads((out / ".sealed").read_text(encoding="utf-8"))
    assert plan["git"] == git
    assert seal["git"] == git


def test_interleaved_seals_include_git(tmp_path: Path) -> None:
    fix = json.loads(FIXTURE.read_text(encoding="utf-8"))
    git = _git_block()
    out = tmp_path / "intl"
    run_interleaved_session(
        entries=fix["entries"],
        out_dir=out,
        local=StubLocalBackend(script=fix["local_script"]),
        cloud=StubCloudBackend(
            tokens_in=fix["cloud_tokens_in"],
            tokens_out=fix["cloud_tokens_out"],
        ),
        policies=("cloud_only",),
        policy_caps_usd={"cloud_only": 1000.0},
        session_max_usd=1000.0,
        skip_entry_assert=True,
        seal=True,
        seal_git=git,
    )
    session_seal = json.loads((out / ".sealed").read_text(encoding="utf-8"))
    assert session_seal["git"] == git
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["git"] == git
    arm_seal = json.loads((out / "policies" / "cloud_only" / ".sealed").read_text(encoding="utf-8"))
    assert arm_seal["git"] == git
