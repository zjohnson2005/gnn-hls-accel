"""Load one JSON file the way the boot readers do, BOM or not.

The launchers call this after they write a file, so a BOM cannot pass a handoff.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.json_io import load_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("REFUSED -- usage: read_json_utf8.py <path>", file=sys.stderr)
        return 2
    path = Path(args[0])
    if "sealed_" in path.as_posix():
        print(f"REFUSED -- refusing to read a sealed path: {path}", file=sys.stderr)
        return 2
    load_json(path)
    print("json_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
