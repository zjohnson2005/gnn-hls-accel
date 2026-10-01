"""Score sealed-source P1 A0 points. Does not start a measurement."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
A0_ID = "8a529053-fc47-486d-8809-6c699d156b06"
D482_ID = "d482c621-4292-4281-b6a1-8635e5eeb6da"
K_COUNTS = {0: 38, 1: 30, 2: 40, 4: 92}
EMPTY_N = 46
EXEC_N = 35
SLOW_IDS = (
    "multi_turn_base_60",
    "multi_turn_base_77",
    "multi_turn_base_88",
    "multi_turn_base_114",
    "multi_turn_base_169",
    "multi_turn_base_179",
    "multi_turn_base_193",
)


def pass_at_k_ceiling(baseline: int, k_counts: dict[int, int], n: int = 200) -> float:
    """Sum of 1-(1-baseline/n)^k. This is any-sample-correct, not a majority vote."""
    rate = baseline / n
    return sum(count * (1.0 - (1.0 - rate) ** k) for k, count in sorted(k_counts.items()))


def rate_arm(baseline: int, eligible: int, n: int = 200) -> float:
    """Baseline plus one extra sample on each eligible trajectory at the baseline rate."""
    return baseline + eligible * baseline / n


def _read(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} is not an object")
    return data


def a0_points(root: Path = ROOT) -> list[dict[str, Any]]:
    directory = root / "derived" / "p1_quality" / A0_ID / "points"
    return [_read(path) for path in sorted(directory.glob("*.json"))]


def step_stats(points: list[dict[str, Any]]) -> dict[str, Any]:
    steps = [step for point in points for step in point["steps"]]
    ttas = [float(step["tta_s"]) for step in steps]
    fallback = [step for step in steps if step.get("fallback")]
    return {
        "n_steps": len(steps),
        "n_fallback": len(fallback),
        "n_fallback_on_in_budget_pass": sum(
            1
            for point in points
            if point["in_budget_pass"]
            for step in point["steps"]
            if step.get("fallback")
        ),
        "n_tta_gt_10": sum(1 for value in ttas if value > 10.0),
        "max_tta_s": max(ttas),
        "median_tta_s": float(statistics.median(ttas)),
        "p90_tta_s": float(statistics.quantiles(ttas, n=10, method="inclusive")[8]),
        "p90_method": "statistics.quantiles(data, n=10, method='inclusive')[8]",
    }


def paired_local_pass(root: Path = ROOT) -> dict[str, Any]:
    h1 = _read(root / "derived" / "h1_hybrid" / "analysis_d482c621" / "H1_3POLICY_RESULTS.json")
    local = {
        str(row["entry_id"])
        for row in h1["per_entry"]
        if row["policy"] == "slo_escalate" and row["local_pass"]
    }
    a0 = {str(point["id"]) for point in a0_points(root) if point["in_budget_pass"]}
    return {
        "d482_run_id": D482_ID,
        "d482_local_pass": len(local),
        "a0_in_budget_pass": len(a0),
        "both": len(a0 & local),
        "only_a0": sorted(a0 - local),
        "only_d482": sorted(local - a0),
        "entries_that_differ": len(a0 ^ local),
    }


def slow_recount(root: Path = ROOT) -> list[dict[str, Any]]:
    ledger = _read(
        root
        / "derived"
        / "h1_hybrid"
        / f"interleaved_{D482_ID}"
        / "policies"
        / "slo_escalate"
        / "turn_ledger.json"
    )
    points = {str(point["id"]): point for point in a0_points(root)}
    rows: list[dict[str, Any]] = []
    for entry in ledger["entries"]:
        entry_id = str(entry["entry_id"])
        if entry_id not in SLOW_IDS:
            continue
        local_turns = [
            turn
            for turn in entry["turns"]
            if turn.get("placement") == "local" and not turn.get("escalated")
        ]
        point = points[entry_id]
        rows.append(
            {
                "entry_id": entry_id,
                "max_t_generate_s": max(float(turn["t_generate"]) for turn in local_turns),
                "a0_in_budget_pass": bool(point["in_budget_pass"]),
                "a0_n_steps": len(point["steps"]),
                "a0_n_fallback": sum(1 for step in point["steps"] if step.get("fallback")),
                "a0_max_tta_s": max(float(step["tta_s"]) for step in point["steps"]),
            }
        )
    return rows


def kv_quote(path: Path) -> dict[str, Any]:
    cell = _read(path)["cell"]
    device = cell["device_config"]
    readback = cell["kv_cache_precision_readback"][0]["readback"]
    return {
        "arm_id": device["arm_id"],
        "arm_properties": device["arm_properties"],
        "label": device["label"],
        "readback_normalized": readback["normalized"],
        "readback_raw": readback["raw"],
    }
