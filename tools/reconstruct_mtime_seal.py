"""Copy a c2 run into sealed_<id> when every source mtime is within finish+120s.

Does not modify the source run directory. The tree hash is written only to
.sealed, labeled RECONSTRUCTED, with the mtime evidence.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.seal_verify import tree_sha256, verify_seal  # noqa: E402

COPY_FILES = (
    "plan.json",
    "summary.json",
    "arm_results.json",
    "probes.ndjson",
    "watchdog_kills.jsonl",
)
GATE = timedelta(seconds=120)


def _finish(source: Path) -> datetime:
    summary = json.loads((source / "summary.json").read_text(encoding="utf-8-sig"))
    for key in ("ended_utc", "finished_utc", "sealed_utc"):
        value = summary.get(key)
        if isinstance(value, str) and value.strip():
            return datetime.fromisoformat(value)
    raise SystemExit(f"REFUSED -- no recorded finish time in {source / 'summary.json'}")


def reconstruct(source: Path) -> Path | None:
    source = source.resolve()
    finish = _finish(source)
    deadline = finish + GATE
    late: list[tuple[str, str]] = []
    newest_path = ""
    newest_stamp: datetime | None = None
    for file in source.rglob("*"):
        if not file.is_file():
            continue
        stamp = datetime.fromtimestamp(file.stat().st_mtime, finish.tzinfo)
        if newest_stamp is None or stamp > newest_stamp:
            newest_stamp = stamp
            newest_path = file.relative_to(source).as_posix()
        if stamp > deadline:
            late.append((file.relative_to(source).as_posix(), stamp.isoformat()))
    if late:
        print(f"NOT SEALED {source.name}")
        for rel, stamp in sorted(late):
            print(f"  newer than finish+120s: {rel} {stamp}")
        return None
    out = source.parent / f"sealed_{source.name}"
    if out.exists():
        raise SystemExit(f"REFUSED -- seal already exists: {out}")
    out.mkdir(parents=True)
    copied: list[str] = []
    for name in COPY_FILES:
        src = source / name
        if src.is_file():
            shutil.copy2(src, out / name)
            copied.append(name)
    if not copied:
        raise SystemExit(f"REFUSED -- no seal files in {source}")
    digest = tree_sha256(out)
    marker = {
        "label": "RECONSTRUCTED",
        "run_id": source.name,
        "tree_sha256": digest,
        "mtime_gate_s": 120,
        "recorded_finish_time": finish.isoformat(),
        "newest_source_file": newest_path,
        "newest_source_mtime_utc": None if newest_stamp is None else newest_stamp.isoformat(),
        "copied_files": copied,
        "source_path": source.relative_to(ROOT).as_posix(),
        "note": (
            "seal_c2 file set copied out of the source run. "
            "Source bytes were not modified. tree_sha256 is only in this file."
        ),
    }
    (out / ".sealed").write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    status = verify_seal(out)
    if status != "MATCH":
        raise SystemExit(f"REFUSED -- reconstructed tree verified {status}")
    print(f"SEALED {out.relative_to(ROOT).as_posix()} {digest} {status}")
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("usage: reconstruct_mtime_seal.py <source-run-dir>")
    reconstruct(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
