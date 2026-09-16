"""Lock the TLP-01 protocol from a published S2 task manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apu_characterization.tlp01.protocol_lock import (
    build_locked_protocol,
    write_locked_protocol,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s2-task-manifest", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("apu_characterization/out/tlp01/protocol_tlp01_v1.locked.json"),
    )
    args = parser.parse_args()
    manifest = json.loads(args.s2_task_manifest.read_text(encoding="utf-8"))
    locked = build_locked_protocol(s2_task_manifest=manifest)
    path = write_locked_protocol(locked, args.output)
    print(f"locked protocol written: {path}")


if __name__ == "__main__":
    main()
