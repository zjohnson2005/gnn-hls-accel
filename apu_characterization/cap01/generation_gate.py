"""Gate live OpenAI generation on a pre-generation protocol lock."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import sha256_json


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_generation_cleared(
    *,
    locked_protocol_path: Path,
    corpus_manifest_path: Path,
    generation_config_path: Path,
) -> Mapping[str, Any]:
    protocol = _load_json(locked_protocol_path)
    if protocol.get("status") != "locked":
        raise ValueError("protocol is not locked")
    if protocol.get("lock_phase") != "pre_generation":
        raise ValueError(
            "live generation requires lock_phase=pre_generation; "
            f"got {protocol.get('lock_phase')!r}"
        )
    lock_fields = protocol.get("lock_fields") or {}
    corpus = _load_json(corpus_manifest_path)
    generation = _load_json(generation_config_path)
    expected_corpus = lock_fields.get("corpus_manifest_sha256")
    expected_generation = lock_fields.get("generation_config_sha256")
    actual_corpus = sha256_json(corpus)
    actual_generation = sha256_json(generation)
    if expected_corpus != actual_corpus:
        raise ValueError(
            "corpus manifest hash does not match locked protocol "
            f"(expected {expected_corpus}, got {actual_corpus})"
        )
    if expected_generation != actual_generation:
        raise ValueError(
            "generation config hash does not match locked protocol "
            f"(expected {expected_generation}, got {actual_generation})"
        )
    return protocol
