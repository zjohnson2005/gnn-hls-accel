"""RESIDENT turn-0 TTFT must stay at least 0.40x the first arm. Fail the entry, keep going."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.h1_provenance import (  # noqa: E402
    TTFT_COLD_FRACTION,
    prefix_cache_control_failure,
)
from tools.run_h1_hybrid import (  # noqa: E402
    INTERLEAVE_POLICIES,
    StubCloudBackend,
    StubLocalBackend,
    run_interleaved_session,
)

FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_3entries.json"


def test_control_threshold_is_point_four() -> None:
    assert TTFT_COLD_FRACTION == 0.40
    ok = prefix_cache_control_failure([("a", 2.0), ("b", 0.80)])
    assert ok is None
    bad = prefix_cache_control_failure([("a", 2.0), ("b", 0.79)])
    assert bad is not None
    assert bad["below"][0]["policy"] == "b"
    skipped = prefix_cache_control_failure([("cloud", None), ("a", 2.0), ("b", 0.5)])
    assert skipped is not None
    assert skipped["reference_policy"] == "a"


def test_resident_fast_later_arm_fails_entry_and_session_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def fast_later(_rows: list, _entry_id: str) -> float:
        calls["n"] += 1
        if calls["n"] % 3 == 1:
            return 2.0
        return 0.2

    monkeypatch.setattr("tools.h1_provenance.entry_turn0_local_ttft", fast_later)
    fix = json.loads(FIXTURE.read_text(encoding="utf-8"))
    local = StubLocalBackend(script=fix["local_script"])
    local.residency = "RESIDENT"  # type: ignore[attr-defined]
    cloud = StubCloudBackend(
        tokens_in=fix["cloud_tokens_in"],
        tokens_out=fix["cloud_tokens_out"],
    )
    out = tmp_path / "ctrl"
    summary = run_interleaved_session(
        entries=fix["entries"],
        out_dir=out,
        local=local,
        cloud=cloud,
        policy_caps_usd=dict.fromkeys(INTERLEAVE_POLICIES, 100.0),
        session_max_usd=1000.0,
        run_id="ctrl-1",
        skip_entry_assert=True,
        seal=False,
    )
    assert summary["status"] == "complete"
    assert summary["prefix_cache_control_failures"] == len(fix["entries"])
    assert {row["entry_id"] for row in summary["prefix_cache_control"]} == {
        e["id"] for e in fix["entries"]
    }
