"""Hybrid trajectory scoring: merged local+cloud decode, both scopes."""

from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.bfcl_feasibility_probe import (  # noqa: E402
    decode_execute_anthropic,
    gold_decoded_for_entry,
    select_multi_turn_entries,
)
from tools.run_h1_hybrid import (  # noqa: E402
    CostGuard,
    StubCloudBackend,
    StubLocalBackend,
    merged_decoded_steps,
    run_hybrid_entry,
)

CLOUD_REPORT = ROOT / "derived" / "bfcl_feasibility" / "cloud_multi_turn_report.json"


def _row(
    *,
    emitted: bool,
    decoded: list[list[str]] | None,
    raw: str = "",
) -> dict[str, Any]:
    return {
        "n_ctx": 400,
        "ttft_s": 1.0,
        "decode_tok_s": 12.0,
        "emitted_parseable_tool_call": emitted,
        "n_steps": 1 if emitted else 0,
        "tool_exec_error": False,
        "turn_wall_s": 0.05,
        "t_generate": 0.03,
        "t_tokenize": 0.005,
        "t_template_build": 0.005,
        "t_tool_exec": 0.005,
        "raw_text": raw,
        "decoded_steps": decoded,
    }


def _tool_uses(calls: list[str]) -> list[dict[str, Any]]:
    """Test-only inverse of an execute string into Anthropic tool_use blocks."""
    blocks: list[dict[str, Any]] = []
    for call in calls:
        node = ast.parse(call, mode="eval").body
        assert isinstance(node, ast.Call) and isinstance(node.func, ast.Name), f"not a call: {call}"
        assert not node.args, f"positional arg would not round-trip: {call}"
        inp = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
        blocks.append({"type": "tool_use", "name": node.func.id, "input": inp})
    return blocks


def _three_turn_entry() -> tuple[dict[str, Any], list[list[list[str]]]]:
    """First BFCL entry whose first three gold turns are kwargs-only calls."""
    for entry in select_multi_turn_entries():
        gold = gold_decoded_for_entry(entry)
        if len(gold) < 3:
            continue
        prefix = gold[:3]
        try:
            for turn in prefix:
                flat = [c for step in turn for c in step]
                blocks = _tool_uses(flat)
                assert decode_execute_anthropic(blocks) == flat
        except (AssertionError, SyntaxError, ValueError):
            continue
        sliced = copy.deepcopy(entry)
        sliced["question"] = list(entry["question"])[:3]
        sliced["reference"] = list(entry["reference"])[:3]
        raw = copy.deepcopy(entry["raw_entry"])
        raw["question"] = list(raw.get("question") or entry["question"])[:3]
        sliced["raw_entry"] = raw
        return sliced, prefix
    raise AssertionError("no 3-turn kwargs-only BFCL entry")


def _flatten(decoded: list[list[list[str]]]) -> list[str]:
    return [c for turn in decoded for step in turn for c in step]


def test_bounce_merges_cloud_turn1_with_later_local_turns() -> None:
    """Local fails turn 1; cloud solves it; local completes turns 2 and 3."""
    entry, gold = _three_turn_entry()
    eid = str(entry["id"])
    failed = [["not_a_real_call()"]]
    local = StubLocalBackend(
        script={
            eid: [
                _row(emitted=False, decoded=failed, raw="[local_fail_turn_1]"),
                _row(emitted=True, decoded=gold[1], raw="[local_turn_2]"),
                _row(emitted=True, decoded=gold[2], raw="[local_turn_3]"),
            ]
        }
    )
    cloud = StubCloudBackend(
        tokens_in=100,
        tokens_out=20,
        tool_use_by_turn={0: _tool_uses([c for step in gold[0] for c in step])},
    )
    er = run_hybrid_entry(
        entry,
        policy="full_signal_bounceback",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert er.turns_executed == 3
    assert er.turns[0].placement == "cloud"
    assert er.turns[1].placement == "local"
    assert er.turns[2].placement == "local"
    merged = merged_decoded_steps(er)
    assert len(merged) == 3
    flat = _flatten(merged)
    for call in _flatten(gold):
        assert call in flat
    assert "not_a_real_call()" not in flat
    q = er.as_quality_dict()
    assert q["hybrid_quality_scope"] == "hybrid"
    assert q["local_quality_scope"] == "local_probe"
    assert q["quality_scope"] == "local_probe"
    assert q["hybrid_pass"] is True
    assert q["hybrid_model_result_decoded"] == merged
    assert q["local_pass"] is False
    assert q["trajectory_pass"] is False
    assert q["trajectory_pass"] is not q["hybrid_pass"]


def test_emission_escalate_keeps_cloud_turns() -> None:
    """After the first escalation every remaining turn is cloud decode."""
    entry, gold = _three_turn_entry()
    eid = str(entry["id"])
    local = StubLocalBackend(
        script={
            eid: [
                _row(emitted=False, decoded=[["not_a_real_call()"]], raw="[no_emit]"),
                _row(emitted=True, decoded=[[]], raw="[unused_local]"),
                _row(emitted=True, decoded=[[]], raw="[unused_local]"),
            ]
        }
    )
    cloud = StubCloudBackend(
        tokens_in=80,
        tokens_out=16,
        tool_use_by_turn={i: _tool_uses([c for step in gold[i] for c in step]) for i in range(3)},
    )
    er = run_hybrid_entry(
        entry,
        policy="emission_escalate",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert er.turns_executed == 3
    assert all(t.placement == "cloud" for t in er.turns)
    merged = merged_decoded_steps(er)
    flat = _flatten(merged)
    for call in _flatten(gold):
        assert call in flat
    assert "not_a_real_call()" not in flat
    q = er.as_quality_dict()
    assert q["hybrid_quality_scope"] == "hybrid"
    assert q["hybrid_pass"] is True
    assert q["local_pass"] is False
    assert q["local_quality_scope"] == "local_probe"


def test_slo_all_local_merge_still_scores() -> None:
    entry, gold = _three_turn_entry()
    eid = str(entry["id"])
    local = StubLocalBackend(script={eid: [_row(emitted=True, decoded=gold[i]) for i in range(3)]})
    cloud = StubCloudBackend(tokens_in=10, tokens_out=2)
    er = run_hybrid_entry(
        entry,
        policy="slo_escalate",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert all(t.placement == "local" for t in er.turns)
    assert er.cloud_usd_entry == 0.0
    q = er.as_quality_dict()
    assert q["hybrid_quality_scope"] == "hybrid"
    assert q["hybrid_pass"] is True
    assert q["local_pass"] is True
    assert q["local_quality_scope"] == "local_probe"
    assert q["quality_scope"] == "local_probe"
    assert q["hybrid_model_result_decoded"] == gold


def test_sealed_cloud_report_conversion_matches_original_strings() -> None:
    """decode_execute_anthropic on sealed raw heads matches model_result_decoded."""
    if not CLOUD_REPORT.is_file():
        pytest.fail(f"sealed cloud report missing: {CLOUD_REPORT}")
    report = json.loads(CLOUD_REPORT.read_text(encoding="utf-8"))
    full = report["cloud_arm"]["per_entry_full"]
    entry = next(e for e in full if e["id"] == "multi_turn_base_0")
    decoded = entry["model_result_decoded"]
    heads = entry["model_result_raw_heads"]
    matched = 0
    for turn_idx, turn_heads in enumerate(heads):
        turn_calls = [c for step in decoded[turn_idx] for c in step]
        for head in turn_heads:
            text = str(head).strip()
            if not text.startswith("["):
                continue
            try:
                blocks = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(blocks, list) or not blocks:
                continue
            if not all(isinstance(b, dict) and "name" in b for b in blocks):
                continue
            produced = decode_execute_anthropic(blocks)
            for call in produced:
                assert (
                    call in turn_calls
                ), f"turn {turn_idx}: {call!r} not in original decoded {turn_calls}"
            matched += len(produced)
    assert matched > 0, "sealed report exposed no convertible tool-use heads"
