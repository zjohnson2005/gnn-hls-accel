"""Debug thread registry booking (Linux only)."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from apu_characterization.instr import RunAccumulator, set_run_accumulator
from apu_characterization.taxonomy import Category
from apu_characterization.thread_identity import ThreadRole, _native_tid, get_thread_registry


def burn(seconds: float) -> None:
    end = time.thread_time() + seconds
    while time.thread_time() < end:
        pass


def main() -> None:
    acc = RunAccumulator(profile="test", instr_version=3)
    set_run_accumulator(acc)
    reg = get_thread_registry()
    reg.snapshot()
    sid = "s0"

    def worker() -> None:
        import threading

        tid = _native_tid()
        reg.register(tid, ThreadRole.HTTP_TRANSPORT, sid, overwrite=True)
        burn(0.1)
        now = reg._thread_cpu_ns()
        print("worker tid", tid, "psutil tids", list(now.keys())[:8], "cpu", now.get(tid))
        print("booked", reg.sample_and_book(acc))

    with ThreadPoolExecutor(max_workers=1) as ex:
        ex.submit(worker).result()
    http = acc.totals_for(Category.CLIENT_HTTP, sid).cpu_ns
    print("CLIENT_HTTP ns", http)
    print("provenance", acc.provenance_summary(sid))


if __name__ == "__main__":
    main()
