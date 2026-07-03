"""Timing presets + calibration load/save."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

CALIBRATION_DIR = Path("orchestration_engine/characterization/out")


def calibration_path(preset: str) -> Path:
    return CALIBRATION_DIR / f"calibration_{preset}.json"


@dataclass
class AgentTiming:
    gpu_prefill_us: int = 80_000
    gpu_decode_us: int = 2_000_000
    tool_io_mean_us: int = 1_000_000
    tool_io_jitter_us: int = 500_000
    parse_request_us: int = 800
    parse_response_us: int = 2_000
    tokenize_us: int = 400
    state_update_us: int = 1_500
    react_steps: int = 8
    orchestration_per_step_us: int = 180
    orchestration_live_task_penalty_us: int = 12
    # One-time per-session graph/session init (first orchestration step extra).
    orchestration_setup_us: int = 0


PRESETS: dict[str, AgentTiming] = {
    "action_heavy": AgentTiming(
        gpu_prefill_us=60_000,
        gpu_decode_us=900_000,
        tool_io_mean_us=1_200_000,
        tool_io_jitter_us=800_000,
        react_steps=10,
    ),
    "reasoning_heavy": AgentTiming(
        gpu_prefill_us=180_000,
        gpu_decode_us=4_500_000,
        tool_io_mean_us=120_000,
        tool_io_jitter_us=80_000,
        react_steps=6,
    ),
    "balanced": AgentTiming(),
}


def save_calibration(
    path: Path,
    preset: str,
    timing: AgentTiming,
    bucket_us: dict[str, int],
    meta: dict[str, str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "preset": preset,
        "timing": asdict(timing),
        "measured_bucket_us": bucket_us,
        "meta": meta,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_calibration(preset: str) -> dict | None:
    path = calibration_path(preset)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def timing_for_preset(preset: str, calibrated: bool = False) -> AgentTiming:
    base = PRESETS[preset]
    if not calibrated:
        return base

    data = load_calibration(preset)
    if not data:
        return base

    merged = asdict(base)
    for key, val in data.get("timing", {}).items():
        if key in merged and isinstance(val, int):
            merged[key] = val
    return AgentTiming(**merged)


def apply_measured_to_preset(preset: str, measured: dict[str, int], step_count: int) -> AgentTiming:
    """Build calibrated timing from wall-clock bucket totals."""
    base = PRESETS[preset]
    steps = max(1, step_count)
    tool_io = measured.get("cpu_io_wait", 0)
    # Subtract estimated LLM remote time if present in io bucket during calib
    gpu = measured.get("gpu_inference", 0)
    orch = measured.get("cpu_orchestration", 0)

    tool_steps = max(1, steps // 2)
    return AgentTiming(
        gpu_prefill_us=max(10_000, gpu // max(1, steps * 2)),
        gpu_decode_us=max(50_000, gpu // max(1, steps)),
        tool_io_mean_us=max(10_000, tool_io // tool_steps),
        tool_io_jitter_us=max(0, base.tool_io_jitter_us // 4),
        parse_request_us=max(100, measured.get("cpu_parse", 0) // max(1, tool_steps * 2)),
        parse_response_us=max(100, measured.get("cpu_parse", 0) // max(1, tool_steps * 2)),
        tokenize_us=max(100, measured.get("cpu_tokenize", 0) // steps),
        state_update_us=max(100, measured.get("cpu_state", 0) // tool_steps),
        react_steps=base.react_steps,
        orchestration_per_step_us=max(50, orch // steps),
        orchestration_live_task_penalty_us=base.orchestration_live_task_penalty_us,
    )
