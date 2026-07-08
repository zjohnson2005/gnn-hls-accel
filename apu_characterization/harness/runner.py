"""Batch runner for concurrent agent sessions."""

from __future__ import annotations

from .. import env_pin as _env_pin  # noqa: F401 — pin BLAS before numpy (tools.impl)

import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal

from ..instr import (
    RunAccumulator,
    get_run_accumulator,
    install_gc_hooks,
    reset_thread_state,
    set_run_accumulator,
)
from ..profiles import PROFILES, ProfileSpec
from ..tasks import assign_task, suite_digest
from ..tools.impl import _load_corpus, _load_vectors
from .mock_llm import _get_encoder
from .react_loop import run_agent_session


def _warm_shared_state() -> None:
    """Load tokenizer, corpus, vector matrix, and sympy before the measured
    window.

    These one-time costs (BPE download, 50 MB file read, npy mmap, sympy
    import, possibly fixture generation on first ever run) are setup, not
    agent work; leaving them lazy would bill them to whichever session
    touches them first (e.g. sympy's ~200 ms import landing in one task's
    TOOL_COMPUTE) or dump them into RESIDUAL."""
    _get_encoder()
    _load_corpus()
    _load_vectors()
    try:
        import sympy  # noqa: F401

        sympy.sympify("1 + 1")  # first sympify builds caches
    except ImportError:
        pass

ExecutionMode = Literal["asyncio", "threads"]


def _os_times_snapshot() -> dict[str, float]:
    try:
        import psutil

        ct = psutil.Process().cpu_times()
        return {"user": ct.user, "system": ct.system}
    except Exception:
        t = os.times()
        return {"user": t.user, "system": t.system}


def _os_times_delta(start: dict[str, float], end: dict[str, float]) -> dict[str, float]:
    return {
        "user": end["user"] - start["user"],
        "system": end["system"] - start["system"],
    }


async def _run_asyncio_batch(
    concurrency: int,
    spec: ProfileSpec,
    seed: int,
    llm_median_scale: float,
    record_timeline: bool,
) -> dict[str, Any]:
    install_gc_hooks()
    _warm_shared_state()
    acc = RunAccumulator(profile=spec.name, record_timeline=record_timeline)
    set_run_accumulator(acc)
    reset_thread_state()

    os_start = _os_times_snapshot()
    wall_start = time.perf_counter_ns()
    thread_start = time.thread_time_ns()

    async def one(i: int) -> dict[str, Any]:
        sid = f"agent_{i}"
        task = assign_task(spec.name, seed, i)
        return await run_agent_session(sid, spec, task, seed + i, llm_median_scale)

    tasks = [asyncio.create_task(one(i)) for i in range(concurrency)]
    per_session = await asyncio.gather(*tasks)

    thread_end = time.thread_time_ns()
    wall_end = time.perf_counter_ns()
    os_end = _os_times_snapshot()

    total_thread_cpu = thread_end - thread_start
    result = acc.to_run_dict(
        env={},
        config={
            "concurrency": concurrency,
            "profile": spec.name,
            "seed": seed,
            "mode": "asyncio",
            "llm_median_scale": llm_median_scale,
            "task_suite_digest": suite_digest(),
        },
        total_thread_cpu_ns=total_thread_cpu,
        total_wall_ns=wall_end - wall_start,
        os_times=_os_times_delta(os_start, os_end),
        per_session=per_session,
    )
    set_run_accumulator(None)
    return result


def _run_threads_batch(
    concurrency: int,
    spec: ProfileSpec,
    seed: int,
    llm_median_scale: float,
    workers: int | None,
) -> dict[str, Any]:
    install_gc_hooks()
    _warm_shared_state()
    acc = RunAccumulator(profile=spec.name)
    os_start = _os_times_snapshot()
    wall_start = time.perf_counter_ns()

    per_session: list[dict[str, Any]] = []
    max_workers = workers or min(32, concurrency)
    # thread_time_ns is per-thread: total CPU must be summed across workers,
    # measured inside each worker, not on the main thread.
    worker_cpu_ns: list[int] = []
    worker_cpu_lock = threading.Lock()

    def session_worker(i: int) -> dict[str, Any]:
        set_run_accumulator(acc)
        reset_thread_state()
        task = assign_task(spec.name, seed, i)
        t0 = time.thread_time_ns()
        try:
            return asyncio.run(
                run_agent_session(f"agent_{i}", spec, task, seed + i, llm_median_scale)
            )
        finally:
            with worker_cpu_lock:
                worker_cpu_ns.append(time.thread_time_ns() - t0)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = [pool.submit(session_worker, i) for i in range(concurrency)]
        for fut in as_completed(futs):
            per_session.append(fut.result())

    wall_end = time.perf_counter_ns()
    os_end = _os_times_snapshot()
    total_worker_cpu = sum(worker_cpu_ns)

    result = acc.to_run_dict(
        env={},
        config={
            "concurrency": concurrency,
            "profile": spec.name,
            "seed": seed,
            "mode": "threads",
            "llm_median_scale": llm_median_scale,
            "workers": max_workers,
            "task_suite_digest": suite_digest(),
        },
        total_thread_cpu_ns=total_worker_cpu,
        total_wall_ns=wall_end - wall_start,
        os_times=_os_times_delta(os_start, os_end),
        per_session=per_session,
    )
    set_run_accumulator(None)
    return result


def run_batch(
    concurrency: int,
    profile: str,
    seed: int,
    mode: ExecutionMode = "asyncio",
    llm_median_scale: float = 1.0,
    record_timeline: bool = False,
    workers: int | None = None,
) -> dict[str, Any]:
    spec = PROFILES[profile]
    if mode == "asyncio":
        return asyncio.run(
            _run_asyncio_batch(concurrency, spec, seed, llm_median_scale, record_timeline)
        )
    return _run_threads_batch(concurrency, spec, seed, llm_median_scale, workers)
