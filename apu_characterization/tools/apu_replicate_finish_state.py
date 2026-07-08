"""Update replicate_v3.state.json when an unattended run finishes."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    exit_code = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    repo = Path(__file__).resolve().parents[2]
    state_path = repo / "apu_characterization/out/replicate_v3.state.json"
    if not state_path.is_file():
        return
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["status"] = "finished"
    state["exit_code"] = exit_code
    state["finished_at"] = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
