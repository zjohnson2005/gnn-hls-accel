from __future__ import annotations

from apu_characterization.cap01.audit import (
    audit_accounting,
    audit_budget_integrity,
    audit_candidate_matching,
    audit_replication,
    audit_throughput_consistency,
    audit_verifier_determinism,
)


def _event(candidate_id: str, index: int, *, solved: bool = False) -> dict:
    return {
        "sequence_index": index,
        "candidate_id": candidate_id,
        "latency_ns": 10_000_000,
        "verifier_wall_ns": 1_000_000,
        "counted": True,
        "abandoned": False,
        "solved": solved,
        "verdict_digest": f"verdict-{solved}",
    }


def _cell(seed: int = 0, harness: str = "rust") -> dict:
    return {
        "cell_id": f"{harness}-{seed}",
        "task_id": "task-1",
        "seed": seed,
        "harness": harness,
        "latency_scale_ms": 5,
        "wall_budget_ms": 2_000,
        "budget_ns": 2_000_000_000,
        "elapsed_ns": 12_000_000,
        "process_cpu_ns": 100_000,
        "accounted_cpu_ns": 86_000,
        "residual_cpu_ns": 14_000,
        "host_measured_floor_ns": 1_000_000,
        "candidate_events": [_event("a", 0)],
    }


def test_g1_requires_below_15_percent_and_conservation() -> None:
    assert audit_accounting(_cell())["pass"]
    at_limit = {**_cell(), "accounted_cpu_ns": 85_000, "residual_cpu_ns": 15_000}
    assert not audit_accounting(at_limit)["pass"]
    broken = {**_cell(), "accounted_cpu_ns": 50_000}
    assert not audit_accounting(broken)["pass"]


def test_g2_retains_overshoot_and_applies_global_one_percent_limit() -> None:
    cells = [_cell() for _ in range(100)]
    cells[0] = {**cells[0], "elapsed_ns": 2_040_000_001}
    one_percent = audit_budget_integrity(cells)
    assert one_percent["pass"]
    assert len(one_percent["violations"]) == 1
    cells[1] = {**cells[1], "elapsed_ns": 2_040_000_001}
    assert not audit_budget_integrity(cells)["pass"]

    broken = {**_cell(), "started": 2, "counted": 1, "abandoned": 0}
    assert not audit_budget_integrity([broken])["pass"]


def test_g3_requires_seed_and_cross_harness_prefixes() -> None:
    short = _cell(harness="rust")
    long = {
        **_cell(harness="langgraph"),
        "candidate_events": [_event("a", 0), _event("b", 1)],
    }
    ordering = {("task-1", 0): ["a", "b", "c"]}
    assert audit_candidate_matching([short, long], ordering)["pass"]
    mismatch = {
        **long,
        "candidate_events": [_event("a", 0), _event("c", 1)],
    }
    assert not audit_candidate_matching([short, mismatch], ordering)["pass"]
    assert not audit_candidate_matching(
        [{**short, "pool_exhausted": True}], ordering
    )["pass"]


def test_g4_reexecutes_once_and_removes_flipped_task_globally() -> None:
    cells = [_cell(), {**_cell(), "cell_id": "second"}]
    calls: list[str] = []

    def rerun(record: dict) -> dict:
        calls.append(record["cell"])
        return {"solved": record["cell"] == "second", "verdict_digest": "verdict-False"}

    result = audit_verifier_determinism(cells, rerun)
    assert calls == ["rust-0", "second"]
    assert not result["pass"]
    assert result["removed_task_ids"] == ["task-1"]
    assert len(result["ledger"]) == 2
    assert result["ledger"][1]["flipped"]


def test_g5_requires_exactly_five_present_seeds_per_required_cell() -> None:
    cells = [_cell(seed) for seed in range(5)]
    required = [_cell(0)]
    assert audit_replication(cells, required_cells=required)["pass"]
    assert not audit_replication(cells[:-1], required_cells=required)["pass"]
    assert not audit_replication(cells + [_cell(4)], required_cells=required)["pass"]


def test_g7_denominator_uses_latency_floor_and_verifier_wall() -> None:
    result = audit_throughput_consistency(_cell())
    assert result["pass"]
    assert result["denominator"] == {
        "actual_latency_draw_ns": 10_000_000.0,
        "host_measured_harness_floor_ns": 1_000_000.0,
        "measured_verifier_wall_ns": 1_000_000.0,
    }
    assert not audit_throughput_consistency(
        {**_cell(), "candidates_per_second": 10}
    )["pass"]
