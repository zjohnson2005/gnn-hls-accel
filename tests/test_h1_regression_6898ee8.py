"""Regression guard for DEMO-2 build (task AI).

With no new flags, every existing policy must produce exactly the ledgers it
produced at 6898ee8. The fixture was generated from the 6898ee8 code before
any DEMO-2 change; this test re-runs the same stub corpus and compares the
serialized EntryResult ledgers (as_ledger_dict) byte for byte (as JSON).

Regenerate only on purpose:
  python -c "from tests.test_h1_regression_6898ee8 import write_fixture; write_fixture()"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_h1_hybrid import (  # noqa: E402
    CostGuard,
    StubCloudBackend,
    StubLocalBackend,
    run_hybrid_entry,
)

FIXTURE = ROOT / "tests" / "fixtures" / "h1_regression_6898ee8.json"
POLICIES = (
    "cloud_only",
    "agnostic_default",
    "local_only",
    "slo_escalate",
    "emission_escalate",
    "full_signal_bounceback",
)


def _row(**kw: Any) -> dict[str, Any]:
    row = {
        "n_ctx": 400,
        "ttft_s": 1.0,
        "decode_tok_s": 12.0,
        "emitted_parseable_tool_call": True,
        "turn_wall_s": 0.05,
        "t_generate": 0.03,
        "t_tokenize": 0.005,
        "t_template_build": 0.005,
        "t_tool_exec": 0.005,
    }
    row.update(kw)
    return row


# entry id -> (n turns in entry, script rows, stop_reason when short)
CORPUS: dict[str, tuple[int, list[dict[str, Any]], str | None]] = {
    "all_ok": (3, [_row(), _row(n_ctx=900), _row(n_ctx=1400)], None),
    "ttft_trip_t1": (3, [_row(), _row(ttft_s=12.5), _row()], None),
    "decode_trip_t0": (2, [_row(decode_tok_s=4.0), _row()], None),
    "no_parse_t1": (3, [_row(), _row(emitted_parseable_tool_call=False), _row()], None),
    "step_budget_t0": (2, [_row(n_steps=6), _row(n_steps=1)], None),
    "tool_err_t1": (
        3,
        [_row(), _row(tool_exec_error=True, tool_exec_error_class="KeyError"), _row()],
        None,
    ),
    "empty_exec_end": (3, [_row(), _row(emitted_parseable_tool_call=False)], "empty_execute"),
    "gen_err_end": (3, [_row(), _row(emitted_parseable_tool_call=False)], "generation_error"),
    "max_steps_end": (3, [_row(n_steps=21)], "max_steps"),
    "big_ctx": (2, [_row(n_ctx=30_000, ttft_s=9.0), _row(n_ctx=31_000, ttft_s=9.5)], None),
}


def _entry(eid: str, n: int, stop: str | None) -> dict[str, Any]:
    e: dict[str, Any] = {"id": eid, "question": [[] for _ in range(n)], "n_user_turns": n}
    if stop is not None:
        e["stop_reason"] = stop
    return e


def ledgers() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for policy in POLICIES:
        for eid, (n, rows, stop) in CORPUS.items():
            local = StubLocalBackend(
                script={eid: [dict(r) for r in rows]},
                stop_reasons={eid: stop} if stop else {},
            )
            cloud = StubCloudBackend(tokens_in=1000, tokens_out=200)
            er = run_hybrid_entry(
                _entry(eid, n, stop),
                policy=policy,
                local=local,
                cloud=cloud,
                cost=CostGuard(max_usd=100.0),
                model="stub-4B",
            )
            out[f"{policy}/{eid}"] = er.as_ledger_dict()
    return json.loads(json.dumps(out, sort_keys=True))


def write_fixture() -> None:
    FIXTURE.write_text(json.dumps(ledgers(), indent=1, sort_keys=True) + "\n", encoding="utf-8")


def test_existing_policies_unchanged_since_6898ee8() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    got = ledgers()
    assert set(got) == set(expected)
    for key in sorted(expected):
        assert got[key] == expected[key], key
