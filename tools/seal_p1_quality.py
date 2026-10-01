"""Copy a P1 quality session into a write-once seal and record tree_sha256.

Does not modify the source directory. .sealed is excluded from the tree hash.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.seal_verify import tree_sha256, verify_seal  # noqa: E402


def seal_session(session_id: str, *, root: Path = ROOT) -> dict[str, Any]:
    source = root / "derived" / "p1_quality" / session_id
    dest = root / "derived" / "p1_quality" / f"sealed_{session_id}"
    if dest.exists():
        raise SystemExit(f"REFUSED -- seal destination exists: {dest}")
    if not (source / "summary.json").is_file():
        raise SystemExit(f"REFUSED -- missing summary: {source}")
    dest.mkdir()
    for name in ("plan.json", "summary.json"):
        shutil.copy2(source / name, dest / name)
    points = dest / "points"
    points.mkdir()
    for path in sorted((source / "points").glob("*.json")):
        shutil.copy2(path, points / path.name)
    canaries = dest / "work" / "canaries"
    canaries.mkdir(parents=True)
    for path in sorted((source / "work" / "canaries").glob("canary.*.json")):
        shutil.copy2(path, canaries / path.name)
    digest = tree_sha256(dest)
    marker = {
        "run_id": session_id,
        "seal_style": "derived_diagnostic",
        "tree_sha256": digest,
        "note": (
            "tree_sha256 excludes .sealed. Not seam.rawstore.verify_sealed; "
            "raw/ was not written. Do not mutate this directory after seal."
        ),
    }
    (dest / ".sealed").write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    status = verify_seal(dest)
    if status != "MATCH":
        raise SystemExit(f"REFUSED -- verify_seal {status} for {dest}")
    return {
        "session_id": session_id,
        "seal_dir": dest.relative_to(root).as_posix(),
        "tree_sha256": digest,
        "verify_seal": status,
    }


if __name__ == "__main__":
    print(json.dumps(seal_session("8a529053-fc47-486d-8809-6c699d156b06"), indent=2))
