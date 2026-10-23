"""Task BM (A19-A36): DXGI probe, failure taxonomy, A31 rejection, i8 arm, balloon, predictions."""

from __future__ import annotations

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
from seam import dxgi_budget  # noqa: E402
from seam.ov_kv_precision import (  # noqa: E402
    kv_bytes_per_token,
    normalize_kv_precision_name,
    requested_kv_cache_precision,
)
from seam.tools import _delta_n_child as child  # noqa: E402
from tools import cc_bl_predict as bl  # noqa: E402
from tools import cc_bm_predict as bm  # noqa: E402
from tools import cc_failure, gpu_balloon  # noqa: E402
from tools import cc_predict as cc  # noqa: E402

SPEC = ["--arm", "gpu_only_u4", "--model-spec", "configs/models/Qwen3-4B-int4-ov.yaml"]


@pytest.mark.skipif(sys.platform == "win32", reason="off-Windows contract")
def test_dxgi_off_windows_reports_errors() -> None:
    assert dxgi_budget.snapshot() == {"error": "not windows"}
    assert dxgi_budget.global_memory() == {"error": "not windows"}
    w = dxgi_budget.BudgetWatch()
    assert w.error == "not windows" and w.poll() == 0 and "error" in w.query()
    w.close()


def test_failure_taxonomy_on_sealed_shapes() -> None:
    f = cc_failure.classify
    sealed_u4 = {
        "failure_mode": "turn1:RuntimeError",
        "exception": {"type": "RuntimeError", "message": "[GPU] CL_OUT_OF_RESOURCES exception."},
    }
    assert f(sealed_u4) == {"class": "device_alloc", "phase": "prefill", "censored": False}
    budget = {
        "failure_mode": "load:RuntimeError",
        "exception": {"message": "Requested cache size is larger than available memory size"},
    }
    assert f(budget)["class"] == "budget_check" and f(budget)["phase"] == "construction"
    assert f({"failure_mode": "timeout:3600s@running", "exception": None})["censored"] is True
    assert (
        f({"failure_mode": "kv_compiled_mismatch", "exception": {"type": "KvCompiledMismatch"}})[
            "class"
        ]
        == "kv_mismatch"
    )
    assert f({})["class"] == "none"


def test_a31_rejection_rules() -> None:
    on = {"reject_kv_mismatch": True}
    assert child.compiled_kv_mismatch({}, "u4", None) is None
    assert child.compiled_kv_mismatch(on, None, None) is None
    assert "not read back" in str(child.compiled_kv_mismatch(on, "u4", {}))
    assert child.compiled_kv_mismatch(on, "u4", {"kv_cache_precision": "u4"}) is None
    assert "!=" in str(child.compiled_kv_mismatch(on, "u8", {"kv_cache_precision": "i8"}))
    assert child.compiled_kv_mismatch(on, "i8", {"kv_cache_precision": "i8"}) is None


def test_i8_arm_and_names() -> None:
    import yaml

    cfg = yaml.safe_load((ROOT / "configs" / "delta_n.yaml").read_text(encoding="utf-8"))
    arm = next(a for a in cfg["arms"] if a["id"] == "gpu_only_i8")
    assert arm["properties"] == {"KV_CACHE_PRECISION": "i8"}
    assert requested_kv_cache_precision(arm["properties"]) == "i8"
    assert normalize_kv_precision_name("<Type: 'int8_t'>") == "i8"
    assert kv_bytes_per_token("i8") == kv_bytes_per_token("u8")
    assert normalize_kv_precision_name("<Type: 'uint8_t'>") == "u8"


def test_bm_flags_route_and_refuse(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run(**_kw: Any) -> int:
        seen.update(b4.CC_OVERRIDE)
        return 0

    monkeypatch.setattr(rrl, "run_resident_limit", run)
    try:
        rrl.main(
            [
                *SPEC,
                "--cc-cell",
                "x",
                "--mem-trace-hz",
                "10",
                "--dxgi-trace",
                "--compiled-readback",
                "--reject-kv-mismatch",
            ]
        )
    finally:
        b4.set_pilot_overrides()
        b4.set_cc_overrides()
    assert seen["dxgi_trace"] is True and seen["reject_kv_mismatch"] is True
    for bad in (["--reject-kv-mismatch"], ["--dxgi-trace"]):
        with pytest.raises(SystemExit, match="REFUSED"):
            rrl.main([*SPEC, "--cc-cell", "x", *bad])
        b4.set_pilot_overrides()
        b4.set_cc_overrides()


def test_cpu_balloon_touches_pages() -> None:
    held, method = gpu_balloon._cpu_alloc(3 * 1024 * 1024)
    assert method == "numpy_page_touch" and sum(h.size for h in held) == 3 * 1024 * 1024


def test_committed_bm_predictions_match_generator_and_earlier_files_unchanged() -> None:
    d = ROOT / "derived" / "cc"
    doc = json.loads((d / "CC_BM_PREDICTIONS.json").read_text(encoding="utf-8"))
    assert doc == json.loads(json.dumps(bm.build()))
    assert doc["runner_must_not_read_this_file"] is True
    assert json.loads((d / "CC_PREDICTIONS.json").read_text(encoding="utf-8")) == json.loads(
        json.dumps(cc.build())
    )
    assert json.loads((d / "CC_BL_PREDICTIONS.json").read_text(encoding="utf-8")) == json.loads(
        json.dumps(bl.build())
    )


def test_bm_arithmetic() -> None:
    doc = bm.build()
    assert doc["A24_ttft_law"]["L_TTFT"] == {"5s": 5712, "20s": 16729, "30s": 22164}
    assert doc["A25_A36_slider"]["at"]["M_15.5GiB"]["f16_law"] == 681
    assert doc["A25_A36_slider"]["at"]["M_16.0GiB"]["f16_law"] == 703
    assert doc["A29_t2s_balloon_conc_ii"] == {
        "balloon_0GiB_fails_at_N": 10,
        "balloon_4.5GiB_fails_at_N": 9,
        "balloon_9GiB_fails_at_N": 8,
    }
    assert doc["A21_8bit_rebisect"]["predict"] == [20921, 21486]


def test_runners_never_read_bm_files() -> None:
    for name in ("run_resident_limit.py", "boot4_session.py", "run_h1_hybrid.py"):
        text = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert "CC_BM_PREDICTIONS" not in text
