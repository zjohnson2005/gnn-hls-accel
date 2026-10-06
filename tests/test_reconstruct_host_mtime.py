"""Host mtimes, not copy mtimes, are the finish+120s gate."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

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


def test_missing_end_stamp_uses_the_newest_host_mtime(tmp_path: Path) -> None:
    source = tmp_path / RUN
    source.mkdir()
    (source / "summary.json").write_text(
        json.dumps({"status": "complete"}) + "\n", encoding="utf-8"
    )
    listing = tmp_path / "mtimes.txt"
    listing.write_text(
        "2026-10-05T20:00:00.0000000Z\t"
        f"C:\\Users\\zach\\Projects\\gnn-hls-accel\\derived\\npu\\{RUN}\\summary.json\n",
        encoding="utf-8",
    )
    sealed = reconstruct_from_host_manifest(source, listing)
    assert sealed is not None
    marker = json.loads((sealed / ".sealed").read_text(encoding="utf-8"))
    assert marker["finish_source"] == "newest_host_mtime"
    assert marker["recorded_finish_time"].startswith("2026-10-05T20:00:00")


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


def _stamped_tree(tmp_path: Path) -> Path:
    source = tmp_path / RUN
    (source / "work").mkdir(parents=True)
    probe = {
        "arm_id": "gpu_only_f16",
        "n_tokens": 64,
        "repeat_index": 0,
        "prefill_s": 1.25,
        "decode_tok_s": 20.0,
        "outcome": "pass",
        "wall_s": 1.5,
        "completed": True,
    }
    (source / "probes.ndjson").write_text(json.dumps(probe) + "\n", encoding="utf-8")
    result = {"generation": {"prefill_s": 1.25, "decode_tok_s": 20.0}, "completed": True}
    (source / "work" / "gpu_only_f16.n64.r0.a0.result.json").write_text(
        json.dumps(result),
        encoding="utf-8",
    )
    body = {
        "ended_utc": "2026-10-03T21:27:00.199699+00:00",
        "status": "complete",
        "watchdog_log": r"C:\apu\ovn\watchdog.log",
        "foreign_queue_evidence": [],
        "arm_results": [{"ttft_limit_n": 64, "repeats": [probe]}],
    }
    for name in ("plan.json", "summary.json"):
        (source / name).write_text(json.dumps(body), encoding="utf-8")
    return source


def _listing(tmp_path: Path, plan_stamp: str) -> Path:
    listing = tmp_path / "mtimes.txt"
    rows = [
        f"{plan_stamp}\tC:\\host\\{RUN}\\plan.json",
        f"{plan_stamp}\tC:\\host\\{RUN}\\summary.json",
        f"2026-10-03T21:26:00.0000000Z\tC:\\host\\{RUN}\\probes.ndjson",
        f"2026-10-03T21:26:00.0000000Z\tC:\\host\\{RUN}\\work\\gpu_only_f16.n64.r0.a0.result.json",
    ]
    listing.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return listing


def _log(tmp_path: Path, text: str = "BOOT_COMPLETE\n") -> Path:
    path = tmp_path / "t2s-boot1.log"
    path.write_text(text, encoding="utf-8")
    return path


def test_launcher_boot_end_stamp_seals_plan_and_summary(tmp_path: Path) -> None:
    source = _stamped_tree(tmp_path)
    sealed = reconstruct_from_host_manifest(
        source,
        _listing(tmp_path, "2026-10-03T22:09:09.1195123Z"),
        launch_log=_log(tmp_path),
        boot_complete_utc=datetime.fromisoformat("2026-10-03T22:09:09.1332033Z"),
        boot_complete_source="last stamp write before BOOT_COMPLETE",
    )
    assert sealed is not None
    assert verify_seal(sealed) == "MATCH"
    marker = json.loads((sealed / ".sealed").read_text(encoding="utf-8"))
    rule = marker["launcher_boot_end_stamp"]
    assert rule["rule"] == "launcher boot-end stamp"
    assert rule["gate_reference"] == "BOOT_COMPLETE"
    assert rule["launch_log_shows"] == "BOOT_COMPLETE"
    assert rule["measured_fields_match"]["mismatches"] == 0


def test_boot_end_stamp_refuses_when_a_measured_field_differs(tmp_path: Path) -> None:
    source = _stamped_tree(tmp_path)
    summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    summary["arm_results"][0]["repeats"][0]["prefill_s"] = 9.0
    (source / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(SystemExit, match="measured fields differ"):
        reconstruct_from_host_manifest(
            source,
            _listing(tmp_path, "2026-10-03T22:09:09.1195123Z"),
            launch_log=_log(tmp_path),
            boot_complete_utc=datetime.fromisoformat("2026-10-03T22:09:09.1332033Z"),
        )
    assert not (tmp_path / f"sealed_{RUN}").exists()


def test_boot_end_stamp_refuses_a_late_file_that_is_not_plan_or_summary(tmp_path: Path) -> None:
    source = _stamped_tree(tmp_path)
    listing = _listing(tmp_path, "2026-10-03T22:09:09.1195123Z")
    listing.write_text(
        listing.read_text(encoding="utf-8").replace(
            "2026-10-03T21:26:00.0000000Z\tC:\\host\\" + RUN + "\\probes.ndjson",
            "2026-10-03T22:09:09.1195123Z\tC:\\host\\" + RUN + "\\probes.ndjson",
        ),
        encoding="utf-8",
    )
    assert (
        reconstruct_from_host_manifest(
            source,
            listing,
            launch_log=_log(tmp_path),
            boot_complete_utc=datetime.fromisoformat("2026-10-03T22:09:09.1332033Z"),
        )
        is None
    )
    assert not (tmp_path / f"sealed_{RUN}").exists()


def test_boot_end_stamp_requires_boot_complete_in_the_launch_log(tmp_path: Path) -> None:
    source = _stamped_tree(tmp_path)
    assert (
        reconstruct_from_host_manifest(
            source,
            _listing(tmp_path, "2026-10-03T22:09:09.1195123Z"),
            launch_log=_log(tmp_path, "cell finished\n"),
            boot_complete_utc=datetime.fromisoformat("2026-10-03T22:09:09.1332033Z"),
        )
        is None
    )
    assert not (tmp_path / f"sealed_{RUN}").exists()
