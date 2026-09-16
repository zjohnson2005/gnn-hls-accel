"""Frozen data contracts and deterministic coordinates for CAP-01."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

PROTOCOL_VERSION = "cap01_v2.2"
PROTOCOL_PATH = Path(__file__).with_name("protocol_cap01_v2.json")
CANDIDATE_ORDER_NAMESPACE = "cap01_v1"

Domain = Literal[
    "FUNCTION_CALLING",
    "TEXT_TO_SQL",
    "CODE",
    "MATH",
    "STRUCTURED_EXTRACTION",
]
TaskClass = Literal["SCALING", "SATURATED", "DEAD"]
Harness = Literal["langgraph", "rust", "raw_python"]
InstrMode = Literal["throttle", "stripped"]
BudgetKind = Literal["wall", "energy"]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


PENDING_MANIFEST_DIGEST = sha256_json(
    {"lock_phase": "pre_generation", "manifest": "pending"}
)


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("CAP-01 protocol version mismatch")
    return protocol


def protocol_sha256(path: Path = PROTOCOL_PATH) -> str:
    return sha256_json(load_protocol(path))


def stable_seed(*parts: object) -> int:
    material = "\0".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    domain: Domain
    prompt: str
    source: str
    source_version: str
    provenance: str
    license: str
    verifier: Mapping[str, Any]
    contamination_note: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TaskRecord":
        record = cls(
            task_id=str(value["task_id"]),
            domain=str(value["domain"]),  # type: ignore[arg-type]
            prompt=str(value["prompt"]),
            source=str(value["source"]),
            source_version=str(value["source_version"]),
            provenance=str(value["provenance"]),
            license=str(value["license"]),
            verifier=dict(value["verifier"]),
            contamination_note=str(value.get("contamination_note") or ""),
        )
        record.validate()
        return record

    def validate(self) -> None:
        if not self.task_id or any(char.isspace() for char in self.task_id):
            raise ValueError("task_id must be non-empty and contain no whitespace")
        if self.domain not in (
            "FUNCTION_CALLING",
            "TEXT_TO_SQL",
            "CODE",
            "MATH",
            "STRUCTURED_EXTRACTION",
        ):
            raise ValueError(f"unsupported task domain: {self.domain}")
        if not self.prompt:
            raise ValueError(f"{self.task_id}: prompt is empty")
        if not self.source or not self.source_version:
            raise ValueError(f"{self.task_id}: source and source_version are required")
        if not self.provenance or not self.license:
            raise ValueError(f"{self.task_id}: provenance and license are required")
        if not self.verifier:
            raise ValueError(f"{self.task_id}: verifier configuration is required")
        if not self.contamination_note:
            raise ValueError(f"{self.task_id}: contamination_note is required")

    def digest(self) -> str:
        return sha256_json(asdict(self))


@dataclass(frozen=True)
class CandidateRecord:
    candidate_id: str
    task_id: str
    ordinal: int
    content: str
    prompt_tokens: int
    completion_tokens: int
    generation_request_id: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CandidateRecord":
        record = cls(
            candidate_id=str(value["candidate_id"]),
            task_id=str(value["task_id"]),
            ordinal=int(value["ordinal"]),
            content=str(value["content"]),
            prompt_tokens=int(value["prompt_tokens"]),
            completion_tokens=int(value["completion_tokens"]),
            generation_request_id=(
                str(value["generation_request_id"])
                if value.get("generation_request_id") is not None
                else None
            ),
        )
        if record.ordinal < 0:
            raise ValueError("candidate ordinal cannot be negative")
        if record.prompt_tokens < 0 or record.completion_tokens < 0:
            raise ValueError("candidate token counts cannot be negative")
        if not record.content:
            raise ValueError("candidate content cannot be empty")
        return record

    def digest(self) -> str:
        return sha256_json(asdict(self))


@dataclass(frozen=True)
class PoolMetadata:
    task_id: str
    generation_model: str
    temperature: float
    prompt_template_sha256: str
    candidates: tuple[CandidateRecord, ...]

    def validate(self, minimum_candidates: int) -> None:
        if len(self.candidates) < minimum_candidates:
            raise ValueError(
                f"{self.task_id}: pool has {len(self.candidates)} candidates; "
                f"requires at least {minimum_candidates}"
            )
        if any(candidate.task_id != self.task_id for candidate in self.candidates):
            raise ValueError(f"{self.task_id}: candidate task_id mismatch")
        ordinals = [candidate.ordinal for candidate in self.candidates]
        if ordinals != list(range(len(self.candidates))):
            raise ValueError(f"{self.task_id}: candidate ordinals are not contiguous")
        ids = [candidate.candidate_id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.task_id}: duplicate candidate_id")
        if not self.generation_model or not self.prompt_template_sha256:
            raise ValueError(f"{self.task_id}: incomplete generation provenance")

    def pool_sha256(self) -> str:
        return sha256_json(
            {
                "task_id": self.task_id,
                "generation_model": self.generation_model,
                "temperature": self.temperature,
                "prompt_template_sha256": self.prompt_template_sha256,
                "candidates": [asdict(candidate) for candidate in self.candidates],
            }
        )

    def seed_order(self, seed: int) -> tuple[int, ...]:
        order = list(range(len(self.candidates)))
        random.Random(
            stable_seed(CANDIDATE_ORDER_NAMESPACE, self.task_id, seed)
        ).shuffle(order)
        return tuple(order)

    def ordered_candidates(self, seed: int) -> tuple[CandidateRecord, ...]:
        return tuple(self.candidates[index] for index in self.seed_order(seed))


@dataclass(frozen=True)
class CellCoordinates:
    harness: Harness
    latency_scale_ms: int
    wall_budget_ms: int
    seed: int
    instr_mode: InstrMode = "throttle"
    budget_kind: BudgetKind = "wall"

    @property
    def cell_id(self) -> str:
        return (
            f"h-{self.harness}__l-{self.latency_scale_ms}ms__"
            f"b-{self.wall_budget_ms}ms__s-{self.seed}__"
            f"i-{self.instr_mode}__k-{self.budget_kind}"
        )


@dataclass(frozen=True)
class CandidateEvent:
    sequence_index: int
    candidate_id: str
    candidate_sha256: str
    latency_ns: int
    verifier_wall_ns: int
    verifier_cpu_ns: int
    started_ns: int
    verdict_ns: int | None
    counted: bool
    abandoned: bool
    solved: bool
    verdict_digest: str | None
    verdict_status: str | None = None
    verifier_runtime: str | None = None
    verifier_network_isolated: bool | None = None


def enumerate_primary_matrix(
    protocol: Mapping[str, Any] | None = None,
) -> list[CellCoordinates]:
    cfg = dict(protocol or load_protocol())
    matrix = cfg["matrix"]
    latency_scales = cfg["latency_backend"]["median_scales_ms"]
    return [
        CellCoordinates(
            harness=harness,
            latency_scale_ms=int(scale),
            wall_budget_ms=int(budget),
            seed=int(seed),
            instr_mode=str(matrix["instrument_mode"]),  # type: ignore[arg-type]
        )
        for budget in matrix["budget_order"]
        for scale in latency_scales
        for seed in matrix["seeds"]
        for harness in matrix["harnesses"]
    ]


def validate_lock(protocol: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if protocol.get("status") != "locked":
        errors.append("protocol status is not locked")
    lock_fields = protocol.get("lock_fields") or {}
    required = (
        "corpus_manifest_sha256",
        "pool_manifest_sha256",
        "classification_manifest_sha256",
        "generation_config_sha256",
        "answer_space_sha256",
        "expectations_sha256",
        "verifier_pin_manifest_sha256",
        "d5_normalization_sha256",
    )
    for name in required:
        value = lock_fields.get(name)
        if not isinstance(value, str) or len(value) != 64:
            errors.append(f"lock field {name} is not a sha256 digest")
    lock_phase = protocol.get("lock_phase")
    if lock_phase == "pre_generation":
        for name in ("pool_manifest_sha256", "classification_manifest_sha256"):
            if lock_fields.get(name) != PENDING_MANIFEST_DIGEST:
                errors.append(
                    f"pre_generation lock requires pending digest for {name}"
                )
    elif lock_phase == "post_generation":
        for name in ("pool_manifest_sha256", "classification_manifest_sha256"):
            if lock_fields.get(name) == PENDING_MANIFEST_DIGEST:
                errors.append(
                    f"post_generation lock cannot use pending digest for {name}"
                )
    return errors


def common_prefix(values: Sequence[Sequence[str]]) -> tuple[str, ...]:
    if not values:
        return ()
    shortest = min(len(value) for value in values)
    end = 0
    while end < shortest:
        item = values[0][end]
        if any(value[end] != item for value in values[1:]):
            break
        end += 1
    return tuple(values[0][:end])
