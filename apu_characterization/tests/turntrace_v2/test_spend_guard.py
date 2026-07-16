from __future__ import annotations

import json
from pathlib import Path

import pytest

from apu_characterization.turntrace_v2.spend_guard import (
    BudgetLock,
    SpendCeilingExceeded,
)


def test_budget_lock_loads_and_rejects_over_ceiling(tmp_path: Path) -> None:
    src = Path("apu_characterization/turntrace_v2/budget_lock.json")
    raw = json.loads(src.read_text(encoding="utf-8"))
    # Artificially low ceiling to prove hard stop
    raw["totals"]["hard_ceiling_usd"] = 0.001
    low = tmp_path / "budget_lock_low.json"
    low.write_text(json.dumps(raw), encoding="utf-8")
    lock = BudgetLock.load(low)
    planned = lock.estimate_run_usd(
        cell_id="C1", n_trajectories=10, harnesses=2, turns_per_traj=6.0
    )
    assert planned > 0.001
    with pytest.raises(SpendCeilingExceeded):
        lock.assert_under_ceiling(planned_usd=planned, spent_usd=0.0, allow_override=False)
    # Override path allowed
    lock.assert_under_ceiling(planned_usd=planned, spent_usd=0.0, allow_override=True)


def test_real_budget_lock_filled() -> None:
    lock = BudgetLock.load(Path("apu_characterization/turntrace_v2/budget_lock.json"))
    assert lock.projected_usd > 0
    assert lock.hard_ceiling_usd >= lock.projected_usd
    assert lock.cell("C1")["n_trajectories"] >= 10
    assert "FILL" not in lock.cell("C1")["model_id"]
