from __future__ import annotations

from copy import deepcopy

from apu_characterization.cap01.analyze import (
    analyze_artifacts,
    normalize_task_cells,
)
from apu_characterization.cap01.contracts import load_protocol


def _fixture() -> tuple[list[dict], dict]:
    protocol = load_protocol()
    protocol["latency_backend"]["median_scales_ms"] = [4000, 5]
    cells = []
    floors = {"langgraph": 5.0, "rust": 0.8, "raw_python": 0.22}
    domains = list(protocol["statistics"]["primary_cell"]["domains"])
    for scale in (4000, 5):
        for budget in (2000, 10000):
            for domain in domains:
                for task_index in range(4):
                    task_id = f"{domain}-{task_index}"
                    for seed in range(5):
                        for harness in ("langgraph", "rust", "raw_python"):
                            solved = (
                                True if scale == 4000 else harness != "langgraph"
                            )
                            cells.append(
                                {
                                    "task_id": task_id,
                                    "task_class": "SCALING",
                                    "domain": domain,
                                    "harness": harness,
                                    "latency_scale_ms": scale,
                                    "wall_budget_ms": budget,
                                    "seed": seed,
                                    "solved": solved,
                                    "host_measured_floor_ms": floors[harness],
                                    "measured_verifier_wall_ms": 0.1,
                                    "candidates_started": 1,
                                    "abandoned_count": 0,
                                }
                            )
    gates = {
        f"G{index}": {"pass": True, "errors": []}
        for index in range(1, 9)
    }
    return [{"task_cells": cells, "audit": {"gates": gates}}], protocol


def test_analysis_derives_primary_secondary_controls_and_fit() -> None:
    artifacts, protocol = _fixture()
    before = deepcopy(artifacts)
    aggregate = analyze_artifacts(
        artifacts,
        protocol=protocol,
        bootstrap_resamples=100,
        bootstrap_seed=11,
    )
    assert artifacts == before
    assert aggregate["primary_result"]["difference_pp"] == -100.0
    assert aggregate["primary_result"]["mcnemar"]["p_value"] < 0.05
    assert aggregate["positive_control"]["holds"]
    assert aggregate["claim_rung"]["name"] == "rung_1"
    assert aggregate["classification_counts"] == {
        "SCALING": 20,
        "SATURATED": 0,
        "DEAD": 0,
        "ALL": 20,
        "by_domain": {
            domain: {"SCALING": 4, "SATURATED": 0, "DEAD": 0, "ALL": 4}
            for domain in protocol["statistics"]["primary_cell"]["domains"]
        },
    }
    assert aggregate["capability_floor_fit"]["fit"]["n_x_points"] == 3
    assert len(aggregate["capability_floor_fit"]["residuals"]) == 3
    populations = {cell["population"] for cell in aggregate["statistics"]}
    assert populations == {"SCALING", "ALL"}
    assert len(aggregate["secondary_results"]) == 17
    assert all("holm" in cell for cell in aggregate["secondary_results"])


def test_positive_control_failure_blocks_headline() -> None:
    artifacts, protocol = _fixture()
    for row in artifacts[0]["task_cells"]:
        if row["latency_scale_ms"] == 4000 and row["harness"] == "langgraph":
            row["solved"] = False
    aggregate = analyze_artifacts(
        artifacts,
        protocol=protocol,
        bootstrap_resamples=50,
    )
    assert not aggregate["positive_control"]["holds"]
    assert aggregate["headline_blocked"]
    assert aggregate["promotion_summary"].startswith("Headline blocked.")


def test_primary_requires_all_five_domains() -> None:
    artifacts, protocol = _fixture()
    missing = protocol["statistics"]["primary_cell"]["domains"][0]
    artifacts[0]["task_cells"] = [
        row for row in artifacts[0]["task_cells"] if row["domain"] != missing
    ]
    aggregate = analyze_artifacts(
        artifacts,
        protocol=protocol,
        bootstrap_resamples=50,
    )
    assert aggregate["primary_result"] is None
    assert aggregate["headline_blocked"]


def test_normalizes_immutable_runner_result_with_external_class_and_floor() -> None:
    runner_result = {
        "task_id": "t1",
        "coordinates": {
            "harness": "rust",
            "latency_scale_ms": 5,
            "wall_budget_ms": 10000,
            "seed": 0,
        },
        "solved": True,
        "started": 1,
        "counted": 1,
        "abandoned": 0,
        "candidate_events": [
            {
                "counted": True,
                "abandoned": False,
                "solved": True,
                "latency_ns": 5_000_000,
                "verifier_wall_ns": 100_000,
            }
        ],
    }
    classification = {"tasks": [{"task_id": "t1", "task_class": "SCALING"}]}
    audit = {
        "gates": {
            "G6": {
                "harnesses": {
                    "rust": {
                        "measured_floor_ns": 800_000,
                        "x_coordinate_ns": 800_000,
                    }
                }
            }
        }
    }
    rows = normalize_task_cells([runner_result, classification, audit])
    assert len(rows) == 1
    assert rows[0]["task_class"] == "SCALING"
    assert rows[0]["actual_candidates"] == 1
    assert rows[0]["host_measured_floor_ms"] == 0.8
    assert rows[0]["latency_draw_wall_ms"] == 5.0
    assert rows[0]["measured_verifier_wall_ms"] == 0.1
