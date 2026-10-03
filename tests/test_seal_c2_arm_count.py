"""seal_c2_ttft takes the arm count from plan.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.seal_c2_ttft import require_matching_arms  # noqa: E402

C2 = ROOT / "derived" / "c2_ttft"


def _load(run_id: str, name: str) -> dict:
    return json.loads((C2 / run_id / name).read_text(encoding="utf-8-sig"))


def test_one_arm_control_matches_its_plan() -> None:
    run_id = "c76fed24-63a9-4b3b-98be-11ff83da7a4c"
    arms = require_matching_arms(_load(run_id, "plan.json"), _load(run_id, "summary.json"))
    assert arms == ["gpu_only_f16"]


def test_three_arm_cell_matches_its_plan() -> None:
    run_id = "62395fdb-1899-415f-b708-6adc81a24dda"
    arms = require_matching_arms(_load(run_id, "plan.json"), _load(run_id, "summary.json"))
    assert arms == ["gpu_only_f16", "gpu_only_u8", "gpu_only_u4"]


def test_plan_summary_arm_mismatch_refuses() -> None:
    plan = {"arms": ["gpu_only_f16", "gpu_only_u8", "gpu_only_u4"]}
    summary = {"arm_results": [{"arm_id": "gpu_only_f16"}]}
    with pytest.raises(SystemExit, match="plan/summary arm mismatch"):
        require_matching_arms(plan, summary)
