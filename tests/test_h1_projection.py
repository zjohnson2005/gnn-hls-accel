"""After 20 entries, stop the session when the linear projection exceeds the cap."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.h1_provenance import PROJECTION_MIN_ENTRIES, project_session_cost  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    StubCloudBackend,
    StubLocalBackend,
    cloud_usd,
    run_interleaved_session,
)


def test_projection_stays_quiet_before_twenty_entries() -> None:
    assert PROJECTION_MIN_ENTRIES == 20
    assert project_session_cost(running_usd=10.0, n_done=19, n_planned=40) is None
    assert project_session_cost(running_usd=10.0, n_done=40, n_planned=40) is None
    assert project_session_cost(running_usd=10.0, n_done=20, n_planned=40) == 20.0


def test_projection_stops_without_crashing(tmp_path: Path) -> None:
    per = cloud_usd(1000, 200)
    n_planned = 25
    cap = 22.0 * per
    assert 20.0 * per <= cap < 25.0 * per
    script = {
        f"e{i}": [
            {
                "n_ctx": 100,
                "ttft_s": 50.0,
                "decode_tok_s": 1.0,
                "emitted_parseable_tool_call": True,
                "turn_wall_s": 0.01,
                "t_generate": 0.004,
                "t_tokenize": 0.002,
                "t_template_build": 0.002,
                "t_tool_exec": 0.002,
            }
        ]
        for i in range(n_planned)
    }
    entries = [{"id": f"e{i}", "question": [[]], "n_user_turns": 1} for i in range(n_planned)]
    summary = run_interleaved_session(
        entries=entries,
        out_dir=tmp_path / "proj",
        local=StubLocalBackend(script=script),
        cloud=StubCloudBackend(tokens_in=1000, tokens_out=200),
        policies=("slo_escalate",),
        policy_caps_usd={"slo_escalate": 100.0},
        session_max_usd=cap,
        run_id="proj-1",
        skip_entry_assert=True,
        seal=False,
    )
    assert summary["status"] == "aborted_projection"
    assert summary["policies"]["slo_escalate"]["n_entries_completed"] == 20
    assert "projection" in (summary["abort_reason"] or "")
