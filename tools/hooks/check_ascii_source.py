"""Pre-commit hook: reject non-ASCII bytes in SEAM source files.

Dispatch prose (en dashes, curly quotes, ellipses) has leaked into tools/,
tests/, and seam/ more than once. Ruff RUF002 catches some docstring cases;
this gate rejects any codepoint > 127 in staged .py / .ps1 under those trees.

Exit 0 = clean, 1 = blocked.
"""

from __future__ import annotations

import sys
from pathlib import Path

ALLOWED_SUFFIXES = {".py", ".ps1"}
ALLOWED_ROOTS = ("tools/", "tests/", "seam/")


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _in_scope(rel: str) -> bool:
    if not any(rel.startswith(root) for root in ALLOWED_ROOTS):
        return False
    return Path(rel).suffix.lower() in ALLOWED_SUFFIXES


def scan(paths: list[str]) -> int:
    violations: list[str] = []
    for raw in paths:
        rel = _norm(raw)
        if not _in_scope(rel):
            continue
        path = Path(raw)
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        # Skip obvious binaries (NUL in first 8 KiB).
        sample = data[:8192]
        if b"\x00" in sample:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            violations.append(f"{rel}: not valid UTF-8 ({exc})")
            continue
        for i, ch in enumerate(text):
            if ord(ch) > 127:
                line = text.count("\n", 0, i) + 1
                col = i - text.rfind("\n", 0, i)
                esc = ch.encode("unicode_escape").decode("ascii")
                violations.append(
                    f"{rel}:{line}:{col}: non-ASCII {esc} (U+{ord(ch):04X})"
                )
                break

    if violations:
        sys.stderr.write(
            "\nBLOCKED - non-ASCII in tools/tests/seam source "
            "(.py / .ps1). Use ASCII punctuation only:\n"
        )
        for v in violations:
            sys.stderr.write(f"  {v}\n")
        sys.stderr.write(
            "\nReplace en/em dashes with '-', ellipsis with '...', "
            "arrows with '->', etc., then re-stage.\n\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(scan(sys.argv[1:]))
