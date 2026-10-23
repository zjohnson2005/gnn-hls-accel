"""Task BO: second-model predictions, fleet tools, red flags, queue status, figures, canary option."""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.boot4_session as b4  # noqa: E402
import tools.run_resident_limit as rrl  # noqa: E402
from tools import cc_m2_predict as m2  # noqa: E402
from tools import fleet_cdf, fleet_predict, queue_status, redflags  # noqa: E402


def test_m2_predictions_match_generator_and_config_rule() -> None:
    doc = json.loads(
        (ROOT / "derived" / "cc" / "CC_M2_PREDICTIONS.json").read_text(encoding="utf-8")
    )
    assert doc == json.loads(json.dumps(m2.build()))
    assert m2.a_config({"intermediate_size": 9728, "hidden_size": 2560}) == 98_304
    assert doc["alloc_slope_a"]["f16"]["point"] == 131_072
    assert doc["uncapped_limits"]["f16"]["point"] == 3846
    assert doc["kv_compression_bound"]["G_max"] == 2.125


def test_canary_option_keeps_4b_canary_for_8b(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run(**_kw: Any) -> int:
        seen.update(b4.CC_OVERRIDE)
        seen["specs"] = b4._cc_canary_specs(
            {"model_spec": Path("configs/models/Qwen3-8B-int4-ov.v2.yaml")}
        )
        return 0

    monkeypatch.setattr(rrl, "run_resident_limit", run)
    try:
        rrl.main(
            [
                "--arm",
                "gpu_only_f16",
                "--model-spec",
                "configs/models/Qwen3-8B-int4-ov.v2.yaml",
                "--cc-cell",
                "CC-M2",
                "--canary-model-spec",
                "configs/models/Qwen3-4B-int4-ov.yaml",
            ]
        )
    finally:
        b4.set_pilot_overrides()
        b4.set_cc_overrides()
    assert b4._canary_model(seen["specs"]).name == "Qwen3-4B-int4-ov.yaml"
    assert b4._cc_canary_specs({"model_spec": Path("x.yaml")}) == [Path("x.yaml")]


def test_fleet_cdf_on_synthetic_trace(tmp_path: Path) -> None:
    recs = [
        {
            "provider": "a",
            "session_id": "s",
            "round_index": i,
            "input_tokens_total": v,
            "prefix_tokens": 0,
        }
        for i, v in enumerate([1000, 2000, 4000, 8000, 70000])
    ]
    p = tmp_path / "t.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    assert fleet_cdf.check_schema(p)["missing_fields"] == []
    out = fleet_cdf.by_provider(fleet_cdf.rounds(p), {"4k": 4096, "40k": 40960})
    assert out["all"]["fit_fraction"] == {"4k": 0.6, "40k": 0.8}
    assert out["all"]["quantiles"]["p50"] == 4000


def test_fleet_cdf_refuses_results_before_gate_and_wrong_hash(tmp_path: Path) -> None:
    p = tmp_path / "x.gz"
    p.write_bytes(b"x")
    with pytest.raises(SystemExit, match="pinned"):
        fleet_cdf.main(["--raw", str(p), "--check-schema"])


def test_fleet_tiers_follow_the_windows_formula() -> None:
    doc = json.loads(
        (ROOT / "derived" / "fleet" / "FLEET_PREDICTIONS.json").read_text(encoding="utf-8")
    )
    assert doc == json.loads(json.dumps(fleet_predict.build()))
    assert fleet_predict.graphics_tier(64.0) == 48.0 and fleet_predict.graphics_tier(16.0) == 8.0
    assert doc["tiers"]["16GiB"]["L_mem_uncapped"] == {"f16": 15000, "u4": 26500}
    assert doc["tiers"]["8GiB"]["L_mem_uncapped"] == {"f16": 0, "u4": 0}


def test_redflags_synthetic() -> None:
    doc = {
        "R1": {"value": 21000, "run_ids": ["r1"]},
        "R2": {"ratios": [1.5], "slider_r2": 0.99},
        "R3": {"a_kb": {"f16": 96, "u4": 95}},
        "R4": {
            "cap256_vs_uncapped": {"f16": {"capped": 24000, "uncapped": 15000}},
            "headline_failure_classes": ["device_alloc"],
        },
        "R5": {"kv": [{"requested": "u4", "applied": "u4", "headline": True}]},
        "R6": {"t2s": {"shared_mib": 48634, "formula_mib": 48634}},
        "R7": {"u4_c256_median": 35000},
        "R8": {"median_abs_err": 0.08, "binding_correct_frac": 0.95, "n": 31},
        "R9": {"items": [{"item": "Singh", "kills": False}]},
    }
    res = {r["id"]: r["status"] for r in redflags.evaluate(doc)}
    assert res["R1"] == redflags.PASS and res["R2"] == redflags.RED and res["R7"] == redflags.RED
    assert (
        res["R3"] == res["R4"] == res["R5"] == res["R6"] == res["R8"] == res["R9"] == redflags.PASS
    )
    assert res["R10"] == redflags.NYM
    assert redflags.evaluate({"R3": {"a_kb": {"f16": 96}}})[2]["status"] == redflags.NYM


def test_queue_status_reads_a_window(tmp_path: Path) -> None:
    w = tmp_path / "t2s" / "window_20261023_130443_cc_v3"
    w.mkdir(parents=True)
    (w / "STATUS.txt").write_text("updated x\nnow: conc_ii\n", encoding="utf-8")
    (w / "steps.txt").write_text("[10-23 13:06:13 ET] A14_DONE\n", encoding="utf-8")
    (w / "cells.txt").write_text("reh rc=0 run_id=a\nreh_i8 rc=1 run_id=b\n", encoding="utf-8")
    (w / "reh_i8_logtail.txt").write_text("[GPU] CL_OUT_OF_RESOURCES exception\n", encoding="utf-8")
    s = queue_status.window_summary(w)
    assert s["now"] == "conc_ii" and s["rc"] == {"0": 1, "1": 1}
    assert s["failure_classes_in_logtails"] == {"device_alloc": 1}
    assert queue_status.windows(tmp_path, False) == [w]


def test_figures_render_with_placeholders(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    from tools.figs import (
        fig1_roofline,
        fig2_bytes,
        fig3_slopes,
        fig4_pred_vs_meas,
        fig5_kv_bound,
        fig6_os_formula,
        fig7_binding_map,
    )

    for mod in (
        fig1_roofline,
        fig2_bytes,
        fig3_slopes,
        fig4_pred_vs_meas,
        fig5_kv_bound,
        fig6_os_formula,
        fig7_binding_map,
    ):
        man = mod.make(tmp_path)
        assert all(Path(p).is_file() for p in man["outputs"])
        assert man["inputs_sha256"]
