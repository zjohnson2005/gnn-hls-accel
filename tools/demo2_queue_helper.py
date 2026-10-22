"""Task BE queue helper (Mac side of the window scripts): where to resume after a watchdog fire.

  python tools/demo2_queue_helper.py resume --pin <pin.json> --hang-events <hang_events.json> \\
      [--order-by-toolset] [--offset <first run's offset>]

Prints "RESUME <offset> <entry_id>": the hung entry's index in run order (the pin order, or
tools.run_h1_hybrid.order_by_toolset when the run used --order-by-toolset). The continuation
cell is the same launch with -EntryOffset <offset> -SkipEntries <entry_id> -SkipHangRecord
<host path of hang_events.json>: it records the hung entry as a local fail (outcome
hang/stall/turn_budget_exceeded) and runs the rest. Reads only; writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def resume_offset(entries: list[dict], hung_id: str, *, order: bool) -> int:
    from tools.run_h1_hybrid import order_by_toolset

    seq = order_by_toolset(entries) if order else entries
    ids = [str(e["id"]) for e in seq]
    if hung_id not in ids:
        raise SystemExit(f"REFUSED -- {hung_id} not in the pin")
    return ids.index(hung_id)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resume")
    r.add_argument("--pin", type=Path, required=True)
    r.add_argument("--hang-events", type=Path, required=True)
    r.add_argument("--order-by-toolset", action="store_true")
    a = ap.parse_args(argv)
    entries = json.loads(a.pin.read_text(encoding="utf-8"))
    events = json.loads(a.hang_events.read_text(encoding="utf-8-sig")).get("events") or []
    fired = [e for e in events if e.get("outcome") in ("hang", "stall", "turn_budget_exceeded")]
    if not fired:
        raise SystemExit("REFUSED -- no hang/stall/turn_budget_exceeded event")
    hung = str(fired[-1]["entry_id"])
    print(f"RESUME {resume_offset(entries, hung, order=a.order_by_toolset)} {hung}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
