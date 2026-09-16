"""Serial, resumable runner for the measured CAP-01 execution plane."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .budget import PoolExhaustionError, TaskExecutionResult, execute_task_loop
from .contracts import (
    PROTOCOL_PATH,
    PROTOCOL_VERSION,
    CellCoordinates,
    PoolMetadata,
    TaskRecord,
    canonical_json_bytes,
    load_protocol,
    protocol_sha256,
    sha256_bytes,
    validate_lock,
)
from .harnesses import make_harness
from .latency import encode_execution_plan, make_latency_plan
from ..validity import CAPABILITY_SCALING, DEBUG_ONLY


@dataclass(frozen=True)
class PreparedTaskPlan:
    candidates: tuple[Any, ...]
    latency_ns: tuple[int, ...]
    canonical_bytes: bytes

    @property
    def sha256(self) -> str:
        return sha256_bytes(self.canonical_bytes)


@dataclass(frozen=True)
class RunRequest:
    task: TaskRecord
    pool: PoolMetadata
    coordinates: CellCoordinates
    verifier: Callable[[Any], Any]
    task_class: str = "SCALING"


def prepare_task_plan(
    task: TaskRecord, pool: PoolMetadata, coordinates: CellCoordinates
) -> PreparedTaskPlan:
    if pool.task_id != task.task_id:
        raise ValueError("task and candidate pool IDs differ")
    ordered = pool.ordered_candidates(coordinates.seed)
    latency = make_latency_plan(
        task.task_id,
        coordinates.seed,
        coordinates.latency_scale_ms,
        len(ordered),
    ).draws_ns
    encoded = encode_execution_plan(
        task.task_id,
        coordinates.seed,
        (candidate.candidate_id for candidate in ordered),
        latency,
    )
    return PreparedTaskPlan(
        candidates=ordered, latency_ns=latency, canonical_bytes=encoded
    )


def run_task(
    task: TaskRecord,
    pool: PoolMetadata,
    coordinates: CellCoordinates,
    verifier: Callable[[Any], Any],
    *,
    adapter: Any | None = None,
    rust_executable: Path | None = None,
    protocol_path: Path = PROTOCOL_PATH,
    result_validity: str = DEBUG_ONLY,
    task_class: str = "SCALING",
    clock_ns: Callable[[], int] = time.monotonic_ns,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if coordinates.budget_kind != "wall":
        raise ValueError("this execution plane supports the registered wall arm only")
    if coordinates.harness not in ("raw_python", "langgraph", "rust"):
        raise ValueError("unregistered harness arm")
    protocol = load_protocol(protocol_path)
    lock_errors = validate_lock(protocol)
    if result_validity == CAPABILITY_SCALING and lock_errors:
        raise ValueError(
            "capability_scaling validity requires a locked protocol: "
            + "; ".join(lock_errors)
        )
    plan = prepare_task_plan(task, pool, coordinates)
    selected = adapter or make_harness(
        coordinates.harness, rust_executable=rust_executable
    )
    hard_failure: str | None = None
    try:
        result: TaskExecutionResult = execute_task_loop(
            task_id=task.task_id,
            candidates=plan.candidates,
            latency_ns=plan.latency_ns,
            wall_budget_ms=coordinates.wall_budget_ms,
            adapter=selected,
            verifier=verifier,
            instr_mode=coordinates.instr_mode,
            clock_ns=clock_ns,
            sleep=sleep,
        )
    except PoolExhaustionError as exc:
        result = exc.result
        hard_failure = "pool_exhaustion"
    execution = result.to_dict()
    trace = execution["trace"]
    assert isinstance(trace, dict)
    categories = trace["categories"]
    assert isinstance(categories, dict)
    process_cpu_ns = int(trace["process_inclusive_cpu_ns"])
    residual_cpu_ns = int(trace["residual_cpu_ns"])
    return {
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": protocol_sha256(protocol_path),
        "protocol_status": protocol.get("status"),
        "result_validity": result_validity,
        "task_id": task.task_id,
        "domain": task.domain,
        "task_class": task_class,
        "hard_failure": hard_failure,
        "coordinates": asdict(coordinates),
        "cell_id": coordinates.cell_id,
        "harness": coordinates.harness,
        "latency_scale_ms": coordinates.latency_scale_ms,
        "wall_budget_ms": coordinates.wall_budget_ms,
        "budget_ns": coordinates.wall_budget_ms * 1_000_000,
        "seed": coordinates.seed,
        "task_sha256": task.digest(),
        "pool_sha256": pool.pool_sha256(),
        "execution_plan_sha256": plan.sha256,
        "execution_plan": json.loads(plan.canonical_bytes),
        **execution,
        "candidate_events": execution["events"],
        "accounting": {
            "process_cpu_ns": process_cpu_ns,
            "accounted_cpu_ns": max(0, process_cpu_ns - residual_cpu_ns),
            "residual_cpu_ns": residual_cpu_ns,
            "category_cpu_ns": {
                name: int(value["cpu_ns"])
                for name, value in categories.items()
                if isinstance(value, dict)
            },
        },
    }


def _safe_component(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    if not safe:
        raise ValueError("empty path component")
    return safe


def _write_json_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value) + b"\n"
    with path.open("xb") as handle:
        handle.write(payload)


def _manifest(
    requests: tuple[RunRequest, ...],
    run_id: str,
    *,
    protocol_path: Path,
    result_validity: str,
) -> dict[str, Any]:
    cells = [
        {
            "cell_id": request.coordinates.cell_id,
            "task_id": request.task.task_id,
            "domain": request.task.domain,
            "task_class": request.task_class,
            "task_sha256": request.task.digest(),
            "pool_sha256": request.pool.pool_sha256(),
        }
        for request in requests
    ]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": protocol_sha256(protocol_path),
        "protocol_status": load_protocol(protocol_path).get("status"),
        "result_validity": result_validity,
        "run_id": run_id,
        "measurement_order": "serial",
        "arms": sorted({request.coordinates.harness for request in requests}),
        "cells": cells,
    }


def run_serial(
    requests: Iterable[RunRequest],
    *,
    output_root: Path,
    run_id: str,
    resume: bool = False,
    rust_executable: Path | None = None,
    protocol_path: Path = PROTOCOL_PATH,
    result_validity: str = DEBUG_ONLY,
) -> Path:
    """Execute cells serially in an immutable marker-based run directory."""
    request_tuple = tuple(requests)
    if any(
        request.coordinates.harness not in ("raw_python", "langgraph", "rust")
        for request in request_tuple
    ):
        raise ValueError("run contains an unregistered arm")
    lock_errors = validate_lock(load_protocol(protocol_path))
    if result_validity == CAPABILITY_SCALING and lock_errors:
        raise ValueError(
            "publication run requires locked protocol: " + "; ".join(lock_errors)
        )
    safe_run_id = _safe_component(run_id)
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = output_root / safe_run_id
    running_marker = run_dir / "RUNNING.json"
    completed_marker = run_dir / "COMPLETED.json"
    failed_marker = run_dir / "FAILED.json"
    manifest_path = run_dir / "manifest.json"
    serial_lock = output_root / ".cap01-serial.lock"
    expected_manifest = _manifest(
        request_tuple,
        run_id,
        protocol_path=protocol_path,
        result_validity=result_validity,
    )

    if completed_marker.exists():
        raise FileExistsError(f"completed run is immutable: {run_dir}")
    if failed_marker.exists():
        raise RuntimeError(
            f"run has a retained hard failure and cannot resume: {run_dir}"
        )
    if resume:
        if not running_marker.is_file() or not manifest_path.is_file():
            raise FileNotFoundError("resume requires RUNNING.json and manifest.json")
        existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing_manifest != expected_manifest:
            raise ValueError("resume manifest does not match requested run")
        if serial_lock.exists():
            owner = str(
                json.loads(serial_lock.read_text(encoding="utf-8")).get("run_id", "")
            )
            if owner != run_id:
                raise RuntimeError(f"another CAP-01 run owns the serial lock: {owner}")
        else:
            _write_json_new(serial_lock, {"run_id": run_id})
    else:
        if run_dir.exists():
            raise FileExistsError(f"run directory already exists: {run_dir}")
        try:
            _write_json_new(serial_lock, {"run_id": run_id})
        except FileExistsError as exc:
            raise RuntimeError("another CAP-01 run owns the serial lock") from exc
        run_dir.mkdir()
        _write_json_new(manifest_path, expected_manifest)
        _write_json_new(
            running_marker,
            {"run_id": run_id, "pid": os.getpid(), "protocol": PROTOCOL_VERSION},
        )

    try:
        for request in request_tuple:
            result_path = (
                run_dir
                / "results"
                / _safe_component(request.coordinates.cell_id)
                / f"{_safe_component(request.task.task_id)}.json"
            )
            if result_path.exists():
                if resume:
                    continue
                raise FileExistsError(f"result already exists: {result_path}")
            result = run_task(
                request.task,
                request.pool,
                request.coordinates,
                request.verifier,
                rust_executable=rust_executable,
                protocol_path=protocol_path,
                result_validity=result_validity,
                task_class=request.task_class,
            )
            _write_json_new(result_path, result)
            if result.get("hard_failure"):
                _write_json_new(
                    failed_marker,
                    {
                        "run_id": run_id,
                        "cell_id": request.coordinates.cell_id,
                        "task_id": request.task.task_id,
                        "failure": result["hard_failure"],
                    },
                )
                raise RuntimeError(
                    f"CAP-01 hard failure: {result['hard_failure']} "
                    f"for {request.task.task_id}"
                )
        _write_json_new(
            completed_marker,
            {
                "run_id": run_id,
                "result_count": len(request_tuple),
                "status": "complete",
            },
        )
        running_marker.unlink()
        serial_lock.unlink()
    except BaseException:
        # RUNNING and lock markers intentionally survive. A resume can prove
        # ownership and continue without mutating completed result files.
        raise
    return run_dir
