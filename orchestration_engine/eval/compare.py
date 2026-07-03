"""Compare hardware engine sim vs CPU baseline on synthetic workloads."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", type=Path, default=None, help="Path to oe_bench.exe")
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--fanout", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    bench = args.bench
    if bench is None:
        bench = Path(__file__).resolve().parents[1] / "build" / "oe_bench.exe"

    if not bench.exists():
        print(
            f"Benchmark binary not found: {bench}\n"
            "Build first: cd orchestration_engine && ./build.ps1 (or g++ manually)",
            file=sys.stderr,
        )
        sys.exit(1)

    proc = subprocess.run(
        [str(bench), str(args.depth), str(args.fanout), str(args.seed)],
        capture_output=True,
        text=True,
        check=False,
    )
    print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")

    report = {
        "depth": args.depth,
        "fanout": args.fanout,
        "seed": args.seed,
        "stdout": proc.stdout,
        "exit_code": proc.returncode,
    }
    if args.output:
        args.output.write_text(json.dumps(report, indent=2))

    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
