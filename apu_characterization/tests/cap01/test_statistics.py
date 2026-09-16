from __future__ import annotations

from apu_characterization.cap01.statistics import (
    DEFAULT_BOOTSTRAP_RESAMPLES,
    analyze_pairs,
    mcnemar_exact_two_sided,
)


def test_mcnemar_exact_two_sided_known_tail() -> None:
    result = mcnemar_exact_two_sided(
        [True] * 8,
        [False] * 7 + [True],
    )
    assert result["first_only"] == 7
    assert result["second_only"] == 0
    assert result["p_value"] == 0.015625


def test_task_clustered_bca_is_deterministic_and_test_override_is_recorded() -> None:
    pairs = [
        {
            "task_id": task_id,
            "seed": seed,
            "first_solved": False,
            "second_solved": task_id != "t3",
        }
        for task_id in ("t1", "t2", "t3")
        for seed in (0, 1)
    ]
    first = analyze_pairs(pairs, bootstrap_resamples=200, bootstrap_seed=17)
    second = analyze_pairs(pairs, bootstrap_resamples=200, bootstrap_seed=17)
    assert first == second
    assert first["difference_pp"] < 0
    assert first["bca_ci"]["resamples"] == 200
    assert first["bca_ci"]["unit"] == "task"
    assert first["seed_sensitivity"]["leave_one_seed_out_preserves_sign"]


def test_default_bootstrap_resamples_is_frozen() -> None:
    assert DEFAULT_BOOTSTRAP_RESAMPLES == 10_000
