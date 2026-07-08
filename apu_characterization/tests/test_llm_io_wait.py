"""llm_io_wait_s regression: LLM round-trip wall must be booked under v2/v3.

The v2 instr rework skipped the HTTP_CLIENT booking entirely when
instr_version >= 2, so llm_io_wait_s (which reads HTTP_CLIENT wall_ns) read
0.0 on live OpenAI runs — the v3 replication wall-axis anomaly.
"""

from __future__ import annotations

import time
import unittest
from uuid import uuid4

from apu_characterization.harness.instr_callback import InstrLLMCallback
from apu_characterization.instr import RunAccumulator, set_run_accumulator
from apu_characterization.taxonomy import Category


class _FakeGeneration:
    text = "hello world"


class _FakeResponse:
    generations = [[_FakeGeneration()]]


class TestLLMIOWait(unittest.TestCase):
    def _round_trip(self, instr_version: int) -> RunAccumulator:
        acc = RunAccumulator(profile="test", instr_version=instr_version)
        set_run_accumulator(acc)
        cb = InstrLLMCallback("s0")
        run_id = uuid4()
        cb.on_llm_start({}, ["prompt"], run_id=run_id)
        time.sleep(0.05)  # blocking network wait: wall advances, thread CPU ~0
        cb.on_llm_end(_FakeResponse(), run_id=run_id)
        set_run_accumulator(None)
        return acc

    def test_v3_books_llm_wall_into_http_client(self) -> None:
        acc = self._round_trip(instr_version=3)
        totals = acc.totals_for(Category.HTTP_CLIENT, "s0")
        self.assertGreaterEqual(
            totals.wall_ns,
            int(0.05 * 1e9),
            "LLM round-trip wall must land in HTTP_CLIENT.wall_ns "
            "(llm_io_wait_s reads exactly this field)",
        )
        # CPU must NOT be booked here under v2/v3: transport CPU is owned by
        # thread-identity (CLIENT_HTTP); double-booking breaks the audit.
        self.assertLess(totals.cpu_ns, int(0.01 * 1e9))

    def test_v1_path_unchanged(self) -> None:
        acc = self._round_trip(instr_version=1)
        totals = acc.totals_for(Category.HTTP_CLIENT, "s0")
        self.assertGreaterEqual(totals.wall_ns, int(0.05 * 1e9))


if __name__ == "__main__":
    unittest.main()
