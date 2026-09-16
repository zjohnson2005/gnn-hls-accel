"""Shared deadline semantics for all measured CAP-01 harnesses."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

from ..taxonomy import Category
from .contracts import CandidateEvent, CandidateRecord, canonical_json_bytes, sha256_bytes
from .instrumentation import TurnInstrumentor, TurnTrace


class HarnessAdapter(Protocol):
    category: Category | str

    def setup(self) -> None: ...

    def dispatch(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def close(self) -> None: ...


Verifier = Callable[[CandidateRecord], Any]
Clock = Callable[[], int]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class TaskExecutionResult:
    task_id: str
    setup_wall_ns: int
    setup_cpu_ns: int
    ready_ns: int
    deadline_ns: int
    ended_ns: int
    solved: bool
    started: int
    counted: int
    abandoned: int
    pool_exhausted: bool
    events: tuple[CandidateEvent, ...]
    harness_reports: tuple[dict[str, Any], ...]
    trace: TurnTrace

    def validate(self) -> None:
        if self.started != self.counted + self.abandoned:
            raise RuntimeError("candidate conservation failed")
        if self.started != len(self.events):
            raise RuntimeError("event count does not equal candidates started")
        if any(event.counted == event.abandoned for event in self.events):
            raise RuntimeError("each event must be exactly counted or abandoned")
        if self.solved != any(event.solved and event.counted for event in self.events):
            raise RuntimeError("solve status does not match counted verdicts")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "task_id": self.task_id,
            "setup_wall_ns": self.setup_wall_ns,
            "setup_cpu_ns": self.setup_cpu_ns,
            "ready_ns": self.ready_ns,
            "deadline_ns": self.deadline_ns,
            "ended_ns": self.ended_ns,
            "elapsed_ns": max(0, self.ended_ns - self.ready_ns),
            "solved": self.solved,
            "started": self.started,
            "counted": self.counted,
            "abandoned": self.abandoned,
            "pool_exhausted": self.pool_exhausted,
            "events": [asdict(event) for event in self.events],
            "harness_reports": list(self.harness_reports),
            "trace": self.trace.to_dict(),
        }


class PoolExhaustionError(RuntimeError):
    def __init__(self, result: TaskExecutionResult):
        super().__init__(
            f"{result.task_id}: candidate pool exhausted before solve or deadline"
        )
        self.result = result


def _verdict_parts(value: Any) -> tuple[bool, str]:
    if isinstance(value, Mapping):
        solved = bool(value.get("solved", value.get("passed", False)))
        serializable: Any = dict(value)
        supplied_digest = value.get("verdict_digest", value.get("digest"))
    elif hasattr(value, "solved"):
        solved = bool(value.solved)
        supplied_digest = getattr(value, "digest", None)
        serializable = (
            asdict(value)
            if is_dataclass(value)
            else {"solved": solved, "digest": supplied_digest}
        )
    else:
        solved = bool(value)
        serializable = {"solved": solved}
        supplied_digest = None
    if isinstance(supplied_digest, str) and supplied_digest:
        return solved, supplied_digest
    try:
        digest = sha256_bytes(canonical_json_bytes(serializable))
    except (TypeError, ValueError):
        digest = sha256_bytes(repr(value).encode("utf-8"))
    return solved, digest


def _verdict_metadata(value: Any) -> tuple[str | None, str | None, bool | None]:
    if isinstance(value, Mapping):
        status = value.get("status")
        runtime = value.get("runtime")
        isolated = value.get("network_isolated")
    else:
        status = getattr(value, "status", None)
        runtime = getattr(value, "runtime", None)
        isolated = getattr(value, "network_isolated", None)
    return (
        str(status) if status is not None else None,
        str(runtime) if runtime is not None else None,
        bool(isolated) if isolated is not None else None,
    )


def execute_task_loop(
    *,
    task_id: str,
    candidates: Sequence[CandidateRecord],
    latency_ns: Sequence[int],
    wall_budget_ms: float,
    adapter: HarnessAdapter,
    verifier: Verifier,
    instr_mode: str = "throttle",
    clock_ns: Clock = time.monotonic_ns,
    sleep: Sleeper = time.sleep,
) -> TaskExecutionResult:
    """Run request, wait, candidate, verifier turns against one hard deadline."""
    if wall_budget_ms < 0:
        raise ValueError("wall_budget_ms cannot be negative")
    if len(candidates) != len(latency_ns):
        raise ValueError("candidate and latency plan lengths differ")
    if any(wait < 0 for wait in latency_ns):
        raise ValueError("latency cannot be negative")

    # Session setup is deliberately outside the task budget. The timestamp
    # immediately following setup is the task-ready barrier.
    setup_wall_start = clock_ns()
    setup_cpu_start = time.process_time_ns()
    adapter.setup()
    setup_wall_ns = max(0, clock_ns() - setup_wall_start)
    setup_cpu_ns = max(0, time.process_time_ns() - setup_cpu_start)
    instrumentor = TurnInstrumentor(mode=instr_mode)  # type: ignore[arg-type]
    ready_ns = clock_ns()
    budget_ns = int(round(wall_budget_ms * 1_000_000.0))
    deadline_ns = ready_ns + budget_ns
    events: list[CandidateEvent] = []
    harness_reports: list[dict[str, Any]] = []
    solved = False
    pool_exhausted = False
    instrumentor.start()
    try:
        for sequence_index, (candidate, requested_wait_ns) in enumerate(
            zip(candidates, latency_ns)
        ):
            if clock_ns() >= deadline_ns:
                break

            started_ns = clock_ns()
            request = {
                "op": "candidate",
                "task_id": task_id,
                "sequence_index": sequence_index,
                "candidate_id": candidate.candidate_id,
                "candidate_sha256": candidate.digest(),
                "latency_ns": int(requested_wait_ns),
            }
            with instrumentor.span(adapter.category):
                response = adapter.dispatch(request)
            if response.get("candidate_id") != candidate.candidate_id:
                raise RuntimeError("harness returned a different candidate")
            if response.get("candidate_sha256") != candidate.digest():
                raise RuntimeError("harness returned a different candidate digest")
            if int(response.get("sequence_index", -1)) != sequence_index:
                raise RuntimeError("harness returned a different sequence index")
            report = {
                "sequence_index": sequence_index,
                "timer_scope": str(response.get("timer_scope", "current_process")),
                "harness_wall_ns": max(0, int(response.get("harness_wall_ns", 0))),
                "harness_cpu_ns": max(0, int(response.get("harness_cpu_ns", 0))),
            }
            harness_reports.append(report)
            if report["timer_scope"] == "harness_process":
                instrumentor.record_external_process(
                    adapter.category,
                    cpu_ns=report["harness_cpu_ns"],
                    wall_ns=report["harness_wall_ns"],
                )

            remaining_ns = max(0, deadline_ns - clock_ns())
            wait_ns = min(int(requested_wait_ns), remaining_ns)
            if wait_ns:
                with instrumentor.span(Category.HTTP_CLIENT):
                    sleep(wait_ns / 1_000_000_000.0)

            if requested_wait_ns > remaining_ns or clock_ns() >= deadline_ns:
                events.append(
                    CandidateEvent(
                        sequence_index=sequence_index,
                        candidate_id=candidate.candidate_id,
                        candidate_sha256=candidate.digest(),
                        latency_ns=int(requested_wait_ns),
                        verifier_wall_ns=0,
                        verifier_cpu_ns=0,
                        started_ns=started_ns,
                        verdict_ns=None,
                        counted=False,
                        abandoned=True,
                        solved=False,
                        verdict_digest=None,
                    )
                )
                break

            verifier_wall_start = clock_ns()
            verifier_cpu_start = time.process_time_ns()
            with instrumentor.span(Category.TOOL_COMPUTE):
                verdict = verifier(candidate)
            measured_verifier_cpu_ns = max(
                0, time.process_time_ns() - verifier_cpu_start
            )
            if isinstance(verdict, Mapping):
                reported_verifier_cpu_ns = int(
                    verdict.get("cpu_ns", measured_verifier_cpu_ns)
                )
            else:
                reported_verifier_cpu_ns = int(
                    getattr(verdict, "cpu_ns", measured_verifier_cpu_ns)
                )
            verifier_cpu_ns = max(
                measured_verifier_cpu_ns, reported_verifier_cpu_ns
            )
            external_verifier_cpu_ns = max(
                0, verifier_cpu_ns - measured_verifier_cpu_ns
            )
            if external_verifier_cpu_ns:
                instrumentor.record_external_process(
                    Category.TOOL_COMPUTE,
                    cpu_ns=external_verifier_cpu_ns,
                    wall_ns=0,
                )
            verdict_ns = clock_ns()
            verifier_wall_ns = max(0, verdict_ns - verifier_wall_start)
            before_deadline = verdict_ns < deadline_ns
            candidate_solved, verdict_digest = _verdict_parts(verdict)
            verdict_status, verifier_runtime, network_isolated = _verdict_metadata(
                verdict
            )
            events.append(
                CandidateEvent(
                    sequence_index=sequence_index,
                    candidate_id=candidate.candidate_id,
                    candidate_sha256=candidate.digest(),
                    latency_ns=int(requested_wait_ns),
                    verifier_wall_ns=verifier_wall_ns,
                    verifier_cpu_ns=verifier_cpu_ns,
                    started_ns=started_ns,
                    verdict_ns=verdict_ns,
                    counted=before_deadline,
                    abandoned=not before_deadline,
                    solved=candidate_solved if before_deadline else False,
                    verdict_digest=verdict_digest,
                    verdict_status=verdict_status,
                    verifier_runtime=verifier_runtime,
                    verifier_network_isolated=network_isolated,
                )
            )
            if before_deadline and candidate_solved:
                solved = True
                break
            if not before_deadline:
                break
        else:
            if not solved and clock_ns() < deadline_ns:
                pool_exhausted = True
    finally:
        trace = instrumentor.stop()
        ended_ns = clock_ns()
        adapter.close()

    counted = sum(event.counted for event in events)
    abandoned = sum(event.abandoned for event in events)
    result = TaskExecutionResult(
        task_id=task_id,
        setup_wall_ns=setup_wall_ns,
        setup_cpu_ns=setup_cpu_ns,
        ready_ns=ready_ns,
        deadline_ns=deadline_ns,
        ended_ns=ended_ns,
        solved=solved,
        started=len(events),
        counted=counted,
        abandoned=abandoned,
        pool_exhausted=pool_exhausted,
        events=tuple(events),
        harness_reports=tuple(harness_reports),
        trace=trace,
    )
    result.validate()
    if pool_exhausted:
        raise PoolExhaustionError(result)
    return result
