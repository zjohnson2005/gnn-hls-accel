"""Safe filesystem walks that skip broken reparse points / symlink loops.

Item I1: `.venv-cap01-fc/lib64` once aborted every recursive search and caused
a false "traj.json unreachable" conclusion. Any tooling that walks the tree
must use this helper rather than bare `Path.rglob` / `os.walk` from repo root.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

DEFAULT_SKIP = frozenset({
    ".git", ".venv", ".venv-cap01-fc", "node_modules", "__pycache__",
    "target", ".rustup", ".cargo", ".tox", ".mypy_cache", ".pytest_cache",
})


def safe_walk(
    root: Path | str,
    *,
    follow_symlinks: bool = False,
    skip_dir_names: frozenset[str] = DEFAULT_SKIP,
) -> Iterator[tuple[Path, list[str], list[str]]]:
    """Yield (dirpath, dirnames, filenames) like os.walk, pruning symlinks."""
    root_p = Path(root)
    if not root_p.is_dir():
        return

    for dirpath_s, dirnames, filenames in os.walk(
        root_p, topdown=True, followlinks=follow_symlinks, onerror=lambda _e: None
    ):
        dirpath = Path(dirpath_s)
        kept: list[str] = []
        for name in list(dirnames):
            if name in skip_dir_names:
                continue
            child = dirpath / name
            try:
                if child.is_symlink():
                    continue
            except OSError:
                continue
            kept.append(name)
        dirnames[:] = kept
        yield dirpath, dirnames, list(filenames)


def safe_rglob(root: Path | str, pattern: str) -> Iterator[Path]:
    """Filename glob under ``root`` that will not hang on symlink loops."""
    suffix = None
    if pattern.startswith("*."):
        suffix = pattern[1:]  # e.g. ".traj.json"
    for dirpath, _dirs, files in safe_walk(root):
        for name in files:
            if suffix is not None:
                if name.endswith(suffix):
                    yield dirpath / name
            elif Path(name).match(pattern):
                yield dirpath / name
