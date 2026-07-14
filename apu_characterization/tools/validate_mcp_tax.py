"""Validate MCP-01 aggregates for the protocol_microbenchmark claim class."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from apu_characterization.mcp_tax.validate import validate_mcp_tax


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "json",
        nargs="?",
        type=Path,
        default=Path("apu_characterization/out/mcp_tax/mcp_tax.matrix.json"),
    )
    parser.add_argument(
        "--debug-smoke",
        action="store_true",
        help="validate smoke structure while explicitly allowing WSL/dirty/debug/n<5",
    )
    args = parser.parse_args()
    data = json.loads(args.json.read_text(encoding="utf-8"))
    errors = validate_mcp_tax(data, debug_smoke=args.debug_smoke)
    print(f"artifact: {args.json}")
    print(f"mode: {'DEBUG SMOKE' if args.debug_smoke else 'PUBLISHABLE PROTOCOL'}")
    if errors:
        print("FAIL:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
