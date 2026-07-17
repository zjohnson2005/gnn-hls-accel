"""Deterministic rev C task suite with real, hash-pinned repository payloads."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from apu_characterization.turntrace_v2.arms import ArmConfig
from apu_characterization.turntrace_v2.contracts import canonical_json_bytes
from apu_characterization.turntrace_v2.harnesses.langgraph_harness import GraphStep
from apu_characterization.turntrace_v2.harnesses.raw_python import HarnessTurn


WORKLOAD_PREFIX = "turntrace_rev_c"
SEEDS = (0, 1, 2, 3, 4)
FROZEN_PAYLOAD_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "rev_c_payload_manifest.json"

PAYLOAD_SOURCE_PATHS = (
    "apu_characterization/fixtures/corpus.txt",
    "apu_characterization/METHODOLOGY.md",
    "apu_characterization/METHODOLOGY_TLP01.md",
    "apu_characterization/METHODOLOGY_CAP01.md",
    "apu_characterization/tasks.py",
    "apu_characterization/turntrace_v2/boundary-cases.md",
    "apu_characterization/turntrace_v2/export.py",
    "apu_characterization/turntrace_v2/rev_c_payloads/turntrace_pytest_output.txt",
)


@dataclass(frozen=True)
class TaskClassSpec:
    task_id: str
    shape: str
    turns: int
    box_target_tokens: int
    cpu_target_tokens: int
    tool_cycle: tuple[str, ...]


TASK_CLASSES = {
    "TT-EDIT": TaskClassSpec(
        "TT-EDIT",
        "edit_verify_loop",
        20,
        12000,
        4000,
        ("read_file", "edit_file", "run_tests"),
    ),
    "TT-RET": TaskClassSpec(
        "TT-RET",
        "retrieval_accumulation",
        18,
        16000,
        5000,
        ("search", "fetch", "append_summary"),
    ),
    "TT-FAN": TaskClassSpec(
        "TT-FAN",
        "fanout_then_synthesize",
        12,
        8000,
        3000,
        ("search", "read_file", "synthesize"),
    ),
    "TT-DOC": TaskClassSpec(
        "TT-DOC",
        "progressive_long_document_read",
        16,
        20000,
        6000,
        ("read_chunk",),
    ),
    "TT-CHAIN": TaskClassSpec(
        "TT-CHAIN",
        "chained_transform_pipeline",
        15,
        10000,
        4000,
        ("transform",),
    ),
}


@dataclass(frozen=True)
class PayloadCatalog:
    repo_root: str
    sources: tuple[dict[str, object], ...]
    corpus_sha256: str
    corpus_text: str
    source_texts: tuple[tuple[str, str], ...]

    def manifest_dict(self) -> dict[str, object]:
        return {
            "schema_version": "turntrace_rev_c_payload_v1",
            "source_kind": "real_repository_content",
            "sources": list(self.sources),
            "corpus_sha256": self.corpus_sha256,
            "corpus_bytes": len(self.corpus_text.encode("utf-8")),
        }


@dataclass(frozen=True)
class SuitePlan:
    task_class: str
    seed: int
    arm: str
    interventions_active: tuple[str, ...]
    pair_id: str
    workload_id: str
    target_tokens: int
    messages_by_turn: tuple[tuple[dict[str, str], ...], ...]
    tool_names_by_turn: tuple[tuple[str, ...], ...]
    tool_args_by_turn: tuple[tuple[dict[str, object], ...], ...]
    payload_manifest_sha256: str


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_payload_catalog(repo_root: Path | None = None) -> PayloadCatalog:
    repo_root = Path(repo_root or default_repo_root()).resolve()
    sources: list[dict[str, object]] = []
    texts: list[str] = []
    source_texts: list[tuple[str, str]] = []
    for rel in PAYLOAD_SOURCE_PATHS:
        path = repo_root / rel
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        sources.append(
            {
                "path": rel.replace("\\", "/"),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        )
        source_texts.append((rel, text))
        texts.append(f"\n\n--- SOURCE: {rel} ---\n{text}")
    corpus = "".join(texts)
    return PayloadCatalog(
        repo_root=str(repo_root),
        sources=tuple(sources),
        corpus_sha256=hashlib.sha256(corpus.encode("utf-8")).hexdigest(),
        corpus_text=corpus,
        source_texts=tuple(source_texts),
    )


def freeze_payload_manifest(
    path: Path,
    *,
    repo_root: Path | None = None,
    catalog: PayloadCatalog | None = None,
) -> dict[str, object]:
    catalog = catalog or build_payload_catalog(repo_root)
    manifest = payload_manifest_dict(catalog)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def payload_manifest_dict(catalog: PayloadCatalog) -> dict[str, object]:
    manifest = catalog.manifest_dict()
    manifest["task_classes"] = {
        name: asdict(spec) for name, spec in TASK_CLASSES.items()
    }
    manifest["seeds"] = list(SEEDS)
    manifest["manifest_sha256"] = hashlib.sha256(
        canonical_json_bytes(manifest)
    ).hexdigest()
    return manifest


def validate_frozen_payload_manifest(
    path: Path = FROZEN_PAYLOAD_MANIFEST_PATH,
    *,
    repo_root: Path | None = None,
) -> list[str]:
    path = Path(path)
    if not path.is_file():
        return [f"missing frozen payload manifest: {path}"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    embedded_hash = str(manifest.get("manifest_sha256") or "")
    hash_payload = dict(manifest)
    hash_payload.pop("manifest_sha256", None)
    observed_hash = hashlib.sha256(canonical_json_bytes(hash_payload)).hexdigest()
    errors: list[str] = []
    if embedded_hash != observed_hash:
        errors.append("payload manifest self-hash mismatch")
    root = Path(repo_root or default_repo_root()).resolve()
    texts: list[str] = []
    for source in manifest.get("sources") or []:
        rel = str(source.get("path") or "")
        source_path = root / rel
        if not source_path.is_file():
            errors.append(f"payload source missing: {rel}")
            continue
        raw = source_path.read_bytes()
        if len(raw) != int(source.get("bytes") or -1):
            errors.append(f"payload source byte-size mismatch: {rel}")
        if hashlib.sha256(raw).hexdigest() != str(source.get("sha256") or ""):
            errors.append(f"payload source hash mismatch: {rel}")
        text = raw.decode("utf-8", errors="replace")
        texts.append(f"\n\n--- SOURCE: {rel} ---\n{text}")
    if len(texts) == len(manifest.get("sources") or []):
        corpus = "".join(texts)
        if len(corpus.encode("utf-8")) != int(manifest.get("corpus_bytes") or -1):
            errors.append("payload corpus byte-size mismatch")
        if hashlib.sha256(corpus.encode("utf-8")).hexdigest() != str(
            manifest.get("corpus_sha256") or ""
        ):
            errors.append("payload corpus hash mismatch")
    return errors


def _payload_words(catalog: PayloadCatalog, *, seed: int) -> list[str]:
    text = catalog.corpus_text
    if not text:
        raise ValueError("rev C payload corpus is empty")
    # A bounded cyclic window avoids materializing millions of Python strings
    # from the large real-payload corpus for every seed/arm plan.
    window_chars = min(len(text), 2_000_000)
    start = random.Random(seed).randrange(len(text))
    end = start + window_chars
    sample = text[start:end]
    if end > len(text):
        sample += text[: end - len(text)]
    words = sample.split()
    if not words:
        raise ValueError("rev C payload corpus is empty")
    return words


def _chunk_words(words: Sequence[str], start: int, count: int) -> tuple[str, int]:
    if count <= 0:
        return "", start
    selected = [words[(start + idx) % len(words)] for idx in range(count)]
    return " ".join(selected), start + count


def _tool_args(
    spec: TaskClassSpec,
    *,
    turn_index: int,
    payload: str,
    prior_result_id: str | None,
) -> tuple[tuple[str, ...], tuple[dict[str, object], ...]]:
    tool = spec.tool_cycle[turn_index % len(spec.tool_cycle)]
    base: dict[str, object] = {
        "turn_index": turn_index,
        "_payload": payload,
        "result_id": f"{spec.task_id}-result-{turn_index:02d}",
    }
    if spec.task_id == "TT-EDIT":
        base["path"] = "apu_characterization/turntrace_v2/schema.py"
    elif spec.task_id == "TT-RET":
        base["query"] = f"rev-c-topic-{turn_index:02d}"
    elif spec.task_id == "TT-DOC":
        base["chunk_index"] = turn_index
    elif spec.task_id == "TT-CHAIN" and prior_result_id:
        base["from_result"] = prior_result_id
    if spec.task_id == "TT-FAN" and turn_index < spec.turns - 1:
        names = ("search", "read_file")
        return names, (
            {**base, "query": f"fanout-{turn_index}-a"},
            {**base, "path": "apu_characterization/fixtures/corpus.txt"},
        )
    if spec.task_id == "TT-FAN":
        return ("synthesize",), (base,)
    return (tool,), (base,)


def build_suite_plan(
    task_class: str,
    *,
    seed: int,
    arm_config: ArmConfig,
    harness_id: str,
    deployment_id: str,
    target: str = "cpu_prebox",
    pair_variant: str = "full",
    catalog: PayloadCatalog | None = None,
    token_count: Callable[[str], int] | None = None,
    message_token_count: Callable[[Sequence[dict[str, str]]], object] | None = None,
) -> SuitePlan:
    if task_class not in TASK_CLASSES:
        raise ValueError(f"unknown rev C task class: {task_class}")
    if seed not in SEEDS:
        raise ValueError(f"seed must be one of {SEEDS}")
    if target not in {"cpu_prebox", "box"}:
        raise ValueError("target must be cpu_prebox or box")
    spec = TASK_CLASSES[task_class]
    target_tokens = (
        spec.cpu_target_tokens if target == "cpu_prebox" else spec.box_target_tokens
    )
    catalog = catalog or build_payload_catalog()
    count_tokens = token_count or (lambda text: len(text.split()))
    words = _payload_words(catalog, seed=seed)
    static = [
        {
            "role": "system",
            "content": (
                "TurnTrace rev C deterministic characterization. Follow the fixed "
                "tool sequence; do not change task content."
            ),
        },
        {
            "role": "user",
            "content": f"Task class {task_class}; seed {seed}; shape {spec.shape}.",
        },
    ]
    history = list(static)
    messages_by_turn: list[tuple[dict[str, str], ...]] = []
    names_by_turn: list[tuple[str, ...]] = []
    args_by_turn: list[tuple[dict[str, object], ...]] = []
    cursor = 0
    prior_result_id: str | None = None
    source_texts = dict(catalog.source_texts)
    # Grow approximately linearly, then top up the final turn to the target.
    payload_words_per_turn = max(1, target_tokens // spec.turns)
    for turn_index in range(spec.turns):
        messages_by_turn.append(tuple(dict(message) for message in history))
        next_tool = spec.tool_cycle[turn_index % len(spec.tool_cycle)]
        if spec.task_id == "TT-EDIT" and next_tool == "run_tests":
            payload = source_texts[
                "apu_characterization/turntrace_v2/rev_c_payloads/turntrace_pytest_output.txt"
            ]
        else:
            payload, cursor = _chunk_words(words, cursor, payload_words_per_turn)
        names, args = _tool_args(
            spec,
            turn_index=turn_index,
            payload=payload,
            prior_result_id=prior_result_id,
        )
        names_by_turn.append(names)
        args_by_turn.append(args)
        history.append(
            {
                "role": "assistant",
                "content": (
                    "tool_call "
                    + " + ".join(
                        (
                            f"{name}({json.dumps({k: v for k, v in arg.items() if not k.startswith('_')}, sort_keys=True, ensure_ascii=False, separators=(',', ':'))})"
                            if arm_config.prefix_stable_layout
                            else f"{name}({repr({k: v for k, v in arg.items() if not k.startswith('_')})})"
                        )
                        for name, arg in zip(names, args)
                    )
                ),
            }
        )
        history.append(
            {
                "role": "user",
                "content": "tool_result: " + payload,
            }
        )
        prior_result_id = f"{spec.task_id}-result-{turn_index:02d}"

    # The target is an engine-token acceptance threshold. This top-up only
    # guarantees the deterministic planning tokenizer reaches it; live cells
    # must still audit engine_tokens_in on the final call.
    final_messages = [dict(message) for message in messages_by_turn[-1]]

    def _planned_count(messages: Sequence[dict[str, str]]) -> int:
        if message_token_count is not None:
            measured = message_token_count(messages)
            exact = (
                int(measured)
                if isinstance(measured, (int, float))
                else len(measured)
            )
            if exact > 0:
                return exact
        text = "\n".join(
            f"{message['role']}: {message['content']}" for message in messages
        )
        return count_tokens(text)

    for _ in range(5):
        deficit = target_tokens - _planned_count(final_messages)
        if deficit <= 0:
            break
        top_up, cursor = _chunk_words(words, cursor, deficit + 16)
        final_messages.append({"role": "user", "content": "payload_top_up: " + top_up})
    messages_by_turn[-1] = tuple(final_messages)

    pair_id = f"{task_class}:{seed}:{harness_id}:{deployment_id}:{pair_variant}"
    manifest_sha = str(payload_manifest_dict(catalog)["manifest_sha256"])
    return SuitePlan(
        task_class=task_class,
        seed=seed,
        arm=arm_config.arm,
        interventions_active=arm_config.interventions_active,
        pair_id=pair_id,
        workload_id=f"{WORKLOAD_PREFIX}:{task_class}",
        target_tokens=target_tokens,
        messages_by_turn=tuple(messages_by_turn),
        tool_names_by_turn=tuple(names_by_turn),
        tool_args_by_turn=tuple(args_by_turn),
        payload_manifest_sha256=manifest_sha,
    )


def to_raw_python_turns(plan: SuitePlan) -> list[HarnessTurn]:
    turns: list[HarnessTurn] = []
    for messages, names, args in zip(
        plan.messages_by_turn, plan.tool_names_by_turn, plan.tool_args_by_turn
    ):
        fanout = (
            [(name, dict(arg)) for name, arg in zip(names, args)]
            if len(names) > 1
            else None
        )
        turns.append(
            HarnessTurn(
                messages=[dict(message) for message in messages],
                tool_name=names[0] if len(names) == 1 else None,
                tool_args=dict(args[0]) if len(args) == 1 else {},
                call_site_tag=plan.task_class,
                fanout_tools=fanout,
            )
        )
    return turns


def to_langgraph_steps(plan: SuitePlan) -> list[GraphStep]:
    steps: list[GraphStep] = []
    for messages, names, args in zip(
        plan.messages_by_turn, plan.tool_names_by_turn, plan.tool_args_by_turn
    ):
        steps.append(
            GraphStep(
                node_name=plan.task_class,
                messages=[dict(message) for message in messages],
                tool_name=names[0] if len(names) == 1 else None,
                tool_args=dict(args[0]) if len(args) == 1 else None,
                fanout_tools=(
                    [(name, dict(arg)) for name, arg in zip(names, args)]
                    if len(names) > 1
                    else None
                ),
            )
        )
    return steps
