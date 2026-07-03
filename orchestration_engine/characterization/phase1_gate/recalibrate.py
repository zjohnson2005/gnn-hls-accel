"""Recalibrate mock timing from the real OpenAI ladder (trace-anchored mocks).

Derives steady-state per-decision cost and per-session setup cost from real
gate traces and writes them into calibration_{preset}.json, then clears cached
mock traces so the next gate run regenerates them with real constants.

Run:  py -3 -m orchestration_engine.characterization.phase1_gate.recalibrate
"""

from __future__ import annotations

import statistics
from pathlib import Path

from orchestration_engine.characterization.langgraph_react.timing import (
    calibration_path,
    save_calibration,
    timing_for_preset,
)
from orchestration_engine.characterization.taxonomy import Bucket
from orchestration_engine.characterization.trace_io import load_trace

GATE_DIR = Path("orchestration_engine/characterization/out/gate")

# Parallel --fast ladder anchors; c=1 excluded (3 spans, noise).
SOURCE_LEVELS = [10, 20, 100, 500]


def _setup_steady_durations(profile) -> tuple[list[int], list[int]]:
    per_agent: dict[str, list] = {}
    for s in profile.spans:
        if s.bucket == Bucket.CPU_ORCHESTRATION:
            per_agent.setdefault(s.agent_id, []).append(s)
    setup, steady = [], []
    for spans in per_agent.values():
        spans.sort(key=lambda x: x.start_us)
        setup.append(spans[0].duration_us)
        steady.extend(x.duration_us for x in spans[1:])
    return setup, steady


def recalibrate(preset: str = "action_heavy") -> Path | None:
    setup_all: list[int] = []
    steady_all: list[int] = []
    used = []
    for c in SOURCE_LEVELS:
        path = GATE_DIR / f"openai_action_heavy_c{c}.json"
        if not path.is_file():
            continue
        prof = load_trace(path)
        if prof.meta.get("orch_measurement") != "wall_residual":
            continue
        setup, steady = _setup_steady_durations(prof)
        setup_all.extend(setup)
        steady_all.extend(steady)
        used.append(c)

    if not steady_all:
        print("No wall_residual traces found - run the OpenAI ladder first.")
        return None

    steady_med = int(statistics.median(steady_all))
    setup_med = int(statistics.median(setup_all))

    timing = timing_for_preset(preset, calibrated=False)
    from dataclasses import replace

    # Keep the live-task penalty as a structural parameter; anchor the constants.
    timing = replace(
        timing,
        orchestration_per_step_us=steady_med,
        orchestration_setup_us=max(0, setup_med - steady_med),
    )

    path = calibration_path(preset)
    save_calibration(
        path,
        preset,
        timing,
        bucket_us={},
        meta={
            "source": "real OpenAI ladder (wall_residual, parallel --fast)",
            "levels": ",".join(str(c) for c in used),
            "steady_median_us": str(steady_med),
            "setup_median_us": str(setup_med),
            "n_steady_spans": str(len(steady_all)),
            "n_setup_spans": str(len(setup_all)),
        },
    )
    print(
        f"Calibrated {preset}: steady {steady_med} us/decision, "
        f"setup +{max(0, setup_med - steady_med)} us (median of {len(steady_all)} / "
        f"{len(setup_all)} spans from c={used})"
    )
    print(f"Wrote {path.resolve()}")

    stale = sorted(GATE_DIR.glob("mock_*.json"))
    for p in stale:
        p.unlink()
    print(f"Cleared {len(stale)} cached mock traces - next gate run regenerates them.")
    return path


if __name__ == "__main__":
    recalibrate()
