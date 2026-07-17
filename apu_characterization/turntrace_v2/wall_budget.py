"""Pre-launch CPU wall-clock projection for rev C G-BUDGET-WALL."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from apu_characterization.turntrace_v2.workload.rev_c_suite import TASK_CLASSES


@dataclass(frozen=True)
class CpuWallProjection:
    schema_version: str
    model_id: str
    quantization: str
    engine: str
    hardware: str
    seeds: int
    harnesses: int
    include_ablations: bool
    total_calls: int
    projected_prefill_ms: float
    projected_prefill_hours: float
    wall_multiplier: float
    projected_wall_hours: float
    exceeds_24h: bool
    target_kind: str
    prefill_profile_sha256: str | None
    protocol_sha256: str | None
    payload_manifest_sha256: str | None
    profile_r2_passed: bool
    assumptions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def linear_context_schedule(final_tokens: int, turns: int) -> list[int]:
    return [
        max(1, round(final_tokens * (turn + 1) / turns))
        for turn in range(turns)
    ]


def project_cpu_wall(
    f_prefill: Callable[[int], float],
    *,
    model_id: str,
    quantization: str,
    engine: str,
    hardware: str,
    seeds: int = 5,
    harnesses: int = 2,
    include_ablations: bool = True,
    ablation_classes: Sequence[str] = ("TT-EDIT", "TT-RET"),
    wall_multiplier: float = 1.20,
    target_kind: str = "cpu_prebox",
    prefill_profile_sha256: str | None = None,
    protocol_sha256: str | None = None,
    payload_manifest_sha256: str | None = None,
    profile_r2_passed: bool = False,
) -> CpuWallProjection:
    if target_kind not in {"cpu_prebox", "box"}:
        raise ValueError("target_kind must be cpu_prebox or box")
    if seeds <= 0 or harnesses <= 0:
        raise ValueError("seeds and harnesses must be positive")
    per_trajectory_ms: dict[str, float] = {}
    per_trajectory_calls: dict[str, int] = {}
    for name, spec in TASK_CLASSES.items():
        final = (
            spec.cpu_target_tokens
            if target_kind == "cpu_prebox"
            else spec.box_target_tokens
        )
        schedule = linear_context_schedule(final, spec.turns)
        per_trajectory_ms[name] = sum(max(0.0, float(f_prefill(n))) for n in schedule)
        per_trajectory_calls[name] = len(schedule)

    # Full-stack A/B is two trajectories per seed/harness for all classes.
    multiplier = seeds * harnesses
    total_ms = 2 * multiplier * sum(per_trajectory_ms.values())
    total_calls = 2 * multiplier * sum(per_trajectory_calls.values())
    if include_ablations:
        # Each ablation is itself paired against Arm A. Local C-P2 requires
        # B-CACHE-only and B-APPEND+B-LAYOUT on at least two classes.
        for name in ablation_classes:
            if name not in TASK_CLASSES:
                raise ValueError(f"unknown ablation class: {name}")
            total_ms += 4 * multiplier * per_trajectory_ms[name]
            total_calls += 4 * multiplier * per_trajectory_calls[name]

    prefill_hours = total_ms / 3_600_000.0
    wall_hours = prefill_hours * wall_multiplier
    return CpuWallProjection(
        schema_version="turntrace_rev_c_cpu_wall_v1",
        model_id=model_id,
        quantization=quantization,
        engine=engine,
        hardware=hardware,
        seeds=seeds,
        harnesses=harnesses,
        include_ablations=include_ablations,
        total_calls=total_calls,
        projected_prefill_ms=total_ms,
        projected_prefill_hours=prefill_hours,
        wall_multiplier=wall_multiplier,
        projected_wall_hours=wall_hours,
        exceeds_24h=wall_hours > 24.0,
        target_kind=target_kind,
        prefill_profile_sha256=prefill_profile_sha256,
        protocol_sha256=protocol_sha256,
        payload_manifest_sha256=payload_manifest_sha256,
        profile_r2_passed=profile_r2_passed,
        assumptions=(
            "linear context accumulation to each frozen final-turn target",
            "full-stack paired A/B on all five classes",
            "local B-CACHE and B-APPEND+B-LAYOUT paired ablations on TT-EDIT and TT-RET",
            "wall multiplier covers decode, tools, orchestration, and run overhead",
            "projection is invalid until the selected model/engine profile passes R2>=0.99",
        ),
    )


def quadratic_prefill_from_profile(value: dict) -> Callable[[int], float]:
    quadratic = value.get("quadratic") or {}
    if not quadratic.get("passed_r2_gate"):
        raise ValueError("prefill profile quadratic fit has not passed the R2 gate")
    params = quadratic.get("params") or {}
    a = float(params.get("a", 0.0))
    b = float(params.get("b", 0.0))
    c = float(params.get("c", 0.0))
    return lambda n: a * float(n) ** 2 + b * float(n) + c


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--harnesses", type=int, default=2)
    parser.add_argument("--wall-multiplier", type=float, default=1.20)
    parser.add_argument("--target", choices=("cpu_prebox", "box"), default="cpu_prebox")
    args = parser.parse_args(argv)
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    from apu_characterization.turntrace_v2.contracts import protocol_sha256
    from apu_characterization.turntrace_v2.workload.rev_c_suite import (
        FROZEN_PAYLOAD_MANIFEST_PATH,
    )

    payload_manifest = json.loads(
        FROZEN_PAYLOAD_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    projection = project_cpu_wall(
        quadratic_prefill_from_profile(profile),
        model_id=str(profile.get("model_id") or "unknown"),
        quantization=str(profile.get("quantization") or "unknown"),
        engine=str(profile.get("engine") or "unknown"),
        hardware=str(profile.get("hardware") or "unknown"),
        seeds=args.seeds,
        harnesses=args.harnesses,
        wall_multiplier=args.wall_multiplier,
        target_kind=args.target,
        prefill_profile_sha256=hashlib.sha256(args.profile.read_bytes()).hexdigest(),
        protocol_sha256=protocol_sha256(),
        payload_manifest_sha256=str(payload_manifest["manifest_sha256"]),
        profile_r2_passed=True,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(projection.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(projection.to_dict(), indent=2, sort_keys=True))
    return 2 if projection.exceeds_24h else 0


if __name__ == "__main__":
    raise SystemExit(main())
