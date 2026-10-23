"""A19 read-only record (Task BM): system memory, DXGI adapter memory and this process's
video-memory budget, as one JSON line. Changes nothing. Off Windows it prints an error field.

Usage: python tools/dxgi_probe.py [--watch-s N]   (N > 0 also counts budget-change events)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.dxgi_budget import BudgetWatch, snapshot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--watch-s", type=float, default=0.0)
    a = ap.parse_args(argv)
    out = {"event": "dxgi_probe", "t_unix": time.time(), **snapshot()}
    if a.watch_s > 0:
        w = BudgetWatch()
        t_end = time.time() + a.watch_s
        while time.time() < t_end:
            w.poll()
            time.sleep(0.1)
        w.close()
        out["budget_change_events"] = w.count
        out["budget_watch_error"] = w.error
    print(json.dumps(out, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
