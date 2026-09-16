"""Hard replication-floor gate: sparse task_ids never enter primary bands."""

from __future__ import annotations

from apu_characterization.tlp01.analyze import analyze_experiment, speedup_bands
from apu_characterization.tlp01.extract import make_synthetic_parallel_session
from apu_characterization.tlp01.labels import DATA_SOURCE_SYNTHETIC
from apu_characterization.tlp01.replication_floor import (
    partition_by_replication_floor,
)


def _sessions_for_task(task_id: str, seeds: list[int], *, width: int = 3):
    out = []
    for seed in seeds:
        # Real-trace-shaped ids so infer_task_id yields task_id.
        sid = f"S1-{task_id}-s{seed}"
        out.append(
            make_synthetic_parallel_session(
                session_id=sid, task_class=task_id.split("-")[0], seed=seed, width=width
            )
        )
    return out


def test_partition_excludes_sparse_task_ids() -> None:
    sessions = (
        _sessions_for_task("EL-01", [0, 1, 2, 3, 4])
        + _sessions_for_task("SP-01", [0, 1])  # n=2 sparse
    )
    part = partition_by_replication_floor(sessions, required_seeds=5)
    assert part["behavior"] == "exclusion_with_separate_section"
    eligible_ids = {row["task_id"] for row in part["eligible_task_ids"]}
    sparse_ids = {row["task_id"] for row in part["sparse_task_ids"]}
    assert eligible_ids == {"EL-01"}
    assert sparse_ids == {"SP-01"}
    assert len(part["eligible_sessions"]) == 5
    assert len(part["sparse_sessions"]) == 2


def test_speedup_bands_exclude_n2_task_id() -> None:
    sessions = (
        _sessions_for_task("EL-01", [0, 1, 2, 3, 4])
        + _sessions_for_task("SP-01", [0, 1])
    )
    bands = speedup_bands(sessions, model="M1a", enforce_replication_floor=True)
    assert "EL-01" in bands
    assert "SP-01" not in bands


def test_analyze_experiment_sparse_section_only() -> None:
    sessions = (
        _sessions_for_task("EL-01", [0, 1, 2, 3, 4])
        + _sessions_for_task("SP-01", [0, 1])
    )
    aggregate = analyze_experiment(
        sessions, include_frontier=False, data_source=DATA_SOURCE_SYNTHETIC
    )
    assert "SP-01" not in aggregate["m1a_speedup_bands"]
    assert "EL-01" in aggregate["m1a_speedup_bands"]
    sparse = aggregate["sparse_descriptive"]
    assert sparse["section"] == "single_seed_descriptive_not_banded"
    obs_ids = {row["task_id"] for row in sparse["m1a_observations"]}
    assert obs_ids == {"SP-01"}
    assert all(row["banded"] is False for row in sparse["m1a_observations"])
    assert all(
        "below replication floor" in row["tag"]
        for row in sparse["m1a_observations"]
    )
    inv = {
        row["task_id"]: row["n"]
        for row in aggregate["replication_floor"]["sparse_task_ids"]
    }
    assert inv == {"SP-01": 2}
