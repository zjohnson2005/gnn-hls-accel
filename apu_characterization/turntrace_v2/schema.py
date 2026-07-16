"""CallRecord / TrajectoryRecord schemas for TurnTrace v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Mapping, Sequence

from apu_characterization.turntrace_v2.contracts import (
    CACHE_STATES,
    REASONING_MODES,
    TOOL_CLASSES,
    load_protocol,
)

ToolClass = Literal["read_only", "state_mutating", "none"]
CacheState = Literal["cold", "warm-hit", "warm-partial", "disabled"]
ReasoningMode = Literal["on", "off", "n/a"]


@dataclass
class StepFeatures:
    is_tool_call: bool
    tool_class: ToolClass
    repeat_count: int
    loop_membership: bool
    fanout_siblings: int
    trajectory_position: float

    def validate(self) -> None:
        if self.tool_class not in TOOL_CLASSES:
            raise ValueError(f"invalid tool_class: {self.tool_class}")
        if self.repeat_count < 0:
            raise ValueError("repeat_count must be >= 0")
        if self.fanout_siblings < 0:
            raise ValueError("fanout_siblings must be >= 0")
        if not (0.0 <= self.trajectory_position <= 1.0):
            raise ValueError("trajectory_position must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StepFeatures":
        feat = cls(
            is_tool_call=bool(value["is_tool_call"]),
            tool_class=str(value["tool_class"]),  # type: ignore[arg-type]
            repeat_count=int(value["repeat_count"]),
            loop_membership=bool(value["loop_membership"]),
            fanout_siblings=int(value["fanout_siblings"]),
            trajectory_position=float(value["trajectory_position"]),
        )
        feat.validate()
        return feat


@dataclass
class CallRecord:
    trajectory_id: str
    turn_index: int
    harness_id: str
    deployment_id: str
    step_type_semantic: str
    step_features: StepFeatures
    t_orch_pre_ms: float
    t_orch_post_ms: float
    t_network_ms: float
    network_method: str
    t_prefill_ms: float
    prefill_method: str
    t_decode_ms: float
    # F3: context_tokens_in is an alias of engine_tokens_in (engine tokenizer ground truth).
    context_tokens_in: int
    engine_tokens_in: int
    requested_tokens_in: int
    token_reconciliation_delta: int
    tokens_out: int
    call_shape_ratio: float
    cache_state: CacheState
    prefix_hit_tokens: int
    prefill_necessary_tokens: int
    prefill_redundant_tokens: int
    t_prefill_necessary_ms: float
    t_prefill_redundant_ms: float
    retemplated_tokens: int
    pred_context_tokens: int
    pred_cache_state: CacheState
    pred_decode_tokens: float
    pred_t_prefill_ms: float
    pred_t_decode_ms: float
    energy_j: float | None
    model_id: str
    quantization: str
    reasoning_mode: ReasoningMode
    engine: str
    engine_version: str
    wall_clock_start: float
    wall_clock_end: float
    audit_flags: list[str] = field(default_factory=list)

    def validate(self) -> None:
        protocol = load_protocol()
        required = protocol["call_record_required_fields"]
        payload = self.to_dict()
        missing = [name for name in required if name not in payload]
        if missing:
            raise ValueError(f"CallRecord missing fields: {missing}")
        self.step_features.validate()
        if self.cache_state not in CACHE_STATES:
            raise ValueError(f"invalid cache_state: {self.cache_state}")
        if self.pred_cache_state not in CACHE_STATES:
            raise ValueError(f"invalid pred_cache_state: {self.pred_cache_state}")
        if self.reasoning_mode not in REASONING_MODES:
            raise ValueError(f"invalid reasoning_mode: {self.reasoning_mode}")
        if self.engine_tokens_in < 0 or self.tokens_out < 0 or self.requested_tokens_in < 0:
            raise ValueError("token counts must be non-negative")
        if self.context_tokens_in != self.engine_tokens_in:
            raise ValueError("context_tokens_in must equal engine_tokens_in (F3 alias)")
        if self.token_reconciliation_delta != self.engine_tokens_in - self.requested_tokens_in:
            raise ValueError("token_reconciliation_delta mismatch")
        if self.turn_index < 0:
            raise ValueError("turn_index must be >= 0")
        if self.prefix_hit_tokens > self.engine_tokens_in:
            raise ValueError("prefix_hit_tokens cannot exceed engine_tokens_in")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["step_features"] = self.step_features.to_dict()
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CallRecord":
        data = dict(value)
        features = StepFeatures.from_dict(data.pop("step_features"))
        flags = list(data.pop("audit_flags") or [])
        record = cls(step_features=features, audit_flags=flags, **data)  # type: ignore[arg-type]
        record.validate()
        return record


@dataclass
class TrajectoryRecord:
    trajectory_id: str
    workload_id: str
    harness_id: str
    deployment_id: str
    cache_mode: str
    task_success: bool | float
    success_metric: str
    n_turns: int
    total_wall_clock_ms: float
    total_cost_usd: float
    total_energy_j: float | None
    replay_bundle_path: str | None

    def validate(self, *, headline: bool = False) -> None:
        protocol = load_protocol()
        required = protocol["trajectory_record_required_fields"]
        payload = self.to_dict()
        missing = [name for name in required if name not in payload]
        if missing:
            raise ValueError(f"TrajectoryRecord missing fields: {missing}")
        if headline and not self.replay_bundle_path:
            raise ValueError("headline TrajectoryRecord requires non-null replay_bundle_path")
        if self.n_turns < 0:
            raise ValueError("n_turns must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TrajectoryRecord":
        record = cls(**dict(value))  # type: ignore[arg-type]
        record.validate()
        return record


def validate_call_records(records: Sequence[CallRecord]) -> list[str]:
    errors: list[str] = []
    for idx, record in enumerate(records):
        try:
            record.validate()
        except ValueError as exc:
            errors.append(f"call[{idx}]: {exc}")
    return errors
