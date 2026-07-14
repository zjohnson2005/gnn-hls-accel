from __future__ import annotations

import unittest

from apu_characterization.mcp_tax.contracts import (
    PROTOCOL_VERSION,
    enumerate_matrix,
    load_protocol,
)
from apu_characterization.mcp_tax.taxonomy import MCP_INSTRUMENTED, McpCategory


class ProtocolLockTests(unittest.TestCase):
    def test_matrix_counts_are_frozen(self) -> None:
        self.assertEqual(len(enumerate_matrix()), 120)
        self.assertEqual(len(enumerate_matrix(include_http_stream=True)), 160)

    def test_categories_match_protocol(self) -> None:
        protocol = load_protocol()
        self.assertEqual(
            protocol["category_names"],
            [category.value for category in McpCategory],
        )
        self.assertNotIn(McpCategory.RESIDUAL, MCP_INSTRUMENTED)

    def test_version_is_v1_5(self) -> None:
        self.assertEqual(PROTOCOL_VERSION, "mcp_tax_v1.5")
        protocol = load_protocol()
        self.assertEqual(protocol["protocol_version"], "mcp_tax_v1.5")
        self.assertIn("MSG_VALIDATE", protocol["clarifications"])
        self.assertIn("MSG_DISPATCH", protocol["clarifications"])
        self.assertIn("g6_provenance_coverage", protocol["clarifications"])
        self.assertIn("g7_gap_split_conservation", protocol["clarifications"])
        self.assertIn("diffuseness_verdict", protocol["clarifications"])
        self.assertIn("verdict_min_population", protocol["clarifications"])
        self.assertIn("verdict_per_arm", protocol["clarifications"])
        self.assertIn("gap_syscall_return_subprovenance", protocol["clarifications"])
        audit = protocol["audit"]
        self.assertEqual(audit["g6_dominant_category_share"], 0.50)
        self.assertEqual(audit["g6_named_provenance_share"], 0.80)
        self.assertEqual(
            audit["diffuseness_verdict"]["confirm_min_mechanisms"], 3
        )
        self.assertEqual(
            audit["diffuseness_verdict"]["confirm_min_boundaries"], 2
        )
        self.assertEqual(
            audit["diffuseness_verdict"]["unattributed_forces_inconclusive_share"],
            0.20,
        )
        self.assertEqual(audit["verdict_min_population"]["min_seeds"], 3)
        self.assertEqual(
            audit["verdict_min_population"]["min_measured_messages"], 20
        )
        self.assertEqual(
            audit["gap_split_precedence"][0], "gap_instrumentation"
        )


if __name__ == "__main__":
    unittest.main()
