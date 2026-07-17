"""Trajectory replay bundles and swapped-step replay (Layer 1 handoff)."""

from __future__ import annotations

import json
import zlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from apu_characterization.turntrace_v2.contracts import canonical_json_bytes, load_tool_manifest, sha256_bytes


@dataclass
class EnvSnapshotRef:
    git_commit: str
    container_image_id: str
    dirty_patch: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "arguments": dict(self.arguments)}


@dataclass
class TurnBundle:
    turn_index: int
    assembled_context: Any  # str | list[dict]
    raw_model_output: str
    tool_calls: list[ToolCall]
    tool_results: list[Any]
    sampling_params: dict[str, Any]
    reasoning_mode: str
    env_snapshot_ref: EnvSnapshotRef
    tokenizer_id: str
    context_byte_sha256: str | None = None
    # Delta storage: if set, assembled_context is reconstructed from prior + delta.
    context_delta_tokens: list[str] | None = None
    context_full_tokens: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "assembled_context": self.assembled_context,
            "raw_model_output": self.raw_model_output,
            "tool_calls": [c.to_dict() for c in self.tool_calls],
            "tool_results": list(self.tool_results),
            "sampling_params": dict(self.sampling_params),
            "reasoning_mode": self.reasoning_mode,
            "env_snapshot_ref": self.env_snapshot_ref.to_dict(),
            "tokenizer_id": self.tokenizer_id,
            "context_byte_sha256": sha256_bytes(
                canonical_json_bytes(self.assembled_context)
            ),
            "context_delta_tokens": self.context_delta_tokens,
            "context_full_tokens": self.context_full_tokens,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TurnBundle":
        env = value["env_snapshot_ref"]
        return cls(
            turn_index=int(value["turn_index"]),
            assembled_context=value["assembled_context"],
            raw_model_output=str(value["raw_model_output"]),
            tool_calls=[
                ToolCall(name=str(c["name"]), arguments=dict(c.get("arguments") or {}))
                for c in (value.get("tool_calls") or [])
            ],
            tool_results=list(value.get("tool_results") or []),
            sampling_params=dict(value.get("sampling_params") or {}),
            reasoning_mode=str(value["reasoning_mode"]),
            env_snapshot_ref=EnvSnapshotRef(
                git_commit=str(env["git_commit"]),
                container_image_id=str(env["container_image_id"]),
                dirty_patch=env.get("dirty_patch"),
            ),
            tokenizer_id=str(value["tokenizer_id"]),
            context_byte_sha256=value.get("context_byte_sha256")
            or sha256_bytes(canonical_json_bytes(value["assembled_context"])),
            context_delta_tokens=list(value["context_delta_tokens"])
            if value.get("context_delta_tokens") is not None
            else None,
            context_full_tokens=list(value["context_full_tokens"])
            if value.get("context_full_tokens") is not None
            else None,
        )


@dataclass
class ReplayBundle:
    trajectory_id: str
    workload_id: str
    harness_id: str
    deployment_id: str
    turns: list[TurnBundle] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def append_turn(self, turn: TurnBundle) -> None:
        """Append-only: refuse mutation of prior turns."""
        if self.turns and turn.turn_index != self.turns[-1].turn_index + 1:
            if turn.turn_index != len(self.turns):
                raise ValueError("replay bundles are append-only and must be contiguous")
        if any(t.turn_index == turn.turn_index for t in self.turns):
            raise ValueError("cannot mutate an existing turn in an append-only bundle")
        self.turns.append(turn)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trajectory_id": self.trajectory_id,
            "workload_id": self.workload_id,
            "harness_id": self.harness_id,
            "deployment_id": self.deployment_id,
            "turns": [t.to_dict() for t in self.turns],
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReplayBundle":
        bundle = cls(
            trajectory_id=str(value["trajectory_id"]),
            workload_id=str(value["workload_id"]),
            harness_id=str(value["harness_id"]),
            deployment_id=str(value["deployment_id"]),
            meta=dict(value.get("meta") or {}),
        )
        for turn in value.get("turns") or []:
            bundle.append_turn(TurnBundle.from_dict(turn))
        return bundle


def context_delta_tokens(prior: Sequence[str], current: Sequence[str]) -> list[str]:
    n = min(len(prior), len(current))
    lcp = 0
    while lcp < n and prior[lcp] == current[lcp]:
        lcp += 1
    # Store LCP length + suffix (prefix-redundant compression).
    return [f"__lcp__:{lcp}", *current[lcp:]]


def reconstruct_context_tokens(prior: Sequence[str], delta: Sequence[str]) -> list[str]:
    if not delta or not str(delta[0]).startswith("__lcp__:"):
        return list(delta)
    lcp = int(str(delta[0]).split(":", 1)[1])
    return list(prior[:lcp]) + list(delta[1:])


def save_bundle(bundle: ReplayBundle, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json_bytes(bundle.to_dict())
    compressed = zlib.compress(raw, level=9)
    path.write_bytes(compressed)
    meta_path = path.with_suffix(path.suffix + ".sha256")
    meta_path.write_text(sha256_bytes(raw) + "\n", encoding="utf-8")
    return path


def load_bundle(path: Path) -> ReplayBundle:
    raw = zlib.decompress(Path(path).read_bytes())
    return ReplayBundle.from_dict(json.loads(raw.decode("utf-8")))


ToolExecutor = Callable[[str, Mapping[str, Any], TurnBundle], Any]
ModelFn = Callable[[Any, Mapping[str, Any]], str]


@dataclass
class SwapReplayResult:
    trajectory_id: str
    swap_turn: int
    model_id: str
    reasoning_mode: str
    success: bool
    tool_replay_modes: list[dict[str, str]]
    outputs: list[str]
    notes: str = ""


def replay_policy_for(tool_name: str, manifest: Mapping[str, Any] | None = None) -> str:
    manifest = manifest or load_tool_manifest()
    policy = manifest.get("replay_policy") or {}
    return str(policy.get(tool_name, policy.get("_default", "archived")))


def swapped_step_replay(
    bundle: ReplayBundle,
    *,
    swap_turn: int,
    model_fn: ModelFn,
    model_id: str,
    reasoning_mode: str,
    tool_executor: ToolExecutor | None = None,
    task_success_fn: Callable[[Sequence[str], ReplayBundle], bool] | None = None,
) -> SwapReplayResult:
    """Reconstruct state at turn k from archive alone, swap model, run forward.

    Tools use live or archived results per manifest; mode is recorded.
    """
    if swap_turn < 0 or swap_turn >= len(bundle.turns):
        raise ValueError("swap_turn out of range")
    modes: list[dict[str, str]] = []
    outputs: list[str] = []
    # Prefix turns are taken verbatim from the archive (historical ground truth).
    for turn in bundle.turns[:swap_turn]:
        outputs.append(turn.raw_model_output)

    for turn in bundle.turns[swap_turn:]:
        sampling = dict(turn.sampling_params)
        sampling["reasoning_mode"] = reasoning_mode
        sampling["model_id"] = model_id
        raw_out = model_fn(turn.assembled_context, sampling)
        outputs.append(raw_out)
        # Execute / substitute tools after the swapped model decision.
        for idx, call in enumerate(turn.tool_calls):
            mode = replay_policy_for(call.name)
            if mode == "live" and tool_executor is not None:
                result = tool_executor(call.name, call.arguments, turn)
            else:
                mode = "archived"
                result = turn.tool_results[idx] if idx < len(turn.tool_results) else None
            modes.append({"turn": str(turn.turn_index), "tool": call.name, "mode": mode})
            _ = result  # result available for future stateful executors

    success_fn = task_success_fn or (lambda _outs, b: bool(b.meta.get("task_success", True)))
    success = bool(success_fn(outputs, bundle))
    return SwapReplayResult(
        trajectory_id=bundle.trajectory_id,
        swap_turn=swap_turn,
        model_id=model_id,
        reasoning_mode=reasoning_mode,
        success=success,
        tool_replay_modes=modes,
        outputs=outputs,
        notes="archive_only_replay",
    )


def estimate_bundle_bytes(bundle: ReplayBundle, *, use_deltas: bool = True) -> dict[str, int]:
    full = len(canonical_json_bytes(bundle.to_dict()))
    if not use_deltas:
        return {"full_json_bytes": full, "delta_json_bytes": full}
    # Rebuild with deltas only (drop full assembled_context strings where tokens exist).
    slim = ReplayBundle(
        trajectory_id=bundle.trajectory_id,
        workload_id=bundle.workload_id,
        harness_id=bundle.harness_id,
        deployment_id=bundle.deployment_id,
        meta=dict(bundle.meta),
    )
    prior: list[str] = []
    for turn in bundle.turns:
        tokens = turn.context_full_tokens
        if tokens is None and isinstance(turn.assembled_context, str):
            tokens = turn.assembled_context.split()
        tokens = list(tokens or [])
        delta = context_delta_tokens(prior, tokens)
        slim.append_turn(
            TurnBundle(
                turn_index=turn.turn_index,
                assembled_context={"delta": True},
                raw_model_output=turn.raw_model_output,
                tool_calls=turn.tool_calls,
                tool_results=turn.tool_results,
                sampling_params=turn.sampling_params,
                reasoning_mode=turn.reasoning_mode,
                env_snapshot_ref=turn.env_snapshot_ref,
                tokenizer_id=turn.tokenizer_id,
                context_byte_sha256=turn.context_byte_sha256,
                context_delta_tokens=delta,
                context_full_tokens=None,
            )
        )
        prior = tokens
    delta_bytes = len(canonical_json_bytes(slim.to_dict()))
    return {"full_json_bytes": full, "delta_json_bytes": delta_bytes}
