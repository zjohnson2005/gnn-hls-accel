"""Pre-pull OA-01 SWE-bench images via Epoch GHCR and retag to mini-SWE names.

Docker Hub blob pulls are unreliable on some Docker Desktop setups. Epoch's
public GHCR registry is used only as a local cache source; images are retagged
to the exact ``docker.io/swebench/sweb.eval...`` names the unmodified subject
requests, so the agent itself is not redirected.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = Path(__file__).resolve().parent / "task_manifest.json"


def official_image(instance_id: str) -> str:
    docker_id = instance_id.replace("__", "_1776_").lower()
    return f"docker.io/swebench/sweb.eval.x86_64.{docker_id}:latest"


def epoch_image(instance_id: str) -> str:
    return f"ghcr.io/epoch-research/swe-bench.eval.x86_64.{instance_id}:latest"


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--orders",
        type=str,
        default="",
        help="Comma-separated task orders to pull (default: all)",
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    wanted: set[int] | None = None
    if args.orders.strip():
        wanted = {int(x) for x in args.orders.split(",") if x.strip()}
    tasks = [
        t
        for t in manifest["tasks"]
        if wanted is None or int(t["order"]) in wanted
    ]
    for task in tasks:
        iid = str(task["instance_id"])
        src = epoch_image(iid)
        dst = official_image(iid)
        print(f"# order={task['order']} {iid}", flush=True)
        _run(["docker", "pull", src])
        _run(["docker", "tag", src, dst])
        print(f"# ready {dst}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
