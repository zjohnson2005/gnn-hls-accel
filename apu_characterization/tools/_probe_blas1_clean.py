"""Fresh-process retrieve probe with OPENBLAS_NUM_THREADS=1 (set before numpy
import via env). Clean discriminator: with no BLAS worker pool, all matmul CPU
runs on the calling thread inside timed(TOOL_COMPUTE)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import apu_characterization.harness  # noqa: F401,E402

from apu_characterization.instr import RunAccumulator, set_run_accumulator  # noqa: E402
from apu_characterization.provenance import MEASURED, RESIDUAL  # noqa: E402
from apu_characterization.taxonomy import Category  # noqa: E402
from apu_characterization.thread_identity import (  # noqa: E402
    get_thread_registry,
    install_thread_identity_hooks,
    sample_session_threads,
)


def main() -> None:
    import os

    import numpy as np

    print(f"OPENBLAS_NUM_THREADS={os.environ.get('OPENBLAS_NUM_THREADS')}")
    print(f"numpy {np.__version__}")

    install_thread_identity_hooks()
    from apu_characterization.tools.impl import _load_vectors, tool_retrieve
    import random
    import threading

    _load_vectors()

    acc = RunAccumulator(profile="probe", instr_version=3)
    set_run_accumulator(acc)
    reg = get_thread_registry()
    sid = "s1"
    reg.begin_session(sid)

    def body() -> None:
        rng = random.Random(0)
        for i in range(13):
            tool_retrieve(f"probe query {i}", sid, rng)

    proc0 = time.process_time()
    t = threading.Thread(target=body, name="probe_clean")
    t.start()
    t.join()
    sample_session_threads(acc, burst=True)
    proc_ms = (time.process_time() - proc0) * 1000

    tool = acc.totals_for(Category.TOOL_COMPUTE, sid).cpu_ns / 1e6
    pool = acc.totals_for(Category.THREADPOOL, sid).cpu_ns / 1e6
    prov = acc.provenance_summary(sid)
    print(f"process CPU  : {proc_ms:9.1f} ms")
    print(f"TOOL_COMPUTE : {tool:9.1f} ms")
    print(f"THREADPOOL   : {pool:9.1f} ms")
    print(f"measured     : {prov[MEASURED] / 1e6:9.1f} ms  residual: {prov[RESIDUAL] / 1e6:.1f} ms")


if __name__ == "__main__":
    main()
