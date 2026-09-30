"""Resident-limit search. The runner does not open the preregistration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.boot4_session import (  # noqa: E402
    RESIDENT_HIGH,
    RESIDENT_LOW,
    RESIDENT_RESOLUTION,
    bisect_holds,
    grid_mid,
)
from tools.ttft_slo_canary import estimate_bisect_planned_probes  # noqa: E402

PREREG = ROOT / "derived" / "delta_prefill" / "RESIDENT_LIMIT_PREREG.json"


def _holds_until(limit: int):
    def attempt(n: int) -> dict[str, object]:
        holds = n <= limit
        return {
            "n_cached": n,
            "holds": holds,
            "turn2_ttft_s": float(n) / 1000.0 if holds else None,
        }

    return attempt


def test_search_bounds_match_the_prereg_and_runners_do_not_read_it() -> None:
    doc = json.loads(PREREG.read_text(encoding="utf-8"))
    assert doc["runner_must_not_read_this_file"] is True
    assert doc["low"] == RESIDENT_LOW
    assert doc["high"] == RESIDENT_HIGH
    assert doc["resolution"] == RESIDENT_RESOLUTION
    for rel in (
        "tools/run_resident_limit.py",
        "tools/boot4_session.py",
        "tools/launch_boot1.ps1",
        "tools/launch_resident_limit.ps1",
    ):
        assert PREREG.name not in (ROOT / rel).read_text(encoding="utf-8")


def test_probe_upper_bound_is_eight() -> None:
    assert (
        estimate_bisect_planned_probes(
            n_arms=1,
            low=RESIDENT_LOW,
            high=RESIDENT_HIGH,
            resolution=RESIDENT_RESOLUTION,
            repeats=1,
        )
        == 8
    )


def test_bisect_stops_on_the_largest_passing_rung() -> None:
    found = bisect_holds(
        low=RESIDENT_LOW,
        high=RESIDENT_HIGH,
        resolution=RESIDENT_RESOLUTION,
        attempt=_holds_until(15500),
    )
    assert found["largest_n_cached"] == 15500
    assert found["first_fail_n_cached"] == 16000
    assert found["failure_in_range"] is True
    ns = [int(point["n_cached"]) for point in found["points"]]
    assert len(ns) == len(set(ns))
    assert all((n - RESIDENT_LOW) % RESIDENT_RESOLUTION == 0 for n in ns)
    assert found["passing_turn2_ttft_s"]["15500"] == 15.5
    assert "16000" not in found["passing_turn2_ttft_s"]


def test_high_that_holds_is_not_called_a_ceiling() -> None:
    found = bisect_holds(
        low=12000,
        high=30000,
        resolution=500,
        attempt=_holds_until(30000),
    )
    assert found["largest_n_cached"] == 30000
    assert found["failure_in_range"] is False
    assert len(found["points"]) == 2


def test_low_failure_records_no_passing_rung() -> None:
    found = bisect_holds(
        low=12000,
        high=30000,
        resolution=500,
        attempt=_holds_until(11999),
    )
    assert found["largest_n_cached"] is None
    assert len(found["points"]) == 1
    assert found["passing_turn2_ttft_s"] == {}


def test_grid_mid_stays_inside_the_open_interval() -> None:
    assert grid_mid(12000, 30000, 500) == 21000
    assert grid_mid(15500, 16000, 500) is None
