"""Phase A: bug checks, platform notes, and reconcile_bug_checks.md generation."""

from __future__ import annotations

import subprocess
import sys
import sysconfig
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "reconcile_bug_checks.md"
MOCK_API = ROOT / "harness" / "mock_api.py"


def _run_tests() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "apu_characterization.tests.test_reconcile_worker"],
        capture_output=True,
        text=True,
        cwd=ROOT.parent,
    )
    return proc.stdout + proc.stderr + f"\nexit_code={proc.returncode}\n"


def _read_excerpt(path: Path, start: int, end: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    snippet = lines[start - 1 : end]
    return "\n".join(f"{i}: {line}" for i, line in enumerate(snippet, start=start))


def build_markdown() -> str:
    gil = sysconfig.get_config_var("Py_GIL_DISABLED")
    test_out = _run_tests()
    mock_excerpt = _read_excerpt(MOCK_API, 57, 61)
    now = datetime.now(timezone.utc).isoformat()
    return textwrap.dedent(
        f"""\
        # Reconcile bug hypothesis checks

        Generated: {now}

        ## A2.1 Mock remote search path

        `sync_mock_remote_call` uses `time.sleep(rng.lognormvariate(...))` for the round trip.
        No polling or busy-wait loop.

        ```
        {mock_excerpt}
        ```

        Request/response envelope work is wrapped in `timed(Category.HTTP_CLIENT, ...)`.
        Sleep interval thread CPU is booked separately to HTTP_CLIENT (should be near zero CPU).

        ## A2.2 Reconcile arithmetic (synthetic worker thread)

        Unit test module: `apu_characterization/tests/test_reconcile_worker.py`

        ```
        {test_out.strip()}
        ```

        Interpretation: an untagged 200 ms worker burn produces reconcile near 80% of process CPU
        under v1 booking. Tagged worker burn under v2 leaves RESIDUAL_UNATTRIBUTED below 5%.

        ## A2.3 Free-threaded build and clock semantics

        - Python: {sys.version.split()[0]}
        - Platform: {sys.platform}
        - `Py_GIL_DISABLED`: {gil!r} (None or 0 = GIL enabled; 1 = free-threaded build)
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
        """
    )


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_markdown(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
