"""Discriminator: step-infer vs thread-identity booking on misaligned CPU."""

from __future__ import annotations

import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from apu_characterization.instr import RunAccumulator, set_run_accumulator, timed
from apu_characterization.provenance import MEASURED, RESIDUAL, STEP_INFERRED
from apu_characterization.taxonomy import Category
from apu_characterization.thread_identity import ThreadRole, get_thread_registry, sample_session_threads


def _burn_cpu(seconds: float) -> None:
    end = time.thread_time() + seconds
    while time.thread_time() < end:
        pass


class TestAttributionProvenance(unittest.TestCase):
    def test_step_infer_books_provenance_tier(self) -> None:
        acc = RunAccumulator(profile="test", instr_version=2)
        set_run_accumulator(acc)
        acc.book_cpu(
            Category.CLIENT_HTTP,
            "s0",
            50_000_000,
            50_000_000,
            provenance=STEP_INFERRED,
        )
        prov = acc.provenance_summary("s0")
        self.assertEqual(prov[STEP_INFERRED], 50_000_000)
        self.assertEqual(prov[MEASURED], 0)

    def test_unknown_worker_books_to_active_session(self) -> None:
        if __import__("sys").platform == "win32":
            self.skipTest("thread-identity sampling requires Linux psutil threads")
        acc = RunAccumulator(profile="test", instr_version=3)
        set_run_accumulator(acc)
        reg = get_thread_registry()
        sid = "s0"
        reg.begin_session(sid)

        def orphan_worker() -> None:
            from apu_characterization.thread_identity import _native_tid

            reg.register(_native_tid(), ThreadRole.UNKNOWN, sid, overwrite=True)
            _burn_cpu(0.05)
            reg.sample_and_book(acc)

        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(orphan_worker).result()
        prov = acc.provenance_summary(sid)
        self.assertGreater(prov[MEASURED], 0)
        self.assertEqual(prov[RESIDUAL], 0)
        self.assertGreater(acc.totals_for(Category.THREADPOOL, sid).cpu_ns, 0)

    def test_thread_registry_books_measured_on_worker(self) -> None:
        if __import__("sys").platform == "win32":
            self.skipTest("thread-identity sampling requires Linux psutil threads")
        acc = RunAccumulator(profile="test", instr_version=3)
        set_run_accumulator(acc)
        reg = get_thread_registry()
        reg.snapshot()
        sid = "s0"

        def http_worker() -> None:
            from apu_characterization.thread_identity import _native_tid

            reg.register(_native_tid(), ThreadRole.HTTP_TRANSPORT, sid, overwrite=True)
            _burn_cpu(0.08)
            reg.sample_and_book(acc)

        with timed(Category.FRAMEWORK, sid):
            _burn_cpu(0.02)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(http_worker).result()
        http_ns = acc.totals_for(Category.CLIENT_HTTP, sid).cpu_ns
        self.assertGreater(http_ns, 0)

    def test_timed_region_not_double_counted_by_sampler(self) -> None:
        """CPU booked via @timed must be subtracted from psutil thread deltas."""
        if __import__("sys").platform == "win32":
            self.skipTest("thread-identity sampling requires Linux psutil threads")
        acc = RunAccumulator(profile="test", instr_version=3)
        set_run_accumulator(acc)
        reg = get_thread_registry()
        sid = "s0"
        burn_s = 0.10

        def tool_worker() -> None:
            from apu_characterization.thread_identity import _native_tid

            reg.register(_native_tid(), ThreadRole.EXECUTOR, sid, overwrite=True)
            with timed(Category.TOOL_COMPUTE, sid):
                _burn_cpu(burn_s)
            reg.sample_and_book(acc)

        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(tool_worker).result()

        tool_ms = acc.totals_for(Category.TOOL_COMPUTE, sid).cpu_ns / 1e6
        pool_ms = acc.totals_for(Category.THREADPOOL, sid).cpu_ns / 1e6
        total_measured_ms = acc.provenance_summary(sid)[MEASURED] / 1e6
        self.assertGreater(tool_ms, burn_s * 1000 * 0.8)
        # THREADPOOL must hold only the untagged remainder, not a second
        # copy of the burn (psutil ticks at ~10 ms; allow generous slack).
        self.assertLess(pool_ms, burn_s * 1000 * 0.5)
        self.assertLess(total_measured_ms, burn_s * 1000 * 1.6)

    def test_fanout_burst_low_residual(self) -> None:
        """Parallel tool-pool threads must not land in session-end residual."""
        if __import__("sys").platform == "win32":
            self.skipTest("thread-identity sampling requires Linux psutil threads")
        from apu_characterization.harness.thread_hooks import install_thread_hooks
        from apu_characterization.thread_identity import install_thread_identity_hooks

        install_thread_hooks()
        install_thread_identity_hooks()

        acc = RunAccumulator(profile="test", instr_version=3)
        set_run_accumulator(acc)
        reg = get_thread_registry()
        sid = "s0"
        reg.begin_session(sid)

        def tool_worker() -> None:
            with timed(Category.TOOL_COMPUTE, sid):
                _burn_cpu(0.03)

        with ThreadPoolExecutor(max_workers=4) as pool:
            for fut in [pool.submit(tool_worker) for _ in range(4)]:
                fut.result()
        sample_session_threads(acc, burst=True)

        prov = acc.provenance_summary(sid)
        res_ms = prov[RESIDUAL] / 1e6
        tool_ms = acc.totals_for(Category.TOOL_COMPUTE, sid).cpu_ns / 1e6
        self.assertGreater(tool_ms, 80.0)
        self.assertLess(res_ms, tool_ms * 0.20)

    def test_subtick_fanout_threads_not_residual(self) -> None:
        """Threads burning < one 10 ms /proc tick must still be attributed.

        psutil utime+stime reads 0 for sub-tick threads; the schedstat path
        (ns-accurate) must capture them so they don't land in the session-end
        residual gap (the FO-01 / SH-02 audit failure mode).

        Uses 15 ms burns so worker CPU dominates executor-hook overhead (~15 ms
        fixed cost on a 9-task fan-out); a 6 ms micro-bench falsely fails the
        15% gate even when schedstat attributes every worker correctly.
        """
        if __import__("sys").platform == "win32":
            self.skipTest("thread-identity sampling requires Linux psutil threads")
        import time as _time

        from apu_characterization.harness.thread_hooks import install_thread_hooks
        from apu_characterization.provenance import RESIDUAL
        from apu_characterization.thread_identity import (
            install_thread_identity_hooks,
            sample_session_threads,
        )
        from apu_characterization.taxonomy import Category

        install_thread_hooks()
        install_thread_identity_hooks()

        acc = RunAccumulator(profile="test", instr_version=3)
        set_run_accumulator(acc)
        reg = get_thread_registry()
        sid = "s0"
        reg.begin_session(sid)

        burn_s = 0.015  # below psutil tick individually, visible to schedstat

        def tiny_worker() -> None:
            _burn_cpu(burn_s)

        proc0 = _time.process_time()
        with ThreadPoolExecutor(max_workers=9) as pool:
            for fut in [pool.submit(tiny_worker) for _ in range(9)]:
                fut.result()
        sample_session_threads(acc, burst=True)
        proc_ns = int((_time.process_time() - proc0) * 1e9)

        pool_ns = acc.totals_for(Category.THREADPOOL, sid).cpu_ns
        prov = acc.provenance_summary(sid)
        # schedstat must book sub-tick worker CPU to THREADPOOL (psutil path ≈ 0).
        self.assertGreater(
            pool_ns,
            int(9 * burn_s * 1e9 * 0.65),
            f"THREADPOOL={pool_ns/1e6:.1f}ms expected ~{9*burn_s*1000:.0f}ms from workers",
        )

        # Mirror v3 session-end gap booking (real_agent_breakdown).
        instr = sum(
            t.cpu_ns
            for (_cat, s, _prof), t in acc.by_key.items()
            if s == sid
        )
        session_gap = max(0, proc_ns - instr)
        if session_gap > 0:
            acc.book_cpu(
                Category.RESIDUAL_UNATTRIBUTED,
                sid,
                session_gap,
                session_gap,
                provenance=RESIDUAL,
            )
        prov = acc.provenance_summary(sid)
        self.assertLess(
            prov[RESIDUAL],
            proc_ns * 0.15,
            f"residual={prov[RESIDUAL]/1e6:.1f}ms proc={proc_ns/1e6:.1f}ms "
            f"measured={prov[MEASURED]/1e6:.1f}ms pool={pool_ns/1e6:.1f}ms",
        )

    def test_parallel_fanout_process_bounded(self) -> None:
        """Parallel executor: categories must not exceed process CPU by >15%."""
        if __import__("sys").platform == "win32":
            self.skipTest("thread-identity sampling requires Linux psutil threads")
        import time as _time
        from apu_characterization.harness.thread_hooks import install_thread_hooks
        from apu_characterization.thread_identity import install_thread_identity_hooks

        install_thread_hooks()
        install_thread_identity_hooks()

        acc = RunAccumulator(profile="test", instr_version=3)
        set_run_accumulator(acc)
        reg = get_thread_registry()
        sid = "s0"
        reg.begin_session(sid)

        def tool_worker() -> None:
            with timed(Category.TOOL_COMPUTE, sid):
                _burn_cpu(0.04)

        proc0 = _time.process_time()
        with ThreadPoolExecutor(max_workers=4) as pool:
            for fut in [pool.submit(tool_worker) for _ in range(4)]:
                fut.result()
        sample_session_threads(acc, burst=True)
        proc_ms = (_time.process_time() - proc0) * 1000
        instr_ms = (
            acc.totals_for(Category.TOOL_COMPUTE, sid).cpu_ns
            + acc.totals_for(Category.THREADPOOL, sid).cpu_ns
        ) / 1e6
        prov = acc.provenance_summary(sid)
        self.assertLess(instr_ms, proc_ms * 1.15 + 5.0)
        self.assertLess(prov[RESIDUAL], proc_ms * 1e6 * 0.15)


if __name__ == "__main__":
    unittest.main()
