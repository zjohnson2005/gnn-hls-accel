from __future__ import annotations

import unittest

from apu_characterization.validity import (
    PROTOCOL_MICROBENCHMARK,
    artifact_stem,
    validity_banner,
)


class ProtocolMicrobenchmarkValidityTests(unittest.TestCase):
    def test_has_narrow_publication_banner(self) -> None:
        banner = validity_banner(PROTOCOL_MICROBENCHMARK)
        self.assertIn("Protocol microbenchmark", banner)
        self.assertIn("bare-metal", banner)
        self.assertIn("not production-agent", banner)

    def test_artifact_does_not_get_debug_suffix(self) -> None:
        self.assertEqual(
            artifact_stem("mcp_tax", PROTOCOL_MICROBENCHMARK),
            "mcp_tax",
        )


if __name__ == "__main__":
    unittest.main()
