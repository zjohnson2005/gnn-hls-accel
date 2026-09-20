"""Refuse hardcoded per-user absolute paths in tools/ and seam/ (PORT-1)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("tools", "seam")
# Constructed so this file itself does not embed the forbidden literal as a path root.
_USER = "zjohn"
_FORBIDDEN = re.compile(
    rf"(?i)(?:C:[/\\]Users[/\\]{_USER}|/Users/{_USER}|/home/{_USER})",
)

# One-shot migrators / temp probes may mention the pattern in comments while rewriting;
# keep the deny-list empty unless a documented exception is required.
_ALLOW_RELATIVE = {
    "tools/_fix_hardcoded_roots.py",  # migrator; delete after PORT-1 lands
    "tools/_tmp_check_yaml.py",
    "tools/_tmp_import_gates.py",
}


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for dirname in SCAN_DIRS:
        root = REPO_ROOT / dirname
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {
                ".py",
                ".ps1",
                ".psm1",
                ".psd1",
                ".md",
                ".yaml",
                ".yml",
                ".json",
                ".toml",
                ".txt",
                ".cfg",
                ".ini",
            }:
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            files.append(path)
    return files


@pytest.mark.parametrize("path", _iter_files(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_no_hardcoded_user_paths(path: Path) -> None:
    rel = path.relative_to(REPO_ROOT).as_posix()
    if rel in _ALLOW_RELATIVE:
        pytest.skip(f"allowlisted migrator/temp: {rel}")
    text = path.read_text(encoding="utf-8", errors="replace")
    hits = []
    for i, line in enumerate(text.splitlines(), start=1):
        if _FORBIDDEN.search(line):
            hits.append(f"{rel}:{i}:{line.strip()}")
    assert not hits, (
        "hardcoded per-user absolute path(s) found (PORT-1). "
        "Derive repo root from __file__ / $PSScriptRoot instead:\n" + "\n".join(hits[:20])
    )
