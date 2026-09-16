"""Append-safe construction and immutable storage for CAP-01 candidate pools."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import (
    PROTOCOL_VERSION,
    CandidateRecord,
    PoolMetadata,
    canonical_json_bytes,
    sha256_bytes,
    sha256_json,
)


class PoolError(RuntimeError):
    """Raised when a pool artifact is incomplete, inconsistent, or corrupt."""


def _json_line(value: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _write_all(descriptor: int, content: bytes) -> None:
    view = memoryview(content)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise PoolError("write made no progress")
        view = view[written:]


def _read_candidates(path: Path) -> tuple[CandidateRecord, ...]:
    candidates: list[CandidateRecord] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.endswith("\n"):
                    raise PoolError(
                        f"{path}: incomplete JSONL record at line {line_number}"
                    )
                try:
                    value = json.loads(line)
                    candidate = CandidateRecord.from_dict(value)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise PoolError(
                        f"{path}: invalid candidate at line {line_number}"
                    ) from exc
                candidates.append(candidate)
    except FileNotFoundError as exc:
        raise PoolError(f"candidate pool does not exist: {path}") from exc
    return tuple(candidates)


class PoolWriter:
    """Durably append candidates to a resumable JSONL staging file."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        task_id: str,
        *,
        resume: bool = True,
    ) -> None:
        self.path = Path(path)
        self.task_id = task_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and not resume:
            raise FileExistsError(self.path)
        self._candidates = list(_read_candidates(self.path)) if self.path.exists() else []
        for index, candidate in enumerate(self._candidates):
            if candidate.task_id != task_id or candidate.ordinal != index:
                raise PoolError("staging pool does not match task or contiguous ordinals")
        ids = [candidate.candidate_id for candidate in self._candidates]
        if len(ids) != len(set(ids)):
            raise PoolError("staging pool contains duplicate candidate IDs")

    @property
    def count(self) -> int:
        return len(self._candidates)

    @property
    def candidates(self) -> tuple[CandidateRecord, ...]:
        return tuple(self._candidates)

    def append(self, candidate: CandidateRecord) -> None:
        if candidate.task_id != self.task_id:
            raise PoolError("candidate task_id does not match the staging pool")
        if candidate.ordinal != self.count:
            raise PoolError(
                f"candidate ordinal {candidate.ordinal} does not equal next ordinal "
                f"{self.count}"
            )
        if any(item.candidate_id == candidate.candidate_id for item in self._candidates):
            raise PoolError(f"duplicate candidate_id: {candidate.candidate_id}")
        data = _json_line(asdict(candidate))
        flags = (
            os.O_APPEND
            | os.O_CREAT
            | os.O_WRONLY
            | getattr(os, "O_BINARY", 0)
        )
        descriptor = os.open(self.path, flags, 0o600)
        try:
            _write_all(descriptor, data)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self._candidates.append(candidate)

    def extend(self, candidates: Iterable[CandidateRecord]) -> None:
        for candidate in candidates:
            self.append(candidate)


def build_manifest(
    metadata: PoolMetadata,
    pool_bytes: bytes,
    *,
    generation_backend: str = "openai",
) -> dict[str, Any]:
    """Build the complete, canonical manifest for one frozen task pool."""
    token_counts = [
        {
            "candidate_id": candidate.candidate_id,
            "prompt_tokens": candidate.prompt_tokens,
            "completion_tokens": candidate.completion_tokens,
        }
        for candidate in metadata.candidates
    ]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "generation_backend": generation_backend,
        "task_id": metadata.task_id,
        "generation_model": metadata.generation_model,
        "temperature": metadata.temperature,
        "prompt_template_sha256": metadata.prompt_template_sha256,
        "candidate_count": len(metadata.candidates),
        "candidate_token_counts": token_counts,
        "candidate_sha256": {
            candidate.candidate_id: candidate.digest()
            for candidate in metadata.candidates
        },
        "task_pool_sha256": metadata.pool_sha256(),
        "jsonl_sha256": sha256_bytes(pool_bytes),
    }


def freeze_pool(
    writer: PoolWriter,
    frozen_path: str | os.PathLike[str],
    manifest_path: str | os.PathLike[str],
    *,
    generation_model: str,
    temperature: float,
    prompt_template_sha256: str,
    minimum_candidates: int = 2048,
    generation_backend: str = "openai",
) -> PoolMetadata:
    """Atomically freeze a staging pool into immutable JSONL and manifest files."""
    metadata = PoolMetadata(
        task_id=writer.task_id,
        generation_model=generation_model,
        temperature=temperature,
        prompt_template_sha256=prompt_template_sha256,
        candidates=writer.candidates,
    )
    metadata.validate(minimum_candidates)
    pool_bytes = b"".join(_json_line(asdict(item)) for item in metadata.candidates)
    manifest = build_manifest(
        metadata, pool_bytes, generation_backend=generation_backend
    )

    frozen = Path(frozen_path)
    manifest_file = Path(manifest_path)
    frozen.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    if frozen.exists() or manifest_file.exists():
        raise FileExistsError("frozen pool artifacts are write-once")

    temporary_pool = frozen.with_name(f".{frozen.name}.{os.getpid()}.tmp")
    temporary_manifest = manifest_file.with_name(
        f".{manifest_file.name}.{os.getpid()}.tmp"
    )
    try:
        _write_new_file(temporary_pool, pool_bytes)
        _write_new_file(
            temporary_manifest,
            canonical_json_bytes(manifest) + b"\n",
        )
        os.replace(temporary_pool, frozen)
        os.replace(temporary_manifest, manifest_file)
        _make_read_only(frozen)
        _make_read_only(manifest_file)
    finally:
        temporary_pool.unlink(missing_ok=True)
        temporary_manifest.unlink(missing_ok=True)
    return metadata


def _write_new_file(path: Path, content: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_CREAT
        | os.O_EXCL
        | os.O_WRONLY
        | getattr(os, "O_BINARY", 0),
        0o600,
    )
    try:
        _write_all(descriptor, content)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _make_read_only(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def load_frozen_pool(
    frozen_path: str | os.PathLike[str],
    manifest_path: str | os.PathLike[str],
    *,
    minimum_candidates: int = 2048,
) -> PoolMetadata:
    """Load a frozen pool only after validating all recorded hashes."""
    frozen = Path(frozen_path)
    manifest_file = Path(manifest_path)
    try:
        pool_bytes = frozen.read_bytes()
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise PoolError("missing or invalid frozen pool artifact") from exc
    candidates = _read_candidates(frozen)
    try:
        metadata = PoolMetadata(
            task_id=str(manifest["task_id"]),
            generation_model=str(manifest["generation_model"]),
            temperature=float(manifest["temperature"]),
            prompt_template_sha256=str(manifest["prompt_template_sha256"]),
            candidates=candidates,
        )
        metadata.validate(minimum_candidates)
    except (KeyError, TypeError, ValueError) as exc:
        raise PoolError("invalid pool manifest metadata") from exc
    backend = str(manifest.get("generation_backend") or "openai")
    expected = build_manifest(
        metadata, pool_bytes, generation_backend=backend
    )
    if manifest != expected:
        raise PoolError("pool manifest or JSONL hash verification failed")
    return metadata


def pool_manifest_sha256(manifests: Iterable[Mapping[str, Any]]) -> str:
    """Hash task manifests in deterministic task_id order."""
    ordered = sorted((dict(item) for item in manifests), key=lambda item: item["task_id"])
    return sha256_json(ordered)
