"""WARM-KV cell entry. Turn-2 delta-prefill TTFT limit. No model load in this body.

This process stops before constructing a pipeline. The boot sequencer dry-run
only prints the command line.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="WARM-KV turn-2 delta-prefill limit")
    parser.add_argument("--arm", required=True)
    parser.add_argument("--model-spec", required=True)
    parser.parse_args(argv)
    raise SystemExit(
        "REFUSED -- WARM-KV measurement body is not started. "
        "No pipeline is constructed."
    )


if __name__ == "__main__":
    main(sys.argv[1:])
