"""Allocation diagnosis for a bisection failure.

Reads a result JSON from the path given on the command line. Does not open
a preregistration, amendment, or predictions file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_c1_ceiling import classify_c1_failure  # noqa: E402


def diagnose(result: dict[str, Any]) -> dict[str, Any]:
    classified = classify_c1_failure(result)
    return {
        "error_class": classified.get("error_class"),
        "requested_bytes": classified.get("requested_bytes"),
        "alloc_logits_pattern": bool(classified.get("alloc_logits_pattern")),
        "failure_kind": classified.get("failure_kind"),
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        raise SystemExit("usage: alloc_diag.py RESULT.json")
    result = json.loads(Path(args[0]).read_text(encoding="utf-8-sig"))
    if not isinstance(result, dict):
        raise SystemExit("REFUSED -- result JSON must be an object")
    print(json.dumps(diagnose(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
