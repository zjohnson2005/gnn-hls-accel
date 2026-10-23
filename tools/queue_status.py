"""Read-only summary of the weekend queue windows (Task BO).

For each ~/seam_closeout_1013/{xps,t2s}/window_* (default: the newest *_v3 per host, or all with
--all): the STATUS.txt "now" line, the last step and its time, cell counts by rc, alert count, and
any failure class seen in the copied log tails (tools/cc_failure classes, by text match). Nothing is
written and no host is contacted.
Usage: python tools/queue_status.py [--root ~/seam_closeout_1013] [--all]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.cc_failure import _RULES  # noqa: E402

_RC = re.compile(r"\brc=([A-Za-z0-9_]+)")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def window_summary(w: Path) -> dict[str, Any]:
    status = _read(w / "STATUS.txt")
    now = next((ln[5:].strip() for ln in status.splitlines() if ln.startswith("now:")), None)
    steps = [ln for ln in _read(w / "steps.txt").splitlines() if ln.strip()]
    cells = [ln for ln in _read(w / "cells.txt").splitlines() if ln.strip()]
    rcs = Counter(m.group(1) for ln in cells for m in [_RC.search(ln)] if m)
    classes: Counter[str] = Counter()
    for tail in w.glob("*_logtail.txt"):
        text = _read(tail)
        for name, rx in _RULES:
            if rx.search(text):
                classes[name] += 1
    return {
        "window": w.name,
        "now": now,
        "last_step": steps[-1] if steps else None,
        "cells": len(cells),
        "rc": dict(rcs),
        "alerts": len([ln for ln in _read(w / "ALERTS.txt").splitlines() if ln.strip()]),
        "failure_classes_in_logtails": dict(classes),
    }


def windows(root: Path, all_: bool) -> list[Path]:
    out: list[Path] = []
    for host in ("xps", "t2s"):
        ws = sorted((root / host).glob("window_*"), key=lambda p: p.name)
        if all_:
            out += ws
        else:
            v3 = [w for w in ws if w.name.endswith("_v3")]
            if v3:
                out.append(v3[-1])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=Path.home() / "seam_closeout_1013")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    ws = windows(a.root, a.all)
    if not ws:
        print("no v3 windows yet")
    for w in ws:
        s = window_summary(w)
        print(f"== {w.parent.name}/{s['window']}")
        print(f"   now: {s['now']}")
        print(f"   last: {s['last_step']}")
        print(
            f"   cells: {s['cells']} rc={s['rc']} alerts={s['alerts']} failure classes={s['failure_classes_in_logtails']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
