"""Resume past a recorded hang (Task AY): --skip-entries / --skip-hang-record, and the
P10-HANG123 isolation scheduler flags (--sched-exploratory, --sched-dynamic-split-fuse)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.genai_runtime import SIZE_MAX_U64, build_runtime_options  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    StubCloudBackend,
    StubLocalBackend,
    build_argparser,
    load_skip_hangs,
    main,
    run_interleaved_session,
)


def _turn() -> dict[str, Any]:
    return {
        "n_ctx": 100,
        "ttft_s": 0.5,
        "decode_tok_s": 20.0,
        "emitted_parseable_tool_call": True,
        "turn_wall_s": 0.01,
        "t_generate": 0.004,
        "t_tokenize": 0.002,
        "t_template_build": 0.002,
        "t_tool_exec": 0.002,
    }


class _Recording(StubLocalBackend):
    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.ran: list[str] = []

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> Any:
        self.ran.append(str(entry["id"]))
        return super().run_turn(entry, turn_idx, model=model)


def _entries(n: int = 3) -> list[dict[str, Any]]:
    return [{"id": f"e{i}", "question": [[]], "n_user_turns": 1} for i in range(n)]


def _record(tmp: Path, entry_id: str = "e1", outcome: str = "hang") -> Path:
    path = tmp / "hang_events.json"
    path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "run_id": "src-run",
                        "entry_id": entry_id,
                        "policy": "local_only",
                        "turn": 0,
                        "elapsed_s": 1800.453,
                        "limit_s": 1800.0,
                        "fired_utc": "2026-10-20T19:57:27+00:00",
                        "outcome": outcome,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _session(out: Path, local: Any, skip: dict[str, Any] | None) -> dict[str, Any]:
    return run_interleaved_session(
        entries=_entries(),
        out_dir=out,
        local=local,
        cloud=StubCloudBackend(tokens_in=1000, tokens_out=200),
        policies=("local_only",),
        policy_caps_usd={"local_only": 0.0},
        session_max_usd=1.0,
        run_id="skip-1",
        skip_entry_assert=True,
        seal=False,
        skip_hangs=skip,
    )


def test_load_skip_hangs_off_and_record(tmp_path: Path) -> None:
    assert load_skip_hangs(None, None, _entries()) is None
    rec = _record(tmp_path)
    doc = load_skip_hangs("e1", rec, _entries(), root=tmp_path)
    assert doc is not None
    assert doc["entries"]["e1"]["source_run_id"] == "src-run"
    assert doc["entries"]["e1"]["turn"] == 0
    assert doc["hang_record"]["path"] == "hang_events.json"
    assert doc["hang_record"]["sha256"] == hashlib.sha256(rec.read_bytes()).hexdigest()


def test_load_skip_hangs_refusals(tmp_path: Path) -> None:
    rec = _record(tmp_path)
    with pytest.raises(SystemExit, match="go together"):
        load_skip_hangs("e1", None, _entries())
    with pytest.raises(SystemExit, match="go together"):
        load_skip_hangs(None, rec, _entries())
    with pytest.raises(SystemExit, match="not in this run's entry set"):
        load_skip_hangs("e9", rec, _entries())
    with pytest.raises(SystemExit, match="distinct"):
        load_skip_hangs("e1,e1", rec, _entries())
    with pytest.raises(SystemExit, match="no recorded hang for e2"):
        load_skip_hangs("e2", rec, _entries())
    other = tmp_path / "o"
    other.mkdir()
    with pytest.raises(SystemExit, match="no recorded hang"):
        load_skip_hangs("e1", _record(other, outcome="complete"), _entries())
    with pytest.raises(SystemExit, match="not found"):
        load_skip_hangs("e1", tmp_path / "missing.json", _entries())


def test_session_counts_skipped_hang_as_local_fail(tmp_path: Path) -> None:
    skip = load_skip_hangs("e1", _record(tmp_path), _entries(), root=tmp_path)
    script = {f"e{i}": [_turn()] for i in range(3)}
    local = _Recording(script=script)
    out = tmp_path / "run"
    summary = _session(out, local, skip)
    assert "e1" not in local.ran and {"e0", "e2"} <= set(local.ran)
    plan = json.loads((out / "plan.json").read_text())
    assert plan["skip_entries"]["entries"]["e1"]["source_run_id"] == "src-run"
    pol = out / "policies" / "local_only"
    quality = json.loads((pol / "entry_quality.json").read_text())["entries"]
    row = next(q for q in quality if q["entry_id"] == "e1")
    assert row["outcome"] == "hang" and row["status"] == "skipped_hang"
    assert row["local_pass"] is False and row["hybrid_pass"] is False
    psum = json.loads((pol / "summary.json").read_text())
    assert psum["status"] == "complete"
    assert psum["n_entries_planned"] == 3
    assert psum["n_entries_completed"] == 2
    assert psum["n_entries_skipped_hang"] == 1
    # Stub entries carry no score; the hang row is a scored local fail.
    assert psum["quality"]["local_probe"]["n_entries_with_score"] == 1
    assert psum["quality"]["local_probe"]["n_local_pass"] == 0
    assert summary["status"] == "complete"
    assert summary["policies"]["local_only"]["n_entries_skipped_hang"] == 1
    ckpt = json.loads((pol / "checkpoint.json").read_text())
    assert ckpt["skipped_hang_entry_ids"] == ["e1"]
    cells = json.loads((out / "checkpoint.json").read_text())["cell_log"]
    assert [c["status"] for c in cells if c["entry_id"] == "e1"] == ["skipped_hang"]
    # Resume: nothing re-run, no duplicate row.
    again = _Recording(script=script)
    _session(out, again, skip)
    assert again.ran == []
    quality = json.loads((pol / "entry_quality.json").read_text())["entries"]
    assert [q["entry_id"] for q in quality].count("e1") == 1


def test_default_off_unchanged(tmp_path: Path) -> None:
    out = tmp_path / "run"
    _session(out, _Recording(script={f"e{i}": [_turn()] for i in range(3)}), None)
    plan = json.loads((out / "plan.json").read_text())
    assert "skip_entries" not in plan
    pol = out / "policies" / "local_only"
    assert "skipped_hang_entry_ids" not in json.loads((pol / "checkpoint.json").read_text())
    psum = json.loads((pol / "summary.json").read_text())
    assert "n_entries_skipped_hang" not in psum and psum["n_entries_completed"] == 3


def test_cli_defaults_and_non_interleaved_refusal(tmp_path: Path) -> None:
    args = build_argparser().parse_args(["--out", str(tmp_path)])
    assert args.skip_entries is None and args.skip_hang_record is None
    assert args.sched_exploratory is False and args.sched_dynamic_split_fuse is None
    with pytest.raises(SystemExit, match="interleaved only"):
        main(
            [
                "--out",
                str(tmp_path),
                "--allow-dirty",
                "--policy",
                "slo_escalate",
                "--skip-entries",
                "e1",
            ]
        )


def _opts(**kw: Any) -> dict[str, Any] | None:
    base: dict[str, Any] = {"residency": "RESIDENT", "kv": "default", "placement": "gpu_only"}
    return build_runtime_options(**{**base, **kw})


def test_exploratory_scheduler_isolation_options() -> None:
    with pytest.raises(ValueError, match="not RESIDENT"):
        _opts(sched_prefix_caching="off", sched_max_batched_tokens=SIZE_MAX_U64)
    o = _opts(
        sched_prefix_caching="off",
        sched_max_batched_tokens=SIZE_MAX_U64,
        sched_exploratory=True,
    )
    assert o is not None and o["sched_exploratory"] is True
    assert o["scheduler_overrides"] == {
        "enable_prefix_caching": False,
        "max_num_batched_tokens": SIZE_MAX_U64,
    }
    o = _opts(
        sched_prefix_caching="on",
        sched_max_batched_tokens=SIZE_MAX_U64,
        sched_dynamic_split_fuse="off",
        sched_exploratory=True,
    )
    assert o is not None
    assert o["scheduler_overrides"]["dynamic_split_fuse"] is False
    with pytest.raises(ValueError, match="needs an explicit SchedulerConfig"):
        _opts(sched_exploratory=True)
    with pytest.raises(ValueError, match="pass both"):
        _opts(sched_dynamic_split_fuse="off")
    o = _opts(sched_prefix_caching="on", sched_max_batched_tokens=4096)
    assert o is not None and "sched_exploratory" not in o
    assert "dynamic_split_fuse" not in o["scheduler_overrides"]


def test_launcher_passthrough_lines() -> None:
    text = (ROOT / "tools" / "launch_h1.ps1").read_text(encoding="utf-8")
    assert '[string]$SkipEntries = ""' in text and '[string]$SkipHangRecord = ""' in text
    assert "$resolvedCmd + ' --skip-entries ' + $SkipEntries" in text
    assert "$resolvedCmd + ' --skip-hang-record \"' + $skipRec + '\"'" in text
    assert "$resolvedCmd + ' --sched-dynamic-split-fuse ' + $SchedDynamicSplitFuse" in text
    assert "if ($SchedExploratory) { $resolvedCmd = $resolvedCmd + ' --sched-exploratory' }" in text
