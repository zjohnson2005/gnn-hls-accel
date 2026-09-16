from __future__ import annotations

import importlib.util
import shutil
import unittest

from apu_characterization.cap01.harnesses import (
    HarnessUnavailableError,
    LangGraphHarness,
    RawPythonHarness,
    RustHarness,
    build_rust_harness,
)

REQUEST = {
    "op": "candidate",
    "sequence_index": 3,
    "candidate_id": "candidate-3",
    "candidate_sha256": "a" * 64,
}


def exercise(harness: object) -> dict[str, object]:
    harness.setup()  # type: ignore[attr-defined]
    try:
        return dict(harness.dispatch(REQUEST))  # type: ignore[attr-defined]
    finally:
        harness.close()  # type: ignore[attr-defined]


class HarnessTests(unittest.TestCase):
    def assert_contract(self, response: dict[str, object]) -> None:
        self.assertTrue(response["ok"])
        self.assertEqual(response["candidate_id"], REQUEST["candidate_id"])
        self.assertEqual(response["candidate_sha256"], REQUEST["candidate_sha256"])
        self.assertEqual(response["sequence_index"], REQUEST["sequence_index"])
        self.assertGreaterEqual(int(response["harness_wall_ns"]), 0)
        self.assertGreaterEqual(int(response["harness_cpu_ns"]), 0)

    def test_raw_python_contract(self) -> None:
        self.assert_contract(exercise(RawPythonHarness()))

    def test_langgraph_is_real_or_explicitly_refused(self) -> None:
        if importlib.util.find_spec("langgraph") is None:
            with self.assertRaises(HarnessUnavailableError):
                LangGraphHarness().setup()
            return
        self.assert_contract(exercise(LangGraphHarness()))

    @unittest.skipUnless(shutil.which("rustc"), "rustc is not installed")
    def test_actual_rust_binary_contract(self) -> None:
        executable = build_rust_harness(force=True)
        self.assert_contract(exercise(RustHarness(executable, build=False)))

    @unittest.skipUnless(shutil.which("rustc"), "rustc is not installed")
    def test_rust_large_payload_is_not_echoed(self) -> None:
        """Anti-leak smoke: response must echo ids only, never the content blob.

        MCP-01 raw stdio taught that payload-scaling copy paths look like
        physics until measured. CAP-01 Rust must not reintroduce that class of
        leak before the LangGraph-vs-Rust primary cell re-run.
        """
        executable = build_rust_harness(force=True)
        blob = "Z" * (256 * 1024)
        request = {
            "op": "candidate",
            "sequence_index": 9,
            "candidate_id": "big-candidate",
            "candidate_sha256": "b" * 64,
            "content": blob,
        }
        harness = RustHarness(executable, build=False)
        harness.setup()
        try:
            response = dict(harness.dispatch(request))
        finally:
            harness.close()
        self.assertTrue(response["ok"])
        self.assertEqual(response["candidate_id"], "big-candidate")
        self.assertEqual(response["candidate_sha256"], "b" * 64)
        self.assertEqual(response["sequence_index"], 9)
        encoded = str(response)
        self.assertNotIn(blob[:64], encoded)
        self.assertNotIn("content", encoded)


if __name__ == "__main__":
    unittest.main()
