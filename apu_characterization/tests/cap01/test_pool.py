from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from apu_characterization.cap01.contracts import CandidateRecord
from apu_characterization.cap01.pool import (
    PoolError,
    PoolWriter,
    freeze_pool,
    load_frozen_pool,
)


def candidate(ordinal: int) -> CandidateRecord:
    return CandidateRecord(
        candidate_id=f"c-{ordinal}",
        task_id="math-1",
        ordinal=ordinal,
        content=str(ordinal),
        prompt_tokens=10,
        completion_tokens=1,
        generation_request_id=f"req-{ordinal}",
    )


class PoolTests(unittest.TestCase):
    def test_writer_resumes_and_freezes_verified_pool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            staging = root / "staging.jsonl"
            writer = PoolWriter(staging, "math-1")
            writer.extend([candidate(0), candidate(1)])
            resumed = PoolWriter(staging, "math-1")
            resumed.append(candidate(2))

            frozen = root / "pool.jsonl"
            manifest = root / "manifest.json"
            metadata = freeze_pool(
                resumed,
                frozen,
                manifest,
                generation_model="gpt-test",
                temperature=1.0,
                prompt_template_sha256="a" * 64,
                minimum_candidates=3,
            )
            loaded = load_frozen_pool(frozen, manifest, minimum_candidates=3)
            self.assertEqual(metadata.pool_sha256(), loaded.pool_sha256())
            self.assertEqual(3, len(loaded.candidates))
            recorded = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(3, len(recorded["candidate_token_counts"]))

    def test_incomplete_append_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "staging.jsonl"
            path.write_text('{"candidate_id":"partial"}', encoding="utf-8")
            with self.assertRaises(PoolError):
                PoolWriter(path, "math-1")


if __name__ == "__main__":
    unittest.main()
