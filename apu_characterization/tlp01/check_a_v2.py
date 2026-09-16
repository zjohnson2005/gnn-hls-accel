"""Check A v2: analytical expectations per control × machine (edge taxonomy)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from apu_characterization.tlp01.contracts import TraceEvent, load_protocol
from apu_characterization.tlp01.schedule import simulate_model
from apu_characterization.tlp01.schema import validate_trace_events


def make_sc_emit_parallel_fixture(
    *,
    turn_ns: int = 1_000_000,
    tool_ns: int = 1_000_000,
    k: int = 4,
    session_id: str = "syn-SC-EMIT-fixture",
) -> list[TraceEvent]:
    """Positive structural control: one planning turn + k independent tools."""
    payload: list[dict[str, Any]] = [
        {
            "session_id": session_id,
            "seq": 0,
            "event_type": "turn",
            "t_issue_ns": 0,
            "t_complete_ns": turn_ns,
            "inputs_hash": "goal",
            "output_hash": "plan",
            "output_text_ref": "plan",
            "tool_name": None,
            "args_ref": None,
            "result_ref": None,
            "stage_timings": {"orch_ns": 0},
            "harness_order_index": 0,
            "task_class": "FO",
            "seed": 0,
            "input_text": "",
            "output_text": "",
            "dep_refs": [],
        }
    ]
    cursor = turn_ns
    for index in range(1, k + 1):
        payload.append(
            {
                "session_id": session_id,
                "seq": index,
                "event_type": "tool_call",
                "t_issue_ns": cursor,
                "t_complete_ns": cursor + tool_ns,
                "inputs_hash": f"in-{index}",
                "output_hash": f"out-{index}",
                "output_text_ref": f"out-{index}",
                "tool_name": f"source{index}.search",
                "args_ref": f"args-{index}",
                "result_ref": f"result-{index}",
                "stage_timings": {"orch_ns": 0},
                "harness_order_index": index,
                "task_class": "FO",
                "seed": 0,
                "control_parent_seq": 0,
                "result_ids": [f"RID-{index}"],
                "input_text": f"unique topic {index} alpha",
                "output_text": f"unique topic {index} alpha payload",
                "dep_refs": [],
            }
        )
    return validate_trace_events(payload)

REPO = Path(__file__).resolve().parents[2]
EXPECTATIONS_PATH = Path(__file__).with_name("check_a_v2_expectations.json")
TOLERANCE = 0.05  # G-V-grade ±5%


def _turn_work(events: Sequence[TraceEvent]) -> int:
    return sum(max(e.duration_ns, 1) for e in events if e.event_type == "turn")


def _tool_work(events: Sequence[TraceEvent]) -> int:
    return sum(max(e.duration_ns, 1) for e in events if e.event_type == "tool_call")


def _work_serial(events: Sequence[TraceEvent]) -> int:
    return max(_turn_work(events) + _tool_work(events), 1)


def analytical_m1a_speedup(events: Sequence[TraceEvent]) -> float:
    """Serial data chain + respected SC-EMIT → no reordering; expect 1.0."""
    return 1.0


def analytical_m1b_speedup(events: Sequence[TraceEvent]) -> float:
    """Perfect SC break: turn overlaps the data-serial tool chain.

    makespan = max(turn_work, tool_work) for a single data chain of tools
    (all tools data-chained; only the first is ready with the turn).
    """
    turn = _turn_work(events)
    tools = _tool_work(events)
    work = max(turn + tools, 1)
    makespan = max(turn, tools, 1)
    return work / makespan


def analytical_m1a_parallel_fixture(
    *, turn_ns: int, tool_ns: int, k: int
) -> float:
    """Planning turn + k independent tools; M1a respects SC-EMIT."""
    work = turn_ns + k * tool_ns
    makespan = turn_ns + tool_ns  # tools parallel after turn
    return work / max(makespan, 1)


def analytical_m1b_parallel_fixture(
    *, turn_ns: int, tool_ns: int, k: int
) -> float:
    """M1b breaks SC-EMIT: turn overlaps parallel tools."""
    work = turn_ns + k * tool_ns
    makespan = max(turn_ns, tool_ns)
    return work / max(makespan, 1)


def compute_control_expectations(
    sessions_by_task: dict[str, list[Sequence[TraceEvent]]],
) -> dict[str, Any]:
    """Freeze-ready table: per control × seed × machine analytical speedup."""
    rows: list[dict[str, Any]] = []
    for task_id in ("MT-SER-01", "MT-SER-02"):
        for events in sessions_by_task.get(task_id) or []:
            rows.append(
                {
                    "task_id": task_id,
                    "session_id": events[0].session_id,
                    "seed": int(events[0].seed),
                    "turn_work_ns": _turn_work(events),
                    "tool_work_ns": _tool_work(events),
                    "work_serial_ns": _work_serial(events),
                    "M1a": {
                        "expected_speedup": analytical_m1a_speedup(events),
                        "tolerance": TOLERANCE,
                    },
                    "M1b": {
                        "expected_speedup": analytical_m1b_speedup(events),
                        "tolerance": TOLERANCE,
                    },
                }
            )
    fixture = {
        "name": "synthetic_sc_emit_parallel",
        "turn_ns": 1_000_000,
        "tool_ns": 1_000_000,
        "k": 4,
        "M1a": {
            "expected_speedup": analytical_m1a_parallel_fixture(
                turn_ns=1_000_000, tool_ns=1_000_000, k=4
            ),
            "tolerance": TOLERANCE,
        },
        "M1b": {
            "expected_speedup": analytical_m1b_parallel_fixture(
                turn_ns=1_000_000, tool_ns=1_000_000, k=4
            ),
            "tolerance": TOLERANCE,
        },
    }
    return {
        "protocol_version": load_protocol()["protocol_version"],
        "check": "A_v2",
        "tolerance": TOLERANCE,
        "controls": rows,
        "positive_structural_fixture": fixture,
        "frozen": True,
        "note": (
            "Frozen BEFORE simulator comparison. PASS = empirical within "
            "tolerance of these analytical expectations."
        ),
    }


def freeze_expectations(payload: dict[str, Any], path: Path = EXPECTATIONS_PATH) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_expectations(path: Path = EXPECTATIONS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _within(empirical: float, expected: float, tol: float) -> bool:
    if expected <= 0:
        return abs(empirical - expected) <= tol
    return abs(empirical - expected) / expected <= tol


def evaluate_check_a_v2(
    sessions_by_task: dict[str, list[Sequence[TraceEvent]]],
    *,
    expectations: dict[str, Any] | None = None,
    tier: str = "Tier_S",
) -> dict[str, Any]:
    exp = expectations or load_expectations()
    by_session = {
        row["session_id"]: row for row in exp.get("controls") or []
    }
    results: list[dict[str, Any]] = []
    fail = False
    for task_id in ("MT-SER-01", "MT-SER-02"):
        for events in sessions_by_task.get(task_id) or []:
            sid = events[0].session_id
            row = by_session.get(sid)
            if row is None:
                fail = True
                results.append(
                    {
                        "session_id": sid,
                        "pass": False,
                        "error": "missing frozen expectation",
                    }
                )
                continue
            for model in ("M1a", "M1b"):
                empirical = simulate_model(events, model, tier).speedup
                expected = float(row[model]["expected_speedup"])
                tol = float(row[model].get("tolerance", TOLERANCE))
                ok = _within(empirical, expected, tol)
                if not ok:
                    fail = True
                results.append(
                    {
                        "task_id": task_id,
                        "session_id": sid,
                        "seed": row["seed"],
                        "model": model,
                        "tier": tier,
                        "expected": expected,
                        "empirical": empirical,
                        "tolerance": tol,
                        "pass": ok,
                    }
                )
    fixture = exp["positive_structural_fixture"]
    syn = make_sc_emit_parallel_fixture(
        turn_ns=int(fixture["turn_ns"]),
        tool_ns=int(fixture["tool_ns"]),
        k=int(fixture["k"]),
    )
    for model in ("M1a", "M1b"):
        empirical = simulate_model(syn, model, "Tier_S").speedup
        expected = float(fixture[model]["expected_speedup"])
        tol = float(fixture[model].get("tolerance", TOLERANCE))
        ok = _within(empirical, expected, tol)
        if not ok:
            fail = True
        results.append(
            {
                "task_id": fixture["name"],
                "session_id": syn[0].session_id,
                "seed": 0,
                "model": model,
                "tier": "Tier_S",
                "expected": expected,
                "empirical": empirical,
                "tolerance": tol,
                "pass": ok,
            }
        )
    return {
        "status": "FAIL" if fail else "PASS",
        "tolerance": TOLERANCE,
        "rows": results,
        "expectations_path": str(EXPECTATIONS_PATH),
    }
