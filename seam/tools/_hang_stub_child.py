"""Write a terminal result file, then spin until the parent kills the process."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    payload = {
        "phase": "failed",
        "completed": False,
        "failure_mode": "turn1:RuntimeError",
        "memory_resident_before_inference": {"rss_mb": 1.0},
        "exception": {
            "type": "RuntimeError",
            "message": "CL_OUT_OF_RESOURCES stub; child spins after the result file",
        },
    }
    args.out.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    time.sleep(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
