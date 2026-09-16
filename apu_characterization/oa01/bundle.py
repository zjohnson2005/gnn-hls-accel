"""Append-only OA-01 replay bundle packaging."""

from __future__ import annotations

import hashlib
import json
import zlib
from pathlib import Path
from typing import Any, Mapping


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def save_bundle(value: Mapping[str, Any], path: Path) -> Path:
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"append-only replay bundle already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(dict(value))
    path.write_bytes(zlib.compress(raw, level=9))
    path.with_suffix(path.suffix + ".sha256").write_text(
        hashlib.sha256(raw).hexdigest() + "\n", encoding="utf-8"
    )
    return path


def load_bundle(path: Path) -> dict[str, Any]:
    raw = zlib.decompress(Path(path).read_bytes())
    digest_path = Path(path).with_suffix(Path(path).suffix + ".sha256")
    if digest_path.is_file():
        expected = digest_path.read_text(encoding="utf-8").strip()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise ValueError(f"replay bundle hash mismatch: {path}")
    return json.loads(raw.decode("utf-8"))

