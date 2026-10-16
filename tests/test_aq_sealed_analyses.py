"""tools/aq_sealed_analyses.py: classification and the exact random baseline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import aq_sealed_analyses as aq  # noqa: E402


def _turn(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "placement": "local",
        "escalated": False,
        "emitted_parseable_tool_call": True,
        "tool_exec_error": False,
        "turn": 0,
    }
    base.update(kw)
    return base


def test_classify_local() -> None:
    ok = {"turns": [_turn()], "local_pass": True, "stop_reason": "completed"}
    silent = {"turns": [_turn()], "local_pass": False, "stop_reason": "completed"}
    loud = {"turns": [_turn(emitted_parseable_tool_call=False)], "local_pass": False}
    budget = {"turns": [_turn()], "local_pass": False, "stop_reason": "max_steps"}
    esc = {"turns": [_turn(placement="cloud", escalated=True)], "local_pass": False}
    assert [aq.classify_local(e) for e in (ok, silent, loud, budget, esc)] == [
        "pass",
        "silent",
        "loud",
        "loud",
        "escalated",
    ]


def test_cause_bucket() -> None:
    assert aq.cause_bucket("ttft>10.0") == "step0_ttft"
    assert aq.cause_bucket("decode<6") == "decode"
    assert aq.cause_bucket(None) == "none"


def test_random_baseline_exact() -> None:
    # 2 entries: one passes only locally, one only on the cloud.
    rows = [(True, False, 0.0), (False, True, 1.0)]
    r = aq._random_baseline(rows, 1)
    assert r["expected_passes"] == 1.0
    assert r["expected_usd_per_task"] == 0.25
    assert aq._random_baseline(rows, 0)["expected_passes"] == 1.0
    assert aq._random_baseline(rows, 2)["passes_95pct_interval"] == [1, 1]
