"""--entry-offset / --entry-count chunking for one boot (H1-CPU)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_h1_hybrid import (  # noqa: E402
    StubCloudBackend,
    StubLocalBackend,
    build_argparser,
    run_interleaved_session,
    slice_entries,
)

PIN = {"sha256": "abc", "name": "X", "n": 5}
ENTRIES = [{"id": f"e{i}"} for i in range(5)]


def test_no_flags_is_the_full_set() -> None:
    entries, pin = slice_entries(ENTRIES, PIN, offset=None, count=None)
    assert entries == ENTRIES and pin == PIN


def test_chunk_slices_and_records() -> None:
    entries, pin = slice_entries(ENTRIES, PIN, offset=1, count=3)
    assert [e["id"] for e in entries] == ["e1", "e2", "e3"]
    assert pin["chunk"] == {"offset": 1, "count": 3, "first_entry_id": "e1", "last_entry_id": "e3"}
    assert pin["sha256"] == "abc" and "chunk" not in PIN
    tail, pin2 = slice_entries(ENTRIES, PIN, offset=3, count=None)
    assert [e["id"] for e in tail] == ["e3", "e4"] and pin2["chunk"]["count"] == 2


@pytest.mark.parametrize(("offset", "count"), [(-1, 2), (0, 0), (4, 2), (5, None)])
def test_out_of_range_chunk_is_refused(offset: int, count: int | None) -> None:
    with pytest.raises(SystemExit, match="outside the pinned set"):
        slice_entries(ENTRIES, PIN, offset=offset, count=count)


def test_cli_flags() -> None:
    args = build_argparser().parse_args(["--policy", "slo_escalate"])
    assert args.entry_offset is None and args.entry_count is None
    args = build_argparser().parse_args(
        ["--policy", "slo_escalate", "--entry-offset", "67", "--entry-count", "67"]
    )
    assert (args.entry_offset, args.entry_count) == (67, 67)


def test_plan_records_the_chunk(tmp_path: Path) -> None:
    row = {
        "n_ctx": 100,
        "ttft_s": 0.5,
        "decode_tok_s": 30.0,
        "emitted_parseable_tool_call": True,
        "turn_wall_s": 0.05,
        "t_generate": 0.03,
        "t_tokenize": 0.005,
        "t_template_build": 0.005,
        "t_tool_exec": 0.005,
    }
    full = [{"id": f"e{i}", "question": [[]], "n_user_turns": 1} for i in range(4)]
    chunk, pin = slice_entries(full, PIN, offset=2, count=2)
    out = tmp_path / "chunk"
    run_interleaved_session(
        entries=chunk,
        out_dir=out,
        local=StubLocalBackend(script={e["id"]: [row] for e in full}),
        cloud=StubCloudBackend(tokens_in=1, tokens_out=1),
        policies=("local_only",),
        policy_caps_usd={"local_only": 1.0},
        session_max_usd=1.0,
        run_id="chunk",
        skip_entry_assert=True,
        seal=False,
        entry_pin=pin,
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["entry_pin"]["chunk"]["first_entry_id"] == "e2"
    assert plan["n_entries"] == 2


def test_launcher_passes_the_chunk() -> None:
    text = (ROOT / "tools" / "launch_h1.ps1").read_text(encoding="ascii")
    assert "' --entry-offset ' + $EntryOffset" in text
    assert "' --entry-count ' + $EntryCount" in text


# ---------------------------------------------------------------- H1-CPU amendment 2

AMEND_2 = ROOT / "derived" / "h1_hybrid" / "H1_CPU_AMEND_2.json"


def test_amendment_2_boots_cover_the_entry_sets_and_caps_add_up() -> None:
    doc = json.loads(AMEND_2.read_text(encoding="ascii"))
    assert doc["runner_must_not_read_this_file"] is True and doc["does_not_edit_the_prereg"]
    design = doc["design"]
    slo = design["slo_escalate"]["boots"]
    assert [(b["entry_offset"], b["entry_count"]) for b in slo] == [(0, 67), (67, 67), (134, 66)]
    sub = design["subset_arms"]["boots"]
    assert [(b["entry_offset"], b["entry_count"]) for b in sub] == [(0, 15), (15, 15)]
    assert design["total_boots"] == 5
    caps = doc["caps_usd"]
    assert caps["session"] == 77.03 == round(caps["slo_escalate"] + 3 + 2 + 0, 2)
    per = doc["per_boot_caps_usd"]
    assert round(sum(per[f"boot{i}"]["slo_escalate"] for i in (1, 2, 3)), 2) == 72.03
    assert round(per["boot4"]["emission_escalate"] + per["boot5"]["emission_escalate"], 2) == 3
    assert (
        round(per["boot4"]["full_signal_bounceback"] + per["boot5"]["full_signal_bounceback"], 2)
        == 2
    )
    for pred in ("emission_escalate", "full_signal_bounceback"):
        assert doc["predictions"][pred]["holds_if"] == "at least 24/30 entries agree"


def test_runner_and_launcher_never_open_amendment_2(monkeypatch, tmp_path: Path) -> None:
    for rel in ("tools/run_h1_hybrid.py", "tools/launch_h1.ps1"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "H1_CPU_AMEND" not in text and "H1_CPU_PREREG" not in text, rel
    import builtins
    import io

    real_open = builtins.open

    def guarded(file, *args, **kwargs):
        if "H1_CPU_AMEND" in str(file) or "H1_CPU_PREREG" in str(file):
            raise AssertionError(f"runner opened {file}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded)
    monkeypatch.setattr(io, "open", guarded)
    test_plan_records_the_chunk(tmp_path)


def test_launcher_interleaved_caps_and_local_only() -> None:
    text = (ROOT / "tools" / "launch_h1.ps1").read_text(encoding="ascii")
    assert '"local_only"             = 0.0' in text
    assert '"cloud_only", "local_only")' in text
    assert '[string]$PolicyCapUsd = ""' in text
    assert "$DefaultPolicyCapUsd[$capName] = $capValue" in text
    assert "-PolicyCapUsd requires -Interleaved" in text
