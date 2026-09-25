"""local_only is a selectable arm and never escalates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_h1_hybrid import (  # noqa: E402
    INTERLEAVE_SELECTABLE,
    StubCloudBackend,
    StubLocalBackend,
    decide_local_only,
    run_interleaved_session,
)


def test_decide_local_only_never_escalates() -> None:
    assert decide_local_only() == (False, None)
    assert "local_only" in INTERLEAVE_SELECTABLE


def test_local_only_stays_local_when_slo_and_emission_would_escalate(tmp_path: Path) -> None:
    entry = {"id": "slow", "question": [[]], "n_user_turns": 1}
    script = {
        "slow": [
            {
                "n_ctx": 100,
                "ttft_s": 50.0,
                "decode_tok_s": 1.0,
                "emitted_parseable_tool_call": False,
                "turn_wall_s": 0.05,
                "t_generate": 0.03,
                "t_tokenize": 0.005,
                "t_template_build": 0.005,
                "t_tool_exec": 0.005,
            }
        ]
    }
    local = StubLocalBackend(script=script)
    cloud = StubCloudBackend(tokens_in=1000, tokens_out=200)
    out = tmp_path / "local-only"
    summary = run_interleaved_session(
        entries=[entry],
        out_dir=out,
        local=local,
        cloud=cloud,
        policies=("local_only",),
        policy_caps_usd={"local_only": 5.0},
        session_max_usd=5.0,
        run_id="local-only-1",
        skip_entry_assert=True,
        seal=False,
    )
    assert summary["status"] == "complete"
    assert summary["running_usd_session"] == 0.0
    ledger = json.loads(
        (out / "policies" / "local_only" / "turn_ledger.json").read_text(encoding="utf-8")
    )
    turns = ledger["entries"][0]["turns"]
    assert turns
    assert all(t["placement"] == "local" for t in turns)
    assert all(t["escalated"] is False for t in turns)
