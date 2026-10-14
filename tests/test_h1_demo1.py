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


# ---------------------------------------------------------------- DEMO-1 v2 groundwork

import tools.demo1_atlas as atlas_mod  # noqa: E402

ATLAS_JSON = ROOT / "analysis" / "demo1" / "DEMO1_ATLAS.json"


def test_envelope_band_edges() -> None:
    assert sizing.envelope_band(468) == "[0,468]"
    assert sizing.envelope_band(469) == "(468,10000]"
    assert sizing.envelope_band(10_000) == "(468,10000]"
    assert sizing.envelope_band(16_437) == "(10000,16437]"
    assert sizing.envelope_band(18_500) == "(16437,18500]"
    assert sizing.envelope_band(18_501) == "(18500,inf)"


def test_new_pins_reproduce_from_the_atlas() -> None:
    cases = (
        ("DEMO1_BASE_30", "multi_turn_base_FULL", 30, None, None),
        ("DEMO1_LONGCTX_15", "multi_turn_long_context_FULL", 15, 10_000, None),
        (
            "DEMO1_LONGCTX_OBSK1024_15",
            "multi_turn_long_context_OBS_MASK_K1024",
            15,
            10_000,
            18_500,
        ),
    )
    for pin, stem, n, lo, hi in cases:
        doc = json.loads((ROOT / "analysis" / "demo1" / "atlas" / f"{stem}.json").read_text())
        eligible, selected = sizing.select_subset(doc, n=n, min_ctx=lo, max_ctx=hi)
        meta = json.loads((DEMO / f"{pin}.meta.json").read_text(encoding="utf-8"))
        assert meta["selected"] == selected and meta["eligible"] == eligible
        assert _sha256_file(DEMO / f"{pin}.json") == meta["entries_sha256"]
        assert assert_entry_set_pinned(DEMO / f"{pin}.json")["name"] == pin
    assert (
        len(json.loads((DEMO / "DEMO1_LONGCTX_OBSK1024_15.meta.json").read_text())["eligible"])
        == 37
    )


def test_edge_interpolation_is_log_log_and_bounded() -> None:
    med = {1000: 1.0, 4000: 16.0}
    got = atlas_mod.edge_at(med, 4.0)
    assert got is not None and got["n"] == 2000 and got["between"] == [1000, 4000]
    assert atlas_mod.edge_at(med, 0.5) is None
    assert atlas_mod.edge_at(med, 20.0) is None


def test_slo_sens_edges_from_sealed_runs() -> None:
    edges = atlas_mod.slo_edges()
    assert edges["xps_gpu_4b_u8"]["10s"]["source"] == "c2246b1f"
    assert 10_000 < edges["xps_gpu_4b_u8"]["10s"]["n"] < 10_250
    assert edges["t2s_gpu_4b_u8"]["20s"]["source"] == "65e33de8"
    assert edges["xps_gpu_4b_u8"]["5s"]["n"] is None
    assert edges["xps_gpu_4b_u8"]["5s"]["bound"].startswith("< 8000")
    assert edges["xps_cpu_4b"]["5s"]["bound"].startswith("< 250")


def test_committed_atlas_is_current(tmp_path: Path) -> None:
    out = tmp_path / "atlas.json"
    assert atlas_mod.main(["--out", str(out)]) == 0
    assert json.loads(out.read_text()) == json.loads(ATLAS_JSON.read_text())


def test_route_and_predict_cell() -> None:
    assert atlas_mod.route_entry([2000, 5000, 34000, 34100], 10_000) == 2
    assert atlas_mod.route_entry([2000, 5000], 10_000) == 2
    cell = atlas_mod.predict_cell({"a": [2000, 12_000, 20_000]}, "xps_gpu_4b_u8")
    lo, hi = cell["low"], cell["high"]
    assert lo["local_share"] == round(1 / 3, 3) and lo["escalations_ttft"] == 1
    assert lo["split_usd"]["latency"] > 0 and lo["split_usd"]["context"] > 0
    assert lo["split_usd"]["capability"] == 0.0
    ref = atlas_mod.predict_cell({"a": [2000, 12_000, 20_000]}, None)["low"]
    assert ref["local_share"] == 0.0
    assert ref["usd"] == round(34_000 * 7.11 * 3.20e-6, 2)


def test_paired_pin_v3_v4() -> None:
    full = json.loads((ROOT / "analysis/demo1/atlas/multi_turn_long_context_FULL.json").read_text())
    k1024 = json.loads(
        (ROOT / "analysis/demo1/atlas/multi_turn_long_context_OBS_MASK_K1024.json").read_text()
    )
    eligible, selected = sizing.select_subset(
        k1024, n=15, min_ctx=10_000, max_ctx=18_500, also=full, also_min_ctx=18_500
    )
    meta = json.loads((DEMO / "DEMO1_PAIRED_15.meta.json").read_text(encoding="utf-8"))
    assert meta["eligible"] == eligible and meta["selected"] == selected and len(eligible) == 36
    assert assert_entry_set_pinned(DEMO / "DEMO1_PAIRED_15.json")["name"] == "DEMO1_PAIRED_15"
    assert atlas_mod.CELLS["V3"][0] == atlas_mod.CELLS["V4"][0] == "DEMO1_PAIRED_15"
    fmax = {r["entry_id"]: max(t["n_ctx"] for t in r["turns"]) for r in full["entries"]}
    kmax = {r["entry_id"]: max(t["n_ctx"] for t in r["turns"]) for r in k1024["entries"]}
    assert all(fmax[e] > 18_500 and 10_000 < kmax[e] <= 18_500 for e in selected)


def test_k_rule_selects_1024() -> None:
    full = {r["entry_id"]: r for r in atlas_mod.rows_for("multi_turn_long_context_FULL")}
    jump = [e for e, r in full.items() if any(t["n_ctx"] > 10_000 for t in r["turns"])]
    chosen = None
    for k in atlas_mod.SWEPT_K:
        rows = {
            r["entry_id"]: r for r in atlas_mod.rows_for(f"multi_turn_long_context_OBS_MASK_K{k}")
        }
        share = sum(
            10_000 < max(t["n_ctx"] for t in rows[e]["turns"]) <= 18_500 for e in jump
        ) / len(jump)
        if share >= 0.9:
            chosen = k
            break
    assert len(jump) == 40 and chosen == 1024


# ---------------------------------------------------------------- DEMO_PREREG_v2

PREREG = DEMO / "DEMO_PREREG_v2.json"
NO_READ_SOURCES = (
    ROOT / "tools" / "run_h1_hybrid.py",
    ROOT / "tools" / "launch_h1.ps1",
    ROOT / "tools" / "h1_obs_mask.py",
    ROOT / "tools" / "h1_context_sizing.py",
    ROOT / "tools" / "bfcl_feasibility_probe.py",
)


def test_prereg_is_committed_and_capped() -> None:
    doc = json.loads(PREREG.read_text(encoding="ascii"))
    assert doc["runner_must_not_read_this_file"] is True
    assert doc["registered_before_any_cell"] is True
    assert doc["k_rule"]["applied"] == 1024
    assert doc["cells"]["V3"]["pin"] == doc["cells"]["V4"]["pin"] == "DEMO1_PAIRED_15"
    caps = doc["spend"]["per_cell_caps_usd"]
    assert sum(sum(c.values()) for c in caps.values()) == doc["spend"]["caps_usd_total"] == 145
    assert doc["spend"]["ceiling_usd"] == 200 and doc["spend"]["reserve_usd"] == 55
    for name, cell in doc["cells"].items():
        assert (
            assert_entry_set_pinned(DEMO / f"{cell['pin']}.json")["sha256"] == cell["pin_sha256"]
        ), name
    assert set(doc["v4_at_every_swept_k"]) == {str(k) for k in atlas_mod.SWEPT_K}


def test_runner_sources_do_not_name_the_prereg() -> None:
    for path in NO_READ_SOURCES:
        text = path.read_text(encoding="utf-8")
        assert "DEMO_PREREG" not in text and "DEMO1_DESIGN" not in text, path
        assert "DEMO1_AMEND" not in text and "V5_PREDICTIONS" not in text, path
        assert "V5_ADDENDUM" not in text and "V5CAL_PREREG" not in text, path


def test_runner_never_opens_the_prereg(monkeypatch, tmp_path: Path) -> None:
    import builtins
    import io

    real_open = builtins.open

    def guarded(file, *args, **kwargs):
        name = Path(str(file)).name.upper()
        if (
            "DEMO_PREREG" in str(file)
            or "PREREG" in name
            or "DEMO1_AMEND" in name
            or "V5_PREDICTIONS" in name
        ):
            raise AssertionError(f"runner opened {file}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded)
    monkeypatch.setattr(io, "open", guarded)
    _entries, path = load_w3_entries(DEMO / "DEMO1_PAIRED_15.json")
    assert assert_entry_set_pinned(path)["name"] == "DEMO1_PAIRED_15"
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
    entry = {"id": "e0", "question": [[]], "n_user_turns": 1}
    run_interleaved_session(
        entries=[entry],
        out_dir=tmp_path / "s",
        local=StubLocalBackend(script={"e0": [row]}),
        cloud=StubCloudBackend(tokens_in=1, tokens_out=1),
        policies=("slo_escalate",),
        policy_caps_usd={"slo_escalate": 1.0},
        session_max_usd=1.0,
        run_id="noread",
        skip_entry_assert=True,
        seal=False,
    )


# ---------------------------------------------------------------- amendment 2026-10-13c

AMEND_C = ROOT / "docs" / "amendments" / "DEMO1_AMEND_2026-10-13c_CONFIG.md"
V5_PRED = ROOT / "analysis" / "demo1" / "V5_PREDICTIONS.json"


def test_amendment_c_pins_its_inputs_and_outputs() -> None:
    import hashlib

    text = AMEND_C.read_text(encoding="ascii")
    prefix = ROOT / "analysis" / "demo1" / "PREFIX_CHECK_K1024.json"
    script = ROOT / "tools" / "demo1_v5_predict.py"
    for path in (prefix, script, V5_PRED):
        assert hashlib.sha256(path.read_bytes()).hexdigest() in text, path.name
    doc = json.loads(V5_PRED.read_text(encoding="utf-8"))
    for name in ("V5a_xps_gpu_4b_RESIDENT_u8", "V5b_xps_gpu_4b_RESIDENT_u4"):
        low = doc["cells"][name]["block_low"]
        assert low["local_share"] == 0.164 and low["usd_per_task"] == 0.766
        assert low["bracket_status"] == {"local": 0, "indeterminate": 15, "escalates": 0}
    assert "| V5a RESIDENT u8 | 0.164 | 0.766 (0.829) |" in text


def test_v5_predictions_are_current() -> None:
    from tools import demo1_v5_predict

    assert demo1_v5_predict.predictions() == json.loads(V5_PRED.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- V5 addendum 2026-10-14

ADDENDUM = ROOT / "docs" / "amendments" / "DEMO1_V5_ADDENDUM_2026-10-14.md"
ADD_PRED = ROOT / "analysis" / "demo1" / "V5_ADDENDUM_PREDICTIONS.json"
SCORES = ROOT / "analysis" / "demo1" / "SCORE_XPS_20261013.json"


def test_v5_addendum_pins_and_verdict() -> None:
    import hashlib

    text = ADDENDUM.read_text(encoding="ascii")
    for path in (ADD_PRED, ROOT / "tools" / "demo1_v5_addendum.py"):
        assert hashlib.sha256(path.read_bytes()).hexdigest() in text, path.name
    doc = json.loads(ADD_PRED.read_text(encoding="utf-8"))
    for cell in ("V5a_u8", "V5b_u4"):
        for bound in ("block_low", "block_high"):
            got = doc["registered_per_step"][cell][bound]
            assert got["escalations"] == 15 and got["escalations_outside_grid"] == 0
        assert doc["runner_trigger_per_turn"][cell]["block_low"]["escalations"] == 0
    assert "V5 is NOT worth running" in text


def test_v5_addendum_predictions_are_current() -> None:
    from tools import demo1_v5_addendum

    fresh = json.loads(json.dumps(demo1_v5_addendum.predictions()))
    assert fresh == json.loads(ADD_PRED.read_text(encoding="utf-8"))


def test_xps_scores() -> None:
    from tools import score_demo1_cells

    doc = json.loads(SCORES.read_text(encoding="utf-8"))
    v1 = doc["cells"]["V1_xps_gpu_4b_u8"]
    v4 = doc["cells"]["V4_xps_gpu_4b_u8"]
    assert set(v1["verdict"].values()) == {"MATCH"}
    assert set(v4["verdict"].values()) == {"MISS"}
    assert v4["measured"]["local_share"] == 0.673 and v4["measured"]["escalations_ttft"] == 9
    assert len(v4["gold_jump_entries_not_escalated"]) == 6
    assert score_demo1_cells.score_cell("V4_xps_gpu_4b_u8") == v4


SCORES_T2S = ROOT / "analysis" / "demo1" / "SCORE_T2S_20261013.json"


def test_t2s_scores() -> None:
    from tools import score_demo1_cells

    doc = json.loads(SCORES_T2S.read_text(encoding="utf-8"))
    v1 = doc["cells"]["V1_t2s_gpu_4b_u8"]
    v4 = doc["cells"]["V4_t2s_gpu_4b_u8"]
    v3 = doc["cells"]["V3_t2s_gpu_4b_u8"]
    assert set(v1["verdict"].values()) == {"MATCH"}
    assert set(v4["verdict"].values()) == {"MATCH"}
    assert set(v3["verdict"].values()) == {"MISS"}
    assert v3["gold_edge_tokens"] == 18_500
    assert v3["measured"]["escalations_ttft"] == 5
    assert v4["entries_with_gold_jump"] == 0
    assert len(v3["gold_jump_entries_not_escalated"]) == 10
    for key, cell in doc["cells"].items():
        assert score_demo1_cells.score_cell(key) == cell
