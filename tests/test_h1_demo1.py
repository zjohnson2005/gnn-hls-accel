"""DEMO-1 / H1-CPU tooling: entry subset pin, offline sizing, NON_RESIDENT, CPU placement."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.h1_context_sizing as sizing  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    ARM_CONFIG,
    DEMO1_LONGCTX_30_SHA256,
    KV_MATCH_SEAL_4B,
    W3_ENTRIES_SHA256,
    StubCloudBackend,
    StubLocalBackend,
    _sha256_file,
    arm_config_for,
    arm_id_for_h1,
    assert_entry_set_matches_w3,
    assert_entry_set_pinned,
    build_argparser,
    load_w3_entries,
    local_arm_settings,
    run_interleaved_session,
)

DEMO = ROOT / "derived" / "h1_hybrid" / "demo1"
SUBSET = DEMO / "DEMO1_LONGCTX_30.json"
META = DEMO / "DEMO1_LONGCTX_30.meta.json"
SIZING_LONG = DEMO / "SIZING_multi_turn_long_context.json"
SIZING_BASE = DEMO / "SIZING_multi_turn_base.json"
D482_SLO = (
    ROOT
    / "derived"
    / "h1_hybrid"
    / "interleaved_d482c621-4292-4281-b6a1-8635e5eeb6da"
    / "policies"
    / "slo_escalate"
    / "turn_ledger.json"
)
LAUNCH_H1 = ROOT / "tools" / "launch_h1.ps1"


# ---------------------------------------------------------------- subset pin


def test_subset_file_is_pinned_and_loads() -> None:
    assert _sha256_file(SUBSET) == DEMO1_LONGCTX_30_SHA256
    entries, path = load_w3_entries(SUBSET)
    assert path == SUBSET and len(entries) == 30
    assert {e["category"] for e in entries} == {"multi_turn_long_context"}
    assert {"raw_entry", "question", "reference", "tools_from_docs"} <= set(entries[0])
    pin = assert_entry_set_pinned(SUBSET)
    assert pin["name"] == "DEMO1_LONGCTX_30" and pin["n"] == 30 and pin["seed"] == 20260930


def test_w3_pin_is_still_accepted() -> None:
    """The W-3 pin is the CRLF host checkout; an LF checkout (this Mac) is refused."""
    w3 = (
        ROOT
        / "derived"
        / "bfcl_feasibility"
        / "w3_weight_quality"
        / "sealed_6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a"
        / "artifacts"
        / "multi_turn_probe_entries.json"
    )
    if _sha256_file(w3) != W3_ENTRIES_SHA256:
        pytest.skip("LF checkout of the W-3 entries file; the pin is the CRLF host form")
    entries, _ = load_w3_entries()
    assert len(entries) == 200
    assert assert_entry_set_pinned(w3)["name"] == "W3_multi_turn_base_200"


def test_unpinned_file_is_refused(tmp_path: Path) -> None:
    copy = tmp_path / "subset.json"
    shutil.copyfile(SUBSET, copy)
    copy.write_bytes(copy.read_bytes() + b" ")
    with pytest.raises(SystemExit, match="not a pinned entry set"):
        assert_entry_set_pinned(copy)


def test_w3_only_check_refuses_the_subset() -> None:
    with pytest.raises(SystemExit, match="W-3 pin"):
        assert_entry_set_matches_w3(SUBSET)


def test_subset_selection_reproduces_from_the_sizing_file() -> None:
    doc = json.loads(SIZING_LONG.read_text(encoding="utf-8"))
    eligible, selected = sizing.select_subset(doc)
    meta = json.loads(META.read_text(encoding="utf-8"))
    assert meta["eligible"] == eligible and meta["selected"] == selected
    assert meta["entries_sha256"] == DEMO1_LONGCTX_30_SHA256
    ids = [e["id"] for e in json.loads(SUBSET.read_text(encoding="utf-8"))]
    assert ids == selected
    assert len(eligible) == 40 and len(selected) == 30
    rows = {r["entry_id"]: r for r in doc["entries"]}
    assert all(any(t["n_ctx"] > 10_000 for t in rows[i]["turns"]) for i in selected)


def test_plan_records_the_entry_pin(tmp_path: Path) -> None:
    entry = {"id": "e0", "question": [[]], "n_user_turns": 1}
    script = {
        "e0": [
            {
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
        ]
    }
    pin = assert_entry_set_pinned(SUBSET)
    for name, kwargs, w3 in (
        ("subset", {"entry_pin": pin}, None),
        ("default", {}, W3_ENTRIES_SHA256),
    ):
        out = tmp_path / name
        run_interleaved_session(
            entries=[entry],
            out_dir=out,
            local=StubLocalBackend(script=script),
            cloud=StubCloudBackend(tokens_in=10, tokens_out=1),
            policies=("local_only",),
            policy_caps_usd={"local_only": 1.0},
            session_max_usd=1.0,
            run_id=name,
            skip_entry_assert=True,
            seal=False,
            **kwargs,
        )
        plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
        assert plan["w3_entry_pin"] == w3
        assert plan["entry_pin"]["sha256"] == (pin["sha256"] if w3 is None else W3_ENTRIES_SHA256)


# ---------------------------------------------------------------- offline sizing


def test_base_sizing_matches_the_sealed_turn0_exactly() -> None:
    gold = {
        r["entry_id"]: r for r in json.loads(SIZING_BASE.read_text(encoding="utf-8"))["entries"]
    }
    ledger = json.loads(D482_SLO.read_text(encoding="utf-8"))["entries"]
    turn0 = [(e["turns"][0]["n_ctx"], gold[e["entry_id"]]["turns"][0]["n_ctx"]) for e in ledger]
    assert len(turn0) == 200
    assert all(a == b for a, b in turn0)


def test_sizing_summaries_are_the_reported_numbers() -> None:
    base = json.loads(SIZING_BASE.read_text(encoding="utf-8"))["summary"]
    assert base["turn_n_ctx"]["p50"] == 3873 and base["turn_n_ctx"]["max"] == 5577
    assert base["bands"]["10000-18500"]["turns"] == 0
    long = json.loads(SIZING_LONG.read_text(encoding="utf-8"))["summary"]
    assert long["n_entries"] == 200 and long["tool_exec_errors"] == 0
    assert long["bands"]["10000-18500"]["entries_by_max"] == 1
    assert long["bands"][">18500"]["entries_by_max"] == 39
    assert long["entries_with_a_turn_in_10000_18500"] == 2


def test_gold_pipe_and_summary_shape() -> None:
    pipe = sizing.GoldPipe()
    pipe.queue = ["a", "b"]
    texts = [pipe.generate(["p"], None).texts[0] for _ in range(3)]
    assert texts == ["a", "b", sizing.CLOSING_TEXT]
    rows = [
        {
            "entry_id": "x",
            "max_n_ctx": 12_000,
            "turns": [
                {"n_ctx": 3_000, "tool_exec_error": False},
                {"n_ctx": 12_000, "tool_exec_error": False},
            ],
        },
    ]
    doc = sizing.summarize(rows)
    assert doc["bands"]["10000-18500"] == {"turns": 1, "entries_by_max": 1}
    assert doc["entries_with_a_turn_in_10000_18500"] == 1


# ---------------------------------------------------------------- NON_RESIDENT and CPU


def test_local_arm_defaults_are_unchanged() -> None:
    for policy in ("slo_escalate", "emission_escalate", "full_signal_bounceback", "local_only"):
        assert local_arm_settings(policy) == {
            "placement": ARM_CONFIG[policy]["placement"],
            "residency": ARM_CONFIG[policy]["residency"],
            "kv": ARM_CONFIG[policy]["kv"],
        }
        assert ARM_CONFIG[policy]["placement"] == "gpu_only"
        assert ARM_CONFIG[policy]["residency"] == "RESIDENT"


def test_local_arm_options() -> None:
    cpu = local_arm_settings("slo_escalate", placement="cpu-p", residency="non_resident")
    assert cpu == {"placement": "cpu-p", "residency": "NON_RESIDENT", "kv": "u8"}
    assert arm_id_for_h1(cpu) == "A"
    assert arm_id_for_h1(local_arm_settings("slo_escalate")) == "gpu_only_u8"
    with pytest.raises(SystemExit, match="placement"):
        local_arm_settings("slo_escalate", placement="npu")
    with pytest.raises(SystemExit, match="residency"):
        local_arm_settings("slo_escalate", residency="WARM")


def test_cli_options_default_to_none() -> None:
    args = build_argparser().parse_args(["--policy", "slo_escalate"])
    assert args.placement is None and args.residency is None
    args = build_argparser().parse_args(
        ["--policy", "slo_escalate", "--placement", "cpu-p", "--residency", "NON_RESIDENT"]
    )
    assert args.placement == "cpu-p" and args.residency == "NON_RESIDENT"


def test_slo_escalate_on_cpu_non_resident(tmp_path: Path) -> None:
    """CPU turn 0 over the SLO escalates and the entry stays on cloud."""
    entry = {"id": "c0", "question": [[], []], "n_user_turns": 2}
    row = {
        "n_ctx": 2200,
        "decode_tok_s": 20.0,
        "emitted_parseable_tool_call": True,
        "turn_wall_s": 0.05,
        "t_generate": 0.03,
        "t_tokenize": 0.005,
        "t_template_build": 0.005,
        "t_tool_exec": 0.005,
    }
    script = {"c0": [{**row, "ttft_s": 25.0}, {**row, "ttft_s": 26.0}]}
    local = StubLocalBackend(script=script)
    local.placement = "cpu-p"  # type: ignore[attr-defined]
    local.residency = "NON_RESIDENT"  # type: ignore[attr-defined]
    assert arm_config_for("slo_escalate", local)["placement"] == "cpu-p"
    out = tmp_path / "cpu"
    run_interleaved_session(
        entries=[entry],
        out_dir=out,
        local=local,
        cloud=StubCloudBackend(tokens_in=1000, tokens_out=100),
        policies=("slo_escalate",),
        policy_caps_usd={"slo_escalate": 5.0},
        session_max_usd=5.0,
        run_id="cpu-1",
        skip_entry_assert=True,
        seal=False,
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["placement"] == "cpu-p" and plan["residency"] == "NON_RESIDENT"
    assert plan["kv_match_seal"] is None
    turns = json.loads(
        (out / "policies" / "slo_escalate" / "turn_ledger.json").read_text(encoding="utf-8")
    )["entries"][0]["turns"]
    assert [t["placement"] for t in turns] == ["cloud", "cloud"]
    assert turns[0]["escalate_reason"].startswith("ttft>")
    assert turns[1]["escalate_reason"] == "stay_cloud"


def test_default_gpu_plan_keeps_kv_match_seal(tmp_path: Path) -> None:
    entry = {"id": "g0", "question": [[]], "n_user_turns": 1}
    script = {
        "g0": [
            {
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
        ]
    }
    out = tmp_path / "gpu"
    run_interleaved_session(
        entries=[entry],
        out_dir=out,
        local=StubLocalBackend(script=script),
        cloud=StubCloudBackend(tokens_in=10, tokens_out=1),
        policies=("local_only",),
        policy_caps_usd={"local_only": 1.0},
        session_max_usd=1.0,
        run_id="gpu-1",
        skip_entry_assert=True,
        seal=False,
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["placement"] == "gpu_only" and plan["residency"] == "RESIDENT"
    assert plan["kv_match_seal"] == KV_MATCH_SEAL_4B


def test_launcher_passes_entries_placement_residency() -> None:
    text = LAUNCH_H1.read_text(encoding="ascii")
    assert '[ValidateSet("", "gpu_only", "cpu-p")]' in text
    assert '[ValidateSet("", "RESIDENT", "NON_RESIDENT")]' in text
    assert "' --placement ' + $Placement" in text
    assert "' --residency ' + $Residency" in text
    assert text.count("' --entries \"' + $RunEntries + '\"'") == 2
