from __future__ import annotations

import json

from apu_characterization.cap01.report import append_died_claim, render_report


def _aggregate() -> dict:
    primary = {
        "n_task_seed_pairs": 10,
        "first_solve_rate": 0.4,
        "second_solve_rate": 0.7,
        "difference_pp": -30.0,
        "bca_ci": {"low_pp": -50.0, "high_pp": -10.0, "resamples": 10000},
        "mcnemar": {"p_value": 0.03125, "discordant": 6},
        "seed_sensitivity": {
            "leave_one_seed_out_preserves_sign": True,
            "leave_one_seed_out_difference_pp": {"0": -25.0, "1": -35.0},
        },
    }
    return {
        "protocol_version": "cap01_v2.2",
        "source_artifact_count": 1,
        "task_cell_count": 30,
        "promotion_summary": (
            "CAP-01 rung 1 earned within the frozen primary scope: "
            "5ms model latency, domain-primary tiers, SCALING tasks pooled "
            "across five domains, LangGraph versus rust."
        ),
        "claim_rung": {
            "name": "rung_1",
            "protocol_language": (
                "primary significant in predicted direction; 4000ms null holds; "
                "G3, G6, G7 clean"
            ),
        },
        "headline_blocked": False,
        "primary_result": primary,
        "positive_control": {
            "expected": "no_harness_separation",
            "tests_evaluated": 4,
            "tests_expected": 4,
            "holds": True,
            "failures": [],
        },
        "statistics": [],
        "secondary_results": [],
        "capability_floor_fit": {
            "label": "DESCRIPTIVE ONLY, THREE MEASURED X POINTS, NON-INFERENTIAL",
            "points": [],
        },
        "gate_matrix": {
            f"G{index}": {
                "evaluated": True,
                "pass": True,
                "errors": [],
            }
            for index in range(1, 9)
        },
        "classification_counts": {
            "SCALING": 2,
            "SATURATED": 1,
            "DEAD": 1,
            "ALL": 4,
        },
        "abandonment_tails": [],
        "expectation_actual_vs_predicted": [],
    }


def test_report_contains_required_scope_gates_and_projection_language() -> None:
    report = render_report(_aggregate())
    assert "## Gate matrix" in report
    assert "## Classification counts" in report
    assert "## Abandonment tails" in report
    assert "## Expectation: actual versus predicted" in report
    assert (
        "Tier D design target - projection from measured relationship, not a "
        "result. Promotion path: csynth."
    ) in report
    assert "SCALING tasks pooled across all five domains" in report
    assert "Praetor" not in report
    assert "achieves" not in report


def test_positive_control_failure_has_stop_language() -> None:
    aggregate = _aggregate()
    aggregate["headline_blocked"] = True
    aggregate["positive_control"]["holds"] = False
    report = render_report(aggregate)
    assert "STOP BEFORE HEADLINE FOR DIAGNOSIS" in report


def test_died_ledger_is_append_only(tmp_path) -> None:
    path = tmp_path / "died_ledger.json"
    first = append_died_claim(path, claim="claim one", reason="reason one")
    second = append_died_claim(
        path,
        claim="claim two",
        reason="reason two",
        evidence=["artifact.json"],
    )
    ledger = json.loads(path.read_text(encoding="utf-8"))
    assert first["id"] == 1
    assert second["id"] == 2
    assert [entry["claim"] for entry in ledger["entries"]] == [
        "claim one",
        "claim two",
    ]
