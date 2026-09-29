"""Failure taxonomy, partial cells, and the discarded canary warm-up."""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.boot4_session import cell_exit_code, cell_status  # noqa: E402
from tools.run_c1_ceiling import classify_c1_failure  # noqa: E402
from tools.ttft_slo_canary import (  # noqa: E402
    TtftSloCanaryGuard,
    new_canary_gate,
    update_canary_drift_bookkeeping,
)

# Sealed canary turn-2 samples from e9264a0a. The first is the warm-up.
_E9264_T2 = (1.126149536, 0.662402648, 0.719344543)
_E9264_T1 = (2.666311035, 2.483805419, 2.643773437)


def _primitive_result() -> dict[str, object]:
    return {
        "outcome": "fail",
        "failure_mode": "turn1:RuntimeError",
        "child": {
            "exception": {
                "type": "RuntimeError",
                "message": (
                    "Exception from src\\plugins\\intel_gpu\\src\\graph\\impls\\"
                    "onednn\\primitive_onednn_base.h:550:\n"
                    "could not execute a primitive\n"
                ),
            },
            "memory_at_failure": {"available_mb": 2912.33203125, "rss_mb": 6060.1875},
            "memory_before_generate": {"available_mb": 6466.6796875, "rss_mb": 2568.234375},
        },
    }


def test_primitive_failure_is_not_a_memory_wall() -> None:
    classified = classify_c1_failure(_primitive_result())
    assert classified["failure_kind"] == "onednn_primitive_failure"
    memory = classified["memory"]
    assert isinstance(memory, dict)
    assert set(memory) == {"memory_at_failure", "memory_before_generate"}


def test_memory_wall_is_only_cl_out_or_an_allocation_error() -> None:
    cl_out = {
        "outcome": "fail",
        "failure_mode": "exception:RuntimeError",
        "child": {
            "exception": {
                "type": "RuntimeError",
                "message": "[GPU] CL_OUT_OF_RESOURCES exception.",
            }
        },
    }
    alloc = {
        "outcome": "fail",
        "failure_mode": "exception:MemoryError",
        "child": {"exception": {"type": "MemoryError", "message": "failed to allocate"}},
    }
    access = {
        "outcome": "fail",
        "failure_mode": "exception:OSError",
        "child": {"exception": {"type": "OSError", "message": "0xc0000005"}},
    }
    assert classify_c1_failure(cl_out)["failure_kind"] == "memory_wall"
    assert classify_c1_failure(alloc)["failure_kind"] == "memory_wall"
    assert classify_c1_failure(access)["failure_kind"] == "other"


def test_a_point_failure_is_partial_and_does_not_stop_the_boot() -> None:
    points = [
        {"n_cached": 12000, "outcome": "pass", "failure_kind": None},
        {
            "n_cached": 46000,
            "outcome": "fail",
            "failure_kind": "onednn_primitive_failure",
        },
    ]
    assert cell_status(points) == "partial"
    assert cell_exit_code("partial") == 0
    assert cell_exit_code("complete") == 0
    assert cell_exit_code("FAIL_CANARY_DRIFT") == 1
    assert cell_exit_code("REFUSED_CANARY") == 1
    assert cell_exit_code("failed") == 1
    assert cell_status([{"outcome": "fail", "failure_kind": None}]) == "failed"


def test_the_launcher_continues_after_a_zero_exit() -> None:
    text = (ROOT / "tools" / "launch_boot1.ps1").read_text(encoding="utf-8")
    tail = text.split("SEAM_CELL_STATUS_PATH", 1)[1]
    assert tail.index("if ($exit -ne 0)") < tail.index("continue")


def test_warmup_excludes_the_e9264a0a_t2_drift() -> None:
    included = list(_E9264_T2)
    ref = float(statistics.median(included))
    early_if_included = max(abs(value - ref) / ref for value in included)
    assert early_if_included == pytest.approx(0.5655217613849336)

    gate = new_canary_gate()
    kept: list[dict[str, object]] = []
    rows: list[tuple[float, float, bool]] = [
        (_E9264_T1[0], _E9264_T2[0], True),
        (_E9264_T1[1], _E9264_T2[1], False),
        (_E9264_T1[2], _E9264_T2[2], False),
        (2.60, 0.700, False),
    ]
    for turn1, turn2, warmup in rows:
        prior = [item for item in kept if not item.get("warmup")]
        book = update_canary_drift_bookkeeping(
            rec={
                "classification": "OK",
                "turn1_prefill_s": turn1,
                "turn2_prefill_s": turn2,
                "warmup": warmup,
            },
            gate=gate,
            prior_ok_canaries=prior,
        )
        kept.append(book["rec"])
    assert kept[0]["discarded_from_calibration"] is True
    calibration = list(gate["calibration_turn2_prefill_s"])
    assert _E9264_T2[0] not in calibration
    assert gate["early_max_rel_t2"] < early_if_included
    assert float(gate["early_max_rel_t2"]) < 0.1


def test_discard_warmup_is_off_unless_boot4_asks_for_it() -> None:
    assert TtftSloCanaryGuard.__dataclass_fields__["discard_warmup"].default is False
    text = (ROOT / "tools" / "boot4_session.py").read_text(encoding="utf-8")
    assert "discard_warmup=True" in text


def test_relabel_lives_outside_the_run_tree() -> None:
    path = ROOT / "derived" / "delta_prefill" / "analysis" / "e9264a0a_n46000_relabel.json"
    assert "sealed_" not in path.as_posix()
    analysis = json.loads(path.read_text(encoding="utf-8"))
    assert analysis["failure_kind"] == "onednn_primitive_failure"
    assert analysis["rung"] == 46000
    assert analysis["tree_modified"] is False
    assert "memory_at_failure" in analysis
    point = ROOT / str(analysis["source_point"])
    if point.exists():
        original = json.loads(point.read_text(encoding="utf-8-sig"))
        assert original["failure_kind"] == "other"
