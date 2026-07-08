"""Discriminating probe: where does tool-body CPU land under v3 accounting?

Three experiments, no OpenAI needed:

1. Pure-Python 200 ms burn inside timed(TOOL_COMPUTE) on a hooked executor
   thread -> must land in TOOL (attribution works for GIL-holding code).
2. Real tool_retrieve (NumPy matmul) with env-pinned BLAS (v3.1+ default via
   apu_env.sh / env_pin) -> matmul CPU should stay on the calling thread (TOOL).
3. Same retrieve with threadpoolctl limiting BLAS to 1 thread -> belt-and-suspenders
   check that runtime thread count agrees with the env pin.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Import harness first: tools/__init__ -> impl -> harness -> runner -> tools.impl
# is circular when tools is initialized first; harness-first breaks the cycle.
import apu_characterization.harness  # noqa: F401,E402

from apu_characterization.instr import (
    RunAccumulator,
    set_run_accumulator,
    timed,
)
from apu_characterization.provenance import MEASURED, RESIDUAL
from apu_characterization.taxonomy import Category
from apu_characterization.thread_identity import (
    get_thread_registry,
    install_thread_identity_hooks,
    sample_session_threads,
)


def _burn_cpu(seconds: float) -> None:
    end = time.thread_time() + seconds
    while time.thread_time() < end:
        pass


def run_case(name: str, body, sid: str) -> None:
    import threading

    acc = RunAccumulator(profile="probe", instr_version=3)
    set_run_accumulator(acc)
    reg = get_thread_registry()
    reg.begin_session(sid)

    proc0 = time.process_time()
    t = threading.Thread(target=body, name=f"probe_{name}")
    t.start()
    t.join()
    sample_session_threads(acc, burst=True)
    proc_ms = (time.process_time() - proc0) * 1000

    tool = acc.totals_for(Category.TOOL_COMPUTE, sid).cpu_ns / 1e6
    pool = acc.totals_for(Category.THREADPOOL, sid).cpu_ns / 1e6
    fw = acc.totals_for(Category.FRAMEWORK, sid).cpu_ns / 1e6
    prov = acc.provenance_summary(sid)
    print(f"\n[{name}]")
    print(f"  process CPU      : {proc_ms:9.1f} ms")
    print(f"  TOOL_COMPUTE     : {tool:9.1f} ms")
    print(f"  THREADPOOL       : {pool:9.1f} ms")
    print(f"  FRAMEWORK (main) : {fw:9.1f} ms")
    print(f"  measured prov    : {prov[MEASURED] / 1e6:9.1f} ms   residual: {prov[RESIDUAL] / 1e6:.1f} ms")
    set_run_accumulator(None)


def main() -> None:
    import os

    import numpy as np

    install_thread_identity_hooks()

    print(
        "BLAS env pin:",
        {k: os.environ.get(k, "unset") for k in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS")},
    )

    try:
        import threadpoolctl

        info = threadpoolctl.threadpool_info()
        for lib in info:
            print(f"BLAS lib: {lib.get('internal_api')} threads={lib.get('num_threads')} "
                  f"({lib.get('filepath', '?')})")
    except ImportError:
        threadpoolctl = None
        print("threadpoolctl not installed; case 3 will be skipped")
    print(f"numpy {np.__version__}")

    # Case 1: pure-Python burn inside a TOOL timer on an executor thread.
    def pure_burn() -> None:
        with timed(Category.TOOL_COMPUTE, "s1"):
            _burn_cpu(0.2)

    run_case("pure_python_200ms_burn", pure_burn, "s1")

    # Case 2: real retrieve matmuls with env-pinned BLAS (v3.1+ production default).
    from apu_characterization.tools.impl import _load_vectors, tool_retrieve
    import random

    _load_vectors()  # warm outside the measured window

    def retrieve_default() -> None:
        rng = random.Random(0)
        for i in range(13):
            tool_retrieve(f"probe query {i}", "s2", rng)

    run_case("retrieve_x13_blas_env_pinned", retrieve_default, "s2")

    # Case 3: same retrieve with BLAS limited to 1 thread.
    if threadpoolctl is not None:
        def retrieve_single() -> None:
            rng = random.Random(0)
            with threadpoolctl.threadpool_limits(limits=1):
                for i in range(13):
                    tool_retrieve(f"probe query {i}", "s3", rng)

        run_case("retrieve_x13_blas_1thread", retrieve_single, "s3")

    # Case 4: retrieves separated by LLM-like idle gaps (spin-wait probe).
    # If OpenBLAS workers busy-spin after each matmul, spreading the same 13
    # retrieves over idle wall time should inflate process CPU well beyond
    # the back-to-back case 2 — the LH-01 v1->v3 host CPU delta signature.
    def retrieve_gapped() -> None:
        rng = random.Random(0)
        for i in range(13):
            tool_retrieve(f"probe query {i}", "s4", rng)
            time.sleep(0.8)

    run_case("retrieve_x13_gapped_800ms", retrieve_gapped, "s4")


if __name__ == "__main__":
    main()
