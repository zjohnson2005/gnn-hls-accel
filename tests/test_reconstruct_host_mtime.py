"""Host mtimes, not copy mtimes, are the finish+120s gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.reconstruct_mtime_seal import reconstruct_from_host_manifest  # noqa: E402
from tools.seal_verify import verify_seal  # noqa: E402

RUN = "c76fed24-63a9-4b3b-98be-11ff83da7a4c"


def _tree(tmp_path: Path) -> Path:
    source = tmp_path / RUN
    (source / "work").mkdir(parents=True)
    (source / "summary.json").write_text(
        json.dumps({"ended_utc": "2026-10-03T21:27:00.199699+00:00", "status": "complete"}),
        encoding="utf-8",
    )
    (source / "work" / "probe.json").write_text("{}\n", encoding="utf-8")
    return source


def test_host_mtime_after_finish_refuses(tmp_path: Path) -> None:
    source = _tree(tmp_path)
    listing = tmp_path / "mtimes.txt"
    listing.write_text(
        "2026-10-03T22:09:09.1195123Z\t"
        f"C:\\Users\\zach\\Projects\\gnn-hls-accel\\derived\\c2_ttft\\{RUN}\\summary.json\n"
        "2026-10-03T21:26:00.0000000Z\t"
        f"C:\\Users\\zach\\Projects\\gnn-hls-accel\\derived\\c2_ttft\\{RUN}\\work\\probe.json\n",
        encoding="utf-8",
    )
    assert reconstruct_from_host_manifest(source, listing) is None
    assert not (tmp_path / f"sealed_{RUN}").exists()


def test_host_mtime_inside_gate_seals(tmp_path: Path) -> None:
    source = _tree(tmp_path)
    listing = tmp_path / "mtimes.txt"
    listing.write_text(
        "2026-10-03T21:27:00.1996990Z\t"
        f"C:\\Users\\zach\\Projects\\gnn-hls-accel\\derived\\c2_ttft\\{RUN}\\summary.json\n"
        "2026-10-03T21:26:00.0000000Z\t"
        f"C:\\Users\\zach\\Projects\\gnn-hls-accel\\derived\\c2_ttft\\{RUN}\\work\\probe.json\n",
        encoding="utf-8",
    )
    sealed = reconstruct_from_host_manifest(source, listing)
    assert sealed is not None
    assert verify_seal(sealed) == "MATCH"
    marker = json.loads((sealed / ".sealed").read_text(encoding="utf-8"))
    assert marker["evidence_source"] == "T2S_SOURCE_MANIFEST"
    assert marker["label"] == "RECONSTRUCTED"
    assert (source / "summary.json").read_bytes() == (sealed / "summary.json").read_bytes()
