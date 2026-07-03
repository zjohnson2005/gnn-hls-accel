"""Capture LightningSim trace.pkl for a Vitis HLS solution directory."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build trace.pkl via fifo-advisor LSEnv")
    parser.add_argument(
        "--solution-dir",
        type=Path,
        required=True,
        help="Absolute or repo-relative path to sol1/ (or solution1/)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo root for relative HLS paths in the project (default: auto)",
    )
    args = parser.parse_args()

    repo = args.repo_root
    if repo is None:
        repo = Path(__file__).resolve().parents[2]
    repo = repo.resolve()
    os.chdir(str(repo))

    sol = args.solution_dir.resolve()
    trace = sol / "trace.pkl"
    if trace.is_file():
        print("trace.pkl already exists:", trace)
        return 0

    # LightningSim resolves TB/HLS paths relative to the repo cwd in many flows.
    print("Capturing trace for", sol, "(cwd", repo, ")")
    print("XILINX_VITIS=", os.environ.get("XILINX_VITIS", "unset"))
    print("vitis_hls=", os.environ.get("PATH", "").split(":")[0])

    from fifo_advisor.opt_env import LSEnv

    LSEnv(sol)
    if not trace.is_file():
        print("ERROR: trace.pkl was not created", file=sys.stderr)
        return 1
    print("Wrote", trace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
