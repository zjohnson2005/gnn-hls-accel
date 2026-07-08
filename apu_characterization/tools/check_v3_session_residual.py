#!/usr/bin/env python3
"""Check one session's residual-provenance % against the 15% audit gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="real_agent_breakdown JSON")
    parser.add_argument("task_id", help="task_id to check (e.g. FO-01)")
    parser.add_argument(
        "--limit",
        type=float,
        default=0.15,
        help="max residual provenance fraction of host CPU (default 0.15)",
    )
    args = parser.parse_args()

    art = json.loads(args.artifact.read_text(encoding="utf-8"))
    run = art.get("run") or {}
    per_session = run.get("per_session") or []
    matches = [s for s in per_session if s.get("task_id") == args.task_id]
    if not matches:
        print(f"no session with task_id={args.task_id!r}", file=sys.stderr)
        sys.exit(1)

    worst_frac = 0.0
    worst_label = ""
    for sess in matches:
        host = sess.get("process_cpu_ns", 0)
        if host <= 0:
            continue
        prov = sess.get("provenance") or {}
        res_ns = prov.get("residual", 0)
        frac = res_ns / host
        host_ms = host / 1e6
        res_ms = res_ns / 1e6
        pct = 100 * frac
        print(
            f"{args.task_id} ({sess.get('session_id')}): "
            f"residual-provenance {res_ms:.1f} ms ({pct:.1f}% of host {host_ms:.1f} ms)"
        )
        instr = sess.get("instrumented_cpu_ns", 0)
        ratio = instr / host if host else 0.0
        print(f"  instrumented/host ratio: {ratio:.3f}")
        if frac > worst_frac:
            worst_frac = frac
            worst_label = sess.get("session_id", "?")

    audit = art.get("audit") or {}
    for v in audit.get("violations") or []:
        if args.task_id in v:
            print(f"  audit violation: {v}")

    if worst_frac > args.limit:
        print(
            f"FAIL: worst residual {100 * worst_frac:.1f}% > {100 * args.limit:.0f}% "
            f"(session {worst_label})",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"PASS: residual-provenance <= {100 * args.limit:.0f}%")
    sys.exit(0)


if __name__ == "__main__":
    main()
