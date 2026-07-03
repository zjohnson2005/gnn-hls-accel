"""Wall-clock calibration of mock timing presets from measured LangGraph spans."""

from __future__ import annotations

from pathlib import Path

from orchestration_engine.characterization.langgraph_react.agent import (
    _count_stream_steps,
    run_session,
)
from orchestration_engine.characterization.langgraph_react.timing import (
    calibration_path,
    PRESETS,
    apply_measured_to_preset,
    save_calibration,
)
from orchestration_engine.characterization.taxonomy import Bucket


def calibrate_preset(
    preset: str = "action_heavy",
    seed: int = 42,
    calibrate_steps: int = 4,
    output: Path | None = None,
) -> Path:
    """Run one wall-clock mock session and write calibration JSON."""
    if output is None:
        output = calibration_path(preset)

    profile = run_session(
        preset=preset,
        backend="mock",
        seed=seed,
        wall_clock=True,
        calibrated=False,
        react_steps_override=calibrate_steps,
    )

    totals = profile.bucket_totals_us()
    bucket_us = {b.value: totals[b] for b in Bucket}
    steps = max(1, _count_stream_steps(profile))
    timing = apply_measured_to_preset(preset, bucket_us, steps)

    save_calibration(
        output,
        preset=preset,
        timing=timing,
        bucket_us=bucket_us,
        meta={
            "method": "wall_clock_mock",
            "calibrate_steps": str(calibrate_steps),
            "stream_steps": str(steps),
        },
    )
    return output
