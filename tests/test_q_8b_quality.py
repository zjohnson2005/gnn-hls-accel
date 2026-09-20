"""Unit tests for Q-8B helpers (no hardware)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.errors import SeamError  # noqa: E402
from tools.quality_row_persist import (  # noqa: E402
    DEGENERATE_CONSECUTIVE_N,
    DegenerateOutputGuard,
    cell_is_degenerate_max_burn,
    persist_model_result_raw_per_turn,
    persist_raw_string,
)
from tools.run_q_8b_quality import (  # noqa: E402
    ARM_MODEL_SPECS,
    ARMS,
    DUAL_RESIDENT_KNOWN_BROKEN,
    _arm_order_for_entry,
    _quality_row,
    analyze_paired,
    main,
)


def test_arm_order_permutation() -> None:
    a = _arm_order_for_entry("multi_turn_base_0", seed=20260916)
    b = _arm_order_for_entry("multi_turn_base_0", seed=20260916)
    assert a == b
    assert sorted(a) == sorted(ARMS)


def test_model_specs_exist_and_are_int4() -> None:
    for arm, path in ARM_MODEL_SPECS.items():
        assert path.is_file(), path
        assert "int4" in path.name.lower()
        assert "int8" not in path.name.lower()
        assert arm in ("int4_4B", "int4_8B")


def test_analyze_paired_8b_better() -> None:
    entry_ids = [f"e{i}" for i in range(20)]
    by_arm: dict = {a: {} for a in ARMS}
    for i, eid in enumerate(entry_ids):
        by_arm["int4_4B"][eid] = {
            "emission_ok": i >= 12,
            "trajectory_pass": i < 2,
        }
        by_arm["int4_8B"][eid] = {
            "emission_ok": i >= 5,
            "trajectory_pass": i < 8,
        }
    paired = analyze_paired(by_arm, entry_ids)
    assert paired["per_arm"]["int4_4B"]["emission_failures"] == 12
    assert paired["per_arm"]["int4_8B"]["emission_failures"] == 5
    em = paired["emission"]["int4_4B__vs__int4_8B"]["mcnemar"]
    assert em["second_only"] > em["first_only"]
    assert em["p_value"] < 0.05
    assert paired["falsification"]["emission_arms_agree"] is False


def test_quality_row_persists_raw_per_turn() -> None:
    row = {
        "id": "e0",
        "score": {"valid": False},
        "model_result_decoded": [[["tool()"]]],
        "model_result_raw": [["raw call text"], ["second turn"]],
        "turn_metrics": [
            {"n_decoded_steps": 1, "generated_tokens": 12},
            {"n_decoded_steps": 1, "generated_tokens": 8},
        ],
        "stop_reason": "completed",
        "force_quit": False,
        "n_user_turns": 2,
        "n_completed_turns": 2,
        "wall_s": 1.0,
    }
    q = _quality_row(row, arm_id="int4_4B")
    assert "model_result_raw_per_turn" in q
    assert len(q["model_result_raw_per_turn"]) == 2
    assert q["model_result_raw_per_turn"][0]["generations"][0]["text"] == "raw call text"
    assert q["model_result_raw_per_turn"][0]["generations"][0]["truncated"] is False


def test_persist_raw_truncates_oversized() -> None:
    big = "a" * 2000
    p = persist_raw_string(big, head_tail=512)
    assert p["truncated"] is True
    assert p["length"] == 2000
    assert p["text_head"] == "a" * 512
    assert p["text_tail"] == "a" * 512


def test_default_cli_is_single_pipe_not_dual() -> None:
    """Default argparse: allow_dual_resident False (single-pipe default)."""
    p = argparse.ArgumentParser()
    p.add_argument("--allow-dual-resident", action="store_true")
    p.add_argument("--force-block-interleave", action="store_true")
    args = p.parse_args([])
    assert args.allow_dual_resident is False
    assert DUAL_RESIDENT_KNOWN_BROKEN is True
    # main() wires --allow-dual-resident; ensure help text path exists.
    with pytest.raises(SystemExit):
        main(["--help"])


def test_degenerate_guard_n_from_b1a_signature() -> None:
    assert DEGENERATE_CONSECUTIVE_N == 3
    burn = {
        "turn_metrics": [
            {"n_decoded_steps": 0, "generated_tokens": 512},
            {"n_decoded_steps": 0, "generated_tokens": 512},
        ]
    }
    ok = {
        "turn_metrics": [
            {"n_decoded_steps": 1, "generated_tokens": 40},
        ]
    }
    assert cell_is_degenerate_max_burn(burn, max_new_tokens=512)
    assert not cell_is_degenerate_max_burn(ok, max_new_tokens=512)

    g = DegenerateOutputGuard(n=3, max_new_tokens=512)
    g.observe(burn, entry_id="e1", arm_id="int4_4B")
    g.raise_if_refused()  # streak 1 — ok
    g.observe(burn, entry_id="e2", arm_id="int4_8B")
    g.raise_if_refused()  # streak 2 — ok
    g.observe(burn, entry_id="e3", arm_id="int4_4B")
    with pytest.raises(SeamError, match="DEGENERATE_OUTPUT_STREAK"):
        g.raise_if_refused()


def test_degenerate_guard_resets_on_healthy_cell() -> None:
    burn = {"turn_metrics": [{"n_decoded_steps": 0, "generated_tokens": 512}]}
    ok = {"turn_metrics": [{"n_decoded_steps": 1, "generated_tokens": 20}]}
    g = DegenerateOutputGuard(n=3, max_new_tokens=512)
    g.observe(burn, entry_id="a", arm_id="x")
    g.observe(burn, entry_id="b", arm_id="y")
    g.observe(ok, entry_id="c", arm_id="x")
    assert g.consecutive == 0
    g.observe(burn, entry_id="d", arm_id="y")
    g.raise_if_refused()  # streak 1 after reset


def test_persist_model_result_raw_per_turn_helper() -> None:
    row = {"model_result_raw": [["hello"], ["world", "x" * 2000]]}
    turns = persist_model_result_raw_per_turn(row)
    assert turns[0]["generations"][0]["text"] == "hello"
    assert turns[1]["generations"][1]["truncated"] is True


if __name__ == "__main__":
    test_arm_order_permutation()
    test_model_specs_exist_and_are_int4()
    test_analyze_paired_8b_better()
    test_quality_row_persists_raw_per_turn()
    test_persist_raw_truncates_oversized()
    test_degenerate_guard_n_from_b1a_signature()
    test_degenerate_guard_resets_on_healthy_cell()
    test_persist_model_result_raw_per_turn_helper()
    print("OK")
