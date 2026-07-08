"""Synthetic reconcile semantics and platform checks for Phase A."""

from __future__ import annotations

import sys
import sysconfig
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from apu_characterization.attribution import split_session_orch_after_reconcile
from apu_characterization.instr import (
    CategoryTotals,
    RunAccumulator,
    set_run_accumulator,
    timed,
)
from apu_characterization.taxonomy import Category


def _tagged_cpu_ns(acc: RunAccumulator, session_id: str) -> int:
    total = 0
    with acc._lock:
        for (_cat, sid, _prof), t in acc.by_key.items():
            if sid == session_id:
                total += t.cpu_ns
    return total


def _session_orch_cpu_ns(acc: RunAccumulator, session_id: str) -> int:
    with acc._lock:
        total = 0
        for cat in (Category.ORCH_SETUP.value, Category.ORCH_DISPATCH.value):
            key = (cat, session_id, acc.profile)
            total += acc.by_key.get(key, CategoryTotals()).cpu_ns
    return total


def compute_reconcile_v1(
    acc: RunAccumulator, session_id: str, session_process_ns: int
) -> tuple[int, int]:
    """Mirror v1 booking: gap to ORCH_DISPATCH before trim."""
    session_instr_before = _tagged_cpu_ns(acc, session_id)
    orch_measured_before = _session_orch_cpu_ns(acc, session_id)
    reconcile_added = max(0, session_process_ns - session_instr_before)
    if reconcile_added > 0:
        totals = acc.totals_for(Category.ORCH_DISPATCH, session_id)
        with acc._lock:
            totals.add(reconcile_added, reconcile_added, count=1)
    return reconcile_added, orch_measured_before


def compute_residual_v2(
    acc: RunAccumulator, session_id: str, session_process_ns: int
) -> int:
    """v2: book gap to RESIDUAL_UNATTRIBUTED only."""
    tagged = _tagged_cpu_ns(acc, session_id)
    gap = max(0, session_process_ns - tagged)
    if gap > 0:
        totals = acc.totals_for(Category.RESIDUAL_UNATTRIBUTED, session_id)
        with acc._lock:
            totals.add(gap, gap, count=1)
    return gap


def _burn_cpu(seconds: float) -> None:
    end = time.thread_time() + seconds
    while time.thread_time() < end:
        pass


class TestReconcileWorker(unittest.TestCase):
    def test_untagged_worker_inflates_reconcile_v1(self) -> None:
        acc = RunAccumulator(profile="test")
        set_run_accumulator(acc)
        sid = "s0"
        proc_start = time.process_time()
        with timed(Category.ORCH_SETUP, sid):
            _burn_cpu(0.05)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(_burn_cpu, 0.20).result()
        process_ns = int((time.process_time() - proc_start) * 1e9)
        reconcile_added, _ = compute_reconcile_v1(acc, sid, process_ns)
        self.assertGreater(reconcile_added, 0)
        self.assertAlmostEqual(reconcile_added / process_ns, 0.20 / 0.25, delta=0.08)

    def test_tagged_worker_near_zero_reconcile_v2(self) -> None:
        acc = RunAccumulator(profile="test")
        set_run_accumulator(acc)
        sid = "s0"
        proc_start = time.process_time()

        def tagged_burn() -> None:
            with timed(Category.TOOL_COMPUTE, sid):
                _burn_cpu(0.20)

        with timed(Category.ORCH_SETUP, sid):
            _burn_cpu(0.05)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(tagged_burn).result()
        process_ns = int((time.process_time() - proc_start) * 1e9)
        residual = compute_residual_v2(acc, sid, process_ns)
        # Windows thread-time tick (~15.6 ms) can add one quantizer step of gap.
        max_frac = 0.12 if sys.platform == "win32" else 0.05
        self.assertLessEqual(residual / max(process_ns, 1), max_frac)


class TestPlatformInfo(unittest.TestCase):
    def test_gil_disabled_recorded(self) -> None:
        gil = sysconfig.get_config_var("Py_GIL_DISABLED")
        self.assertIn(gil, (None, 0, 1, True, False))


if __name__ == "__main__":
    unittest.main()
