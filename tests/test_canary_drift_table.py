"""Task AA canary table: reproducible from committed records; refs match the gates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import canary_drift_table as cdt  # noqa: E402

TABLE = ROOT / "analysis" / "canary" / "CANARY_DRIFT_20261014.json"


def _by_session() -> dict[str, dict]:
    return {s["session"]: s for s in cdt.table()["sessions"]}


def test_table_matches_committed_file() -> None:
    assert cdt.table() == json.loads(TABLE.read_text(encoding="utf-8"))


def test_refs_match_recorded_trip_details() -> None:
    s = _by_session()
    assert round(s["NPU-INT8 2048a 0fd9cd8c"]["ref_t1"], 9) == 1.089581542
    assert round(s["NPU-INT8 2048c 4f6a9102"]["ref_t2"], 9) == 0.497527099
    assert round(s["P1 A4 B=10 [53:100] eb6cd6ce"]["ref_t1"], 9) == 2.500856445


def test_trips_are_the_three_refusals() -> None:
    trips = {k for k, v in _by_session().items() if v["trip"]}
    assert trips == {
        "NPU-INT8 2048a 0fd9cd8c",
        "NPU-INT8 2048c 4f6a9102",
        "P1 A4 B=10 [53:100] eb6cd6ce",
    }


def test_first_checked_npu_canary_is_faster_on_t1() -> None:
    s = _by_session()
    for key in (
        "NPU-INT8 1024 1e79daa3",
        "NPU-INT8 2048a 0fd9cd8c",
        "NPU-INT8 4096 63d35555",
        "NPU-INT8 2048c 4f6a9102",
    ):
        assert -0.124 < s[key]["first_checked"]["t1_signed"] < -0.069
