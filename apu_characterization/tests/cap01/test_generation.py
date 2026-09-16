from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apu_characterization.cap01.contracts import TaskRecord
from apu_characterization.cap01.generation import (
    GenerationConfig,
    build_generation_prompt,
    generate_task_pool,
)
from apu_characterization.cap01.pool import PoolWriter


def task() -> TaskRecord:
    return TaskRecord(
        task_id="math-1",
        domain="MATH",
        prompt="Compute 6 * 7.",
        source="synthetic",
        source_version="1",
        provenance="fixture",
        license="CC0",
        verifier={"mode": "exact", "answer": "42", "secret": "hidden"},
        contamination_note="synthetic fixture",
    )


class GenerationTests(unittest.TestCase):
    def test_injected_transport_generates_without_live_call(self) -> None:
        requests: list[dict[str, object]] = []

        def fake_request(payload: object) -> dict[str, object]:
            requests.append(dict(payload))  # type: ignore[arg-type]
            index = len(requests)
            return {
                "id": f"req-{index}",
                "choices": [{"message": {"content": f"answer {index}"}}],
                "usage": {"prompt_tokens": 8, "completion_tokens": 2},
            }

        config = GenerationConfig(model="gpt-test", target_candidates=2)
        with tempfile.TemporaryDirectory() as directory:
            writer = PoolWriter(Path(directory) / "pool.jsonl", "math-1")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "must-not-leak"}):
                records = generate_task_pool(
                    task(), writer, config, request_fn=fake_request
                )

        self.assertEqual(2, len(records))
        self.assertEqual(["req-1", "req-2"], [item.generation_request_id for item in records])
        self.assertNotIn("must-not-leak", repr(requests))
        self.assertNotIn("secret", repr(requests))
        self.assertNotIn("harness", build_generation_prompt(task(), config).lower())

    def test_public_config_never_contains_environment_key(self) -> None:
        config = GenerationConfig(model="gpt-test", target_candidates=1)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "private-value"}):
            self.assertNotIn("private-value", repr(config.public_dict()))


if __name__ == "__main__":
    unittest.main()
