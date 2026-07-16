from __future__ import annotations

from apu_characterization.turntrace_v2.budget import CellBudget, render_budget_table
from apu_characterization.turntrace_v2.collect_cloud import collect_cell
from apu_characterization.turntrace_v2.workload.swebench_lite import write_fixture_subset


def test_budget_table_blocks_unpriced() -> None:
    report = render_budget_table()
    assert report["floor_n_trajectories"] == 10
    assert all(c["status"] == "blocked_on_price_quote" for c in report["cells"])
    priced = CellBudget(
        cell_id="C1",
        model_id="m",
        harnesses=2,
        cache_modes=1,
        n_trajectories=10,
        mean_tokens_in=1000,
        mean_tokens_out=100,
        usd_per_1m_in=1.0,
        usd_per_1m_out=2.0,
    )
    est = priced.estimate_usd(turns_per_traj=8.0)
    assert est["usd_total"] > 0


def test_collect_cloud_mock_both_harnesses(tmp_path) -> None:
    subset = write_fixture_subset(tmp_path / "subset.json", n=2)
    report = collect_cell(
        out_dir=tmp_path / "cell",
        cell_id="C1",
        model_id="mock-model",
        n_trajectories=2,
        subset_path=subset,
        live=False,
        base_url="http://unused",
        api_key=None,
        network_baseline_ms=10.0,
        n_turns=3,
    )
    assert report["live"] is False
    assert report["harness_counts"]["raw_python"] == 2
    assert report["harness_counts"]["langgraph"] == 2
    assert report["n_trajectory_records"] == 4
    assert (tmp_path / "cell" / "collect_report.json").is_file()
    assert (tmp_path / "cell" / "corpus" / "SCHEMA.md").is_file() or (
        tmp_path / "cell" / "corpus"
    ).is_dir()
