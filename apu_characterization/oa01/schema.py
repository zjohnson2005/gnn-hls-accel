"""Machine records for OA-01 boundary observations and offline derivations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass
class UsageRecord:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_provider(cls, value: Mapping[str, Any] | None) -> "UsageRecord":
        raw = dict(value or {})
        input_tokens = int(raw.get("prompt_tokens", raw.get("input_tokens", 0)) or 0)
        output_tokens = int(raw.get("completion_tokens", raw.get("output_tokens", 0)) or 0)
        input_details = raw.get("prompt_tokens_details") or raw.get("input_tokens_details") or {}
        output_details = raw.get("completion_tokens_details") or raw.get("output_tokens_details") or {}
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=int(input_details.get("cached_tokens", 0) or 0),
            reasoning_tokens=int(output_details.get("reasoning_tokens", 0) or 0),
            raw=raw,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApiBoundaryRecord:
    schema_version: str
    trajectory_id: str
    call_id: str
    call_index: int
    method: str
    path: str
    request_headers: dict[str, str]
    request_body_b64: str
    request_json: Any
    response_status: int
    response_headers: dict[str, str]
    response_body_b64: str
    response_json: Any
    request_received_unix_ns: int
    upstream_send_unix_ns: int
    response_headers_unix_ns: int
    response_first_body_byte_unix_ns: int
    response_last_body_byte_unix_ns: int
    response_relay_complete_unix_ns: int
    stream_requested: bool
    model_id: str
    usage: UsageRecord
    cost_usd: float
    flags: list[str] = field(default_factory=list)

    @property
    def upstream_first_byte_ms(self) -> float:
        return max(
            0.0,
            (self.response_first_body_byte_unix_ns - self.upstream_send_unix_ns) / 1_000_000.0,
        )

    @property
    def upstream_body_ms(self) -> float:
        return max(
            0.0,
            (
                self.response_last_body_byte_unix_ns
                - self.response_first_body_byte_unix_ns
            )
            / 1_000_000.0,
        )

    @property
    def upstream_total_ms(self) -> float:
        return max(
            0.0,
            (self.response_last_body_byte_unix_ns - self.upstream_send_unix_ns)
            / 1_000_000.0,
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["usage"] = self.usage.to_dict()
        value["derived_timing"] = {
            "upstream_first_byte_ms": self.upstream_first_byte_ms,
            "upstream_body_ms": self.upstream_body_ms,
            "upstream_total_ms": self.upstream_total_ms,
        }
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ApiBoundaryRecord":
        data = dict(value)
        data.pop("derived_timing", None)
        data["usage"] = UsageRecord.from_provider(data.get("usage", {}).get("raw"))
        return cls(**data)


@dataclass
class ToolExecSpan:
    schema_version: str
    trajectory_id: str
    span_id: str
    argv: list[str]
    docker_operation: str
    container_id: str | None
    command: str | None
    start_unix_ns: int
    end_unix_ns: int
    returncode: int
    timed_out: bool = False
    signal: int | None = None
    flags: list[str] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return max(0.0, (self.end_unix_ns - self.start_unix_ns) / 1_000_000.0)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["duration_ms"] = self.duration_ms
        return value


@dataclass
class TurnRecord:
    trajectory_id: str
    task_id: str
    turn_index: int
    call_id: str
    api_call_ids: list[str]
    api_attempt_count: int
    interval_start_unix_ns: int
    interval_end_unix_ns: int
    t_turn_wall_ms: float
    t_model_observed_ms: float
    t_prefill_ms: float | None
    t_decode_ms: float | None
    t_network_ms: float | None
    timing_method: str
    t_tool_ms: float
    t_orch_gap_ms: float
    input_tokens: int
    output_tokens: int
    local_serialized_tokens: int
    local_lcp_tokens: int
    structurally_redundant_tokens: int
    provider_recovered_tokens: int
    actually_recomputed_redundant_tokens: int
    necessary_prefill_tokens: int
    template_overhead_envelope_tokens: int
    step_type_semantic: str
    is_tool_call: bool
    tool_names: list[str]
    repeat_count: int
    loop_membership: bool
    fanout_siblings: int
    status: str
    audit_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrajectoryRecord:
    trajectory_id: str
    task_id: str
    phase: str
    model_id: str
    outcome: str
    success: bool | None
    censored: bool
    censor_reason: str | None
    turns: int
    wall_clock_ms: float
    cost_usd: float
    cost_anomaly: bool
    exit_status: str
    subject_trajectory_path: str | None
    replay_bundle_path: str | None
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

