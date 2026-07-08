        # Reconcile bug hypothesis checks

        Generated: 2026-07-07T20:58:04.060724+00:00

        ## A2.1 Mock remote search path

        `sync_mock_remote_call` uses `time.sleep(rng.lognormvariate(...))` for the round trip.
        No polling or busy-wait loop.

        ```
        57:     mu = math.log(max(median_s * latency_scale, 1e-6))
58:     cpu0 = time.thread_time_ns()
59:     wall0 = time.perf_counter_ns()
60:     time.sleep(rng.lognormvariate(mu, sigma))
61:     from ..instr import get_run_accumulator
        ```

        Request/response envelope work is wrapped in `timed(Category.HTTP_CLIENT, ...)`.
        Sleep interval thread CPU is booked separately to HTTP_CLIENT (should be near zero CPU).

        ## A2.2 Reconcile arithmetic (synthetic worker thread)

        Unit test module: `apu_characterization/tests/test_reconcile_worker.py`

        ```
        ...
----------------------------------------------------------------------
Ran 3 tests in 0.561s

OK

exit_code=0
        ```

        Interpretation: an untagged 200 ms worker burn produces reconcile near 80% of process CPU
        under v1 booking. Tagged worker burn under v2 leaves RESIDUAL_UNATTRIBUTED below 5%.

        ## A2.3 Free-threaded build and clock semantics

        - Python: 3.14.0
        - Platform: win32
        - `Py_GIL_DISABLED`: 0 (None or 0 = GIL enabled; 1 = free-threaded build)
        - Host CPU basis: `process_time()` per session (all threads, single count for overlap)
        - Region timers: `thread_time()` exclusive self-time on the entering thread
        - Reconcile v1: `max(0, process_cpu - tagged_cpu)` booked to ORCH_DISPATCH before trim
        - Reconcile v2: same gap booked to RESIDUAL_UNATTRIBUTED only

        ## A2.4 Proportional trim vs reconcile booking order

        Order in `run_real_session`:

        1. Compute `reconcile_added_ns = process_cpu - tagged_cpu` (pre-trim snapshot).
        2. v1: add gap to ORCH_DISPATCH; v2: add gap to RESIDUAL_UNATTRIBUTED after trim recalc.
        3. Run `_align_session_cpu_to_process` when summed thread categories exceed process clock
           (parallel overlap). Trim scales category totals down proportionally.
        4. Recompute `session_gap = process_cpu - tagged_cpu` after trim for reporting.

        Trim removes category over-count; it cannot inflate reconcile because reconcile uses
        process minus tagged after trim in v2, and v1 gap was booked before trim then gap
        is recomputed for reporting only (orch split uses pre-trim reconcile_added_ns).

        ## Status

        Run `python -m apu_characterization.experiments.reconcile_phase_a` after code changes
        to refresh this file.
