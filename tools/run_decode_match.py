"""DECODE-MATCH cell entry. int4 vs int8 decode tok/s at matched n. No model load.

This process stops before constructing a pipeline.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="DECODE-MATCH at matched n")
    parser.add_argument("--arm", required=True)
    parser.add_argument("--model-spec", required=True)
    parser.add_argument("--n", required=True, help="comma-separated n list")
    parser.parse_args(argv)
    raise SystemExit(
        "REFUSED -- DECODE-MATCH measurement body is not started. "
        "No pipeline is constructed."
    )


if __name__ == "__main__":
    main(sys.argv[1:])
