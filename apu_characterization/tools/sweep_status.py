"""Poll the background c-ladder sweep and optionally validate when finished."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATE = Path("apu_characterization/out/sweep.state.json")
DEFAULT_ARTIFACT = Path("apu_characterization/out/concurrency_sweep.json")


def _read_state(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _tail_log(log_path: Path, lines: int = 12) -> list[str]:
    if not log_path.is_file():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return text.splitlines()[-lines:]


def _validate_artifact(artifact: Path) -> int:
    if not artifact.is_file():
        print(f"artifact missing: {artifact}")
        return 1
    data = json.loads(artifact.read_text(encoding="utf-8"))
    audit = data.get("audit") or {}
    validity = data.get("result_validity")
    print(f"result_validity: {validity}")
    print(f"audit pass: {audit.get('pass')}")
    summary = data.get("sweep_summary") or {}
    if summary:
        print(f"levels: {summary.get('n_runs')} runs, N_max={summary.get('n_max_measured')}")
    if not audit.get("pass"):
        for v in audit.get("violations") or []:
            print(f"  violation: {v}")
        return 1
    if validity not in ("publishable", "windows_footnote_only"):
        print(f"unexpected validity: {validity}")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE,
        help="state JSON from run_sweep_ladder.sh",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT,
        help="concurrency sweep artifact",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="check audit pass when sweep finished",
    )
    args = parser.parse_args()

    state = _read_state(args.state)
    if not state:
        print(f"No state file at {args.state}")
        print("Start with: .\\apu_characterization\\run_sweep_ladder.ps1")
        sys.exit(3)

    status = state.get("status", "unknown")
    pid = int(state.get("pid") or 0)
    log_path = Path(state.get("log") or "apu_characterization/out/sweep.log")
    started = state.get("started_at", "?")

    print(f"sweep status: {status}")
    print(f"started_at: {started}")
    print(f"pid: {pid}")
    print(f"log: {log_path}")
    print(f"artifact: {state.get('artifact', args.artifact)}")

    running = status == "running" and _pid_alive(pid)
    if running:
        print("\nStill running.")
        tail = _tail_log(log_path)
        if tail:
            print("\n--- log tail ---")
            for line in tail:
                print(line)
        sys.exit(2)

    if status == "running" and not _pid_alive(pid):
        if args.artifact.is_file():
            state["status"] = "finished"
            state["finished_at"] = datetime.now(timezone.utc).isoformat()
            args.state.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            status = "finished"
            print("\nProcess exited; artifact present — treating as finished.")
        else:
            state["status"] = "failed"
            args.state.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            status = "failed"
            print("\nProcess exited without artifact — treating as failed.")

    if status == "done" or status == "finished":
        if args.validate:
            sys.exit(_validate_artifact(args.artifact))
        print("\nSweep finished OK.")
        sys.exit(0)

    if status == "failed":
        tail = _tail_log(log_path, 20)
        if tail:
            print("\n--- log tail ---")
            for line in tail:
                print(line)
        sys.exit(1)

    print(f"\nUnknown status: {status}")
    sys.exit(3)


if __name__ == "__main__":
    main()
