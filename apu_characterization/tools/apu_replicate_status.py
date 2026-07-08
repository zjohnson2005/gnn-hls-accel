"""Poll an unattended v3 replication run and optionally validate when finished."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATE = Path("apu_characterization/out/replicate_v3.state.json")
DEFAULT_ARTIFACT = Path("apu_characterization/out/replication_remote_search_v3.json")
VALIDATE = Path("apu_characterization/tools/validate_publishable.py")


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


def _tail_log(log_path: Path, lines: int = 8) -> list[str]:
    if not log_path.is_file():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return text.splitlines()[-lines:]


def _validate(artifact: Path) -> int:
    proc = subprocess.run(
        [sys.executable, str(VALIDATE), str(artifact)],
        check=False,
    )
    return proc.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE,
        help="state JSON from run_apu_replicate_unattended",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT,
        help="v3 replication artifact to validate",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="run validate_publishable.py when replication finished",
    )
    args = parser.parse_args()

    state = _read_state(args.state)
    if not state:
        print(f"No state file at {args.state}")
        print("Start with: make apu-replicate-unattended")
        sys.exit(3)

    status = state.get("status", "unknown")
    pid = int(state.get("pid") or 0)
    log_path = Path(state.get("log") or "apu_characterization/out/replicate_v3.log")
    started = state.get("started_at", "?")

    print(f"replication status: {status}")
    print(f"started_at: {started}")
    print(f"pid: {pid}")
    print(f"log: {log_path}")

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
        # Process exited without state update — infer from log / artifact mtime.
        if args.artifact.is_file():
            state["status"] = "finished"
            state["finished_at"] = datetime.now(timezone.utc).isoformat()
            args.state.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            status = "finished"
            print("Process ended (state refreshed to finished).")
        else:
            print("Process ended but artifact missing — check log for errors.")
            sys.exit(1)

    if status != "finished":
        print(f"Unexpected status: {status!r}")
        sys.exit(1)

    exit_code = int(state.get("exit_code", 0))
    print(f"exit_code: {exit_code}")
    if exit_code != 0:
        tail = _tail_log(log_path, lines=20)
        if tail:
            print("\n--- log tail ---")
            for line in tail:
                print(line)
        sys.exit(1)

    if args.validate:
        if not args.artifact.is_file():
            print(f"Missing artifact: {args.artifact}")
            sys.exit(1)
        sys.exit(_validate(args.artifact))

    print("Replication finished OK (artifact present).")
    if args.artifact.is_file():
        print(f"artifact: {args.artifact}")
    sys.exit(0)


if __name__ == "__main__":
    main()
