"""Regression: Axis-2 retarget still catches the synthetic 99.8%-duplicate bug."""

from __future__ import annotations

from apu_characterization.cap01.depth_triage import (
    axis2_degeneracy_failures,
    generation_depth_for_band,
    incorrect_duplicate_rate,
    triage_band,
)


def test_incorrect_duplicate_rate_ignores_convergent_correct() -> None:
    contents = ["answer=4"] * 8
    solved = [True] * 8
    assert incorrect_duplicate_rate(contents, solved) == 0.0


def test_incorrect_duplicate_rate_flags_synthetic_style_wrong_collapse() -> None:
    # 998 identical wrong + 2 unique wrong ≈ 99.8% incorrect duplicate rate.
    contents = ["WRONG"] * 998 + [f"unique-{i}" for i in range(2)]
    solved = [False] * 1000
    rate = incorrect_duplicate_rate(contents, solved)
    assert rate >= 0.997
    failures = axis2_degeneracy_failures(
        task_contents={"TASK-A": contents},
        task_solved={"TASK-A": solved},
    )
    assert any("incorrect_duplicate_rate" in item for item in failures)


def test_cross_task_identical_outputs_catch_synthetic_signature() -> None:
    shared = "echo this exact wrong payload"
    failures = axis2_degeneracy_failures(
        task_contents={
            "TASK-A": [shared, "a-unique"],
            "TASK-B": [shared, "b-unique"],
        },
        task_solved=None,
    )
    assert any("cross_task_identical_outputs" in item for item in failures)


def test_triage_bands_and_code_follows_band() -> None:
    assert triage_band(0.95, n=16) == "probable_SATURATED"
    assert triage_band(0.0, n=16) == "probable_DEAD"
    assert triage_band(0.5, n=16) == "SCALING_band"
    assert generation_depth_for_band("probable_SATURATED", domain="MATH") == 256
    assert generation_depth_for_band("SCALING_band", domain="MATH") == 2048
    # CODE sandbox repaired: depth follows triage band like other domains.
    assert generation_depth_for_band("probable_DEAD", domain="CODE") == 256
    assert generation_depth_for_band("SCALING_band", domain="CODE") == 2048
