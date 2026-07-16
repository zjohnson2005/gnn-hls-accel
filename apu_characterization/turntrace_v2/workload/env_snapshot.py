"""Environment snapshot helpers for replay bundles."""

from __future__ import annotations

import subprocess
from pathlib import Path

from apu_characterization.turntrace_v2.replay import EnvSnapshotRef


def _git(cmd: list[str], cwd: Path | None = None) -> str:
    try:
        out = subprocess.check_output(
            ["git", *cmd],
            cwd=str(cwd) if cwd else None,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:
        return "unknown"


def capture_env_snapshot(
    *,
    repo_root: Path | None = None,
    container_image_id: str = "local:no-container",
) -> EnvSnapshotRef:
    root = repo_root or Path.cwd()
    commit = _git(["rev-parse", "HEAD"], cwd=root)
    dirty = _git(["status", "--porcelain"], cwd=root)
    patch = None
    if dirty and dirty != "unknown":
        patch = _git(["diff", "HEAD"], cwd=root) or dirty
        if len(patch) > 200_000:
            patch = patch[:200_000] + "\n# truncated\n"
    return EnvSnapshotRef(
        git_commit=commit,
        container_image_id=container_image_id,
        dirty_patch=patch,
    )


def reconstruct_and_compare_tool(
    *,
    snapshot: EnvSnapshotRef,
    tool_name: str,
    archived_result: object,
    live_result: object,
) -> dict:
    """CI helper: for deterministic tools, byte-compare archived vs live result."""
    equal = str(archived_result) == str(live_result)
    return {
        "tool_name": tool_name,
        "git_commit": snapshot.git_commit,
        "container_image_id": snapshot.container_image_id,
        "equal": equal,
        "mode": "byte_compare_deterministic",
    }
