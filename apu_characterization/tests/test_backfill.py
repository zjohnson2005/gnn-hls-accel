"""Tests for legacy artifact ORCH backfill."""

from __future__ import annotations

import unittest

from apu_characterization.attribution import backfill_session_orch_fields
from apu_characterization.stats import backfill_run_orch_fields, batch_attribution_summary


class TestBackfill(unittest.TestCase):
    def test_backfill_session_from_categories(self) -> None:
        session = {
            "session_id": "agent_0",
            "process_cpu_ns": 1_000_000_000,
            "reconcile_cpu_ns": 900_000_000,
        }
        per_session_category = {
            "agent_0": {
                "ORCH_SETUP": {"cpu_ns": 50_000_000},
                "ORCH_DISPATCH": {"cpu_ns": 950_000_000},
            }
        }
        self.assertTrue(backfill_session_orch_fields(session, per_session_category))
        self.assertEqual(session["orch_measured_cpu_ns"], 100_000_000)
        self.assertEqual(session["orch_reconcile_cpu_ns"], 900_000_000)

    def test_backfill_run_updates_batch_attribution(self) -> None:
        run = {
            "per_session": [
                {
                    "session_id": "a0",
                    "reconcile_cpu_ns": 80,
                }
            ],
            "per_session_category": {
                "a0": {
                    "ORCH_SETUP": {"cpu_ns": 20},
                    "ORCH_DISPATCH": {"cpu_ns": 80},
                }
            },
            "per_category": {
                "ORCH_SETUP": {"cpu_ns": 20},
                "ORCH_DISPATCH": {"cpu_ns": 80},
                "TOKENIZATION": {"cpu_ns": 0},
                "SERIALIZATION": {"cpu_ns": 0},
                "TOOL_COMPUTE": {"cpu_ns": 0},
            },
        }
        n = backfill_run_orch_fields(run)
        self.assertEqual(n, 1)
        ba = batch_attribution_summary(run, 100)
        self.assertAlmostEqual(ba["pooled_orch_reconcile_pct"], 80.0)
        self.assertAlmostEqual(ba["orch_reconcile_pct_of_orch"], 80.0)


if __name__ == "__main__":
    unittest.main()
