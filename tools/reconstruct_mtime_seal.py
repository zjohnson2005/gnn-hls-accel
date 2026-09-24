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


def _summary_path(source: Path) -> Path | None:
    for name in ("summary.json", "SUMMARY.json"):
        path = source / name
        if path.is_file():
            return path
    return None


def _finish(source: Path) -> tuple[datetime, str]:
    summary_path = _summary_path(source)
    if summary_path is not None:
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        for key in ("ended_utc", "finished_utc", "sealed_utc"):
            value = summary.get(key)
            if isinstance(value, str) and value.strip():
                return datetime.fromisoformat(value), f"{summary_path.name}:{key}"
    newest: datetime | None = None
    for file in source.rglob("*"):
        if not file.is_file():
            continue
        stamp = datetime.fromtimestamp(file.stat().st_mtime, datetime.now().astimezone().tzinfo)
        if newest is None or stamp > newest:
            newest = stamp
    if newest is None:
        raise SystemExit(f"REFUSED -- no files to seal in {source}")
    return newest, "newest_source_mtime"


def reconstruct(source: Path) -> Path | None:
    source = source.resolve()
    finish, finish_source = _finish(source)
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
    for src in sorted((p for p in source.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        rel = src.relative_to(source)
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(rel.as_posix())
    if not copied:
        raise SystemExit(f"REFUSED -- no seal files in {source}")
    digest = tree_sha256(out)
    marker = {
        "label": "RECONSTRUCTED",
        "run_id": source.name,
        "tree_sha256": digest,
        "mtime_gate_s": 120,
        "recorded_finish_time": finish.isoformat(),
        "finish_source": finish_source,
        "newest_source_file": newest_path,
        "newest_source_mtime_utc": None if newest_stamp is None else newest_stamp.isoformat(),
        "copied_files": copied,
        "source_path": source.relative_to(ROOT).as_posix(),
        "note": (
            "Full source tree copied out of the run directory. "
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
