"""Tests for ORCH measured vs reconcile split."""

from __future__ import annotations

import unittest

from apu_characterization.attribution import split_session_orch_after_reconcile
from apu_characterization.stats import _pooled_shares_from_run


class TestOrchSplit(unittest.TestCase):
    def test_split_proportional_after_trim(self) -> None:
        measured, reconcile = split_session_orch_after_reconcile(
            orch_measured_before_ns=100,
            reconcile_added_ns=900,
            orch_total_final_ns=500,
        )
        self.assertEqual(measured, 50)
        self.assertEqual(reconcile, 450)

    def test_no_reconcile(self) -> None:
        measured, reconcile = split_session_orch_after_reconcile(100, 0, 100)
        self.assertEqual(measured, 100)
        self.assertEqual(reconcile, 0)

    def test_pooled_shares_from_sessions(self) -> None:
        run = {
            "per_category": {"ORCH_SETUP": {"cpu_ns": 0}, "ORCH_DISPATCH": {"cpu_ns": 0}},
            "per_session": [
                {"orch_measured_cpu_ns": 30, "orch_reconcile_cpu_ns": 70},
                {"orch_measured_cpu_ns": 10, "orch_reconcile_cpu_ns": 90},
            ],
        }
        shares = _pooled_shares_from_run(run, 200)
        self.assertAlmostEqual(shares["pooled_orch_measured_pct"], 20.0)
        self.assertAlmostEqual(shares["pooled_orch_reconcile_pct"], 80.0)


if __name__ == "__main__":
    unittest.main()
