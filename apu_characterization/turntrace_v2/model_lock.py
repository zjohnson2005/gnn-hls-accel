"""Pinned rev C local model lock — refuse silent GGUF swaps."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

MODEL_LOCK_PATH = Path(__file__).resolve().with_name("model_lock_rev_c.json")
SCHEMA_VERSION = "turntrace_rev_c_model_lock_v1"


def load_model_lock(path: Path | None = None) -> dict:
    lock_path = Path(path or MODEL_LOCK_PATH)
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported model lock schema: {data.get('schema_version')!r}"
        )
    return data


def sha256_file(path: Path, *, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def resolve_model_path(lock: dict, *, repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    return (root / str(lock["relative_path"])).resolve()


def validate_model_lock(
    path: Path | None = None,
    *,
    repo_root: Path | None = None,
    require_file: bool = True,
) -> list[str]:
    """Return human-readable errors; empty list means the pin is intact."""
    errors: list[str] = []
    lock_path = Path(path or MODEL_LOCK_PATH)
    try:
        lock = load_model_lock(lock_path)
    except Exception as exc:  # noqa: BLE001 — surface as validation error
        return [f"model lock unreadable: {exc}"]

    required = (
        "sha256",
        "filename",
        "quantization",
        "model_id",
        "relative_path",
        "n_ctx_pinned",
        "engine",
        "engine_version",
        "bytes",
    )
    for key in required:
        if key not in lock:
            errors.append(f"model lock missing field: {key}")
    if errors:
        return errors

    sha = str(lock["sha256"]).lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        errors.append("model lock sha256 must be 64 lowercase hex chars")

    if int(lock["n_ctx_pinned"]) < 16384:
        errors.append("model lock n_ctx_pinned must be >= 16384 for rev C")

    if lock.get("tool_role_remap") is not False:
        errors.append("model lock tool_role_remap must be false (TinyLlama remap must not transfer)")

    if str(lock.get("quantization")) != "Q4_K_M":
        errors.append("model lock quantization must be Q4_K_M for the pinned candidate")

    model_path = resolve_model_path(lock, repo_root=repo_root)
    if require_file:
        if not model_path.is_file():
            errors.append(f"pinned GGUF missing at {model_path}")
            return errors
        size = model_path.stat().st_size
        if int(lock["bytes"]) != size:
            errors.append(
                f"pinned GGUF size mismatch: lock={lock['bytes']} observed={size}"
            )
        observed = sha256_file(model_path)
        if observed != sha:
            errors.append(
                f"pinned GGUF sha256 mismatch: lock={sha} observed={observed}"
            )
    return errors


def assert_model_lock(
    path: Path | None = None,
    *,
    repo_root: Path | None = None,
    require_file: bool = True,
) -> dict:
    errors = validate_model_lock(
        path, repo_root=repo_root, require_file=require_file
    )
    if errors:
        raise ValueError("model lock validation failed: " + "; ".join(errors))
    return load_model_lock(path)
